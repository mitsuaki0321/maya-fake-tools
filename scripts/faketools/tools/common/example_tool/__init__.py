"""
Example Tool - Template for creating new tools.

This is a sample tool demonstrating the FakeTools structure.
"""

from .ui import MainWindow, show_ui

# Tool configuration for registration
TOOL_CONFIG = {
    "name": "Example Tool",
    "version": "1.0.0",
    "description": "Example tool template",
    "menu_label": "Example Tool",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "common",
}

__all__ = ["MainWindow", "show_ui", "TOOL_CONFIG"]
