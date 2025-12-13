"""Robust Weight Transfer - SIGGRAPH Asia 2023 algorithm implementation.

Based on the paper "Robust Skin Weights Transfer via Weight Inpainting"
by Pranav Joshi, Ayush Bijalwan, and Parag Chaudhuri.
"""

TOOL_CONFIG = {
    "name": "Robust Weight Transfer",
    "version": "1.0.0",
    "description": "Transfer skin weights using robust matching algorithm",
    "menu_label": "Robust Weight Transfer",
    "menu_order": 140,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "rig",
}

__all__ = ["TOOL_CONFIG"]
