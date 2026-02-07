"""Extra widgets for the UI."""

from ..qt_compat import (
    QApplication,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    Qt,
    QWidget,
    Signal,
)


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


class ModifierSpinBox(QDoubleSpinBox):
    """Double spin box widget with modifier keys."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent)
        self._shift_multiplier = 10.0
        self._ctrl_multiplier = 0.1

    def setShiftStepMultiplier(self, value: float):
        """Set the step value based on the shift key.

        Args:
            value (float): The multiplier shift value.
        """
        self._shift_multiplier = value

    def setCtrlStepMultiplier(self, value: float):
        """Set the step value based on the control key.

        Args:
            value (float): The multiplier control value.
        """
        self._ctrl_multiplier = value

    def stepBy(self, steps):
        """Step by value. (Overrides QDoubleSpinBox.stepBy)

        Notes:
            - Maya returns 1.0 as the singleStep value under normal conditions.
            - When the Ctrl key is pressed, it returns 10.0 as the singleStep value.
        """
        modifiers = QApplication.keyboardModifiers()

        multiplier = 1.0
        if modifiers & Qt.ControlModifier:
            multiplier = self._ctrl_multiplier * 0.1
        elif modifiers & Qt.ShiftModifier:
            multiplier = self._shift_multiplier

        self.setValue(self.value() + self.singleStep() * steps * multiplier)


class QLineEditWithButton(QWidget):
    """Line edit widget with a button on the right side."""

    button_clicked = Signal()

    def __init__(self, parent=None):
        """Initialize the line edit with button widget.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent=parent)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Create line edit
        self._line_edit = QLineEdit()
        layout.addWidget(self._line_edit)

        # Create button
        self._button = QPushButton()
        self._button.clicked.connect(self.button_clicked.emit)
        layout.addWidget(self._button)

        self.setLayout(layout)

    def set_button_text(self, text: str) -> None:
        """Set the button text.

        Args:
            text (str): The button text.
        """
        self._button.setText(text)

    def text(self) -> str:
        """Get the line edit text.

        Returns:
            str: The line edit text.
        """
        return self._line_edit.text()

    def setText(self, text: str) -> None:
        """Set the line edit text.

        Args:
            text (str): The line edit text.
        """
        self._line_edit.setText(text)

    def setPlaceholderText(self, text: str) -> None:
        """Set the line edit placeholder text.

        Args:
            text (str): The placeholder text.
        """
        self._line_edit.setPlaceholderText(text)

    def setReadOnly(self, read_only: bool) -> None:
        """Set the line edit read-only state.

        Args:
            read_only (bool): Whether the line edit is read-only.
        """
        self._line_edit.setReadOnly(read_only)
