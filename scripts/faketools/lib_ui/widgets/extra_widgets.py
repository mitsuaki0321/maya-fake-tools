"""Extra widgets for the UI."""

from ..qt_compat import QFrame, QSizePolicy


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
