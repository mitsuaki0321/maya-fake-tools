"""
Tool data directory management for FakeTools.

Provides centralized management of tool-specific data directories
and file paths. Each tool gets its own subdirectory under the
global data root.
"""

import logging
from pathlib import Path

from ..config import get_global_config

logger = logging.getLogger(__name__)


class ToolDataManager:
    """
    Tool data directory manager.

    Manages tool-specific data directories and provides utilities
    for file path resolution and directory operations.

    Each tool gets a dedicated directory:
    {data_root}/{category}/{tool_name}/

    Attributes:
        tool_name (str): Name of the tool
        category (str): Tool category (rig/model/anim/common)
    """

    def __init__(self, tool_name: str, category: str):
        """
        Initialize the tool data manager.

        Args:
            tool_name (str): Name of the tool
            category (str): Tool category (rig, model, anim, common)

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> data_dir = manager.get_data_dir()
        """
        self.tool_name = tool_name
        self.category = category
        self._custom_data_dir: Path | None = None
        logger.debug(f"ToolDataManager initialized for {category}/{tool_name}")

    def _resolve_data_dir(self) -> Path:
        """
        Resolve the data directory path.

        Uses custom directory if set, otherwise uses default location
        from global config.

        Returns:
            Path: Resolved data directory path
        """
        if self._custom_data_dir is not None:
            return self._custom_data_dir

        config = get_global_config()
        data_root = config.get_data_root_dir()
        data_dir = data_root / self.category / self.tool_name
        logger.debug(f"Resolved data directory: {data_dir}")
        return data_dir

    def get_data_dir(self) -> Path:
        """
        Get the tool's data directory path.

        Returns:
            Path: Data directory path (may not exist yet)

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> data_dir = manager.get_data_dir()
            >>> print(data_dir)
            /home/user/Documents/maya/faketools_workspace/rig/skin_weights
        """
        return self._resolve_data_dir()

    def set_custom_data_dir(self, path: Path | str) -> None:
        """
        Set a custom data directory path.

        Overrides the default data directory location.

        Args:
            path (Path | str): Custom data directory path

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> manager.set_custom_data_dir("D:/MyProject/skin_data")
        """
        self._custom_data_dir = Path(path).expanduser().resolve()
        logger.info(f"Custom data directory set: {self._custom_data_dir}")

    def ensure_data_dir(self) -> Path:
        """
        Ensure the data directory exists, creating it if necessary.

        Returns:
            Path: Data directory path (guaranteed to exist)

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> data_dir = manager.ensure_data_dir()
            >>> # data_dir now exists on disk
        """
        data_dir = self._resolve_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured data directory exists: {data_dir}")
        return data_dir

    def get_data_path(self, filename: str) -> Path:
        """
        Get the full path for a data file.

        Does not create the file or directory.

        Args:
            filename (str): Name of the data file

        Returns:
            Path: Full path to the data file

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> file_path = manager.get_data_path("character_a.json")
            >>> print(file_path)
            /home/user/Documents/maya/faketools_workspace/rig/skin_weights/character_a.json
        """
        data_dir = self._resolve_data_dir()
        file_path = data_dir / filename
        logger.debug(f"Data file path: {file_path}")
        return file_path

    def list_data_files(self, pattern: str = "*") -> list[Path]:
        """
        List all data files matching a pattern.

        Args:
            pattern (str): Glob pattern for file matching (default: "*")

        Returns:
            list[Path]: List of matching file paths (empty if directory doesn't exist)

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> json_files = manager.list_data_files("*.json")
            >>> for file in json_files:
            ...     print(file.name)
        """
        data_dir = self._resolve_data_dir()
        if not data_dir.exists():
            logger.debug(f"Data directory doesn't exist: {data_dir}")
            return []

        files = list(data_dir.glob(pattern))
        logger.debug(f"Found {len(files)} files matching '{pattern}'")
        return files

    def cleanup_old_files(self, days: int = 30, pattern: str = "*") -> int:
        """
        Delete files older than specified days.

        Args:
            days (int): Age threshold in days (default: 30)
            pattern (str): Glob pattern for file matching (default: "*")

        Returns:
            int: Number of files deleted

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> deleted = manager.cleanup_old_files(days=30, pattern="*.backup")
            >>> print(f"Deleted {deleted} old backup files")
        """
        import time

        data_dir = self._resolve_data_dir()
        if not data_dir.exists():
            logger.debug(f"Data directory doesn't exist: {data_dir}")
            return 0

        current_time = time.time()
        age_threshold = days * 24 * 60 * 60  # Convert days to seconds
        deleted_count = 0

        for file_path in data_dir.glob(pattern):
            if not file_path.is_file():
                continue

            file_age = current_time - file_path.stat().st_mtime
            if file_age > age_threshold:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_path.name}")
                except OSError as e:
                    logger.warning(f"Failed to delete {file_path.name}: {e}")

        logger.info(f"Cleanup completed: {deleted_count} files deleted")
        return deleted_count

    def exists(self) -> bool:
        """
        Check if the data directory exists.

        Returns:
            bool: True if directory exists, False otherwise

        Example:
            >>> manager = ToolDataManager("skin_weights", "rig")
            >>> if not manager.exists():
            ...     manager.ensure_data_dir()
        """
        data_dir = self._resolve_data_dir()
        exists = data_dir.exists()
        logger.debug(f"Data directory exists: {exists}")
        return exists


__all__ = ["ToolDataManager"]
