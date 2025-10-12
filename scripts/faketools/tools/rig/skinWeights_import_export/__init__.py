"""Skin Weights Import/Export

Import and export skin weights to external files.
Supports JSON and Pickle formats for persistent weight storage.
"""

TOOL_CONFIG = {
    "name": "Skin Weights Import/Export",
    "version": "1.0.0",
    "description": "Import and export skin weights for skinned geometries.",
    "menu_label": "Skin Weights I/E",
    "menu_order": 130,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
