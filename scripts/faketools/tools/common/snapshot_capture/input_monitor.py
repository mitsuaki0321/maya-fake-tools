"""Input monitoring for recording overlay.

Monitors mouse clicks and keyboard input using Qt event filter.
Cross-platform compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from ....lib_ui.qt_compat import QEvent, QObject, Qt


@dataclass
class ClickEvent:
    """Represents a mouse click event."""

    click_type: str  # "left", "right", "double"
    x: int  # Screen x coordinate
    y: int  # Screen y coordinate
    timestamp: float  # Time of click


class InputMonitor(QObject):
    """Monitor mouse and keyboard events for recording overlay.

    Uses Qt event filter for cross-platform compatibility.
    Mouse events are monitored on the target widget.
    Keyboard events are monitored globally via QApplication.
    """

    # How long click indicators remain visible (seconds)
    CLICK_DISPLAY_DURATION = 0.3

    def __init__(self, target_widget, parent=None):
        """Initialize input monitor.

        Args:
            target_widget: Qt widget to monitor for mouse events.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._target = target_widget
        self._app = None  # QApplication for global keyboard monitoring
        self._pressed_keys: set[str] = set()
        self._click_events: list[ClickEvent] = []
        self._is_monitoring = False

    def start(self):
        """Start monitoring input events."""
        from ....lib_ui.qt_compat import QApplication

        if not self._is_monitoring:
            # Install on target widget for mouse events
            self._target.installEventFilter(self)

            # Install on QApplication for global keyboard events
            self._app = QApplication.instance()
            if self._app:
                self._app.installEventFilter(self)

            self._is_monitoring = True

    def stop(self):
        """Stop monitoring and clear state."""
        if self._is_monitoring:
            self._target.removeEventFilter(self)

            # Remove from QApplication
            if self._app:
                self._app.removeEventFilter(self)
                self._app = None

            self._is_monitoring = False
        self._pressed_keys.clear()
        self._click_events.clear()

    def get_pressed_keys(self) -> list[str]:
        """Get list of currently pressed keys.

        Returns:
            List of key names (e.g., ["Ctrl", "S"]).
        """
        return list(self._pressed_keys)

    def get_recent_clicks(self) -> list[ClickEvent]:
        """Get recent click events that should still be displayed.

        Automatically removes expired click events.

        Returns:
            List of recent ClickEvent objects.
        """
        current_time = time.time()
        # Remove expired clicks
        self._click_events = [click for click in self._click_events if current_time - click.timestamp < self.CLICK_DISPLAY_DURATION]
        return self._click_events.copy()

    def _is_within_target(self, global_pos) -> bool:
        """Check if global position is within target widget bounds.

        Args:
            global_pos: Global position (QPoint).

        Returns:
            True if position is within target widget.
        """
        if not self._target:
            return False

        # Get target widget's global geometry
        target_pos = self._target.mapToGlobal(self._target.rect().topLeft())
        target_rect_global = self._target.rect()
        target_rect_global.moveTo(target_pos)

        return target_rect_global.contains(global_pos)

    def eventFilter(self, obj, event):
        """Filter and process input events.

        Args:
            obj: Object that received the event.
            event: The Qt event.

        Returns:
            False to allow event propagation.
        """
        event_type = event.type()

        # Keyboard events (processed globally from QApplication)
        if event_type == QEvent.KeyPress:
            key_name = self._get_key_name(event)
            if key_name and key_name not in self._pressed_keys:
                self._pressed_keys.add(key_name)

        elif event_type == QEvent.KeyRelease:
            key_name = self._get_key_name(event)
            if key_name in self._pressed_keys:
                self._pressed_keys.discard(key_name)

        # Mouse events (check if click is within target widget bounds)
        elif event_type == QEvent.MouseButtonPress:
            if self._is_within_target(event.globalPos()):
                self._handle_mouse_press(event)

        elif event_type == QEvent.MouseButtonDblClick:
            if self._is_within_target(event.globalPos()):
                self._handle_double_click(event)

        # Always allow event propagation
        return False

    def _handle_mouse_press(self, event):
        """Handle mouse button press event."""
        button = event.button()
        global_pos = event.globalPos()

        if button == Qt.LeftButton:
            click_type = "left"
        elif button == Qt.RightButton:
            click_type = "right"
        elif button == Qt.MiddleButton:
            click_type = "middle"
        else:
            return

        self._click_events.append(
            ClickEvent(
                click_type=click_type,
                x=global_pos.x(),
                y=global_pos.y(),
                timestamp=time.time(),
            )
        )

    def _handle_double_click(self, event):
        """Handle mouse double click event."""
        global_pos = event.globalPos()

        # Remove the previous single click for this position (if any)
        # and add a double click instead
        self._click_events = [click for click in self._click_events if not (click.x == global_pos.x() and click.y == global_pos.y())]

        self._click_events.append(
            ClickEvent(
                click_type="double",
                x=global_pos.x(),
                y=global_pos.y(),
                timestamp=time.time(),
            )
        )

    def _get_key_name(self, event) -> str | None:
        """Convert key event to display name.

        Args:
            event: Qt key event.

        Returns:
            Key name string or None if not displayable.
        """
        key = event.key()

        # Modifier keys
        modifier_map = {
            Qt.Key_Shift: "Shift",
            Qt.Key_Control: "Ctrl",
            Qt.Key_Alt: "Alt",
            Qt.Key_Meta: "Cmd",  # Command on macOS, Win on Windows
        }
        if key in modifier_map:
            return modifier_map[key]

        # Special keys
        special_map = {
            Qt.Key_Space: "Space",
            Qt.Key_Return: "Enter",
            Qt.Key_Enter: "Enter",
            Qt.Key_Escape: "Esc",
            Qt.Key_Tab: "Tab",
            Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Del",
            Qt.Key_Insert: "Ins",
            Qt.Key_Home: "Home",
            Qt.Key_End: "End",
            Qt.Key_PageUp: "PgUp",
            Qt.Key_PageDown: "PgDn",
            Qt.Key_Up: "↑",
            Qt.Key_Down: "↓",
            Qt.Key_Left: "←",
            Qt.Key_Right: "→",
        }
        if key in special_map:
            return special_map[key]

        # Function keys
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f"F{key - Qt.Key_F1 + 1}"

        # Regular keys
        text = event.text()
        if text and text.isprintable():
            return text.upper()

        return None
