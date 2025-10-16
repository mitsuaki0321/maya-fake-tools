"""Offset Curve to Surface tool.

Create NURBS surface by offsetting selected curves in specified direction.
"""

TOOL_CONFIG = {
    "name": "Offset Curve to Surface",
    "version": "1.0.0",
    "description": "Create NURBS surface by offsetting curve in specified direction",
    "menu_label": "Offset Curve to Surface",
    "menu_order": 50,
    "requires_selection": True,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
