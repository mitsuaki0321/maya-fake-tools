"""
Skin Weights Import/Export Tool for Maya.

This tool allows users to import and export skin weights for skinned geometries in Autodesk Maya.
It supports JSON and Pickle formats for data storage.
"""

TOOL_CONFIG = {
    "name": "Skin Weights Import/Export",
    "version": "1.0.0",
    "description": "Import and export skin weights for skinned geometries.",
    "menu_label": "Skin Weights I/E",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
