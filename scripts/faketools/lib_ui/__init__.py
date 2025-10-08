"""
UI utilities for FakeTools.

This module provides convenient imports for common UI components:
- BaseMainWindow: Standard QMainWindow base class for tools
- ToolOptionSettings: Per-tool settings stored in Maya optionVar
- ToolDataManager: Per-tool data directory management
- Maya UI decorators: error_handler, undo_chunk, disable_undo
- Qt compatibility layer: Unified Qt imports for PySide2/6
- Resolution-independent UI utilities: get_spacing, get_margins
"""

from .base_window import BaseMainWindow, get_margins, get_spacing
from .maya_ui import (
    confirm_dialog,
    delete_workspace_control,
    disable_undo,
    error_handler,
    get_maya_window,
    show_error_dialog,
    show_info_dialog,
    show_warning_dialog,
    undo_chunk,
)
from .optionvar import ToolOptionSettings
from .qt_compat import QT_BINDING, QT_VERSION, QT_VERSION_MAJOR, get_open_file_name, get_save_file_name, is_pyside2, is_pyside6
from .tool_data import ToolDataManager
from .ui_utils import get_default_button_size, get_line_height, get_relative_size, get_text_width, scale_by_dpi

__all__ = [
    # Base window class
    "BaseMainWindow",
    # Settings and data management
    "ToolOptionSettings",
    "ToolDataManager",
    # Maya UI decorators
    "error_handler",
    "undo_chunk",
    "disable_undo",
    "get_maya_window",
    "delete_workspace_control",
    # Maya dialog helpers
    "show_error_dialog",
    "show_warning_dialog",
    "show_info_dialog",
    "confirm_dialog",
    # Qt compatibility
    "get_open_file_name",
    "get_save_file_name",
    "is_pyside2",
    "is_pyside6",
    "QT_VERSION",
    "QT_VERSION_MAJOR",
    "QT_BINDING",
    # Resolution-independent UI utilities
    "get_spacing",
    "get_margins",
    "get_relative_size",
    "get_default_button_size",
    "get_text_width",
    "get_line_height",
    "scale_by_dpi",
]
