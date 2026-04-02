"""
Dynamic menu system for FakeTools.

Automatically creates Maya menu based on registered tools.
"""

import logging
import os
import subprocess
import sys
import webbrowser

import maya.cmds as cmds

from . import single_commands_menu
from .config import get_global_config
from .core.registry import get_registry
from .logging_config import get_log_level, set_log_level

logger = logging.getLogger(__name__)

# Menu name constant
MENU_NAME = "FakeToolsMenu"
MENU_LABEL = "FakeTools"

# Category display names
CATEGORY_LABELS = {
    "common": "Common",
    "anim": "Animation",
    "rig": "Rigging",
    "model": "Modeling",
}


def add_menu():
    """
    Add FakeTools menu to Maya's main menu bar.

    Discovers all registered tools and creates menu items for them.
    If the menu already exists, it will be removed and recreated.
    """
    # Remove existing menu if it exists
    remove_menu()

    # Get Maya's main window
    main_window = cmds.window("MayaWindow", query=True, exists=True)
    if not main_window:
        logger.error("Could not find Maya main window")
        return

    # Create main menu
    menu = cmds.menu(MENU_NAME, parent="MayaWindow", label=MENU_LABEL, tearOff=True)

    # Add single commands menu first
    single_commands_menu.show_menu(parent_menu=menu)
    cmds.menuItem(divider=True, parent=menu)

    # Register runtime command for popup menu (hotkey assignable via Hotkey Editor)
    single_commands_menu.register_runtime_command()

    # Discover tools
    registry = get_registry()
    registry.discover_tools()

    # Get menu structure
    menu_structure = registry.get_menu_structure()

    if not menu_structure:
        cmds.menuItem(label="No tools found", enable=False, parent=menu)
        logger.warning("No tools found to add to menu")
        return

    # Create menu items by category
    for category in CATEGORY_LABELS:
        if category not in menu_structure:
            continue

        tools = menu_structure[category]
        if not tools:
            continue

        # Add category label
        category_label = CATEGORY_LABELS.get(category, category.title())
        cmds.menuItem(label=category_label, subMenu=True, tearOff=True, parent=menu)

        # Add tool menu items
        for tool in tools:
            cmds.menuItem(
                label=tool["label"],
                command=tool["command"],
                annotation=tool.get("description", ""),
            )

        # Close category submenu
        cmds.setParent("..", menu=True)

    # Add separator and utility items
    cmds.menuItem(divider=True, parent=menu)

    # Open Workspace
    cmds.menuItem(label="Open Workspace Folder", command=lambda *args: open_workspace(), parent=menu)

    # Help/Documentation
    cmds.menuItem(label="Help", command=lambda *args: open_documentation(), parent=menu)

    # Separator before Reload Menu
    cmds.menuItem(divider=True, parent=menu)

    # Reload menu item
    cmds.menuItem(label="Reload Menu", command=lambda *args: reload_menu(), parent=menu)

    # Log level submenu
    _add_log_level_menu(menu)

    logger.info(f"FakeTools menu created with {len(menu_structure)} categories")


def remove_menu():
    """Remove FakeTools menu from Maya's main menu bar."""
    if cmds.menu(MENU_NAME, query=True, exists=True):
        cmds.deleteUI(MENU_NAME, menu=True)
        logger.info("FakeTools menu removed")


def reload_menu():
    """Reload the FakeTools menu."""
    logger.info("Reloading FakeTools menu...")
    add_menu()


def open_documentation():
    """Open documentation in default browser."""
    url = "https://mitsuaki0321.github.io/maya-fake-tools/"
    webbrowser.open(url)
    logger.info(f"Opening documentation: {url}")


def open_workspace():
    """Open the faketools_workspace directory in the system file explorer."""
    config = get_global_config()
    data_root = config.get_data_root_dir()

    if not data_root.exists():
        data_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created workspace directory: {data_root}")

    path_str = str(data_root)

    if sys.platform == "win32":
        os.startfile(path_str)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path_str])
    else:
        subprocess.Popen(["xdg-open", path_str])

    logger.info(f"Opening workspace: {data_root}")


def _add_log_level_menu(parent_menu: str):
    """
    Add log level submenu to the parent menu.

    Args:
        parent_menu (str): Parent menu to add the log level submenu to.
    """
    # Log level options
    log_levels = [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ]

    # Create submenu
    log_menu = cmds.menuItem(label="Log Level", subMenu=True, parent=parent_menu, tearOff=False)

    # Create radio button group
    cmds.radioMenuItemCollection(parent=log_menu)

    # Get current log level
    current_level = get_log_level()

    # Add menu items for each log level
    for label, level in log_levels:
        is_current = current_level == level
        cmds.menuItem(
            label=label,
            radioButton=is_current,
            command=lambda *args, lvl=level, lbl=label: _set_log_level_with_feedback(lvl, lbl),
            parent=log_menu,
        )

    logger.debug(f"Log level submenu added with current level: {logging.getLevelName(current_level)}")


def _set_log_level_with_feedback(level: int, level_name: str):
    """
    Set log level and provide user feedback.

    Args:
        level (int): Logging level to set
        level_name (str): Human-readable name of the log level
    """
    set_log_level(level)
    logger.info(f"Log level changed to {level_name}")
    cmds.inViewMessage(amg=f"Log level changed to <hl>{level_name}</hl>", pos="topCenter", fade=True, fst=1000, ft=0.5)


__all__ = ["add_menu", "remove_menu", "reload_menu"]
