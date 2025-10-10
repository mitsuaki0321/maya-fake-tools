"""Single Command Menus."""

from logging import getLogger

import maya.cmds as cmds

from . import single_commands

logger = getLogger(__name__)

MENU_NAME = "Single Commands"


def show_menu(parent_menu: str) -> None:
    """Show the single commands menu.

    Args:
        parent_menu (str): Parent menu to add this submenu to.

    Raises:
        ValueError: If parent menu does not exist.
    """
    if not cmds.menu(parent_menu, exists=True):
        raise ValueError(f"Parent menu does not exist: {parent_menu}")

    # Create submenu
    menu = cmds.menuItem(label=MENU_NAME, subMenu=True, parent=parent_menu, tearOff=True)

    # Scene commands
    scene_cmds = getattr(single_commands.scene_commands, "__all__", [])
    for cmd_name in scene_cmds:
        cmd = f"import faketools.single_commands_menu; faketools.single_commands_menu.execute_single_command('{cmd_name}')"
        cmds.menuItem(label=cmd_name, command=cmd, parent=menu)

    if scene_cmds:
        cmds.menuItem(divider=True, parent=menu)

    # All commands
    all_cmds = getattr(single_commands.all_commands, "__all__", [])
    for cmd_name in all_cmds:
        cmd = f"import faketools.single_commands_menu; faketools.single_commands_menu.execute_single_command('{cmd_name}')"
        cmds.menuItem(label=cmd_name, command=cmd, parent=menu)

    if all_cmds:
        cmds.menuItem(divider=True, parent=menu)

    # Pair commands
    pair_cmds = getattr(single_commands.pair_commands, "__all__", [])
    for cmd_name in pair_cmds:
        cmd = f"import faketools.single_commands_menu; faketools.single_commands_menu.execute_single_command('{cmd_name}')"
        cmds.menuItem(label=cmd_name, command=cmd, parent=menu)

    logger.debug(f"Added single command menu: {menu}")


def execute_single_command(command_name: str) -> None:
    """Execute a single command by name.

    Args:
        command_name (str): The command class name to execute.

    Raises:
        RuntimeError: If command is not found or execution fails.
    """
    # Search for command class in each module
    cmd_cls = None

    # Search in scene_commands
    if hasattr(single_commands.scene_commands, command_name):
        cmd_cls = getattr(single_commands.scene_commands, command_name)
    # Search in all_commands
    elif hasattr(single_commands.all_commands, command_name):
        cmd_cls = getattr(single_commands.all_commands, command_name)
    # Search in pair_commands
    elif hasattr(single_commands.pair_commands, command_name):
        cmd_cls = getattr(single_commands.pair_commands, command_name)
    else:
        cmds.error(f"Command not found: {command_name}")
        return

    # Execute command based on type
    if issubclass(cmd_cls, single_commands.SceneCommand):
        # Scene commands don't need selection
        cmd_cls()
    else:
        # Get selected nodes (type validation delegated to each command)
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No nodes selected")
            return

        if issubclass(cmd_cls, single_commands.AllCommand):
            # All commands process all selected nodes
            cmd_cls(sel_nodes)
        elif issubclass(cmd_cls, single_commands.PairCommand):
            # Pair commands need at least 2 nodes
            if len(sel_nodes) < 2:
                cmds.error("Please select at least 2 nodes")
                return
            # First node is source, rest are targets
            cmd_cls([sel_nodes[0]], sel_nodes[1:])


__all__ = ["show_menu", "execute_single_command"]
