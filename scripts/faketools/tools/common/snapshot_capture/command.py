"""Snapshot Capture command layer.

Re-exports from submodules for backward compatibility.
"""

from .capture import capture_frame, capture_frame_range, set_display_mode
from .constants import (
    BACKGROUND_COLORS,
    DEFAULT_BACKGROUND,
    DEFAULT_HEIGHT,
    DEFAULT_RESOLUTION,
    DEFAULT_WIDTH,
    DISPLAY_MODE_LABELS,
    DISPLAY_MODES,
    MAX_RESOLUTION,
    MIN_RESOLUTION,
    RESOLUTION_PRESETS,
)
from .image import composite_with_background, save_gif, save_png

__all__ = [
    # constants
    "DISPLAY_MODES",
    "DISPLAY_MODE_LABELS",
    "RESOLUTION_PRESETS",
    "DEFAULT_RESOLUTION",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "MIN_RESOLUTION",
    "MAX_RESOLUTION",
    "BACKGROUND_COLORS",
    "DEFAULT_BACKGROUND",
    # capture
    "set_display_mode",
    "capture_frame",
    "capture_frame_range",
    # image
    "composite_with_background",
    "save_png",
    "save_gif",
]
