"""Scene Optimizer

Optimize and clean up Maya scenes.
Remove unused nodes, optimize transforms, and perform batch cleanup operations.
"""

TOOL_CONFIG = {
    "name": "Scene Optimizer",
    "version": "1.0.0",
    "description": "Optimize Maya scenes with various cleanup operations",
    "menu_label": "Scene Optimizer",
    "menu_order": 30,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "common",
}

__all__ = ["TOOL_CONFIG"]
