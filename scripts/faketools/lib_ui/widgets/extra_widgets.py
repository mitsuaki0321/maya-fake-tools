"""Extra widgets for the UI."""

from .. import icons
from ..qt_compat import QApplication, QColor, QFrame, QIcon, QPixmap, QPushButton, QSizePolicy


class HorizontalSeparator(QFrame):
    """
    Horizontal separator line widget.

    Creates a horizontal line to visually separate UI sections.
    """

    def __init__(self, parent=None, height_ratio: float = 2.0):
        """
        Initialize the horizontal separator.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
            height_ratio (float): Height multiplier for the separator. Defaults to 2.0.
        """
        super().__init__(parent=parent)

        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setFixedHeight(int(self.sizeHint().height() * height_ratio))


class VerticalSeparator(QFrame):
    """
    Vertical separator line widget.

    Creates a vertical line to visually separate UI sections.
    """

    def __init__(self, parent=None, width_ratio: float = 2.0):
        """
        Initialize the vertical separator.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
            width_ratio (float): Width multiplier for the separator. Defaults to 2.0.
        """
        super().__init__(parent=parent)

        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.setFixedWidth(int(self.sizeHint().width() * width_ratio))


class ToolIconButton(QPushButton):
    """Tool icon button widget."""

    def __init__(self, icon_name, parent=None):
        super().__init__(parent=parent)

        icon_path = icons.get_path(icon_name)
        pixmap = QPixmap(icon_path)
        icon = QIcon(icon_path)
        self.setIcon(icon)

        palette = self.palette()
        background_color = palette.color(self.backgroundRole())
        style = QApplication.style()
        pm_button_margin = style.PM_ButtonMargin if hasattr(style, "PM_ButtonMargin") else style.PixelMetric.PM_ButtonMargin
        padding = style.pixelMetric(pm_button_margin)
        hover_color = self._get_lightness_color(background_color, 1.2)
        pressed_color = self._get_lightness_color(background_color, 0.5)

        self.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background-color: {background_color.name()};
                border-radius: 1px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {hover_color.name()};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color.name()};
            }}
        """)

        size = pixmap.width() + padding
        self.setMinimumSize(size, size)

    def _get_lightness_color(self, color, factor) -> QColor:
        """Adjust the brightness of a color for hover and pressed states.

        Args:
            color (QColor): The color to adjust.
            factor (float): The brightness factor.

        Returns:
            QColor: The adjusted color.
        """
        h, s, v, a = color.getHsv()
        v = max(0, min(v * factor, 255))
        return QColor.fromHsv(h, s, v, a)
