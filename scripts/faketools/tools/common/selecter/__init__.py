"""Selecter

Advanced selection utilities for Maya scenes.
Includes filtering, hierarchical selection, and batch renaming tools.
"""

TOOL_CONFIG = {
    "name": "Selecter",
    "version": "1.0.0",
    "description": "Selection and renaming utilities for Maya scenes.",
    "menu_label": "Selecter",
    "menu_order": 10,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "common",
}

__all__ = ["TOOL_CONFIG"]
