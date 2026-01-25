"""
User settings manager for Maya Code Editor.
Handles persistent user preferences like editor settings, theme, fonts, etc.
"""

import json
from logging import getLogger
import os
from typing import Any

logger = getLogger(__name__)


class UserSettings:
    """Manages user preferences and settings."""

    def __init__(self, settings_dir: str):
        self.settings_file = os.path.join(settings_dir, "user_settings.json")
        self.default_settings = self._get_default_settings()
        self.current_settings = self.load_settings()

    def _get_default_settings(self) -> dict[str, Any]:
        """Get default user settings."""
        return {
            # General settings
            "general": {
                "language": "JPN",  # Interface language (JPN, ENU, CHS, CHT, KOR, DEU, FRA, ITA, SPA, PTB)
            },
            # Editor settings
            "editor": {
                "font_family": "Consolas",
                "font_size": 10,
                "tab_size": 4,
                "word_wrap": True,
                "show_line_numbers": True,
                "highlight_current_line": True,
                "auto_indent": True,
                "theme": "dark_modern",
            },
            # Terminal settings
            "terminal": {"font_family": "Consolas", "font_size": 9, "max_lines": 1000, "auto_scroll": True},
            # Search settings
            "search": {"match_case": False, "whole_words": False, "use_regex": False, "search_direction": "down"},
            # Auto-save settings
            "autosave": {
                "enabled": True,
                "interval_seconds": 60,
                "backup_on_change": True,
            },
            # File settings
            "files": {"max_recent_files": 20},
            # Layout settings
            "layout": {
                "terminal_at_bottom": True,  # True: editor top/terminal bottom, False: terminal top/editor bottom
            },
            # Snippets settings removed - no longer needed
        }

    def load_settings(self) -> dict[str, Any]:
        """Load settings from file."""
        if not os.path.exists(self.settings_file):
            return self.default_settings.copy()

        try:
            with open(self.settings_file, encoding="utf-8") as f:
                saved_settings = json.load(f)

            # Merge with defaults (in case new settings were added)
            merged_settings = self._merge_settings(self.default_settings, saved_settings)
            return merged_settings

        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load user settings: {e}")
            return self.default_settings.copy()

    def save_settings(self) -> bool:
        """Save current settings to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)

            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)
            return True

        except OSError as e:
            logger.error(f"Failed to save user settings: {e}")
            return False

    def _merge_settings(self, defaults: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge saved settings with defaults."""
        result = defaults.copy()

        for key, value in saved.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'editor.font_size')."""
        keys = key.split(".")
        value = self.current_settings

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set a setting value using dot notation (e.g., 'editor.font_size', 12)."""
        keys = key.split(".")
        setting_dict = self.current_settings

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in setting_dict:
                setting_dict[k] = {}
            setting_dict = setting_dict[k]

        # Set the final value
        setting_dict[keys[-1]] = value

    def get_editor_font_info(self) -> dict[str, Any]:
        """Get editor font information as dictionary."""
        return {"family": self.get("editor.font_family", "Consolas"), "size": self.get("editor.font_size", 10)}

    def get_terminal_font_info(self) -> dict[str, Any]:
        """Get terminal font information as dictionary."""
        return {"family": self.get("terminal.font_family", "Consolas"), "size": self.get("terminal.font_size", 9)}

    def get_search_settings(self) -> dict[str, Any]:
        """Get search dialog settings."""
        return self.get("search", {})

    def set_search_settings(self, match_case: bool, whole_words: bool, use_regex: bool, direction: str):
        """Set search dialog settings."""
        self.set("search.match_case", match_case)
        self.set("search.whole_words", whole_words)
        self.set("search.use_regex", use_regex)
        self.set("search.search_direction", direction)

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.current_settings = self.default_settings.copy()

    def export_settings(self, file_path: str) -> bool:
        """Export settings to a file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)
            return True
        except OSError as e:
            logger.error(f"Failed to export user settings: {e}")
            return False

    def import_settings(self, file_path: str) -> bool:
        """Import settings from a file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                imported_settings = json.load(f)

            # Merge with current settings
            self.current_settings = self._merge_settings(self.current_settings, imported_settings)
            return True

        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to import user settings: {e}")
            return False

    def get_interface_language(self) -> str:
        """Get the interface language setting.

        Returns:
            Language code (JPN, ENU, CHS, CHT, KOR, DEU, FRA, ITA, SPA, PTB)
        """
        return self.get("general.language", "JPN")
