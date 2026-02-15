"""Transform Retargeter

Transfer transform hierarchies between objects with matching topology.
Matches transforms by name and applies positions, rotations, and scales.
"""

TOOL_CONFIG = {
    "name": "Transform Retargeter",
    "version": "1.0.0",
    "description": "Tool to retarget transforms with the same topology",
    "menu_label": "Transform Retargeter",
    "menu_order": 40,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
