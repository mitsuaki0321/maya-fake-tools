"""Bounding Box Creator

Create bounding box geometry around selected objects.
Generates polygon cubes matching the dimensions of object bounds.
"""

TOOL_CONFIG = {
    "name": "Bounded Box Creator",
    "version": "1.0.0",
    "description": "Create bounding boxes around selected objects in Maya",
    "menu_label": "Bounding Box Creator",
    "menu_order": 10,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
