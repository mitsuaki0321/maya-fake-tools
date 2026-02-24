"""Dependency Installer business logic.

Provides package registry, status checking, Maya version discovery,
and pip install execution for FakeTools optional dependencies.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
from logging import getLogger
import os
from pathlib import Path
import subprocess
import sys

logger = getLogger(__name__)

_VERSIONS_DIR = Path(__file__).resolve().parent / "versions"


def get_package_registry(maya_version: str | None = None) -> list[dict]:
    """Load the package registry from a version-specific or common JSON file.

    Looks for ``versions/maya{maya_version}.json`` first; falls back to
    ``versions/common.json``.

    Args:
        maya_version: Maya version string (e.g., "2023"). If None, loads common.json.

    Returns:
        list[dict]: Package registry entries.
    """
    if maya_version:
        version_file = _VERSIONS_DIR / f"maya{maya_version}.json"
        if version_file.exists():
            return json.loads(version_file.read_text(encoding="utf-8"))

    common_file = _VERSIONS_DIR / "common.json"
    return json.loads(common_file.read_text(encoding="utf-8"))


def get_pip_spec(pkg: dict) -> str:
    """Build a pip install specifier from a registry or status dict.

    Checks ``pip_version`` first (used in status dicts from
    :func:`get_all_package_statuses`), then ``version`` (used in raw
    registry entries).  Only values that look like PEP 440 constraints
    (starting with ``=``, ``<``, ``>``, ``!``, or ``~``) are appended.

    Args:
        pkg: A package dict (registry entry or status dict).

    Returns:
        str: e.g. ``"fast-simplification==0.1.12"`` or ``"numpy"``.
    """
    constraint = pkg.get("pip_version") or pkg.get("version") or ""
    if constraint and constraint[0] in ("=", "<", ">", "!", "~"):
        return f"{pkg['pip_name']}{constraint}"
    return pkg["pip_name"]


def discover_maya_versions() -> list[str]:
    """Scan for installed Maya versions on Windows.

    Looks for Maya installations in the standard Autodesk directory.

    Returns:
        list[str]: Sorted list of detected Maya version strings (e.g., ["2023", "2024", "2025"]).
    """
    versions = []
    autodesk_dir = Path("C:/Program Files/Autodesk")
    if not autodesk_dir.exists():
        return versions

    for entry in autodesk_dir.iterdir():
        if entry.is_dir() and entry.name.startswith("Maya"):
            version = entry.name.replace("Maya", "").strip()
            if version.isdigit():
                mayapy = entry / "bin" / "mayapy.exe"
                if mayapy.exists():
                    versions.append(version)

    versions.sort()
    return versions


def get_mayapy_path(maya_version: str) -> str | None:
    """Get the mayapy executable path for a given Maya version.

    Args:
        maya_version: Maya version string (e.g., "2024").

    Returns:
        str | None: Full path to mayapy.exe, or None if not found.
    """
    mayapy = Path(f"C:/Program Files/Autodesk/Maya{maya_version}/bin/mayapy.exe")
    if mayapy.exists():
        return str(mayapy)
    return None


def get_current_maya_version() -> str | None:
    """Get the currently running Maya version.

    Returns:
        str | None: Maya version string, or None if not running inside Maya.
    """
    try:
        import maya.cmds as cmds

        return cmds.about(version=True)
    except ImportError:
        return None


def check_package_installed(import_name: str) -> bool:
    """Check if a package is importable.

    Args:
        import_name: The Python import name of the package.

    Returns:
        bool: True if the package can be imported.
    """
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def get_package_version(pip_name: str) -> str | None:
    """Get the installed version of a package.

    Args:
        pip_name: The pip package name.

    Returns:
        str | None: Version string, or None if not installed.
    """
    try:
        return importlib.metadata.version(pip_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def get_all_package_statuses(mayapy_path: str | None = None, maya_version: str | None = None) -> list[dict]:
    """Get installation status for all packages in the registry.

    When ``mayapy_path`` is provided, checks are performed via subprocess
    so that the result reflects the target Maya environment rather than
    the current process.

    Args:
        mayapy_path: Path to mayapy executable. If None, checks in the
            current process (legacy behaviour).
        maya_version: Maya version string used to select the correct
            package registry JSON (e.g., "2023").

    Returns:
        list[dict]: List of dicts with keys: pip_name, import_name, required_by,
            optional, installed, version, and optionally pip_version (version constraint).
    """
    registry = get_package_registry(maya_version)

    if mayapy_path:
        remote_results = _check_packages_via_subprocess(mayapy_path, registry)
    else:
        remote_results = None

    statuses = []
    for pkg in registry:
        if remote_results is not None:
            info = remote_results.get(pkg["pip_name"], {})
            installed = info.get("installed", False)
            version = info.get("version")
        else:
            installed = check_package_installed(pkg["import_name"])
            version = get_package_version(pkg["pip_name"]) if installed else None

        status = {
            "pip_name": pkg["pip_name"],
            "import_name": pkg["import_name"],
            "required_by": pkg["required_by"],
            "optional": pkg["optional"],
            "installed": installed,
            "version": version,
        }
        if pkg.get("version"):
            status["pip_version"] = pkg["version"]
        statuses.append(status)
    return statuses


def _get_env_site_packages() -> str | None:
    """Read FAKETOOLS_SITE_PACKAGES from the .env file at the repo root.

    Returns:
        str | None: The custom site-packages base path, or None.
    """
    env_file = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "FAKETOOLS_SITE_PACKAGES":
            return value.strip().strip("'\"") or None
    return None


def _check_packages_via_subprocess(mayapy_path: str, registry: list[dict]) -> dict:
    """Check all registry packages by running a probe script in mayapy.

    Executes a single subprocess that attempts to import each package and
    query its version, returning JSON results.  If a custom site-packages
    path is configured via ``.env``, it is injected into ``sys.path``
    inside the subprocess so that packages installed there are detected.

    Args:
        mayapy_path: Path to mayapy executable.
        registry: Package registry entries to check.

    Returns:
        dict: Mapping of pip_name to {"installed": bool, "version": str | None}.
    """
    # Derive Maya version from the mayapy path (e.g. ".../Maya2025/bin/mayapy.exe")
    maya_version = None
    try:
        mayapy_dir = Path(mayapy_path).resolve().parent.parent
        name = mayapy_dir.name  # "Maya2025"
        ver = name.replace("Maya", "").strip()
        if ver.isdigit():
            maya_version = ver
    except Exception:
        pass

    # Build extra sys.path entries from .env
    extra_paths: list[str] = []
    env_site = _get_env_site_packages()
    if env_site and maya_version:
        extra_paths.append(str(Path(env_site) / maya_version / "site-packages"))

    # Build a small self-contained script to probe packages
    packages_json = json.dumps([(p["pip_name"], p["import_name"]) for p in registry])
    extra_paths_json = json.dumps(extra_paths)
    script = (
        "import importlib, importlib.metadata, json, sys\n"
        f"for p in {extra_paths_json}:\n"
        "    if p not in sys.path:\n"
        "        sys.path.insert(0, p)\n"
        f"packages = {packages_json}\n"
        "results = {}\n"
        "for pip_name, import_name in packages:\n"
        "    installed = True\n"
        "    try:\n"
        "        importlib.import_module(import_name)\n"
        "    except ImportError:\n"
        "        installed = False\n"
        "    version = None\n"
        "    if installed:\n"
        "        try:\n"
        "            version = importlib.metadata.version(pip_name)\n"
        "        except Exception:\n"
        "            pass\n"
        "    results[pip_name] = {'installed': installed, 'version': version}\n"
        "print(json.dumps(results))\n"
    )

    try:
        result = subprocess.run(
            [mayapy_path, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to check packages via subprocess: %s", e)

    return {}


def ensure_pip_available(mayapy_path: str) -> bool:
    """Check if pip is available for the given mayapy.

    Args:
        mayapy_path: Path to mayapy executable.

    Returns:
        bool: True if pip is available.
    """
    try:
        result = subprocess.run(
            [mayapy_path, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def install_packages(
    package_names: list[str],
    mayapy_path: str,
    target_path: str | None = None,
    proxy: dict | None = None,
) -> dict:
    """Install packages using pip via mayapy.

    Args:
        package_names: List of pip package names to install.
        mayapy_path: Path to mayapy executable.
        target_path: Custom install target directory. If None, uses default.
        proxy: Dict with optional "http" and "https" proxy URLs.

    Returns:
        dict: Result with keys "success" (bool), "installed" (list[str]),
            "failed" (list[dict]), "stdout" (str), "stderr" (str).
    """
    if not package_names:
        return {"success": True, "installed": [], "failed": [], "stdout": "", "stderr": ""}

    cmd = [mayapy_path, "-m", "pip", "install"]

    if target_path:
        target = Path(target_path)
        target.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--target", str(target)])

    cmd.extend(package_names)

    env = os.environ.copy()
    if proxy:
        if proxy.get("http"):
            env["HTTP_PROXY"] = proxy["http"]
        if proxy.get("https"):
            env["HTTPS_PROXY"] = proxy["https"]

    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "installed": [],
            "failed": [{"name": pkg, "error": "Timed out"} for pkg in package_names],
            "stdout": "",
            "stderr": "Installation timed out after 300 seconds.",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "installed": [],
            "failed": [{"name": pkg, "error": "mayapy not found"} for pkg in package_names],
            "stdout": "",
            "stderr": f"mayapy not found: {mayapy_path}",
        }

    if result.returncode == 0:
        # Invalidate import caches so newly installed packages are visible
        importlib.invalidate_caches()

        # Add target path to sys.path if not already there
        if target_path and target_path not in sys.path:
            sys.path.insert(0, target_path)

        return {
            "success": True,
            "installed": package_names,
            "failed": [],
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    else:
        return {
            "success": False,
            "installed": [],
            "failed": [{"name": pkg, "error": result.stderr} for pkg in package_names],
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
