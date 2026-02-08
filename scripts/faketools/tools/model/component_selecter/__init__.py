"""Component Selecter

Select and filter mesh/curve/surface components.
Includes unique selection, area selection (left/center/right), and CV parameter selection.
"""

TOOL_CONFIG = {
    "name": "Component Selecter Tool",
    "version": "1.0.0",
    "description": "Tool to select and manage components in Maya",
    "menu_label": "Component Selecter",
    "menu_order": 60,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
