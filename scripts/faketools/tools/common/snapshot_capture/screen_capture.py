"""Screen-based viewport capture for real-time recording.

Uses PIL ImageGrab for cross-platform screen capture.
"""

from __future__ import annotations

from PIL import Image, ImageGrab


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
