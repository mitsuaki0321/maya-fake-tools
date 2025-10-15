"""
UI utility functions for resolution-independent interface design.

This module provides functions to calculate sizes, spacing, and other UI metrics
dynamically based on the widget's style and font metrics, ensuring consistent
appearance across different screen resolutions and DPI settings.
"""

from .qt_compat import QApplication, QFontMetrics


def get_relative_size(widget, width_ratio=1.0, height_ratio=1.0, base_size=None):
    """
    Calculate size relative to a base size or screen size.

    Args:
        widget (QWidget): The widget to calculate size for
        width_ratio (float): Width multiplier (default: 1.0)
        height_ratio (float): Height multiplier (default: 1.0)
        base_size: Base (width, height) to multiply ratios by.
            If None, uses a default base size derived from font metrics.

    Returns:
        tuple[int, int]: (width, height) in pixels

    Example:
        >>> # Get a window size 1.5x wider and 1.2x taller than base
        >>> width, height = get_relative_size(my_widget, 1.5, 1.2)
        >>> self.resize(width, height)
    """
    if base_size is None:
        # Use font metrics to determine a reasonable base size
        font = widget.font()
        metrics = QFontMetrics(font)
        # Base unit: approximately 40 characters wide, 25 lines tall
        char_width = metrics.averageCharWidth()
        line_height = metrics.lineSpacing()
        base_size = (char_width * 40, line_height * 25)

    width = int(base_size[0] * width_ratio)
    height = int(base_size[1] * height_ratio)

    return (width, height)


def get_default_button_size(widget):
    """
    Get default button size based on widget style and font metrics.

    Args:
        widget (QWidget): The widget to calculate button size for

    Returns:
        tuple[int, int]: (width, height) in pixels

    Example:
        >>> width, height = get_default_button_size(my_widget)
        >>> button.setMinimumSize(width, height)
    """
    style = QApplication.style()
    font = widget.font()
    metrics = QFontMetrics(font)

    # Calculate width based on typical button text (e.g., "Cancel")
    text_width = metrics.horizontalAdvance("Cancel") if hasattr(metrics, "horizontalAdvance") else metrics.width("Cancel")
    padding = style.pixelMetric(QApplication.style().PM_ButtonMargin if hasattr(style, "PM_ButtonMargin") else style.PixelMetric.PM_ButtonMargin)

    width = text_width + padding * 2 + 20  # Extra padding for comfort
    height = metrics.lineSpacing() + padding

    return (width, height)


def get_text_width(text, widget):
    """
    Calculate the width required to display text in the widget's font.

    Args:
        text (str): The text to measure
        widget (QWidget): The widget (for font information)

    Returns:
        int: Width in pixels

    Example:
        >>> width = get_text_width("My Label Text", my_label)
        >>> label.setMinimumWidth(width)
    """
    font = widget.font()
    metrics = QFontMetrics(font)

    if hasattr(metrics, "horizontalAdvance"):
        return metrics.horizontalAdvance(text)
    else:
        return metrics.width(text)


def get_line_height(widget):
    """
    Get the line height for the widget's font.

    Args:
        widget (QWidget): The widget (for font information)

    Returns:
        int: Line height in pixels

    Example:
        >>> height = get_line_height(my_widget)
        >>> widget.setMinimumHeight(height * 5)  # 5 lines tall
    """
    font = widget.font()
    metrics = QFontMetrics(font)
    return metrics.lineSpacing()


def scale_by_dpi(value, widget=None):
    """
    Scale a value based on DPI settings.

    Use this for icon sizes or other values that should scale with DPI.

    Args:
        value (int | float): The base value at standard DPI (96 DPI on Windows, 72 DPI on Mac)
        widget: Optional widget for context-specific DPI

    Returns:
        int: Scaled value

    Example:
        >>> icon_size = scale_by_dpi(16)  # 16px at standard DPI, auto-scales for high DPI
        >>> icon.setIconSize(QSize(icon_size, icon_size))
    """
    if widget is not None:
        logical_dpi = widget.logicalDpiX()
    else:
        screen = QApplication.primaryScreen() if hasattr(QApplication, "primaryScreen") else QApplication.desktop().screen()
        logical_dpi = screen.logicalDotsPerInchX()

    # Standard DPI reference (96 on Windows)
    standard_dpi = 96
    scale_factor = logical_dpi / standard_dpi

    return int(value * scale_factor)


__all__ = [
    "get_relative_size",
    "get_default_button_size",
    "get_text_width",
    "get_line_height",
    "scale_by_dpi",
]
