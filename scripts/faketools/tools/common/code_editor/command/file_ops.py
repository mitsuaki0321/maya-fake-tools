"""
File system operations for the Code Editor.

Pure filesystem helpers consumed by ``ui.file_explorer``. They never talk to
Qt — error reporting is surfaced via the ``FileOpResult`` dataclass so the UI
layer is free to render messages in whatever widget makes sense.

Every mutating call that might create a name collision resolves it internally
via ``get_unique_name`` so the UI doesn't have to juggle paths and suffixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
import os
import shutil

logger = getLogger(__name__)


@dataclass
class FileOpResult:
    """Outcome of a single filesystem operation.

    ``destination`` is the final path touched (after any ``(N)`` suffix added
    for collision avoidance). ``error`` is empty on success.
    """

    success: bool
    source: str = ""
    destination: str = ""
    error: str = ""

    @classmethod
    def ok(cls, source: str = "", destination: str = "") -> FileOpResult:
        return cls(success=True, source=source, destination=destination)

    @classmethod
    def fail(cls, error: str, source: str = "", destination: str = "") -> FileOpResult:
        return cls(success=False, source=source, destination=destination, error=error)


def get_unique_name(path: str) -> str:
    """Return ``path`` or a `` (N)`` variant if it already exists.

    Matches the original FileExplorer behaviour: ``foo.py`` becomes
    ``foo (1).py``, then ``foo (2).py``, etc.
    """
    if not os.path.exists(path):
        return path

    base_path = path
    counter = 1
    while os.path.exists(path):
        name, ext = os.path.splitext(base_path)
        path = f"{name} ({counter}){ext}"
        counter += 1
    return path


def copy_item(source_path: str, destination_dir: str) -> FileOpResult:
    """Copy a file or directory into ``destination_dir``.

    Uses ``shutil.copy2`` for files (preserves metadata) and ``shutil.copytree``
    for directories. Returns a ``FileOpResult`` with the resolved destination
    so the caller knows the final path after any name-collision suffix.
    """
    source_name = os.path.basename(source_path)
    destination_path = get_unique_name(os.path.join(destination_dir, source_name))

    try:
        if os.path.isfile(source_path):
            shutil.copy2(source_path, destination_path)
        else:
            shutil.copytree(source_path, destination_path)
    except Exception as exc:
        logger.error(f"Copy failed: {source_path} -> {destination_path}: {exc}")
        return FileOpResult.fail(str(exc), source=source_path, destination=destination_path)
    return FileOpResult.ok(source=source_path, destination=destination_path)


def move_item(source_path: str, destination_dir: str) -> FileOpResult:
    """Move a file or directory into ``destination_dir``."""
    source_name = os.path.basename(source_path)
    destination_path = get_unique_name(os.path.join(destination_dir, source_name))

    try:
        shutil.move(source_path, destination_path)
    except Exception as exc:
        logger.error(f"Move failed: {source_path} -> {destination_path}: {exc}")
        return FileOpResult.fail(str(exc), source=source_path, destination=destination_path)
    return FileOpResult.ok(source=source_path, destination=destination_path)


def delete_item(path: str) -> FileOpResult:
    """Remove a file (``os.remove``) or directory tree (``shutil.rmtree``).

    Returns a ``FileOpResult`` with ``error`` populated if the path doesn't
    exist or the removal raised; the UI layer can decide how to surface it.
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            return FileOpResult.fail("Path not found", source=path)
    except Exception as exc:
        logger.error(f"Delete failed: {path}: {exc}")
        return FileOpResult.fail(str(exc), source=path)
    return FileOpResult.ok(source=path, destination=path)


def create_python_file(parent_dir: str, name: str, initial_content: str = "# New Python file\n") -> FileOpResult:
    """Create a new ``.py`` file under ``parent_dir`` with starter content.

    ``name`` is auto-suffixed with ``.py`` when missing so the UI can pass the
    user-entered text verbatim.
    """
    if not name.endswith(".py"):
        name += ".py"
    destination_path = os.path.join(parent_dir, name)

    try:
        with open(destination_path, "w", encoding="utf-8") as f:
            f.write(initial_content)
    except Exception as exc:
        logger.error(f"Create file failed: {destination_path}: {exc}")
        return FileOpResult.fail(str(exc), destination=destination_path)
    return FileOpResult.ok(destination=destination_path)


def create_folder(parent_dir: str, name: str) -> FileOpResult:
    """Create a new folder under ``parent_dir`` (idempotent via ``exist_ok``)."""
    destination_path = os.path.join(parent_dir, name)
    try:
        os.makedirs(destination_path, exist_ok=True)
    except Exception as exc:
        logger.error(f"Create folder failed: {destination_path}: {exc}")
        return FileOpResult.fail(str(exc), destination=destination_path)
    return FileOpResult.ok(destination=destination_path)


__all__ = [
    "FileOpResult",
    "copy_item",
    "create_folder",
    "create_python_file",
    "delete_item",
    "get_unique_name",
    "move_item",
]
