"""MEL language profile.

Wires file association, comment toggle, run, shelf-add (Phase 1) and
syntax highlighting (Phase 2). Autocomplete / folding / context-menu
extender remain ``None`` so consumers gracefully skip those features
for MEL tabs until later phases enable them.
"""

from __future__ import annotations

from .types import LanguageProfile, ShelfConfig


def _mel_highlighter_factory(document):
    """Construct the MEL syntax highlighter on demand.

    Imported lazily so that ``import faketools.tools.common.code_editor.languages``
    doesn't drag Qt into non-editor contexts (smoke tests, lint runs).
    """
    from ..highlighting.mel_highlighter import MelHighlighter

    return MelHighlighter(document)


MEL = LanguageProfile(
    id="mel",
    display_name="MEL",
    extensions=(".mel",),
    default_extension=".mel",
    line_comment="//",
    source_type="mel",
    shelf_config=ShelfConfig(
        source_type="mel",
        label="MEL",
        icon="commandButton.png",
    ),
    highlighter_factory=_mel_highlighter_factory,
)


__all__ = ["MEL"]
