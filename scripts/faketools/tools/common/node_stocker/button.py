"""Node stock button widget with PieMenu support."""

from ....lib_ui import PieMenuButton
from ....lib_ui.qt_compat import QPushButton, Signal


class NodeStockPushButton(PieMenuButton, QPushButton):
    """
    QPushButton-based node stock button with PieMenu support.

    This is the new recommended implementation that replaces the QGraphicsItem-based button.

    Features:
    - Left click: Select nodes
    - Middle click: PieMenu (2-way) - Register/Unregister
    - Right click: PieMenu (4-way) - SetKeyframe and future commands
    - Visual feedback for hover and registered states
    """

    # Signals
    hovered = Signal(object)
    unhovered = Signal()

    def __init__(self, key: str, label: str = "", parent=None):
        """
        Initialize the node stock button.

        Args:
            key (str): The stock key for this button
            label (str): The label text (typically a number)
            parent (QWidget): Parent widget
        """
        super().__init__(label, parent)
        self._key = key
        self._is_stoked = False

        # Setup style
        self._setup_style()

        # PieMenu callbacks will be set by MainWindow
        # Middle click: Register/Unregister (2-way)
        # Right click: Commands (4-way)

        # Enable hover events
        self.setMouseTracking(True)

    @property
    def key(self) -> str:
        """Get the stock key.

        Returns:
            str: The stock key
        """
        return self._key

    def _setup_style(self):
        """Setup button style with monochrome gradient design."""
        self.setStyleSheet(
            """
            QPushButton {
                background-color: #434343;
                border: 2px solid #565656;
                border-radius: 4px;
                color: #D6D6D6;
                font-weight: bold;
                font-size: 1.2em;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #565656;
                border: 2px solid #A5A5A5;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #565656;
                border: 2px solid #747474;
            }
            QPushButton:focus {
                background-color: #565656;
                border: 2px solid #A5A5A5;
                color: #FFFFFF;
            }
        """
        )

    def apply_stoked_color(self):
        """Apply stoked (registered) color to indicate nodes are registered."""
        self._is_stoked = True
        self._update_style()

    def reset_stoked_color(self):
        """Reset to default color when no nodes are registered."""
        self._is_stoked = False
        self._update_style()

    def _update_style(self):
        """Update button style based on current state."""
        if self._is_stoked:
            self.setStyleSheet(
                """
                QPushButton {
                    background-color: #A5A5A5;
                    border: 2px solid #D6D6D6;
                    border-radius: 4px;
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 1.2em;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: #C0C0C0;
                    border: 2px solid #E8E8E8;
                    color: #FFFFFF;
                }
                QPushButton:pressed {
                    background-color: #A5A5A5;
                    border: 2px solid #A5A5A5;
                }
                QPushButton:focus {
                    background-color: #C0C0C0;
                    border: 2px solid #E8E8E8;
                    color: #FFFFFF;
                }
            """
            )
        else:
            self._setup_style()

    def enterEvent(self, event):
        """Emit hovered signal when mouse enters."""
        self.hovered.emit(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Emit unhovered signal when mouse leaves."""
        self.unhovered.emit()
        super().leaveEvent(event)
