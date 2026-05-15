"""Text-based toggle button widget."""

from __future__ import annotations

from ..qt_compat import QColor, QFontMetrics, QPalette, QPushButton
from .color_utils import adjust_lightness


class TextToggleButton(QPushButton):
    """Text toggle button with DPI-aware sizing and palette-based colors.

    Displays bold text and highlights the background when checked.
    Uses font metrics for sizing instead of hardcoded pixel values.

    Examples:
        button = TextToggleButton("MIR", parent=self)
        button.toggled.connect(on_toggle)

        # Custom highlight color
        button = TextToggleButton("FRZ", highlight_color=QColor("#5285a6"), parent=self)
    """

    _STYLESHEET_TEMPLATE = """
        QPushButton {{
            background-color: {bg_color};
            font-weight: bold;
            border: none;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {pressed_color};
        }}
    """

    def __init__(
        self,
        text: str,
        size_ratio: float = 2.0,
        font_ratio: float = 0.75,
        highlight_color: QColor | None = None,
        parent=None,
    ):
        """Initialize the text toggle button.

        Args:
            text: The button text.
            size_ratio: Size multiplier relative to line height for width/height.
            font_ratio: Font size multiplier relative to line height.
            highlight_color: Background color when checked. If None, uses palette highlight.
            parent: Parent widget.
        """
        super().__init__(text, parent=parent)

        self._size_ratio = size_ratio
        self._font_ratio = font_ratio

        # Calculate DPI-aware sizes from font metrics
        metrics = QFontMetrics(self.font())
        line_height = metrics.lineSpacing()
        button_size = int(line_height * size_ratio)

        self.setFixedSize(button_size, button_size)

        # Set scaled font size
        font = self.font()
        font_size = max(1, int(line_height * font_ratio))
        font.setPixelSize(font_size)
        self.setFont(font)

        # Determine colors from palette
        palette = self.palette()
        self._bg_off = palette.color(self.backgroundRole())

        if highlight_color is not None:
            self._bg_on = QColor(highlight_color)
        else:
            highlight_role = QPalette.Highlight if hasattr(QPalette, "Highlight") else QPalette.ColorRole.Highlight
            self._bg_on = palette.color(highlight_role)

        self.setCheckable(True)
        self.setChecked(False)

        self._apply_stylesheet(self._bg_off)

        self.toggled.connect(self._update_style)

    def _apply_stylesheet(self, bg_color: QColor):
        """Apply stylesheet with hover/pressed states derived from base color.

        Args:
            bg_color: The base background color.
        """
        hover_color = adjust_lightness(bg_color, 1.2)
        pressed_color = adjust_lightness(bg_color, 0.5)

        self.setStyleSheet(
            self._STYLESHEET_TEMPLATE.format(
                bg_color=bg_color.name(),
                hover_color=hover_color.name(),
                pressed_color=pressed_color.name(),
            )
        )

    def _update_style(self, checked: bool):
        """Update the style based on the checked state.

        Args:
            checked: The checked state.
        """
        self._apply_stylesheet(self._bg_on if checked else self._bg_off)


class SwitchToggleButton(QPushButton):
    """Checkable push button that highlights with a custom color when checked.

    Unlike ``TextToggleButton`` (square, palette-driven, abbreviated text),
    this button uses normal QPushButton sizing and is intended for full-text
    toggles such as mode switches. When unchecked the default style is used;
    when checked the configured highlight color is applied via stylesheet.

    Examples:
        button = SwitchToggleButton("Connect", parent=self)
        button.setChecked(True)

        # Custom highlight color
        button = SwitchToggleButton("Soft Select", highlight_color="#a65252", parent=self)
    """

    # Geometry-affecting properties (border, padding) are kept identical across
    # both states so that toggling does not shift the layout. Only the colors
    # change via the :checked pseudo-state.
    _STYLESHEET = """
        QPushButton {{
            border: none;
            background-color: #5d5d5d;
            color: #e0e0e0;
            padding: 5px 10px;
        }}
        QPushButton:hover {{
            background-color: #6a6a6a;
        }}
        QPushButton:checked {{
            background-color: {highlight};
            color: #ffffff;
        }}
        QPushButton:checked:hover {{
            background-color: {highlight_hover};
        }}
    """

    def __init__(
        self,
        text: str,
        highlight_color: str | QColor = "#5285A6",
        parent=None,
    ):
        """Initialize the switch toggle button.

        Args:
            text: The button text.
            highlight_color: Background color (hex string or QColor) when checked.
            parent: Parent widget.
        """
        super().__init__(text, parent=parent)

        self._highlight_color = QColor(highlight_color) if not isinstance(highlight_color, QColor) else highlight_color
        highlight_hover = adjust_lightness(self._highlight_color, 1.15)

        self.setCheckable(True)
        self.setChecked(False)
        self.setStyleSheet(
            self._STYLESHEET.format(
                highlight=self._highlight_color.name(),
                highlight_hover=highlight_hover.name(),
            )
        )


__all__ = ["SwitchToggleButton", "TextToggleButton"]
