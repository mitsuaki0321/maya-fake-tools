"""Connection Lister

Connect and copy attributes between source and target objects.
Supports both manual attribute selection and batch operations with single commands.
"""

TOOL_CONFIG = {
    "name": "Connection Lister",
    "version": "1.0.0",
    "description": "Connect and copy transform attributes between objects",
    "menu_label": "Connection Lister",
    "menu_order": 80,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
