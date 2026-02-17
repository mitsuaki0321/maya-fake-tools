"""
Maya FakeTools Package.

A collection of tools for Autodesk Maya.
"""

from pathlib import Path
import sys


def _load_custom_site_packages():
    """Load custom site-packages path from .env file.

    Reads FAKETOOLS_SITE_PACKAGES from the .env file at the repository root.
    If set, adds ``<FAKETOOLS_SITE_PACKAGES>/<maya_version>/site-packages/``
    to ``sys.path`` so that packages installed to a custom location are importable.
    """
    env_file = Path(__file__).parent.parent.parent / ".env"
    if not env_file.exists():
        return

    site_packages_path = None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "FAKETOOLS_SITE_PACKAGES":
            site_packages_path = value.strip().strip("'\"")
            break

    if not site_packages_path:
        return

    try:
        import maya.cmds as cmds

        maya_version = cmds.about(version=True)
    except ImportError:
        return

    custom_path = str(Path(site_packages_path) / maya_version / "site-packages")
    if custom_path not in sys.path:
        sys.path.insert(0, custom_path)


_load_custom_site_packages()

from .logging_config import set_log_level, setup_logging  # noqa: E402

# Initialize logging when package is imported
setup_logging()

__version__ = "1.0.0"
__author__ = "FakeTools"

__all__ = [
    "set_log_level",
    "setup_logging",
]
