"""Blender discovery and GLB to FBX conversion."""

from __future__ import annotations

import contextlib
from logging import getLogger
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .constants import BLENDER_BASE_DIRS, BLENDER_SCRIPT

logger = getLogger(__name__)


def find_blender_executable() -> str | None:
    """Find Blender executable dynamically.

    Search order:
    1. BLENDER_PATH environment variable
    2. Standard installation directories (latest version)
    3. System PATH

    Returns:
        str | None: Path to Blender executable, or None if not found.
    """
    # 1. Check environment variable
    blender_env = os.environ.get("BLENDER_PATH")
    if blender_env and os.path.exists(blender_env):
        logger.debug(f"Found Blender from environment variable: {blender_env}")
        return blender_env

    # 2. Search standard installation directories
    for base_dir in BLENDER_BASE_DIRS:
        base_path = Path(base_dir)
        if not base_path.exists():
            continue

        # Windows: Search Blender X.X folders under Blender Foundation
        if sys.platform == "win32" and "Blender Foundation" in str(base_path):
            blender_versions = []
            try:
                for item in base_path.iterdir():
                    if item.is_dir() and item.name.startswith("Blender "):
                        blender_exe = item / "blender.exe"
                        if blender_exe.exists():
                            try:
                                version_str = item.name.replace("Blender ", "")
                                version_parts = version_str.split(".")
                                major = int(version_parts[0])
                                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                                blender_versions.append(((major, minor), str(blender_exe)))
                            except (ValueError, IndexError):
                                blender_versions.append(((0, 0), str(blender_exe)))

                if blender_versions:
                    blender_versions.sort(reverse=True, key=lambda x: x[0])
                    found_path = blender_versions[0][1]
                    logger.debug(f"Found Blender in standard directory: {found_path}")
                    return found_path
            except OSError:
                pass

        # macOS: Search for Blender.app
        elif sys.platform == "darwin":
            blender_app = base_path / "Blender.app" / "Contents" / "MacOS" / "Blender"
            if blender_app.exists():
                logger.debug(f"Found Blender on macOS: {blender_app}")
                return str(blender_app)

        # Linux: Search for blender executable
        elif sys.platform == "linux":
            blender_bin = base_path / "blender"
            if blender_bin.exists():
                logger.debug(f"Found Blender on Linux: {blender_bin}")
                return str(blender_bin)

    # 3. Search system PATH
    try:
        if sys.platform == "win32":
            result = subprocess.run(["where", "blender"], capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(["which", "blender"], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            blender_path = result.stdout.strip().split("\n")[0]
            if os.path.exists(blender_path):
                logger.debug(f"Found Blender in system PATH: {blender_path}")
                return blender_path
    except (subprocess.TimeoutExpired, OSError):
        pass

    logger.warning("Blender executable not found")
    return None


def convert_glb_to_fbx(
    glb_path: str,
    output_dir: str | None = None,
    axis_forward: str = "-Z",
    axis_up: str = "Y",
) -> tuple[str, str] | None:
    """Convert GLB file to FBX using Blender headless mode.

    Args:
        glb_path: Path to the GLB file.
        output_dir: Output directory (default: same directory as GLB).
        axis_forward: Forward axis for FBX export (default: '-Z').
        axis_up: Up axis for FBX export (default: 'Y').

    Returns:
        tuple[str, str] | None: (fbx_path, texture_dir) on success, None on failure.
    """
    logger.info("Converting GLB to FBX")

    # Find Blender executable
    blender_exe = find_blender_executable()
    if not blender_exe:
        logger.error("Blender not found. Please install Blender or set BLENDER_PATH environment variable.")
        return None

    logger.info(f"Blender executable: {blender_exe}")

    # Validate input file
    glb_path = Path(glb_path)
    if not glb_path.exists():
        logger.error(f"GLB file not found: {glb_path}")
        return None

    # Set output paths
    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = glb_path.parent

    output_fbx = output_dir / f"{glb_path.stem}.fbx"
    texture_dir = output_dir / f"{glb_path.stem}.fbm"

    logger.info(f"Output FBX: {output_fbx}")
    logger.info(f"Texture directory: {texture_dir}")

    # Create texture directory
    texture_dir.mkdir(parents=True, exist_ok=True)

    # Write embedded Blender script to temp file
    script_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(BLENDER_SCRIPT)
            script_file = f.name

        # Build Blender command
        cmd = [
            str(blender_exe),
            "--background",
            "--python",
            script_file,
            "--",
            str(glb_path),
            str(output_fbx),
            str(texture_dir),
            axis_forward,
            axis_up,
        ]

        logger.info("Running conversion command...")
        logger.debug(f"Command: {' '.join(cmd)}")

        # Execute Blender
        result = subprocess.run(cmd, capture_output=True, timeout=300)  # 5 minute timeout

        # Decode output (ignore encoding errors)
        stdout_text = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
        stderr_text = result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""

        # Log output
        if stdout_text:
            for line in stdout_text.split("\n"):
                if line.strip():
                    logger.debug(f"  {line}")

        if stderr_text:
            for line in stderr_text.split("\n"):
                if line.strip() and "Warning" not in line:
                    logger.warning(f"  {line}")

        # Check result
        if result.returncode != 0:
            logger.error(f"Blender conversion error (exit code: {result.returncode})")
            return None

        if not output_fbx.exists():
            logger.error("FBX file was not generated")
            return None

        logger.info(f"FBX conversion succeeded: {output_fbx}")
        return str(output_fbx), str(texture_dir)

    except subprocess.TimeoutExpired:
        logger.error("Conversion timed out (exceeded 5 minutes)")
        return None
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return None
    finally:
        # Clean up temp script file
        if script_file and os.path.exists(script_file):
            with contextlib.suppress(OSError):
                os.remove(script_file)
