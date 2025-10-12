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


class ProgressBar:
    """Context manager for Maya's main progress bar.

    Args:
        maxVal (int): Maximum value for the progress bar.
        **kwargs: Additional keyword arguments.
            message/msg (str): Progress bar status message. Defaults to "Calculation ...".

    Example:
        >>> with ProgressBar(100, msg="Processing") as progress:
        ...     for i in range(100):
        ...         if progress.breakPoint():
        ...             break
    """

    def __init__(self, maxVal, **kwargs):
        """Initialize progress bar.

        Args:
            maxVal (int): Maximum value for the progress bar.
            **kwargs: Additional keyword arguments (message/msg).
        """
        msg = kwargs.get("message", kwargs.get("msg", "Calculation ..."))
        self.pBar = mel.eval("$tmp = $gMainProgressBar")
        cmds.progressBar(self.pBar, e=True, beginProgress=True, isInterruptable=True, status=msg, maxValue=maxVal)

    def breakPoint(self):
        """Check if user cancelled and increment progress.

        Returns:
            bool: True if user cancelled, False otherwise.
        """
        if cmds.progressBar(self.pBar, q=True, isCancelled=True):
            return True
        else:
            cmds.progressBar(self.pBar, e=True, step=1)
            return False

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Exit context manager and end progress."""
        cmds.progressBar(self.pBar, e=True, endProgress=True)


# Keep old name for backwards compatibility
progress_bar = ProgressBar


__all__ = ["get_channels", "get_modifiers", "ProgressBar", "progress_bar"]
