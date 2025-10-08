"""This module contains Maya-specific dialog functions."""

import maya.cmds as cmds


def show_error_dialog(title: str, message: str) -> None:
    """
    Show an error dialog in Maya.

    Args:
        title (str): Dialog title
        message (str): Error message to display
    """
    cmds.confirmDialog(title=title, message=message, button=["OK"], defaultButton="OK", icon="critical")


def show_warning_dialog(title: str, message: str) -> None:
    """
    Show a warning dialog in Maya.

    Args:
        title (str): Dialog title
        message (str): Warning message to display
    """
    cmds.confirmDialog(title=title, message=message, button=["OK"], defaultButton="OK", icon="warning")


def show_info_dialog(title: str, message: str) -> None:
    """
    Show an info dialog in Maya.

    Args:
        title (str): Dialog title
        message (str): Info message to display
    """
    cmds.confirmDialog(title=title, message=message, button=["OK"], defaultButton="OK", icon="information")


def confirm_dialog(title: str, message: str) -> bool:
    """
    Show a confirmation dialog in Maya.

    Args:
        title (str): Dialog title
        message (str): Confirmation message

    Returns:
        bool: True if user clicked Yes, False if No
    """
    result = cmds.confirmDialog(title=title, message=message, button=["Yes", "No"], defaultButton="Yes", cancelButton="No", dismissString="No")
    return result == "Yes"


__all__ = [
    "show_error_dialog",
    "show_warning_dialog",
    "show_info_dialog",
    "confirm_dialog",
]
