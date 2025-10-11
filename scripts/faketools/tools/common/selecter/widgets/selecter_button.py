"""Selecter button widget."""

from .....lib_ui.qt_compat import QColor, QPushButton
from .....lib_ui.ui_utils import get_line_height


class SelecterButton(QPushButton):
    """Select button widget with dynamic sizing."""

    def __init__(self, text: str, color: str = "#333", parent=None):
        """Constructor.

        Args:
            text (str): The button text.
            color (str): The button color.
            parent (QWidget): Parent widget.
        """
        super().__init__(text, parent=parent)

        # Calculate button size based on font metrics
        line_height = get_line_height(self)
        button_size = int(line_height * 2.0)  # ~32px at standard DPI
        font_size = int(line_height * 0.75)  # ~12px at standard DPI

        self.setFixedSize(button_size, button_size)

        color = QColor(color)
        hover_color = self._get_lightness_color(color, 1.2)
        pressed_color = self._get_lightness_color(color, 0.8)
        self.setStyleSheet(
            f"""
            QPushButton {{
                font-weight: bold;
                font-size: {font_size}px;
                border: 1px solid #333;
                background-color: {color.name()};
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {pressed_color};
                }}
                """
        )

    def _get_lightness_color(self, color: QColor, factor: float) -> str:
        """Adjust the brightness of a color for hover and pressed states.

        Args:
            color (QColor): The color to adjust.
            factor (float): The brightness factor.

        Returns:
            str: The adjusted color in hex format.
        """
        h, s, v, a = color.getHsv()
        v = max(0, min(v * factor, 255))
        adjusted_color = QColor.fromHsv(h, s, v, a)
        return adjusted_color.name()


__all__ = ["SelecterButton"]
