"""Single Command Menus.

Provides the FakeTools single commands as both a standard submenu and a
keyboard-triggered popup menu (Ctrl+Shift+Z).
"""

from __future__ import annotations

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
    _add_menu_items(popup, popup_only=True)

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


# --- Menu building (shared) ---------------------------------------------------


def _add_menu_items(parent_menu: str, popup_only: bool = False) -> None:
    """Add single command menu items to the given parent menu.

    Adds Scene, All, and Pair commands in order with dividers between groups.
    Used by both the main submenu and the popup menu.

    Args:
        parent_menu (str): Parent menu to add items to.
        popup_only (bool): If True, only show commands with is_visible() == True.
    """
    modules = [
        single_commands.scene_commands,
        single_commands.all_commands,
        single_commands.pair_commands,
    ]

    added_any = False
    for i, module in enumerate(modules):
        cmd_names = getattr(module, "__all__", [])
        group_added = False
        for cmd_name in cmd_names:
            cmd_cls = getattr(module, cmd_name)
            if popup_only and not cmd_cls.is_visible():
                continue
            if added_any and not group_added:
                cmds.menuItem(divider=True, parent=parent_menu)
            label = cmd_cls.get_name()
            cmd = f"import faketools.single_commands_menu; faketools.single_commands_menu.execute_single_command('{cmd_name}')"
            cmds.menuItem(label=label, command=cmd, parent=parent_menu)
            group_added = True
            added_any = True


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


def _parse_hotkey_string(hotkey_str: str) -> tuple[str, bool, bool, bool] | None:
    """Parse a hotkey string like 'Ctrl+Shift+Z' into components.

    Args:
        hotkey_str (str): Hotkey string (e.g. 'Ctrl+Shift+Z', 'Alt+F', 'Ctrl+Alt+Shift+Q').

    Returns:
        Tuple of (key, ctrl, shift, alt) or None if the string is empty or invalid.
    """
    if not hotkey_str or not hotkey_str.strip():
        return None

    parts = [p.strip() for p in hotkey_str.split("+")]
    if not parts:
        return None

    ctrl = False
    shift = False
    alt = False
    key = None

    for part in parts:
        lower = part.lower()
        if lower == "ctrl":
            ctrl = True
        elif lower == "shift":
            shift = True
        elif lower == "alt":
            alt = True
        else:
            key = part

    if not key:
        return None

    return key, ctrl, shift, alt


def register_runtime_command() -> None:
    """Register Maya runtime commands and hotkey for the popup menu.

    The hotkey is read from the shared config (hotkeys.single_commands_popup).
    If the configured key is already assigned to another command, registration is
    skipped and a warning is shown. Set the value to empty string to disable.
    """
    import maya.mel as mel

    from .lib_ui.shared_config import get_shared_config

    for name in (RUNTIME_COMMAND_NAME, _RUNTIME_RELEASE_NAME):
        if cmds.runTimeCommand(name, exists=True):
            cmds.runTimeCommand(name, edit=True, delete=True)

    cmds.runTimeCommand(
        RUNTIME_COMMAND_NAME,
        annotation="Show FakeTools Single Commands popup menu",
        category="Custom Scripts.FakeTools",
        commandLanguage="python",
        command=f"import {__name__}; {__name__}.show_popup_menu()",
    )
    cmds.runTimeCommand(
        _RUNTIME_RELEASE_NAME,
        annotation="Close FakeTools Single Commands popup menu",
        category="Custom Scripts.FakeTools",
        commandLanguage="python",
        command=f"import {__name__}; {__name__}.close_popup_menu()",
    )

    # Read hotkey from shared config
    config = get_shared_config()
    hotkey_str = config.get("hotkeys", {}).get("single_commands_popup", "")
    parsed = _parse_hotkey_string(hotkey_str)
    if parsed is None:
        logger.debug("Single Commands popup hotkey is disabled (empty or invalid config).")
        return

    key, ctrl, shift, alt = parsed

    # Check for conflicts
    press_nc = RUNTIME_COMMAND_NAME + "NameCommand"
    release_nc = _RUNTIME_RELEASE_NAME + "NameCommand"

    existing = cmds.hotkey(key, query=True, ctrlModifier=ctrl, shiftModifier=shift, altModifier=alt, name=True)
    if existing and existing != press_nc:
        cmds.warning(
            f"FakeTools: {hotkey_str} is already assigned to '{existing}'. "
            "Single Commands popup hotkey was not registered. "
            "You can change the hotkey in the shared config or assign manually via Hotkey Editor."
        )
        return

    # Ensure the current hotkey set is writable (Maya_Default is read-only)
    current_set = cmds.hotkeySet(query=True, current=True)
    if current_set == "Maya_Default":
        all_sets = cmds.hotkeySet(query=True, hotkeySetArray=True) or []
        custom_sets = [s for s in all_sets if s != "Maya_Default"]
        if custom_sets:
            target_set = custom_sets[0]
            cmds.hotkeySet(target_set, edit=True, current=True)
        else:
            target_set = "Maya_Default_Duplicate"
            cmds.hotkeySet(target_set, current=True, source="Maya_Default")
        logger.info(f"Switched hotkey set to '{target_set}' (Maya_Default is read-only).")

    mel.eval(f'nameCommand -ann "FakeTools Single Commands" -command {RUNTIME_COMMAND_NAME} -sourceType mel {press_nc}')
    mel.eval(f'nameCommand -ann "FakeTools Single Commands Release" -command {_RUNTIME_RELEASE_NAME} -sourceType mel {release_nc}')

    mel_flags = f'-k "{key}"'
    if ctrl:
        mel_flags += " -ctl"
    if shift:
        mel_flags += " -sht"
    if alt:
        mel_flags += " -alt"
    mel.eval(f'hotkey {mel_flags} -n "{press_nc}" -rn "{release_nc}"')

    logger.debug(f"Registered Single Commands popup hotkey: {hotkey_str}")


# --- Module exports -----------------------------------------------------------

__all__ = [
    "show_menu",
    "show_popup_menu",
    "close_popup_menu",
    "execute_single_command",
    "register_runtime_command",
]
