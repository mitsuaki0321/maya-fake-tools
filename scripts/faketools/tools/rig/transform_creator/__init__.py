"""
Create transform tools for selected objects.

This tool allows you to create transform nodes (groups) aligned to selected objects,
with options for parenting, naming, and orientation.
"""

TOOL_CONFIG = {
    "name": "Transform Creator",
    "version": "1.0.0",
    "description": "Create transform nodes aligned to selected objects",
    "menu_label": "Transform Creator",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
