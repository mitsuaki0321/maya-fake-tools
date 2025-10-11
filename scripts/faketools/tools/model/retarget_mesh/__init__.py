"""
Retarget Mesh Tool for same topology meshes.

This module provides configuration for the Retarget Mesh Tool in Maya.
"""

TOOL_CONFIG = {
    "name": "Retarget Mesh Tool",
    "version": "1.0.0",
    "description": "Tool to retarget meshes with the same topology",
    "menu_label": "Retarget Mesh",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
