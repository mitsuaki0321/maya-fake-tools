"""Texture Relocator tool for Maya.

Relocate texture file paths in the scene by copying files to a new directory
or replacing paths with existing files in a target directory.
"""

TOOL_CONFIG = {
    "name": "Texture Relocator",
    "version": "1.0.0",
    "description": "Relocate texture file paths in the scene",
    "menu_label": "Texture Relocator",
    "menu_order": 40,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
