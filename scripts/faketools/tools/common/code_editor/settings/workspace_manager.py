"""
Workspace manager for Code Editor.
Handles workspace-specific settings like root directory, project configuration, etc.
"""

import json
from logging import getLogger
import os
from typing import Any

logger = getLogger(__name__)


class WorkspaceManager:
    """Manages workspace-specific settings and configuration."""

    def __init__(self, settings_dir: str):
        self.workspace_file = os.path.join(settings_dir, "workspace.json")
        self.default_workspace = self._get_default_workspace()
        self.current_workspace = self.load_workspace()

    def _get_default_workspace(self) -> dict[str, Any]:
        """Get default workspace settings."""
        return {
            # Workspace settings
            "workspace": {
                "root_directory": "",  # Will be set to default workspace on first run
                "name": "Default Workspace",
                "description": "Code Editor workspace",
                "created_date": "",
                "last_accessed": "",
            },
            # Project settings
            "project": {
                "python_paths": [],  # Additional Python paths for this workspace
                "startup_scripts": [],  # Scripts to run on workspace load
                "environment_vars": {},  # Workspace-specific environment variables
            },
        }

    def load_workspace(self) -> dict[str, Any]:
        """Load workspace settings from file."""
        if not os.path.exists(self.workspace_file):
            return self.default_workspace.copy()

        try:
            with open(self.workspace_file, encoding="utf-8") as f:
                saved_workspace = json.load(f)

            # Merge with defaults (in case new workspace settings were added)
            merged_workspace = self._merge_workspace(self.default_workspace, saved_workspace)
            return merged_workspace

        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load workspace settings: {e}")
            return self.default_workspace.copy()

    def save_workspace(self) -> bool:
        """Save current workspace settings to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.workspace_file), exist_ok=True)

            # Update last accessed timestamp
            import time

            self.current_workspace["workspace"]["last_accessed"] = time.strftime("%Y-%m-%d %H:%M:%S")

            with open(self.workspace_file, "w", encoding="utf-8") as f:
                json.dump(self.current_workspace, f, indent=2, ensure_ascii=False)
            return True

        except OSError as e:
            logger.error(f"Failed to save workspace settings: {e}")
            return False

    def _merge_workspace(self, defaults: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge saved workspace with defaults."""
        result = defaults.copy()

        for key, value in saved.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_workspace(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a workspace value using dot notation (e.g., 'workspace.root_directory')."""
        keys = key.split(".")
        value = self.current_workspace

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set a workspace value using dot notation (e.g., 'workspace.root_directory', '/path')."""
        keys = key.split(".")
        workspace_dict = self.current_workspace

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in workspace_dict:
                workspace_dict[k] = {}
            workspace_dict = workspace_dict[k]

        # Set the final value
        workspace_dict[keys[-1]] = value

    def get_workspace_directory(self) -> str:
        """Get the workspace root directory, creating default if needed."""
        workspace_dir = self.get("workspace.root_directory", "")

        # If no workspace directory is set, create default
        if not workspace_dir:
            logger.debug("No saved workspace directory, creating default")
            workspace_dir = self._create_default_workspace()
            self.set("workspace.root_directory", workspace_dir)
            self.save_workspace()
        else:
            logger.debug(f"Loaded saved workspace directory: {workspace_dir}")

        return workspace_dir

    def _create_default_workspace(self) -> str:
        """Create and return the default workspace directory.

        Uses FakeTools ToolDataManager for path resolution:
        {MAYA_APP_DIR}/faketools_workspace/common/code_editor/workspace/
        """
        try:
            from .....lib_ui.tool_data import ToolDataManager

            data_manager = ToolDataManager("code_editor", "common")
            workspace_dir = str(data_manager.get_data_dir() / "workspace")
            logger.debug(f"Using ToolDataManager for workspace path: {workspace_dir}")
        except (ImportError, RuntimeError) as e:
            # Fallback for standalone mode
            import tempfile

            workspace_dir = os.path.join(tempfile.gettempdir(), "faketools_code_editor_workspace")
            logger.debug(f"Using fallback workspace path (standalone mode): {workspace_dir} ({e})")

        # Create directory if it doesn't exist
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir, exist_ok=True)
            logger.debug(f"Created workspace directory: {workspace_dir}")

        # Copy startup files to workspace
        self._copy_startup_files(workspace_dir)

        # Set workspace creation date if first time
        if not self.get("workspace.created_date"):
            import time

            self.set("workspace.created_date", time.strftime("%Y-%m-%d %H:%M:%S"))

        return workspace_dir

    def _copy_startup_files(self, workspace_dir: str):
        """Copy all Python files from startup directory to workspace."""
        # Get the startup directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        startup_dir = os.path.join(current_dir, "startup")

        # Check if startup directory exists
        if not os.path.exists(startup_dir):
            return

        # Copy all Python files from startup directory
        import shutil

        for filename in os.listdir(startup_dir):
            if filename.endswith(".py"):
                src_file = os.path.join(startup_dir, filename)
                dst_file = os.path.join(workspace_dir, filename)

                # Only copy if file doesn't exist in workspace
                if not os.path.exists(dst_file):
                    try:
                        shutil.copy2(src_file, dst_file)
                        logger.info(f"Copied startup file: {filename}")
                    except OSError as e:
                        logger.error(f"Failed to copy {filename}: {e}")

    def set_workspace_directory(self, directory: str) -> bool:
        """Set the workspace root directory."""
        if os.path.exists(directory):
            self.set("workspace.root_directory", directory)
            return True
        return False

    def add_python_path(self, path: str):
        """Add a Python path to the workspace."""
        python_paths = self.get("project.python_paths", [])
        if path not in python_paths:
            python_paths.append(path)
            self.set("project.python_paths", python_paths)

    def remove_python_path(self, path: str):
        """Remove a Python path from the workspace."""
        python_paths = self.get("project.python_paths", [])
        if path in python_paths:
            python_paths.remove(path)
            self.set("project.python_paths", python_paths)

    def get_python_paths(self) -> list[str]:
        """Get all Python paths for this workspace."""
        paths = self.get("project.python_paths", [])
        workspace_dir = self.get_workspace_directory()

        # Always include workspace directory
        if workspace_dir and workspace_dir not in paths:
            return [workspace_dir] + paths
        return paths

    def add_workspace_to_python_path(self):
        """Add workspace directory and additional paths to Python sys.path."""
        import sys

        for path in self.get_python_paths():
            if path and os.path.exists(path) and path not in sys.path:
                sys.path.insert(0, path)

    def add_startup_script(self, script_path: str):
        """Add a startup script to the workspace."""
        startup_scripts = self.get("project.startup_scripts", [])
        if script_path not in startup_scripts:
            startup_scripts.append(script_path)
            self.set("project.startup_scripts", startup_scripts)

    def get_startup_scripts(self) -> list[str]:
        """Get all startup scripts for this workspace."""
        return self.get("project.startup_scripts", [])

    def set_environment_variable(self, name: str, value: str):
        """Set an environment variable for this workspace."""
        env_vars = self.get("project.environment_vars", {})
        env_vars[name] = value
        self.set("project.environment_vars", env_vars)

    def get_environment_variables(self) -> dict[str, str]:
        """Get all environment variables for this workspace."""
        return self.get("project.environment_vars", {})

    def apply_environment_variables(self):
        """Apply workspace environment variables to the current environment."""
        import os

        env_vars = self.get_environment_variables()
        for name, value in env_vars.items():
            os.environ[name] = value
            logger.debug(f"Set environment variable: {name}={value}")

    def get_workspace_info(self) -> dict[str, Any]:
        """Get workspace information."""
        return {
            "name": self.get("workspace.name", "Unknown Workspace"),
            "description": self.get("workspace.description", ""),
            "root_directory": self.get_workspace_directory(),
            "created_date": self.get("workspace.created_date", ""),
            "last_accessed": self.get("workspace.last_accessed", ""),
            "python_paths": self.get_python_paths(),
            "startup_scripts": self.get_startup_scripts(),
        }
