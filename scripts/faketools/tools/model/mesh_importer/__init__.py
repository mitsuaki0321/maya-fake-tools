"""Mesh Importer - Import glTF/GLB and PLY files into Maya."""

TOOL_CONFIG = {
    "name": "Mesh Importer",
    "version": "1.1.0",
    "description": "Import glTF/GLB files via Blender conversion and PLY files with vertex colors",
    "menu_label": "Mesh Importer",
    "menu_order": 80,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
