"""BlendShape Transfer

Transfer blend shapes from a source base mesh to a fitted mesh
using delta-based transfer.
"""

TOOL_CONFIG = {
    "name": "BlendShape Transfer",
    "version": "1.0.0",
    "description": "Transfer blend shapes between meshes with identical topology",
    "menu_label": "BlendShape Transfer",
    "menu_order": 31,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "model",
}

__all__ = ["TOOL_CONFIG"]
