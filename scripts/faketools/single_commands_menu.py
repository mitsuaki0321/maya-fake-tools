"""Single Command Menus.

Provides the FakeTools single commands as both a standard submenu and a
keyboard-triggered popup menu (Ctrl+Shift+Z).
"""

import contextlib
from logging import getLogger

import maya.cmds as cmds

from . import single_commands

logger = getLogger(__name__)

# --- Constants ----------------------------------------------------------------

MENU_NAME = "Single Commands"
POPUP_MENU_NAME = "FakeToolsSingleCommandsPopupMenu"
RUNTIME_COMMAND_NAME = "FakeToolsSingleCommandsPopup"
_RUNTIME_RELEASE_NAME = RUNTIME_COMMAND_NAME + "Release"

# --- Internal state -----------------------------------------------------------

_popup_menu_instance = None

# --- Menu building (shared) ---------------------------------------------------


def _add_menu_items(parent_menu: str) -> None:
    """Add single command menu items to the given parent menu.

    Adds Scene, All, and Pair commands in order with dividers between groups.
    Used by both the main submenu and the popup menu.

    Args:
        parent_menu (str): Parent menu to add items to.
    """
    modules = [
        single_commands.scene_commands,
        single_commands.all_commands,
        single_commands.pair_commands,
    ]

    for i, module in enumerate(modules):
        cmd_names = getattr(module, "__all__", [])
        for cmd_name in cmd_names:
            cmd_cls = getattr(module, cmd_name)
            label = cmd_cls.get_name()
            cmd = f"import faketools.single_commands_menu; faketools.single_commands_menu.execute_single_command('{cmd_name}')"
            cmds.menuItem(label=label, command=cmd, parent=parent_menu)

        if cmd_names and i < len(modules) - 1:
            cmds.menuItem(divider=True, parent=parent_menu)


# --- Public API: Menu bar submenu ---------------------------------------------


def show_menu(parent_menu: str) -> None:
    """Create a Single Commands submenu under the given parent menu.

    Args:
        parent_menu (str): Parent menu to add this submenu to.

    Raises:
        ValueError: If parent menu does not exist.
    """
    if not cmds.menu(parent_menu, exists=True):
        raise ValueError(f"Parent menu does not exist: {parent_menu}")

    menu = cmds.menuItem(label=MENU_NAME, subMenu=True, parent=parent_menu, tearOff=True)
    _add_menu_items(menu)

    logger.debug(f"Added single command menu: {menu}")


# --- Public API: Popup menu ---------------------------------------------------


def show_popup_menu() -> None:
    """Show the single commands as a popup menu at the cursor position.

    Builds the menu using cmds.popupMenu/menuItem (same as the main menu) so that
    undo grouping is handled natively by Maya. The Maya popupMenu is converted to
    a Qt QMenu via MQtUtil for programmatic display at the cursor position.
    """
    global _popup_menu_instance

    import maya.OpenMayaUI as omui

    from .lib_ui.qt_compat import QCursor, QMenu, shiboken

    close_popup_menu()

    # Build popup menu using Maya commands
    popup = cmds.popupMenu(POPUP_MENU_NAME, parent="MayaWindow")
    _add_menu_items(popup)

    # Convert to Qt QMenu and show at cursor position
    ptr = omui.MQtUtil.findControl(popup)
    if ptr is None:
        logger.warning("Failed to find popup menu Qt widget.")
        return

    qt_menu = shiboken.wrapInstance(int(ptr), QMenu)
    _popup_menu_instance = qt_menu
    qt_menu.popup(QCursor.pos())


def close_popup_menu() -> None:
    """Close the popup menu if open."""
    global _popup_menu_instance

    if _popup_menu_instance is not None:
        with contextlib.suppress(RuntimeError):
            _popup_menu_instance.close()
        _popup_menu_instance = None

    if cmds.popupMenu(POPUP_MENU_NAME, exists=True):
        cmds.deleteUI(POPUP_MENU_NAME)


# --- Public API: Command execution --------------------------------------------


def execute_single_command(command_name: str) -> None:
    """Execute a single command by name.

    Args:
        command_name (str): The command class name to execute.
    """
    cmd_cls = None
    for module in (single_commands.scene_commands, single_commands.all_commands, single_commands.pair_commands):
        if hasattr(module, command_name):
            cmd_cls = getattr(module, command_name)
            break

    if cmd_cls is None:
        cmds.error(f"Command not found: {command_name}")
        return

    if issubclass(cmd_cls, single_commands.SceneCommand):
        cmd_cls()
        return

    sel_nodes = cmds.ls(sl=True)
    if not sel_nodes:
        cmds.error("No nodes selected")
        return

    if issubclass(cmd_cls, single_commands.AllCommand):
        cmd_cls(sel_nodes)
    elif issubclass(cmd_cls, single_commands.PairCommand):
        if len(sel_nodes) < 2:
            cmds.error("Please select at least 2 nodes")
            return
        cmd_cls([sel_nodes[0]], sel_nodes[1:])


# --- Public API: Hotkey registration ------------------------------------------


def register_runtime_command() -> None:
    """Register Maya runtime commands and default hotkey for the popup menu.

    Creates press/release runtime commands and binds them to Ctrl+Shift+Z.
    Press shows the menu, release closes it (marking-menu style).
    Users can reassign via Maya's Hotkey Editor (Custom Scripts.FakeTools category).
    """
    import maya.mel as mel

    for name in (RUNTIME_COMMAND_NAME, _RUNTIME_RELEASE_NAME):
        if cmds.runTimeCommand(name, exists=True):
            cmds.runTimeCommand(name, edit=True, delete=True)

    cmds.runTimeCommand(
        RUNTIME_COMMAND_NAME,
        annotation="Show FakeTools Single Commands popup menu",
        category="Custom Scripts.FakeTools",
        commandLanguage="python",
        command="import faketools.single_commands_menu; faketools.single_commands_menu.show_popup_menu()",
    )
    cmds.runTimeCommand(
        _RUNTIME_RELEASE_NAME,
        annotation="Close FakeTools Single Commands popup menu",
        category="Custom Scripts.FakeTools",
        commandLanguage="python",
        command="import faketools.single_commands_menu; faketools.single_commands_menu.close_popup_menu()",
    )

    # Bind default hotkey: Ctrl+Shift+Z (press to show, release to close)
    press_nc = RUNTIME_COMMAND_NAME + "NameCommand"
    release_nc = _RUNTIME_RELEASE_NAME + "NameCommand"

    mel.eval(f'nameCommand -ann "FakeTools Single Commands" -command {RUNTIME_COMMAND_NAME} -sourceType mel {press_nc}')
    mel.eval(f'nameCommand -ann "FakeTools Single Commands Release" -command {_RUNTIME_RELEASE_NAME} -sourceType mel {release_nc}')
    mel.eval(f'hotkey -k "Z" -ctl -sht -n "{press_nc}" -rn "{release_nc}"')

    logger.debug(f"Registered runtime command: {RUNTIME_COMMAND_NAME} (Ctrl+Shift+Z)")


# --- Module exports -----------------------------------------------------------

__all__ = [
    "show_menu",
    "show_popup_menu",
    "close_popup_menu",
    "execute_single_command",
    "register_runtime_command",
]
