"""This module contains Maya-specific UI functions."""

import maya.cmds as cmds
import maya.mel as mel


def get_channels(long_name=True) -> list[str]:
    """Get attribute names from the channel box.

    Args:
        long_name (bool, optional): Whether to return long names. Defaults to True.

    Returns:
        list[str]: Attribute names.
    """
    g_channel_box = mel.eval("$temp=$gChannelBoxName")
    channels = cmds.channelBox(g_channel_box, q=True, sma=True)

    if not channels:
        return []

    if not long_name:
        return channels
    else:
        sel_nodes = cmds.ls(sl=True)
        return [cmds.attributeQuery(ch, n=sel_nodes[-1], ln=True) for ch in channels]


def get_modifiers() -> list[str]:
    """Get the current modifier keys.

    Returns:
        list[str]: Modifier keys.
    """
    mods = cmds.getModifiers()
    keys = []
    if (mods & 1) > 0:
        keys.append("Shift")
    if (mods & 4) > 0:
        keys.append("Ctrl")
    if (mods & 8) > 0:
        keys.append("Alt")
    if mods & 16:
        keys.append("Command/Windows")

    return keys


__all__ = ["get_channels", "get_modifiers"]
