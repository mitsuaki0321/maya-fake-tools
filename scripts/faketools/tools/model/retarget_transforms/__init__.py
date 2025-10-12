"""Retarget Transforms

Transfer transform hierarchies between objects with matching topology.
Matches transforms by name and applies positions, rotations, and scales.
"""

TOOL_CONFIG = {
    "name": "Retarget Transforms Tool",
    "version": "1.0.0",
    "description": "Tool to retarget transforms with the same topology",
    "menu_label": "Retarget Transforms",
    "menu_order": 30,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
