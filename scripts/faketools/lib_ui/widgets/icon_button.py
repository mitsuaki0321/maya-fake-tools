"""Unified icon button widgets for FakeTools.

Provides IconButton and IconToolButton classes with two styling modes:
- TRANSPARENT: Transparent background with rgba overlay on hover/pressed
- PALETTE: Palette-based dynamic colors with auto-sizing
"""

from __future__ import annotations

from enum import Enum, auto

from .. import icons
from ..qt_compat import (
    QApplication,
    QColor,
    QIcon,
    QPixmap,
    QPushButton,
    QToolButton,
)


class IconButtonStyle(Enum):
    """Style modes for icon buttons."""

    TRANSPARENT = auto()
    """Transparent background with rgba overlay on hover/pressed states."""

    PALETTE = auto()
    """Palette-based dynamic colors with auto-sizing based on icon."""


class IconButtonMixin:
    """Mixin providing shared functionality for icon buttons.

    This mixin handles styling, icon loading, and auto-sizing for icon buttons.
    Must be used as a mixin with QPushButton or QToolButton base classes.

    Attributes:
        _style_mode: Current style mode (TRANSPARENT or PALETTE).
        _auto_size: Whether to auto-size based on icon dimensions.
    """

    _TRANSPARENT_STYLESHEET_TEMPLATE = """
        {widget_type} {{
            background-color: transparent;
            border: none;
        }}
        {widget_type}:hover {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
        {widget_type}:pressed {{
            background-color: rgba(255, 255, 255, 0.2);
        }}
    """

    _PALETTE_STYLESHEET_TEMPLATE = """
        {widget_type} {{
            border: none;
            background-color: {background_color};
            border-radius: 1px;
            text-align: center;
        }}
        {widget_type}:hover {{
            background-color: {hover_color};
        }}
        {widget_type}:pressed {{
            background-color: {pressed_color};
        }}
    """

    def _init_icon_button(
        self,
        icon_name: str | None = None,
        style_mode: IconButtonStyle = IconButtonStyle.PALETTE,
        auto_size: bool = True,
    ):
        """Initialize icon button functionality.

        Args:
            icon_name: Name of icon to load from icons module (without extension).
                       If None, no icon is set automatically.
            style_mode: Style mode to use (TRANSPARENT or PALETTE).
            auto_size: Whether to auto-size based on icon dimensions.
                       Only applicable when style_mode is PALETTE and icon_name is provided.
        """
        self._style_mode = style_mode
        self._auto_size = auto_size
        self._icon_pixmap: QPixmap | None = None

        # Load icon if provided
        if icon_name:
            icon_path = icons.get_path(icon_name)
            self._icon_pixmap = QPixmap(icon_path)
            icon = QIcon(icon_path)
            self.setIcon(icon)

        # Apply styling
        self._apply_style()

        # Auto-size if enabled
        if self._auto_size and self._icon_pixmap and style_mode == IconButtonStyle.PALETTE:
            self._apply_auto_size()

    def _get_widget_type_name(self) -> str:
        """Get the Qt widget type name for stylesheet.

        Returns:
            Widget type name (QPushButton or QToolButton).
        """
        if isinstance(self, QToolButton):
            return "QToolButton"
        return "QPushButton"

    def _apply_style(self):
        """Apply stylesheet based on current style mode."""
        widget_type = self._get_widget_type_name()

        if self._style_mode == IconButtonStyle.TRANSPARENT:
            stylesheet = self._TRANSPARENT_STYLESHEET_TEMPLATE.format(widget_type=widget_type)
        else:
            # PALETTE mode
            palette = self.palette()
            background_color = palette.color(self.backgroundRole())
            hover_color = self._get_lightness_color(background_color, 1.2)
            pressed_color = self._get_lightness_color(background_color, 0.5)

            stylesheet = self._PALETTE_STYLESHEET_TEMPLATE.format(
                widget_type=widget_type,
                background_color=background_color.name(),
                hover_color=hover_color.name(),
                pressed_color=pressed_color.name(),
            )

        self.setStyleSheet(stylesheet)

    def _apply_auto_size(self):
        """Apply auto-sizing based on icon dimensions and button margin."""
        if not self._icon_pixmap:
            return

        style = QApplication.style()
        pm_button_margin = style.PM_ButtonMargin if hasattr(style, "PM_ButtonMargin") else style.PixelMetric.PM_ButtonMargin
        padding = style.pixelMetric(pm_button_margin)

        size = self._icon_pixmap.width() + padding
        self.setMinimumSize(size, size)

    def _get_lightness_color(self, color: QColor, factor: float) -> QColor:
        """Adjust the brightness of a color for hover and pressed states.

        Args:
            color: The color to adjust.
            factor: The brightness factor (>1 for lighter, <1 for darker).

        Returns:
            The adjusted color.
        """
        h, s, v, a = color.getHsv()
        v = max(0, min(int(v * factor), 255))
        return QColor.fromHsv(h, s, v, a)


class IconButton(IconButtonMixin, QPushButton):
    """Icon button based on QPushButton.

    Supports two styling modes:
    - TRANSPARENT: Transparent background with white overlay on hover/pressed
    - PALETTE: Palette-based colors with auto-sizing based on icon

    Examples:
        # Palette-based icon button (default)
        button = IconButton(icon_name="my_icon")

        # Transparent icon button
        button = IconButton(style_mode=IconButtonStyle.TRANSPARENT)
        button.setIcon(QIcon("path/to/icon.png"))
        button.setFixedSize(24, 24)
    """

    def __init__(
        self,
        icon_name: str | None = None,
        style_mode: IconButtonStyle = IconButtonStyle.PALETTE,
        auto_size: bool = True,
        parent=None,
    ):
        """Initialize the icon button.

        Args:
            icon_name: Name of icon to load from icons module (without extension).
                       If None, no icon is set automatically.
            style_mode: Style mode to use (TRANSPARENT or PALETTE).
            auto_size: Whether to auto-size based on icon dimensions.
                       Only applicable when style_mode is PALETTE and icon_name is provided.
            parent: Parent widget.
        """
        super().__init__(parent=parent)
        self._init_icon_button(icon_name, style_mode, auto_size)


class IconToolButton(IconButtonMixin, QToolButton):
    """Icon tool button based on QToolButton.

    Supports popup menus via setPopupMode() and setMenu().
    Supports two styling modes like IconButton.

    Examples:
        # Palette-based icon tool button with menu
        button = IconToolButton(icon_name="my_icon")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(my_menu)

        # Transparent icon tool button
        button = IconToolButton(style_mode=IconButtonStyle.TRANSPARENT)
        button.setIcon(QIcon("path/to/icon.png"))
    """

    def __init__(
        self,
        icon_name: str | None = None,
        style_mode: IconButtonStyle = IconButtonStyle.PALETTE,
        auto_size: bool = True,
        parent=None,
    ):
        """Initialize the icon tool button.

        Args:
            icon_name: Name of icon to load from icons module (without extension).
                       If None, no icon is set automatically.
            style_mode: Style mode to use (TRANSPARENT or PALETTE).
            auto_size: Whether to auto-size based on icon dimensions.
                       Only applicable when style_mode is PALETTE and icon_name is provided.
            parent: Parent widget.
        """
        super().__init__(parent=parent)
        self._init_icon_button(icon_name, style_mode, auto_size)


# Backward compatibility alias
ToolIconButton = IconButton

__all__ = ["IconButton", "IconButtonStyle", "IconToolButton", "ToolIconButton"]
