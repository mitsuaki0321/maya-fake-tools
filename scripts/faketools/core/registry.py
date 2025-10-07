"""
Tool registration system for FakeTools.

Provides automatic tool discovery and registration for the menu system.
"""

import importlib
import logging
from pathlib import Path
from typing import Any

from .base.tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for managing and discovering FakeTools.

    This class provides:
    - Automatic tool discovery from the tools directory
    - Dynamic tool loading
    - Category-based organization
    - Menu generation support
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: dict[str, dict[str, Any]] = {}
        self._categories: dict[str, list[str]] = {}
        self._loaded_modules = set()

    def discover_tools(self, tools_path: Path | None = None) -> None:
        """
        Discover all tools in the tools directory.

        Args:
            tools_path (Path | None): Path to tools directory (default: scripts/faketools/tools)
        """
        if tools_path is None:
            # Get the default tools path
            module_dir = Path(__file__).parent.parent
            tools_path = module_dir / "tools"

        logger.info(f"Discovering tools in {tools_path}")

        if not tools_path.exists():
            logger.warning(f"Tools directory does not exist: {tools_path}")
            return

        # Scan category directories
        for category_dir in tools_path.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue

            category_name = category_dir.name
            logger.debug(f"Scanning category: {category_name}")

            # Scan tool directories within category
            for tool_dir in category_dir.iterdir():
                if not tool_dir.is_dir() or tool_dir.name.startswith("_"):
                    continue

                # Check for __init__.py
                init_file = tool_dir / "__init__.py"
                if not init_file.exists():
                    continue

                tool_name = tool_dir.name
                self._register_tool_from_directory(category_name, tool_name)

    def _register_tool_from_directory(self, category: str, tool_name: str) -> None:
        """
        Register a tool from its directory.

        Args:
            category (str): Tool category
            tool_name (str): Tool directory name
        """
        try:
            # Import the tool module
            module_path = f"faketools.tools.{category}.{tool_name}"

            # Check for config file first
            config = self._load_tool_config(category, tool_name, module_path)
            if config:
                self._register_tool_from_config(category, tool_name, config, module_path)
            else:
                # Try to import and auto-detect
                self._auto_register_tool(module_path, category, tool_name)

        except Exception as e:
            logger.error(f"Failed to register tool {tool_name}: {e}")

    def _load_tool_config(self, category: str, tool_name: str, module_path: str = None) -> dict | None:
        """
        Load tool configuration if it exists.

        Args:
            category (str): Tool category
            tool_name (str): Tool name
            module_path (str | None): Optional module path override

        Returns:
            dict | None: Tool configuration dictionary or None
        """
        try:
            if module_path is None:
                module_path = f"faketools.tools.{category}.{tool_name}"

            module = importlib.import_module(module_path)

            if hasattr(module, "TOOL_CONFIG"):
                return module.TOOL_CONFIG

        except ImportError:
            pass

        return None

    def _auto_register_tool(self, module_path: str, category: str, tool_name: str) -> None:
        """
        Auto-register a tool by scanning for BaseTool subclasses.

        Args:
            module_path (str): Full module path
            category (str): Tool category
            tool_name (str): Tool name
        """
        try:
            # Try to import ui module
            ui_module_path = f"{module_path}.ui"
            ui_module = importlib.import_module(ui_module_path)

            # Find BaseTool subclasses
            for attr_name in dir(ui_module):
                attr = getattr(ui_module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseTool) and attr is not BaseTool:
                    # Register the tool class
                    self._register_tool_class(attr, category, tool_name)
                    break

        except ImportError as e:
            logger.debug(f"Could not auto-register {tool_name}: {e}")

    def _register_tool_from_config(self, category: str, tool_name: str, config: dict, module_path: str) -> None:
        """
        Register a tool from configuration.

        Args:
            category (str): Tool category
            tool_name (str): Tool name
            config (dict): Tool configuration
            module_path (str): Module path
        """
        tool_id = f"{category}.{tool_name}"

        self._tools[tool_id] = {
            "id": tool_id,
            "name": config.get("name", tool_name),
            "category": category,
            "tool_name": tool_name,
            "config": config,
            "module_path": module_path,
        }

        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool_id)

        logger.info(f"Registered tool from config: {tool_id}")

    def _register_tool_class(self, tool_class: type[BaseTool], category: str, tool_name: str) -> None:
        """
        Register a tool class.

        Args:
            tool_class (type[BaseTool]): Tool class (subclass of BaseTool)
            category (str): Tool category
            tool_name (str): Tool name
        """
        tool_id = f"{category}.{tool_name}"
        metadata = tool_class.get_metadata()

        self._tools[tool_id] = {
            "id": tool_id,
            "name": metadata.get("name", tool_name),
            "category": category,
            "tool_name": tool_name,
            "class": tool_class,
            "metadata": metadata,
            "module_path": tool_class.__module__,
        }

        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool_id)

        logger.info(f"Registered tool class: {tool_id}")

    def get_tool(self, tool_id: str) -> dict | None:
        """
        Get tool information by ID.

        Args:
            tool_id (str): Tool ID (e.g., "rig.skin_tools")

        Returns:
            dict | None: Tool information dictionary or None
        """
        return self._tools.get(tool_id)

    def get_tools_by_category(self, category: str) -> list[dict]:
        """
        Get all tools in a category.

        Args:
            category (str): Category name

        Returns:
            list[dict]: List of tool information dictionaries
        """
        tool_ids = self._categories.get(category, [])
        return [self._tools[tid] for tid in tool_ids]

    def get_all_categories(self) -> list[str]:
        """
        Get all registered categories.

        Returns:
            list[str]: List of category names
        """
        return list(self._categories.keys())

    def create_tool_instance(self, tool_id: str, parent=None):
        """
        Create an instance of a tool.

        Args:
            tool_id (str): Tool ID
            parent: Parent widget

        Returns:
            object | None: Tool instance or None
        """
        tool_info = self.get_tool(tool_id)
        if not tool_info:
            logger.error(f"Tool not found: {tool_id}")
            return None

        try:
            if "class" in tool_info:
                # Direct class reference
                tool_class = tool_info["class"]
                return tool_class(parent=parent)
            else:
                # Load from module
                module_path = tool_info["module_path"]
                ui_module = importlib.import_module(f"{module_path}.ui")

                # Try to find the main window class
                if hasattr(ui_module, "MainWindow"):
                    return ui_module.MainWindow(parent=parent)
                elif hasattr(ui_module, "show_ui"):
                    # Old-style tool, use show_ui function
                    return ui_module

        except Exception as e:
            logger.error(f"Failed to create tool instance for {tool_id}: {e}")

        return None

    def get_menu_structure(self) -> dict[str, list[dict]]:
        """
        Get menu structure for all registered tools.

        Returns:
            dict[str, list[dict]]: Dictionary with categories as keys and tool lists as values
        """
        menu_structure = {}

        for category in self.get_all_categories():
            tools = self.get_tools_by_category(category)

            menu_items = []
            for tool in tools:
                menu_item = {
                    "label": tool["name"],
                    "tool_id": tool["id"],
                    "command": self._generate_menu_command(tool["id"]),
                }

                # Add metadata if available
                if "metadata" in tool:
                    menu_item["description"] = tool["metadata"].get("description", "")

                menu_items.append(menu_item)

            menu_structure[category] = menu_items

        return menu_structure

    def _generate_menu_command(self, tool_id: str) -> str:
        """
        Generate Maya menu command for a tool.

        Args:
            tool_id (str): Tool ID

        Returns:
            str: Python command string
        """
        tool = self._tools.get(tool_id)
        if not tool:
            return ""

        # For tools, use show_ui
        module_path = tool["module_path"]
        return f"import {module_path}.ui; {module_path}.ui.show_ui()"


# Global registry instance
_global_registry = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        ToolRegistry: Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


__all__ = ["ToolRegistry", "get_registry"]
