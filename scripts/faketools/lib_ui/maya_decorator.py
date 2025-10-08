"""This module contains decorators for Maya UI functions."""

from __future__ import annotations

from collections.abc import Callable
import functools
import traceback
from typing import TYPE_CHECKING

from maya.api.OpenMaya import MGlobal
import maya.cmds as cmds

if TYPE_CHECKING:
    pass


def error_handler(func: Callable) -> Callable:
    """
    Decorator to handle errors in UI callbacks.

    Catches exceptions and displays them in Maya's error dialog.
    Use this on UI slot methods to prevent silent failures.

    Args:
        func (Callable): Function to wrap

    Notes:
        - functools.wraps is not used because it prevents error output from appearing in Maya's command port.

    Example:
        @error_handler
        def on_button_clicked(self):
            # Your code here
            pass
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            MGlobal.displayError(str(e))

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


__all__ = [
    "error_handler",
    "undo_chunk",
    "disable_undo",
]
