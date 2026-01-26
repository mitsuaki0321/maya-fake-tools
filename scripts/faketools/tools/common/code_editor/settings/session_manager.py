"""
Session manager for Code Editor.
Handles temporary session state like window position, open tabs, draft content, etc.
"""

import json
from logging import getLogger
import os
from typing import Any

logger = getLogger(__name__)

# Constants
MAX_RECENT_FILES = 20


class SessionManager:
    """Manages session state and temporary data."""

    def __init__(self, settings_dir: str):
        self.session_file = os.path.join(settings_dir, "session.json")
        self.default_session = self._get_default_session()
        self.current_session = self.load_session()

    def _get_default_session(self) -> dict[str, Any]:
        """Get default session state."""
        return {
            # Window state
            "window": {
                "width": 800,
                "height": 600,
                "x": 100,
                "y": 100,
                "maximized": False,
                "splitter_sizes": {
                    "horizontal": [200, 600],  # Explorer, Editor area
                    "vertical": [400, 200],  # Editor, Terminal
                },
            },
            # Session settings
            "session": {
                "restore_tabs_on_startup": True,
                "open_tabs": [],  # List of tab information
            },
            # Recent files (session-specific)
            "recent_files": [],
            # Draft tab content
            "draft_content": "",
            # Last session info
            "last_session": {"timestamp": 0},
        }

    def load_session(self) -> dict[str, Any]:
        """Load session from file."""
        if not os.path.exists(self.session_file):
            return self.default_session.copy()

        try:
            with open(self.session_file, encoding="utf-8") as f:
                saved_session = json.load(f)

            # Merge with defaults (in case new session data was added)
            merged_session = self._merge_session(self.default_session, saved_session)
            return merged_session

        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load session: {e}")
            return self.default_session.copy()

    def save_session(self) -> bool:
        """Save current session to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)

            # Update timestamp
            import time

            self.current_session["last_session"]["timestamp"] = int(time.time())

            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(self.current_session, f, indent=2, ensure_ascii=False)
            return True

        except OSError as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def _merge_session(self, defaults: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge saved session with defaults."""
        result = defaults.copy()

        for key, value in saved.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_session(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a session value using dot notation (e.g., 'window.width')."""
        keys = key.split(".")
        value = self.current_session

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set a session value using dot notation (e.g., 'window.width', 800)."""
        keys = key.split(".")
        session_dict = self.current_session

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in session_dict:
                session_dict[k] = {}
            session_dict = session_dict[k]

        # Set the final value
        session_dict[keys[-1]] = value

    def get_window_geometry(self) -> dict[str, int]:
        """Get window geometry settings."""
        return self.get("window", {})

    def set_window_geometry(self, x: int, y: int, width: int, height: int, maximized: bool = False):
        """Set window geometry settings."""
        self.set("window.x", x)
        self.set("window.y", y)
        self.set("window.width", width)
        self.set("window.height", height)
        self.set("window.maximized", maximized)

    def get_splitter_sizes(self, splitter_name: str) -> list[int]:
        """Get splitter sizes."""
        return self.get(f"window.splitter_sizes.{splitter_name}", [])

    def set_splitter_sizes(self, splitter_name: str, sizes: list[int]):
        """Set splitter sizes."""
        self.set(f"window.splitter_sizes.{splitter_name}", sizes)

    def add_recent_file(self, file_path: str):
        """Add a file to the recent files list."""
        recent_files = self.get("recent_files", [])

        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to beginning
        recent_files.insert(0, file_path)

        # Trim to max length
        recent_files = recent_files[:MAX_RECENT_FILES]

        self.set("recent_files", recent_files)

    def get_recent_files(self) -> list[str]:
        """Get list of recent files."""
        recent_files = self.get("recent_files", [])

        # Filter out files that no longer exist
        existing_files = []
        for file_path in recent_files:
            if os.path.exists(file_path):
                existing_files.append(file_path)

        # Update the list if files were removed
        if len(existing_files) != len(recent_files):
            self.set("recent_files", existing_files)

        return existing_files

    def clear_recent_files(self):
        """Clear the recent files list."""
        self.set("recent_files", [])

    def update_recent_file_path(self, old_path: str, new_path: str):
        """Update a file path in the recent files list."""
        recent_files = self.get("recent_files", [])

        # Find and update the old path
        for i, file_path in enumerate(recent_files):
            if file_path == old_path:
                recent_files[i] = new_path
                break

        # Save updated recent files
        self.set("recent_files", recent_files)

    def save_session_state(self, open_tabs: list[dict[str, Any]] = None):
        """Save current session state (open tabs)."""
        if open_tabs is None:
            # Get tabs from main window if available
            open_tabs = self.get_current_tabs()

        # Filter out preview tabs
        filtered_tabs = []
        for tab in open_tabs:
            # Skip preview tabs
            if not tab.get("is_preview", False):
                filtered_tabs.append(tab)

        self.set("session.open_tabs", filtered_tabs)
        self.save_session()

    def get_current_tabs(self) -> list[dict[str, Any]]:
        """Get current tabs from main window."""
        # Try to find main window
        from .....lib_ui.qt_compat import QApplication

        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                if (
                    hasattr(widget, "__class__")
                    and "MayaCodeEditor" in widget.__class__.__name__
                    and hasattr(widget, "code_editor")
                    and widget.code_editor
                ):
                    tabs = []
                    for i in range(widget.code_editor.count()):
                        editor = widget.code_editor.widget(i)
                        if editor:
                            # Skip preview tabs
                            if hasattr(editor, "is_preview") and editor.is_preview:
                                continue

                            tab_info = {
                                "file_path": getattr(editor, "file_path", None),
                                "content": editor.toPlainText(),
                                "cursor_position": editor.textCursor().position(),
                                "is_modified": getattr(editor, "is_modified", False),
                                "tab_name": widget.code_editor.tabText(i),
                                "is_preview": False,
                            }
                            tabs.append(tab_info)
                    return tabs
        return []

    def get_session_state(self) -> list[dict[str, Any]]:
        """Get saved session state."""
        tabs = self.get("session.open_tabs", [])
        return tabs

    def should_restore_session(self) -> bool:
        """Check if session restoration is enabled."""
        result = self.get("session.restore_tabs_on_startup", True)
        return result

    def create_tab_info(
        self,
        file_path: str = None,
        content: str = "",
        cursor_position: int = 0,
        is_modified: bool = False,
        tab_name: str = None,
    ) -> dict[str, Any]:
        """Create tab information dictionary."""
        return {
            "file_path": file_path,
            "content": content,
            "cursor_position": cursor_position,
            "is_modified": is_modified,
            "tab_name": tab_name or (os.path.basename(file_path) if file_path else "Untitled.py"),
        }

    def clear_session_state(self):
        """Clear saved session state."""
        self.set("session.open_tabs", [])
        self.save_session()

    def get_draft_content(self) -> str:
        """Get draft tab content."""
        return self.get("draft_content", "")

    def set_draft_content(self, content: str):
        """Set draft tab content."""
        self.set("draft_content", content)

    def clear_session(self):
        """Clear all session data."""
        self.current_session = self.default_session.copy()

    def is_session_valid(self) -> bool:
        """Check if current session is valid (not too old, etc.)."""
        timestamp = self.get("last_session.timestamp", 0)
        if timestamp == 0:
            return False

        import time

        current_time = int(time.time())
        # Session is valid for 7 days
        return (current_time - timestamp) < (7 * 24 * 60 * 60)
