"""
Neutral completion-item dataclass.

jedi's ``Completion`` objects leak parse trees and file references that the UI
layer shouldn't touch. ``CompletionItem`` captures the fields the popup
actually needs and nothing else, so jedi can be swapped out later without
touching the UI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionItem:
    """One row in the autocomplete popup.

    Attributes:
        name:     Full identifier shown to the user ("polyCube").
        complete: Text to insert at cursor position — the suffix after the
                  partial word the user already typed ("Cube" when they
                  typed "poly").
        type:     jedi's category string — "function", "class", "module",
                  "instance", "keyword", "statement", "param" etc. Used for
                  sort ordering and icon lookup.
    """

    name: str
    complete: str
    type: str = ""

    @classmethod
    def from_jedi(cls, completion) -> CompletionItem:
        """Build an item from a ``jedi.api.classes.Completion``."""
        return cls(
            name=completion.name,
            complete=completion.complete or "",
            type=completion.type or "",
        )


__all__ = ["CompletionItem"]
