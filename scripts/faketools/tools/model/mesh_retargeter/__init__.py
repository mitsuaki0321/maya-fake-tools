"""Mesh Retargeter

Transfer vertex positions between meshes with identical topology.
Useful for shape retargeting and mesh pose transfers.
"""

TOOL_CONFIG = {
    "name": "Mesh Retargeter",
    "version": "1.0.0",
    "description": "Tool to retarget meshes with the same topology",
    "menu_label": "Mesh Retargeter",
    "menu_order": 30,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
