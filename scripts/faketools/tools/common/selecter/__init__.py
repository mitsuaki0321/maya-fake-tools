"""
Selecter tool for Maya.

This tool offers various selection and renaming functionalities for Maya scenes.
"""

# Tool configuration for registration
TOOL_CONFIG = {
    "name": "Selecter",
    "version": "1.0.0",
    "description": "Selection and renaming utilities for Maya scenes.",
    "menu_label": "Selecter",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "common",
}

__all__ = ["TOOL_CONFIG"]
