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
        name:        Full identifier shown to the user ("polyCube").
        complete:    Text to insert at cursor position — the suffix after the
                     partial word the user already typed ("Cube" when they
                     typed "poly").
        type:        jedi's category string — "function", "class", "module",
                     "instance", "keyword", "statement", "param" etc. Used for
                     sort ordering and icon lookup.
        description: Short one-line label (signature or type hint). May be
                     empty. Fetched lazily from jedi; keep cheap.
    """

    name: str
    complete: str
    type: str = ""
    description: str = ""

    @classmethod
    def from_jedi(cls, completion) -> CompletionItem:
        """Build an item from a ``jedi.api.classes.Completion``.

        ``completion.description`` is intentionally skipped. On a file-less
        module (``mCmds`` from the in-house eST3 pipeline, dynamically built
        without a source file) jedi falls back to a re-inference for every
        attribute, which measured ~80 ms × ~280 items = 21 seconds per
        keystroke on the company box. The popup doesn't surface this field
        to the user today, so paying that cost buys nothing. Fetch lazily
        via a resolve step if a future UI does need it.
        """
        return cls(
            name=completion.name,
            complete=completion.complete or "",
            type=completion.type or "",
            description="",
        )


__all__ = ["CompletionItem"]
