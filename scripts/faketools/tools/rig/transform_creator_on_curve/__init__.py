"""
Create transform tools for on selected curves.

This tool allows you to create transform nodes (groups) aligned to selected curves,
with options for parenting, naming, and orientation.
"""

TOOL_CONFIG = {
    "name": "Transform Creator on Curve",
    "version": "1.0.0",
    "description": "Create transform nodes aligned to selected curves",
    "menu_label": "Transform Creator on Curve",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
