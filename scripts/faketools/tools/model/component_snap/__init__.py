"""Component Snap

Snap source mesh vertices to target mesh positions with soft selection support.
"""

TOOL_CONFIG = {
    "name": "Component Snap",
    "version": "1.0.0",
    "description": "Snap components from source to target mesh",
    "menu_label": "Component Snap",
    "menu_order": 55,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
