"""Recording controller for screen capture functionality."""

from __future__ import annotations

import logging

from ....lib_ui.qt_compat import QObject, QTimer, QWidget, Signal, shiboken
from .input_monitor import InputMonitor
from .input_overlay import draw_click_indicators, draw_cursor, draw_key_overlay
from .screen_capture import ScreenCapturer, get_cursor_screen_position, get_widget_screen_bbox

logger = logging.getLogger(__name__)

# Recording Constants
COUNTDOWN_INTERVAL_MS = 1000


class RecordingController(QObject):
    """Controls recording functionality with countdown and frame capture.

    This controller handles:
    - Countdown timer before recording starts
    - Frame capture at specified FPS
    - Input monitoring for cursor/keyboard overlays
    - Recording state management

    Signals:
        recording_started: Emitted when actual recording begins (after countdown).
        recording_stopped: Emitted with captured frames list when recording stops.
        countdown_tick: Emitted with remaining seconds during countdown.
        countdown_cancelled: Emitted when countdown is cancelled by user.
    """

    # Signals
    recording_started = Signal()
    recording_stopped = Signal(list)  # frames
    countdown_tick = Signal(int)  # remaining seconds
    countdown_cancelled = Signal()

    def __init__(self, parent: QObject | None = None):
        """Initialize the recording controller.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._is_recording: bool = False
        self._recorded_frames: list = []
        self._record_timer: QTimer | None = None
        self._countdown_timer: QTimer | None = None
        self._countdown_value: int = 0
        self._input_monitor: InputMonitor | None = None
        self._capture_bbox: tuple[int, int, int, int] | None = None
        self._screen_capturer: ScreenCapturer | None = None

        # Capture settings (set via start_recording)
        self._show_cursor: bool = True
        self._show_clicks: bool = True
        self._show_keys: bool = False
        self._fps: int = 24

    @property
    def is_recording(self) -> bool:
        """Whether recording is currently active."""
        return self._is_recording

    @property
    def is_counting_down(self) -> bool:
        """Whether countdown is currently active."""
        return self._countdown_timer is not None

    @property
    def recorded_frames(self) -> list:
        """Get the recorded frames (read-only copy)."""
        return list(self._recorded_frames)

    def start_recording(
        self,
        viewport_widget: QWidget,
        fps: int = 24,
        delay: int = 3,
        show_cursor: bool = True,
        show_clicks: bool = True,
        show_keys: bool = False,
    ):
        """Start recording with given settings.

        Args:
            viewport_widget: Qt widget to capture from.
            fps: Frames per second for recording.
            delay: Countdown delay in seconds (0 for immediate start).
            show_cursor: Whether to overlay cursor position.
            show_clicks: Whether to show click indicators.
            show_keys: Whether to show keyboard overlay.
        """
        if self._is_recording or self._countdown_timer is not None:
            logger.warning("Recording already in progress")
            return

        # Store settings
        self._fps = fps
        self._show_cursor = show_cursor
        self._show_clicks = show_clicks
        self._show_keys = show_keys

        # Get capture bounding box from viewport widget
        self._capture_bbox = get_widget_screen_bbox(viewport_widget)
        if not self._capture_bbox:
            logger.error("Failed to get viewport bounding box")
            return

        logger.debug(f"Capture bbox: {self._capture_bbox}")

        if delay > 0:
            # Start countdown
            self._countdown_value = delay
            self.countdown_tick.emit(self._countdown_value)

            # Create countdown timer
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
            self._countdown_timer.start(COUNTDOWN_INTERVAL_MS)

            logger.debug(f"Recording countdown started: {delay} seconds")
        else:
            # No delay, start recording immediately
            self._begin_recording(viewport_widget)

    def _on_countdown_tick(self):
        """Handle countdown tick."""
        self._countdown_value -= 1

        if self._countdown_value > 0:
            self.countdown_tick.emit(self._countdown_value)
        else:
            # Countdown finished
            if self._countdown_timer is not None:
                self._countdown_timer.stop()
                self._countdown_timer.deleteLater()
                self._countdown_timer = None

            # Find the viewport widget from parent hierarchy for input monitor
            viewport_widget = self._find_viewport_widget()
            self._begin_recording(viewport_widget)

    def _find_viewport_widget(self) -> QWidget | None:
        """Find viewport widget from parent hierarchy.

        Returns:
            Viewport widget if found, None otherwise.
        """
        # The parent should be SnapshotCaptureWindow which has panel_name
        # This is a workaround since we can't store the widget reference
        # (it might become invalid during countdown)
        parent = self.parent()
        if parent and hasattr(parent, "panel_name"):
            try:
                import maya.api.OpenMayaUI as omui

                view = omui.M3dView.getM3dViewFromModelPanel(parent.panel_name)
                if view:
                    return shiboken.wrapInstance(int(view.widget()), QWidget)
            except Exception as e:
                logger.warning(f"Failed to get viewport widget: {e}")
        return None

    def _begin_recording(self, viewport_widget: QWidget | None):
        """Begin actual recording.

        Args:
            viewport_widget: Qt widget for input monitor.
        """
        self._is_recording = True
        self._recorded_frames = []

        # Create screen capturer (uses mss if available for better performance)
        self._screen_capturer = ScreenCapturer()

        # Start input monitor for cursor/keyboard tracking
        if viewport_widget and (self._show_cursor or self._show_keys):
            self._input_monitor = InputMonitor(viewport_widget)
            self._input_monitor.start()

        # Get interval from FPS
        interval_ms = int(1000 / self._fps)

        # Create and start timer
        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._on_timer_tick)
        self._record_timer.start(interval_ms)

        logger.debug(f"Recording started at {self._fps} FPS (interval: {interval_ms}ms)")
        self.recording_started.emit()

    def _on_timer_tick(self):
        """Capture frame on timer tick."""
        if not self._is_recording:
            return

        if self._capture_bbox is None:
            logger.error("No capture bbox available")
            return

        try:
            # Capture screen region
            image = self._screen_capturer.capture(self._capture_bbox)

            # Draw cursor overlay
            if self._show_cursor:
                cursor_pos = get_cursor_screen_position()
                image = draw_cursor(image, cursor_pos, self._capture_bbox)

                # Draw click indicators
                if self._show_clicks and self._input_monitor:
                    clicks = self._input_monitor.get_recent_clicks()
                    if clicks:
                        image = draw_click_indicators(image, clicks, self._capture_bbox)

            # Draw keyboard overlay
            if self._show_keys and self._input_monitor:
                pressed_keys = self._input_monitor.get_pressed_keys()
                if pressed_keys:
                    image = draw_key_overlay(image, pressed_keys)

            self._recorded_frames.append(image)
            logger.debug(f"Captured frame ({len(self._recorded_frames)} total)")
        except Exception as e:
            logger.error(f"Failed to capture frame: {e}")

    def stop_recording(self) -> list:
        """Stop recording and return captured frames.

        Returns:
            List of captured PIL Image frames.
        """
        self._is_recording = False

        # Stop timer
        if self._record_timer is not None:
            self._record_timer.stop()
            self._record_timer.deleteLater()
            self._record_timer = None

        # Stop input monitor
        if self._input_monitor is not None:
            self._input_monitor.stop()
            self._input_monitor = None

        # Close screen capturer
        if self._screen_capturer is not None:
            self._screen_capturer.close()
            self._screen_capturer = None

        # Clear capture state
        self._capture_bbox = None

        # Get frames and emit signal
        frames = list(self._recorded_frames)
        original_count = len(frames)
        logger.info(f"Recording stopped - {original_count} frames captured")

        self.recording_stopped.emit(frames)
        self._recorded_frames = []

        return frames

    def cancel_countdown(self):
        """Cancel countdown if active."""
        if self._countdown_timer is not None:
            self._countdown_timer.stop()
            self._countdown_timer.deleteLater()
            self._countdown_timer = None
            self._countdown_value = 0
            self._capture_bbox = None

            logger.debug("Recording countdown cancelled")
            self.countdown_cancelled.emit()

    def cleanup(self):
        """Clean up all resources without emitting signals.

        Use this when the window is closing.
        """
        self._is_recording = False

        if self._record_timer is not None:
            self._record_timer.stop()
            self._record_timer.deleteLater()
            self._record_timer = None

        if self._countdown_timer is not None:
            self._countdown_timer.stop()
            self._countdown_timer.deleteLater()
            self._countdown_timer = None

        if self._input_monitor is not None:
            self._input_monitor.stop()
            self._input_monitor = None

        if self._screen_capturer is not None:
            self._screen_capturer.close()
            self._screen_capturer = None

        self._capture_bbox = None
        self._recorded_frames = []


__all__ = ["RecordingController"]
