"""
Dynamic menu system for FakeTools.

Automatically creates Maya menu based on registered tools.
"""

import logging

import maya.cmds as cmds

from .core.registry import get_registry

logger = logging.getLogger(__name__)

# Menu name constant
MENU_NAME = "FakeToolsMenu"
MENU_LABEL = "FakeTools"

# Category display names
CATEGORY_LABELS = {
    "rig": "Rigging",
    "model": "Modeling",
    "anim": "Animation",
    "common": "Common",
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
    for category in ["rig", "model", "anim", "common"]:
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
                command=lambda *args, cmd=tool["command"]: exec(cmd),
                annotation=tool.get("description", ""),
            )

        # Close category submenu
        cmds.setParent("..", menu=True)

    # Add separator and utility items
    cmds.menuItem(divider=True, parent=menu)

    # Reload menu item
    cmds.menuItem(label="Reload Menu", command=lambda *args: reload_menu(), parent=menu)

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


__all__ = ["add_menu", "remove_menu", "reload_menu"]
