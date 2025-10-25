"""Constants and utility functions for selecter widgets."""

import maya.cmds as cmds

from .....lib_ui import maya_ui

# Color constants for different widget categories
FILTER_COLOR = "#6D7B8D"
HIERARCHY_COLOR = "#4C516D"
SUBSTITUTION_COLOR = "#6E7F80"
RENAME_COLOR = "#536878"
REORDER_COLOR = "#627282"  # Reorder normal sort color (brighter)
REORDER_REVERSED_COLOR = "#426272"  # Reorder reversed name sort color (darker)

# Substitution patterns for left/right mirror
LEFT_TO_RIGHT = ["(.*)(L)", r"\g<1>R"]
RIGHT_TO_LEFT = ["(.*)(R)", r"\g<1>L"]


def selecter_handler(func):
    """Selection handler for selecter tools.

    This decorator handles the selection behavior based on modifier keys:
    - No modifier: Replace selection with result
    - Shift: Add result to selection
    - Ctrl: Remove result from selection
    - Shift+Ctrl: Add result to selection

    Args:
        func (function): Function to decorate. Must accept nodes parameter and return result nodes.

    Returns:
        function: Decorated function.
    """

    def wrap(self, **kwargs):
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No object selected.")
            return

        result_nodes = func(self, nodes=sel_nodes, **kwargs)
        mod_keys = maya_ui.get_modifiers()

        if not mod_keys:
            cmds.select(result_nodes, r=True)
        elif mod_keys == ["Shift", "Ctrl"] or "Shift" in mod_keys:
            cmds.select(sel_nodes, r=True)
            cmds.select(result_nodes, add=True)
        elif "Ctrl" in mod_keys:
            cmds.select(sel_nodes, r=True)
            cmds.select(result_nodes, d=True)

    return wrap


__all__ = [
    "FILTER_COLOR",
    "HIERARCHY_COLOR",
    "SUBSTITUTION_COLOR",
    "RENAME_COLOR",
    "REORDER_COLOR",
    "REORDER_REVERSED_COLOR",
    "LEFT_TO_RIGHT",
    "RIGHT_TO_LEFT",
    "selecter_handler",
]
