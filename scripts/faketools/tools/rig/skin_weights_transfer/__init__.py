"""Skin Weights Transfer

Transfer skin weights between influences on selected components.
Supports moving weights from multiple source influences to multiple target influences
with configurable distribution methods (even, proportional, distance-based).
"""

TOOL_CONFIG = {
    "name": "Skin Weights Transfer",
    "version": "1.1.0",
    "description": "Transfer skin weights between influences on selected components",
    "menu_label": "Skin Weights Transfer",
    "menu_order": 125,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
