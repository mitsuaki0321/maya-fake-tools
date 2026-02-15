"""Mesh Fitter

Non-rigid ICP mesh fitting tool for Maya.
Fits a source mesh to a target mesh using trimesh's nricp_amberg algorithm.
"""

TOOL_CONFIG = {
    "name": "Mesh Fitter",
    "version": "1.0.0",
    "description": "Non-rigid ICP mesh fitting with landmark support",
    "menu_label": "Mesh Fitter",
    "menu_order": 10,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
