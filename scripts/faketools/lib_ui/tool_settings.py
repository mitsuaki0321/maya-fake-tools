"""
Tool settings management with preset support.

This module provides a settings manager that stores tool configurations
as JSON files, enabling preset functionality for users to save, load,
and share different configuration sets.

Example:
    >>> settings = ToolSettingsManager("skin_weights", "rig")
    >>> settings.save_settings({"option1": True, "value": 10}, "my_preset")
    >>> data = settings.load_settings("my_preset")
    >>> presets = settings.list_presets()
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from .tool_data import ToolDataManager

logger = logging.getLogger(__name__)


class ToolSettingsManager:
    """
    Manage tool settings with preset support.

    Stores settings as JSON files in the tool's data directory under
    a 'settings' subdirectory. Provides preset save/load/delete and
    export/import functionality.

    Settings are stored at:
    {data_root}/{category}/{tool_name}/settings/{preset_name}.json

    Attributes:
        tool_name (str): Name of the tool
        category (str): Tool category (rig/model/anim/common)
        data_manager (ToolDataManager): Underlying data manager
    """

    DEFAULT_PRESET_NAME = "default"
    SETTINGS_SUBDIR = "settings"

    def __init__(self, tool_name: str, category: str):
        """
        Initialize the tool settings manager.

        Args:
            tool_name (str): Name of the tool
            category (str): Tool category (rig, model, anim, common)

        Example:
            >>> settings = ToolSettingsManager("skin_weights", "rig")
        """
        self.tool_name = tool_name
        self.category = category
        self.data_manager = ToolDataManager(tool_name, category)
        logger.debug(f"ToolSettingsManager initialized for {category}/{tool_name}")

    def _get_settings_dir(self) -> Path:
        """
        Get the settings directory path.

        Returns:
            Path: Settings directory path

        Example:
            >>> settings._get_settings_dir()
            Path('D:/Documents/maya/faketools_workspace/rig/skin_weights/settings')
        """
        return self.data_manager.get_data_dir() / self.SETTINGS_SUBDIR

    def _ensure_settings_dir(self) -> Path:
        """
        Ensure the settings directory exists.

        Returns:
            Path: Settings directory path (guaranteed to exist)
        """
        settings_dir = self._get_settings_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured settings directory exists: {settings_dir}")
        return settings_dir

    def _get_preset_path(self, preset_name: str) -> Path:
        """
        Get the full path for a preset file.

        Args:
            preset_name (str): Name of the preset

        Returns:
            Path: Full path to the preset file

        Example:
            >>> settings._get_preset_path("my_preset")
            Path('D:/Documents/maya/faketools_workspace/rig/skin_weights/settings/my_preset.json')
        """
        settings_dir = self._get_settings_dir()
        return settings_dir / f"{preset_name}.json"

    def _validate_preset_name(self, preset_name: str) -> None:
        """
        Validate preset name for file system safety.

        Args:
            preset_name (str): Name to validate

        Raises:
            ValueError: If preset name contains invalid characters

        Example:
            >>> settings._validate_preset_name("my_preset")  # OK
            >>> settings._validate_preset_name("my/preset")  # Raises ValueError
        """
        if not preset_name:
            raise ValueError("Preset name cannot be empty")

        # Allow alphanumeric, underscore, hyphen, and space
        if not re.match(r"^[a-zA-Z0-9_\- ]+$", preset_name):
            raise ValueError(f"Invalid preset name: '{preset_name}'. Only alphanumeric, underscore, hyphen, and space are allowed.")

        logger.debug(f"Preset name validated: {preset_name}")

    def save_settings(self, data: dict[str, Any], preset_name: str = DEFAULT_PRESET_NAME) -> None:
        """
        Save settings to a preset file.

        Args:
            data (dict[str, Any]): Settings data to save
            preset_name (str): Name of the preset (default: "default")

        Raises:
            ValueError: If preset name is invalid or data is not serializable

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> settings.save_settings({"option1": True, "value": 10}, "my_preset")
        """
        self._validate_preset_name(preset_name)
        settings_dir = self._ensure_settings_dir()
        preset_path = self._get_preset_path(preset_name)

        try:
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved settings to preset '{preset_name}': {preset_path}")
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize settings for preset '{preset_name}': {e}")
            raise ValueError(f"Settings data must be JSON serializable: {e}") from e
        except OSError as e:
            logger.error(f"Failed to write settings file '{preset_path}': {e}")
            raise

    def load_settings(self, preset_name: str = DEFAULT_PRESET_NAME) -> dict[str, Any]:
        """
        Load settings from a preset file.

        Args:
            preset_name (str): Name of the preset (default: "default")

        Returns:
            dict[str, Any]: Settings data, or empty dict if preset doesn't exist

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> data = settings.load_settings("my_preset")
            >>> print(data.get("option1"))
            True
        """
        self._validate_preset_name(preset_name)
        preset_path = self._get_preset_path(preset_name)

        if not preset_path.exists():
            logger.debug(f"Preset '{preset_name}' does not exist, returning empty dict")
            return {}

        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded settings from preset '{preset_name}': {preset_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from '{preset_path}': {e}")
            return {}
        except OSError as e:
            logger.error(f"Failed to read settings file '{preset_path}': {e}")
            return {}

    def list_presets(self) -> list[str]:
        """
        List all available preset names.

        Returns:
            list[str]: List of preset names (without .json extension), sorted alphabetically

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> presets = settings.list_presets()
            >>> print(presets)
            ['default', 'my_preset', 'quick_setup']
        """
        settings_dir = self._get_settings_dir()
        if not settings_dir.exists():
            logger.debug(f"Settings directory doesn't exist: {settings_dir}")
            return []

        preset_files = list(settings_dir.glob("*.json"))
        preset_names = sorted([f.stem for f in preset_files])
        logger.debug(f"Found {len(preset_names)} presets: {preset_names}")
        return preset_names

    def preset_exists(self, preset_name: str) -> bool:
        """
        Check if a preset exists.

        Args:
            preset_name (str): Name of the preset

        Returns:
            bool: True if preset exists, False otherwise

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> if settings.preset_exists("my_preset"):
            ...     print("Preset exists")
        """
        self._validate_preset_name(preset_name)
        preset_path = self._get_preset_path(preset_name)
        exists = preset_path.exists()
        logger.debug(f"Preset '{preset_name}' exists: {exists}")
        return exists

    def delete_preset(self, preset_name: str) -> None:
        """
        Delete a preset file.

        Args:
            preset_name (str): Name of the preset to delete

        Raises:
            ValueError: If trying to delete the default preset or if preset doesn't exist

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> settings.delete_preset("old_preset")
        """
        self._validate_preset_name(preset_name)

        if preset_name == self.DEFAULT_PRESET_NAME:
            raise ValueError(f"Cannot delete the '{self.DEFAULT_PRESET_NAME}' preset")

        preset_path = self._get_preset_path(preset_name)
        if not preset_path.exists():
            raise ValueError(f"Preset '{preset_name}' does not exist")

        try:
            preset_path.unlink()
            logger.info(f"Deleted preset '{preset_name}': {preset_path}")
        except OSError as e:
            logger.error(f"Failed to delete preset '{preset_name}': {e}")
            raise

    def rename_preset(self, old_name: str, new_name: str) -> None:
        """
        Rename a preset file.

        Args:
            old_name (str): Current preset name
            new_name (str): New preset name

        Raises:
            ValueError: If trying to rename the default preset, if old preset doesn't exist,
                       or if new name already exists

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> settings.rename_preset("old_name", "new_name")
        """
        self._validate_preset_name(old_name)
        self._validate_preset_name(new_name)

        if old_name == self.DEFAULT_PRESET_NAME:
            raise ValueError(f"Cannot rename the '{self.DEFAULT_PRESET_NAME}' preset")

        old_path = self._get_preset_path(old_name)
        new_path = self._get_preset_path(new_name)

        if not old_path.exists():
            raise ValueError(f"Preset '{old_name}' does not exist")

        if new_path.exists():
            raise ValueError(f"Preset '{new_name}' already exists")

        try:
            old_path.rename(new_path)
            logger.info(f"Renamed preset '{old_name}' to '{new_name}'")
        except OSError as e:
            logger.error(f"Failed to rename preset '{old_name}' to '{new_name}': {e}")
            raise

    def export_preset(self, preset_name: str, file_path: str | Path) -> None:
        """
        Export a preset to an external JSON file.

        Args:
            preset_name (str): Name of the preset to export
            file_path (str | Path): Destination file path

        Raises:
            ValueError: If preset doesn't exist

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> settings.export_preset("my_preset", "D:/my_preset_backup.json")
        """
        self._validate_preset_name(preset_name)
        preset_path = self._get_preset_path(preset_name)

        if not preset_path.exists():
            raise ValueError(f"Preset '{preset_name}' does not exist")

        dest_path = Path(file_path).expanduser().resolve()

        try:
            import shutil

            shutil.copy2(preset_path, dest_path)
            logger.info(f"Exported preset '{preset_name}' to '{dest_path}'")
        except OSError as e:
            logger.error(f"Failed to export preset '{preset_name}' to '{dest_path}': {e}")
            raise

    def import_preset(self, file_path: str | Path, preset_name: str | None = None) -> str:
        """
        Import a preset from an external JSON file.

        Args:
            file_path (str | Path): Source file path
            preset_name (str | None): Name for the imported preset.
                                     If None, uses the source file's basename (without extension)

        Returns:
            str: Name of the imported preset

        Raises:
            ValueError: If preset name is invalid or file doesn't exist

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> imported_name = settings.import_preset("D:/my_preset_backup.json")
            >>> print(f"Imported as: {imported_name}")
            Imported as: my_preset_backup
        """
        source_path = Path(file_path).expanduser().resolve()

        if not source_path.exists():
            raise ValueError(f"Source file does not exist: {source_path}")

        # Use filename as preset name if not specified
        if preset_name is None:
            preset_name = source_path.stem

        self._validate_preset_name(preset_name)

        # Validate JSON content before importing
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file '{source_path}': {e}")
            raise ValueError(f"Invalid JSON file: {e}") from e
        except OSError as e:
            logger.error(f"Failed to read file '{source_path}': {e}")
            raise

        # Save as new preset
        self.save_settings(data, preset_name)
        logger.info(f"Imported preset '{preset_name}' from '{source_path}'")
        return preset_name


__all__ = ["ToolSettingsManager"]
