"""Open a directory in the host OS file manager.

Wraps the platform-specific shell call (``os.startfile`` on Windows,
``open`` on macOS, ``xdg-open`` on Linux) so UI code can stay free of
``platform.system()`` branches.
"""

from __future__ import annotations

from logging import getLogger
import os
import platform
import subprocess

logger = getLogger(__name__)


def open_directory(path: str) -> tuple[bool, str]:
    """Show ``path`` in the platform's native file manager.

    Args:
        path (str): Directory path. Created if it does not yet exist.

    Returns:
        tuple[bool, str]: ``(True, "")`` on success, ``(False, error_message)``
            on failure. The error string is also written to the logger.
    """
    path = os.path.abspath(os.path.normpath(path))

    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created directory: {path}")
        except Exception as exc:
            return False, f"Failed to create directory: {exc}"

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        elif system == "Linux":
            subprocess.Popen(["xdg-open", path])
        else:
            return False, f"Unsupported platform: {system}"
    except Exception as exc:
        return False, f"Failed to open directory: {exc}"

    return True, ""
