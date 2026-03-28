"""Mesh Mirror

Mirror or flip mesh vertex positions across the X axis.
Supports single-mesh symmetry and dual-mesh correspondence.
"""

TOOL_CONFIG = {
    "name": "Mesh Mirror",
    "version": "1.0.0",
    "description": "Mirror or flip mesh vertex positions across the X axis",
    "menu_label": "Mesh Mirror",
    "menu_order": 65,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
