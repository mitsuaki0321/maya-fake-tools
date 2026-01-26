"""
Settings manager for Code Editor.
Handles persistent storage of editor settings, window state, and user preferences.
Uses a modular architecture with separate managers for different types of settings.
"""

import json
from logging import getLogger
import os
from typing import Any

from .....lib_ui.qt_compat import QFont
from .session_manager import SessionManager
from .user_settings import UserSettings
from .workspace_manager import WorkspaceManager

logger = getLogger(__name__)


class SettingsManager:
    """
    Main settings manager that coordinates between different setting types.
    Provides backward compatibility while using the new modular architecture.
    """

    def __init__(self):
        self.settings_dir = self._get_settings_directory()
        logger.debug(f"Settings directory: {self.settings_dir}")

        # Initialize sub-managers
        self.user_settings = UserSettings(self.settings_dir)
        self.session_manager = SessionManager(self.settings_dir)
        self.workspace_manager = WorkspaceManager(self.settings_dir)

        # Log workspace directory after initialization
        workspace_dir = self.workspace_manager.get_workspace_directory()
        logger.debug(f"Workspace directory: {workspace_dir}")

        # Legacy support - migrate old settings.json to new modular structure
        self._migrate_legacy_settings()

        # Clean up any old backups in root directory on startup
        self._cleanup_old_backups()

    def _get_settings_directory(self) -> str:
        """Get the directory for settings files.

        Uses FakeTools ToolDataManager for path resolution:
        {MAYA_APP_DIR}/faketools_workspace/common/code_editor/config/
        """
        try:
            from .....lib_ui.tool_data import ToolDataManager

            data_manager = ToolDataManager("code_editor", "common")
            settings_dir = str(data_manager.get_data_dir() / "config")
            logger.debug(f"Using ToolDataManager for settings path: {settings_dir}")
        except (ImportError, RuntimeError) as e:
            # Fallback for standalone mode
            import tempfile

            settings_dir = os.path.join(tempfile.gettempdir(), "faketools_code_editor_config")
            logger.debug(f"Using fallback settings path (standalone mode): {settings_dir} ({e})")

        # Create directory if it doesn't exist
        os.makedirs(settings_dir, exist_ok=True)

        return settings_dir

    def _migrate_legacy_settings(self):
        """Migrate legacy settings.json to new modular structure."""
        legacy_file = os.path.join(self.settings_dir, "settings.json")
        # Check if new structure already exists - if so, don't migrate
        user_settings_file = os.path.join(self.settings_dir, "user_settings.json")
        if os.path.exists(user_settings_file):
            # New structure exists, no migration needed
            return
        if os.path.exists(legacy_file):
            try:
                with open(legacy_file, encoding="utf-8") as f:
                    legacy_settings = json.load(f)

                # Migrate to appropriate managers
                self._migrate_to_user_settings(legacy_settings)
                self._migrate_to_session_manager(legacy_settings)
                self._migrate_to_workspace_manager(legacy_settings)

                # Create backup directory if it doesn't exist
                backup_dir = os.path.join(self.settings_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)

                # Create timestamped backup
                import time

                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(backup_dir, f"settings_legacy_{timestamp}.json")

                # Copy to backup instead of rename to preserve original
                import shutil

                shutil.copy2(legacy_file, backup_file)

                # Remove original legacy file
                os.remove(legacy_file)

                backup_filename = os.path.basename(backup_file)
                logger.info(f"Legacy settings migrated to new structure. Backup saved in backups/{backup_filename}")

                # Clean up old backups in root directory
                self._cleanup_old_backups()

            except Exception as e:
                logger.error(f"Failed to migrate legacy settings: {e}")

    def _cleanup_old_backups(self):
        """Clean up old backup files from root settings directory."""
        try:
            import glob

            # Find all old backup files in root directory
            old_backups = glob.glob(os.path.join(self.settings_dir, "settings_legacy_backup*.json"))

            if old_backups:
                # Create backup directory if it doesn't exist
                backup_dir = os.path.join(self.settings_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)

                # Move old backups to backup directory
                import shutil

                for old_backup in old_backups:
                    filename = os.path.basename(old_backup)
                    new_path = os.path.join(backup_dir, filename)

                    # If file already exists in backup dir, skip
                    if not os.path.exists(new_path):
                        shutil.move(old_backup, new_path)
                    else:
                        # Remove duplicate
                        os.remove(old_backup)

                logger.info(f"Moved {len(old_backups)} old backup(s) to backups directory")

        except Exception as e:
            # Non-critical operation, just log the error
            logger.error(f"Failed to cleanup old backups: {e}")

    def _migrate_to_user_settings(self, legacy_settings: dict[str, Any]):
        """Migrate user preferences to UserSettings."""
        user_data = {}
        for key in ["editor", "terminal", "search", "maya", "autosave"]:
            if key in legacy_settings:
                user_data[key] = legacy_settings[key]

        if "max_recent_files" in legacy_settings:
            user_data["files"] = {"max_recent_files": legacy_settings["max_recent_files"]}

        if user_data:
            self.user_settings.current_settings.update(user_data)
            self.user_settings.save_settings()

    def _migrate_to_session_manager(self, legacy_settings: dict[str, Any]):
        """Migrate session data to SessionManager."""
        session_data = {}
        for key in ["window", "session", "recent_files"]:
            if key in legacy_settings:
                session_data[key] = legacy_settings[key]

        if "draft_content" in legacy_settings:
            session_data["draft_content"] = legacy_settings["draft_content"]

        if session_data:
            self.session_manager.current_session.update(session_data)
            self.session_manager.save_session()

    def _migrate_to_workspace_manager(self, legacy_settings: dict[str, Any]):
        """Migrate workspace data to WorkspaceManager."""
        if "workspace" in legacy_settings:
            workspace_data = {"workspace": legacy_settings["workspace"]}
            self.workspace_manager.current_workspace.update(workspace_data)
            self.workspace_manager.save_workspace()

    def load_settings(self) -> dict[str, Any]:
        """Load settings from file (legacy compatibility)."""
        # Return combined settings from all managers
        combined = {}
        combined.update(self.user_settings.current_settings)
        combined.update(self.session_manager.current_session)
        combined.update(self.workspace_manager.current_workspace)
        return combined

    def save_settings(self) -> bool:
        """Save current settings to file (legacy compatibility)."""
        # Save all managers
        user_saved = self.user_settings.save_settings()
        session_saved = self.session_manager.save_session()
        workspace_saved = self.workspace_manager.save_workspace()

        return user_saved and session_saved and workspace_saved

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'editor.font_size')."""
        # Route to appropriate manager based on key prefix
        if key.startswith("window.") or key.startswith("session.") or key.startswith("recent_files") or key.startswith("draft_content"):
            return self.session_manager.get(key, default)
        if key.startswith("workspace.") or key.startswith("project."):
            return self.workspace_manager.get(key, default)
        # Default to user settings
        return self.user_settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value using dot notation (e.g., 'editor.font_size', 12)."""
        # Route to appropriate manager based on key prefix
        if key.startswith("window.") or key.startswith("session.") or key.startswith("recent_files") or key.startswith("draft_content"):
            self.session_manager.set(key, value)
        elif key.startswith("workspace.") or key.startswith("project."):
            self.workspace_manager.set(key, value)
        else:
            # Default to user settings
            self.user_settings.set(key, value)

    def get_window_geometry(self) -> dict[str, int]:
        """Get window geometry settings."""
        return self.session_manager.get_window_geometry()

    def set_window_geometry(self, x: int, y: int, width: int, height: int, maximized: bool = False):
        """Set window geometry settings."""
        self.session_manager.set_window_geometry(x, y, width, height, maximized)

    def get_splitter_sizes(self, splitter_name: str) -> list[int]:
        """Get splitter sizes."""
        return self.session_manager.get_splitter_sizes(splitter_name)

    def set_splitter_sizes(self, splitter_name: str, sizes: list[int]):
        """Set splitter sizes."""
        self.session_manager.set_splitter_sizes(splitter_name, sizes)

    def get_editor_font(self) -> QFont:  # type: ignore
        """Get editor font settings as QFont object."""
        font_info = self.user_settings.get_editor_font_info()
        family = font_info["family"]
        size = font_info["size"]

        font = QFont(family, size)
        if not font.exactMatch():
            font = QFont("Courier New", size)

        return font

    def get_terminal_font(self) -> QFont:  # type: ignore
        """Get terminal font settings as QFont object."""
        font_info = self.user_settings.get_terminal_font_info()
        family = font_info["family"]
        size = font_info["size"]

        font = QFont(family, size)
        if not font.exactMatch():
            font = QFont("Courier New", size)

        return font

    def add_recent_file(self, file_path: str):
        """Add a file to the recent files list."""
        self.session_manager.add_recent_file(file_path)

    def get_recent_files(self) -> list[str]:
        """Get list of recent files."""
        return self.session_manager.get_recent_files()

    def clear_recent_files(self):
        """Clear the recent files list."""
        self.session_manager.clear_recent_files()

    def get_search_settings(self) -> dict[str, Any]:
        """Get search dialog settings."""
        return self.user_settings.get_search_settings()

    def set_search_settings(self, match_case: bool, whole_words: bool, use_regex: bool, direction: str):
        """Set search dialog settings."""
        self.user_settings.set_search_settings(match_case, whole_words, use_regex, direction)

    def get_workspace_directory(self) -> str:
        """Get the workspace root directory, creating default if needed."""
        return self.workspace_manager.get_workspace_directory()

    def set_workspace_directory(self, directory: str) -> bool:
        """Set the workspace root directory."""
        return self.workspace_manager.set_workspace_directory(directory)

    def add_workspace_to_python_path(self):
        """Add workspace directory to Python path if enabled."""
        self.workspace_manager.add_workspace_to_python_path()

    def update_recent_file_path(self, old_path: str, new_path: str):
        """Update a file path in the recent files list."""
        self.session_manager.update_recent_file_path(old_path, new_path)

    # Session management methods
    def save_session_state(self, open_tabs: list[dict[str, Any]]):
        """Save current session state (open tabs)."""
        self.session_manager.save_session_state(open_tabs)

    def get_session_state(self) -> list[dict[str, Any]]:
        """Get saved session state."""
        return self.session_manager.get_session_state()

    def should_restore_session(self) -> bool:
        """Check if session restoration is enabled."""
        return self.session_manager.should_restore_session()

    def create_tab_info(
        self,
        file_path: str = None,
        content: str = "",
        cursor_position: int = 0,
        is_modified: bool = False,
        tab_name: str = None,
    ) -> dict[str, Any]:
        """Create tab information dictionary."""
        return self.session_manager.create_tab_info(file_path, content, cursor_position, is_modified, tab_name)

    def clear_session_state(self):
        """Clear saved session state."""
        self.session_manager.clear_session_state()

    def get_interface_language(self) -> str:
        """Get the interface language setting.

        Returns:
            Language code (JPN, ENU, CHS, CHT, KOR, DEU, FRA, ITA, SPA, PTB)
        """
        return self.user_settings.get_interface_language()
