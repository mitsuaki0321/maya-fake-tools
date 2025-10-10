"""Single commands package."""

# Import all command modules to make them accessible
from . import all_commands, pair_commands, scene_commands
from .base_commands import AllCommand, PairCommand, SceneCommand

__all__ = ["SceneCommand", "AllCommand", "PairCommand", "scene_commands", "all_commands", "pair_commands"]
