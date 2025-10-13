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
        """Setup button style with white border and transparent background."""
        self.setStyleSheet(
            """
            QPushButton {
                border: 2px solid white;
                background-color: transparent;
                color: lightgray;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(82, 133, 166, 100);
                border: 2px solid white;
            }
            QPushButton:pressed {
                background-color: rgba(82, 133, 166, 180);
                border: 2px solid darkgray;
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
                    border: 2px solid white;
                    background-color: rgba(128, 128, 128, 100);
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(82, 133, 166, 150);
                    border: 2px solid white;
                }
                QPushButton:pressed {
                    background-color: rgba(82, 133, 166, 200);
                    border: 2px solid darkgray;
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
