"""
UI utilities for FakeTools.

This module provides convenient imports for common UI components:
- BaseMainWindow: Standard QMainWindow base class for tools
- BaseFramelessWindow: Frameless window base class for compact tools
- ToolOptionSettings: Per-tool settings stored in Maya optionVar
- ToolSettingsManager: JSON-based tool settings with preset support
- ToolDataManager: Per-tool data directory management
- PieMenu: Directional pie menu widget (2, 4, or 8 segments)
- Maya UI decorators: error_handler, undo_chunk, disable_undo, repeatable
- Maya dialog helpers: show_error_dialog, show_warning_dialog, show_info_dialog, confirm_dialog
- Maya UI functions: get_channels, get_modifiers
- Maya Qt utilities: qt_widget_from_maya_control, maya_name_from_qt_widget, qt_widget_from_maya_window, get_maya_main_window
- Qt compatibility layer: Unified Qt imports for PySide2/6
- Resolution-independent UI utilities: get_spacing, get_margins
"""

from .base_window import BaseFramelessWindow, BaseMainWindow, get_margins, get_spacing
from .maya_decorator import disable_undo, error_handler, repeatable, undo_chunk
from .maya_dialog import confirm_dialog, show_error_dialog, show_info_dialog, show_warning_dialog
from .maya_qt import get_maya_main_window, maya_name_from_qt_widget, qt_widget_from_maya_control, qt_widget_from_maya_window
from .maya_ui import get_channels, get_modifiers
from .optionvar import ToolOptionSettings
from .pie_menu import PieMenu, PieMenuButton
from .qt_compat import QT_BINDING, QT_VERSION, QT_VERSION_MAJOR, get_open_file_name, get_save_file_name, is_pyside2, is_pyside6
from .tool_data import ToolDataManager
from .tool_settings import ToolSettingsManager
from .ui_utils import get_default_button_size, get_line_height, get_relative_size, get_text_width, scale_by_dpi

__all__ = [
    # Base window classes
    "BaseMainWindow",
    "BaseFramelessWindow",
    # Settings and data management
    "ToolOptionSettings",
    "ToolSettingsManager",
    "ToolDataManager",
    # Widgets
    "PieMenu",
    "PieMenuButton",
    # Maya UI decorators
    "error_handler",
    "undo_chunk",
    "disable_undo",
    "repeatable",
    # Maya dialog helpers
    "show_error_dialog",
    "show_warning_dialog",
    "show_info_dialog",
    "confirm_dialog",
    # Maya UI functions
    "get_channels",
    "get_modifiers",
    # Maya Qt utilities
    "qt_widget_from_maya_control",
    "maya_name_from_qt_widget",
    "qt_widget_from_maya_window",
    "get_maya_main_window",
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
