"""
Attribute Lister for listing and managing attributes in Maya.

This tool allows you to list, filter, and manage attributes on Maya nodes,
including options to show/hide default attributes, locked attributes,
"""

TOOL_CONFIG = {
    "name": "Attribute Lister",
    "version": "1.0.0",
    "description": "List and manage attributes on Maya nodes",
    "menu_label": "Attribute Lister",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
