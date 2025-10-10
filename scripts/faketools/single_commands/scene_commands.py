"""Command to process the scene."""

from ..lib import lib_optimize
from .base_commands import SceneCommand


class OptimizeSceneCommand(SceneCommand):
    """Command to optimize the entire scene."""

    _name = "OptimizeSceneCommand"
    _description = "Command to optimize the entire scene"

    def execute(self):
        """Execute the command."""
        lib_optimize.RemoveUnknownNodes(echo=True)
        lib_optimize.RemoveUnusedNodes(echo=True)
        lib_optimize.RemoveDataStructures(echo=True)
        lib_optimize.RemoveUnknownPlugins(echo=True)


__all__ = ["OptimizeSceneCommand"]
