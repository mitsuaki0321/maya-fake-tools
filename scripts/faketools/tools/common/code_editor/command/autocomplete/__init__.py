"""
Autocomplete command layer for the Code Editor.

Wraps ``jedi`` so the UI layer never sees jedi types directly. ``engine``
exposes :class:`JediEngine` and the global ``JEDI_AVAILABLE`` flag; ``types``
defines the neutral :class:`CompletionItem` dataclass that crosses the UI
boundary.
"""

from .engine import JEDI_AVAILABLE, JediEngine
from .types import CompletionItem

__all__ = ["JEDI_AVAILABLE", "CompletionItem", "JediEngine"]
