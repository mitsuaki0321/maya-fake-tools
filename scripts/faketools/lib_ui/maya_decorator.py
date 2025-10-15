"""This module contains decorators for Maya UI functions."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import functools
import traceback
from typing import TYPE_CHECKING, Optional

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


def undo_chunk(name: Optional[str] = None) -> Callable:
    """
    Decorator to wrap function in Maya undo chunk.

    Creates a single undo operation for all commands in the function.

    Args:
        name: Optional name for the undo chunk (defaults to function name)

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


def repeatable(label: Optional[str] = None) -> Callable:
    """
    Decorator to make a UI method repeatable with Maya's repeat last command.

    Registers the method with Maya's repeatLast so it can be repeated using
    the 'G' key or Edit -> Repeat menu. Supports methods with arguments.

    Args:
        label: Optional label for the repeat command.
               Defaults to the function name with title case.

    Returns:
        Callable: Decorated function

    Notes:
        - The decorated method must be part of a class that has a global _instance variable
        - The command will be repeated by calling the same method on the global instance
        - Arguments are captured and included in the repeat command

    Example:
        @repeatable("Create Sphere")
        def create_sphere(self):
            cmds.sphere()

        @repeatable("Create Curve U")
        def create_curve(self, axis: str):
            # axis will be captured in repeat command
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Execute the original function
            result = func(self, *args, **kwargs)

            # Build command string for repeatLast
            module_name = self.__class__.__module__
            func_name = func.__name__

            # Format arguments for the command
            args_str = ", ".join([repr(arg) for arg in args])
            kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
            all_args = ", ".join(filter(None, [args_str, kwargs_str]))

            # Use the module's global _instance to call the method
            if all_args:
                cmd = f"import {module_name} as ui_module; ui_module._instance.{func_name}({all_args})"
            else:
                cmd = f"import {module_name} as ui_module; ui_module._instance.{func_name}()"

            # Set label (use provided label or generate from function name)
            cmd_label = label or func_name.replace("_", " ").title()

            # Register with Maya's repeat last (use short flag names: ac, acl)
            # Use double quotes inside python() as per Maya convention
            # Suppress error as repeatLast always errors on first execution
            with contextlib.suppress(Exception):
                cmds.repeatLast(ac=f'python("{cmd}")', acl=cmd_label)

            return result

        return wrapper

    return decorator


__all__ = [
    "error_handler",
    "undo_chunk",
    "disable_undo",
    "repeatable",
]
