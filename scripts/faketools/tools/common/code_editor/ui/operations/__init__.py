"""Editor-side controllers that wire user actions to back-end work.

These objects sit between the editor widgets and the ``command/``
layer: they translate menu / shortcut / toolbar events into
file-system or execution work, then route the results back to the
editor for display.

Public exports:

* :class:`FileOperationsController` -- new / open / save / save-all /
  rename / delete / execute-without-opening flows. Owns the
  multi-step recipes triggered by the toolbar, file-explorer signals,
  and the file shortcuts.
* :class:`ExecutionManager` -- dispatches "Run" requests to
  per-language :class:`NativeExecutionBridge` instances, manages the
  per-tab bridge cache, and surfaces inspection-snippet output in the
  terminal.
"""

from __future__ import annotations

from .execution_manager import ExecutionManager
from .files import FileOperationsController

__all__ = ["ExecutionManager", "FileOperationsController"]
