"""
Neutral completion-item dataclass.

jedi's ``Completion`` objects leak parse trees and file references that the UI
layer shouldn't touch. ``CompletionItem`` captures the fields the popup
actually needs and nothing else, so jedi can be swapped out later without
touching the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompletionItem:
    """One row in the autocomplete popup.

    Attributes:
        name:       Full identifier shown to the user ("polyCube").
        complete:   Text to insert at cursor position — the suffix after the
                    partial word the user already typed ("Cube" when they
                    typed "poly").
        type:       jedi's category string — "function", "class", "module",
                    "instance", "keyword", "statement", "param" etc. Used for
                    sort ordering and icon lookup.
        name_lower: Lower-cased ``name``, precomputed so the fast-path filter
                    in :mod:`engine` can do case-insensitive substring matches
                    without paying ``str.lower()`` per keystroke on every
                    cached item.
    """

    name: str
    complete: str
    type: str = ""
    name_lower: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Frozen dataclass forbids ordinary assignment; ``object.__setattr__``
        # is the canonical escape hatch documented in the dataclasses module.
        object.__setattr__(self, "name_lower", self.name.lower())

    @classmethod
    def from_jedi(cls, completion, *, fetch_type: bool = False) -> CompletionItem:
        """Build an item from a ``jedi.api.classes.Completion``.

        Args:
            completion: jedi ``Completion`` to extract from.
            fetch_type: Whether to access ``completion.type``. Defaults to
                ``False`` because ``.type`` is a lazy property that falls
                back to jedi's type inference, which in turn may walk back
                to the original source file. On a file-less module sourced
                from a network drive (in-house pipeline modules like
                ``eST3.mCmds``) that single attribute access measured
                ~72 ms per item, turning a 50-item popup into a 20 s wait.
                Call sites with known-fast sources — the bundled Maya
                stubs loaded locally — pass ``True`` so the sort retains
                its category ranking (param > keyword > function > ...).
        """
        return cls(
            name=completion.name,
            complete=completion.complete or "",
            type=(completion.type or "") if fetch_type else "",
        )


__all__ = ["CompletionItem"]
