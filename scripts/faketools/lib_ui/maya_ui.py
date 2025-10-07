"""
Maya UI utilities and decorators.

Provides decorators and utilities for Maya UI development:
- Error handling
- Undo chunk management
- Maya window integration
"""

from __future__ import annotations

from collections.abc import Callable
import functools
import traceback
from typing import TYPE_CHECKING

import maya.cmds as cmds

if TYPE_CHECKING:
    from .qt_compat import QWidget


def error_handler(func: Callable) -> Callable:
    """
    Decorator to handle errors in UI callbacks.

    Catches exceptions and displays them in Maya's error dialog.
    Use this on UI slot methods to prevent silent failures.

    Args:
        func (Callable): Function to wrap

    Example:
        @error_handler
        def on_button_clicked(self):
            # Your code here
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}\n\n{traceback.format_exc()}"
            cmds.confirmDialog(title="Error", message=error_msg, button=["OK"], defaultButton="OK", icon="critical")
            raise

    return wrapper


def undo_chunk(name: str = None) -> Callable:
    """
    Decorator to wrap function in Maya undo chunk.

    Creates a single undo operation for all commands in the function.

    Args:
        name (str | None): Optional name for the undo chunk (defaults to function name)

    Returns:
        Callable: Decorated function

    Example:
        @undo_chunk("Create Transforms")
        def create_multiple_transforms(self):
            # All operations here will be in one undo
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            chunk_name = name or func.__name__
            cmds.undoInfo(openChunk=True, chunkName=chunk_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                cmds.undoInfo(closeChunk=True)

        return wrapper

    return decorator


def disable_undo(func: Callable) -> Callable:
    """
    Decorator to temporarily disable undo for a function.

    Useful for query operations or temporary UI updates that shouldn't
    be part of the undo stack.

    Args:
        func (Callable): Function to wrap

    Returns:
        Callable: Decorated function

    Example:
        @disable_undo
        def refresh_ui(self):
            # Query operations here won't affect undo
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Store current undo state
        undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            return func(*args, **kwargs)
        finally:
            # Restore undo state
            cmds.undoInfo(stateWithoutFlush=undo_state)

    return wrapper


def get_maya_window() -> QWidget | None:
    """
    Get the Maya main window as a Qt widget.

    Returns:
        QWidget | None: Maya main window widget, or None if not available
    """
    try:
        from maya import OpenMayaUI as omui
        from shiboken2 import wrapInstance
    except ImportError:
        try:
            from maya import OpenMayaUI as omui
            from shiboken6 import wrapInstance
        except ImportError:
            return None

    from .qt_compat import QWidget

    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    if maya_main_window_ptr is not None:
        return wrapInstance(int(maya_main_window_ptr), QWidget)
    return None


def delete_workspace_control(control_name: str) -> None:
    """
    Delete a workspace control if it exists.

    Args:
        control_name (str): Name of the workspace control to delete
    """
    if cmds.workspaceControl(control_name, query=True, exists=True):
        cmds.deleteUI(control_name)


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
    "error_handler",
    "undo_chunk",
    "disable_undo",
    "get_maya_window",
    "delete_workspace_control",
    "show_error_dialog",
    "show_warning_dialog",
    "show_info_dialog",
    "confirm_dialog",
]
