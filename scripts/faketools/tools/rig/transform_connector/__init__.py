"""Transform Connector

Copy, connect, or zero out transform attributes between objects.
Supports translate, rotate, scale, jointOrient, and visibility attributes.
"""

TOOL_CONFIG = {
    "name": "Transform Connector",
    "version": "1.0.0",
    "description": "Connect and copy transform attributes between objects",
    "menu_label": "Transform Connector",
    "menu_order": 10,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
