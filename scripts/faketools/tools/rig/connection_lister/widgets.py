"""Connection Lister widgets."""

from logging import getLogger

from ....lib_ui.qt_compat import QHBoxLayout, QLabel, Qt, QWidget, Signal
from ....lib_ui.widgets import SwitchToggleButton

logger = getLogger(__name__)


class OperationSwitchWidget(QWidget):
    """Switch operation stack widget."""

    button_changed = Signal(int)

    def __init__(self, parent=None):
        """Initialize the widget."""
        super().__init__(parent=parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.connect_button = SwitchToggleButton("Connect")
        self.connect_button.setChecked(True)
        layout.addWidget(self.connect_button)

        self.command_button = SwitchToggleButton("Command")
        self.command_button.setChecked(False)
        layout.addWidget(self.command_button)

        self.setLayout(layout)

        # Signal & Slot
        self.connect_button.clicked.connect(self._toggle_checked)
        self.command_button.clicked.connect(self._toggle_checked)

    def _toggle_checked(self) -> None:
        """Toggle the checked state of the buttons."""
        sender = self.sender()
        if sender == self.connect_button:
            self.blockSignals(True)

            if self.connect_button.isChecked():
                self.command_button.setChecked(False)
            else:
                self.connect_button.setChecked(True)

            self.blockSignals(False)
        elif sender == self.command_button:
            self.blockSignals(True)

            if self.command_button.isChecked():
                self.connect_button.setChecked(False)
            else:
                self.command_button.setChecked(True)

            self.blockSignals(False)

        self.button_changed.emit(int(self.command_button.isChecked()))


class NodeCountLabel(QLabel):
    """Label to display the number of nodes."""

    def __init__(self, parent=None):
        """Initialize the label."""
        super().__init__(parent=parent)
        self.setText("0 / 0")
        self.setAlignment(Qt.AlignCenter)

    def set_count(self, current: int, total: int) -> None:
        """Set the current and total count.

        Args:
            current (int): The current count.
            total (int): The total count.
        """
        self.setText(f"{current} / {total}")


__all__ = ["NodeCountLabel", "OperationSwitchWidget"]
