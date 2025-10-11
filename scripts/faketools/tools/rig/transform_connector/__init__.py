"""
Transform Connector tool for connecting transformations between objects.

This tool allows you to copy, connect, or zero out transform attributes
(translate, rotate, scale, jointOrient, visibility) between Maya transform nodes.
"""

TOOL_CONFIG = {
    "name": "Transform Connector",
    "version": "1.0.0",
    "description": "Connect and copy transform attributes between objects",
    "menu_label": "Transform Connector",
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
