"""MEL language profile assembly.

Acts as the "manifest" for the MEL implementation: pulls each
concern (indent, folding, highlighting, right-click actions) from a
sibling module and binds them onto a single :class:`LanguageProfile`
instance. Adding a new MEL feature means adding one sibling module and
wiring it here.

Autocomplete is intentionally absent (``completion_engine_factory``
left unset) -- MEL was scoped out of the autocomplete pipeline in
Phase 4 since Maya's own Script Editor offers none either, and MEL
users rarely need attribute-style discovery.
"""

from __future__ import annotations

from ..profile import LanguageProfile, ShelfConfig
from .actions import mel_context_menu_extender
from .folding import MelFoldingStrategy
from .highlighting import mel_highlighter_factory
from .indent import MelIndentResolver

MEL = LanguageProfile(
    id="mel",
    display_name="MEL",
    extensions=(".mel",),
    default_extension=".mel",
    line_comment="//",
    indent_resolver=MelIndentResolver(),
    source_type="mel",
    shelf_config=ShelfConfig(
        source_type="mel",
        label="MEL",
        icon="commandButton.png",
    ),
    highlighter_factory=mel_highlighter_factory,
    context_menu_extender=mel_context_menu_extender,
    folding_strategy=MelFoldingStrategy(),
    accent_color="#E67E22",
)


__all__ = ["MEL"]
