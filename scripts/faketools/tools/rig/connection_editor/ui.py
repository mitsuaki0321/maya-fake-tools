"""Connection Editor launcher.

Launches the external ``fake_connection_editor`` tool.
Repository: https://github.com/mitsuaki0321/fake-connection-editor
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui.maya_decorator import error_handler

logger = getLogger(__name__)


@error_handler
def show_ui():
    """Launch the external Connection Editor tool.

    Imports and launches ``fake_connection_editor``. If the package is not
    installed, a warning is logged instead of raising.
    """
    try:
        import fake_connection_editor
    except ImportError:
        message = "fake_connection_editor is not installed. Install it from https://github.com/mitsuaki0321/fake-connection-editor"
        logger.warning(message)
        cmds.warning(message)
        return

    fake_connection_editor.launch()


__all__ = ["show_ui"]
