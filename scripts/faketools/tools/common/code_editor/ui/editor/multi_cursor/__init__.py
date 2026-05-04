"""Multi-cursor editing feature.

The mixin in :mod:`.handler` is the public entry point. Internal helpers
(controller / input / painter) are loaded by the mixin and not re-exported.
"""

from .handler import MultiCursorMixin

__all__ = ["MultiCursorMixin"]
