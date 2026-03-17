"""Node Lister

List and filter Maya scene nodes with three-stage filtering:
selectFilter -> nodeFilter -> matchFilter.
"""

TOOL_CONFIG = {
    "name": "Node Lister",
    "version": "1.0.0",
    "description": "List and filter Maya scene nodes",
    "menu_label": "Node Lister",
    "menu_order": 90,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
