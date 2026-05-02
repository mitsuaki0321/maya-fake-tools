"""MEL language profile.

Phase 1 minimal skeleton: only the fields required for file association,
comment toggle, run, and shelf-add. Highlighter / autocomplete / folding /
context-menu extender are intentionally left ``None`` so consumers
gracefully skip those features for MEL tabs.
"""

from __future__ import annotations

from .types import LanguageProfile, ShelfConfig

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
)


__all__ = ["MEL"]
