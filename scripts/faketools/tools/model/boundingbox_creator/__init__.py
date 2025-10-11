"""
Bounded Box Creator Tool

This module provides configuration for the Bounded Box Creator tool in Maya.
"""

TOOL_CONFIG = {
    "name": "Bounded Box Creator",
    "version": "2.0.0",
    "description": "Create bounding boxes around selected objects in Maya",
    "menu_label": "Bounding Box Creator",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
