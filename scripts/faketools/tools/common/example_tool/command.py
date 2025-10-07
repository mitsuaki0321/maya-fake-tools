"""
Example Tool Commands.

Business logic layer - pure functions without decorators.
"""

import maya.cmds as cmds


def execute_example() -> str:
    """
    Execute example command.

    This is a pure function without decorators.
    Error handling and undo management are done in the UI layer.

    Returns:
        str: Result message
    """
    # Example: Get selection
    selection = cmds.ls(selection=True)

    if not selection:
        return "No objects selected"

    # Example: Print selection
    result = f"Selected {len(selection)} object(s): {', '.join(selection)}"
    return result


def get_example_data() -> dict:
    """
    Get example data.

    Returns:
        dict: Example data dictionary
    """
    return {
        "maya_version": cmds.about(version=True),
        "selection": cmds.ls(selection=True),
    }


__all__ = ["execute_example", "get_example_data"]
