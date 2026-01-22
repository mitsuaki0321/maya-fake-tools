"""Screen-based viewport capture for real-time recording.

Uses mss for high-performance capture with PIL ImageGrab as fallback.
"""

from __future__ import annotations

import logging

from PIL import Image, ImageGrab

# Check mss availability (similar to aggdraw pattern)
try:
    import mss

    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScreenCapturer:
    """High-performance screen capture with mss/PIL fallback.

    Uses mss when available (2-3x faster than PIL ImageGrab),
    with automatic fallback to PIL ImageGrab when mss is not installed.

    The mss sct object is reused across captures for optimal performance.
    """

    def __init__(self):
        """Initialize the capturer with mss if available."""
        self._sct = None
        if MSS_AVAILABLE:
            self._sct = mss.mss()
            logger.debug("Using mss for screen capture")
        else:
            logger.debug("mss not available, using PIL ImageGrab fallback")

    def capture(self, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Capture screen region.

        Args:
            bbox: Bounding box (left, top, right, bottom) in screen coordinates.

        Returns:
            PIL Image of the captured region.
        """
        if self._sct is not None:
            # mss uses monitor dict format: {"left", "top", "width", "height"}
            monitor = {
                "left": bbox[0],
                "top": bbox[1],
                "width": bbox[2] - bbox[0],
                "height": bbox[3] - bbox[1],
            }
            sct_img = self._sct.grab(monitor)
            # Convert to PIL Image (mss returns BGRA, need to convert to RGB)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        else:
            return ImageGrab.grab(bbox=bbox)

    def close(self):
        """Close the capturer and release resources."""
        if self._sct is not None:
            self._sct.close()
            self._sct = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def capture_screen_region(bbox: tuple[int, int, int, int]) -> Image.Image:
    """Capture screen region using PIL ImageGrab.

    Args:
        bbox: Bounding box (left, top, right, bottom) in screen coordinates.

    Returns:
        PIL Image of the captured region.

    Note:
        - Windows/macOS: Works natively
        - Linux: Requires X11 (Wayland not supported)
        - macOS: May require screen capture permission
    """
    return ImageGrab.grab(bbox=bbox)


def get_widget_screen_bbox(widget) -> tuple[int, int, int, int]:
    """Get widget's bounding box in screen coordinates.

    Args:
        widget: Qt widget to get screen coordinates for.

    Returns:
        Bounding box (left, top, right, bottom) in screen coordinates.
    """
    global_pos = widget.mapToGlobal(widget.rect().topLeft())
    return (
        global_pos.x(),
        global_pos.y(),
        global_pos.x() + widget.width(),
        global_pos.y() + widget.height(),
    )


def get_cursor_screen_position() -> tuple[int, int]:
    """Get current cursor position in screen coordinates.

    Uses Qt QCursor for cross-platform compatibility.

    Returns:
        Cursor position (x, y) in screen coordinates.
    """
    from ....lib_ui.qt_compat import QCursor

    pos = QCursor.pos()
    return (pos.x(), pos.y())
