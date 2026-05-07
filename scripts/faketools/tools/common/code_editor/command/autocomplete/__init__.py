"""
Autocomplete command layer for the Code Editor.

Wraps ``jedi`` so the UI layer never sees jedi types directly. ``engine``
exposes :class:`JediEngine` and the global ``JEDI_AVAILABLE`` flag; ``types``
defines the neutral :class:`CompletionItem` dataclass that crosses the UI
boundary.
"""

from .engine import JEDI_AVAILABLE, JediEngine, expression_root
from .persistence import MAX_ENTRIES as MRU_MAX_ENTRIES, MRU_FILE_NAME, AutocompleteMruStore, make_key as make_mru_key
from .types import CompletionItem

__all__ = [
    "JEDI_AVAILABLE",
    "CompletionItem",
    "JediEngine",
    "expression_root",
    "AutocompleteMruStore",
    "MRU_MAX_ENTRIES",
    "MRU_FILE_NAME",
    "make_mru_key",
]
