"""Animation Import/Export.

Export and import time-based keyframe animation data as JSON and pickle files.
Supports namespace separation and flexible import matching.
"""

TOOL_CONFIG = {
    "name": "Animation Import/Export",
    "version": "1.0.0",
    "description": "Export and import time-based keyframe animation",
    "menu_label": "Animation I/E",
    "menu_order": 50,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "anim",
}

__all__ = ["TOOL_CONFIG"]
