"""
Plain-text file I/O for the Code Editor.

Tiny UTF-8 read/write helpers used by editor tabs. Errors are returned
rather than raised so the UI layer can surface them with whatever
message box it prefers.
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional

logger = getLogger(__name__)


def read_text(path: str) -> tuple[Optional[str], str]:
    """Read a UTF-8 text file.

    Returns ``(content, "")`` on success, ``(None, error_message)`` on failure.
    The content is the full decoded string — streaming isn't used because the
    editor already buffers the whole document in memory.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), ""
    except Exception as exc:
        logger.error(f"Read failed: {path}: {exc}")
        return None, str(exc)


def write_text(path: str, content: str) -> str:
    """Write ``content`` to ``path`` as UTF-8.

    Returns an error message on failure; empty string on success.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        logger.error(f"Write failed: {path}: {exc}")
        return str(exc)
    return ""


__all__ = ["read_text", "write_text"]
