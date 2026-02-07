"""Color utility functions for widgets."""

from __future__ import annotations

from ..qt_compat import QColor


def adjust_lightness(color: QColor, factor: float) -> QColor:
    """Adjust the brightness of a color.

    Args:
        color: The color to adjust.
        factor: The brightness factor (>1 for lighter, <1 for darker).

    Returns:
        The adjusted color.
    """
    h, s, v, a = color.getHsv()
    v = max(0, min(int(v * factor), 255))
    return QColor.fromHsv(h, s, v, a)
