"""MEL language profile.

Wires file association, comment toggle, run, shelf-add (Phase 1),
syntax highlighting (Phase 2), and the auto-indent resolver (Phase 3).
Autocomplete / folding / context-menu extender remain ``None`` so
consumers gracefully skip those features for MEL tabs until later
phases enable them.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

from .indent_resolver import IndentResolver
from .mel_actions import mel_context_menu_extender
from .mel_folding import MelFoldingStrategy
from .types import LanguageProfile, ShelfConfig


class MelIndentResolver(IndentResolver):
    """Auto-indent resolver for MEL.

    Rule 0: ``{`` at end of line opens a 4-space block, and
    ``case X:`` / ``default:`` (the only ``:``-terminated lines in MEL)
    get the same treatment. Without this, the bracket-based Rule 1
    would line-wrap to the column right after ``{``, which doesn't
    match how MEL code is conventionally indented.

    Also overrides :meth:`_iter_code_brackets` so the bracket scanner
    skips MEL ``//`` line comments, ``/* ... */`` block comments and
    ``"..."`` string literals -- otherwise a commented-out ``{`` would
    leak into the Rule 1 / Rule 2 stacks and produce nonsense indent.
    """

    def _indent_on_enter(self, *, text_before_cursor: str, current_indent: str, **_) -> Optional[str]:
        stripped = text_before_cursor.strip()
        if stripped.startswith("//"):
            return None
        if stripped.endswith("{") or stripped.endswith(":"):
            return current_indent + "    "
        return None

    def _iter_code_brackets(self, text: str) -> Iterator[tuple[int, str]]:
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            # // line comment -- nothing on the rest of the line is code.
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                return
            # /* block comment */ -- skip to closer (or rest of line).
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                end = text.find("*/", i + 2)
                if end < 0:
                    return
                i = end + 2
                continue
            # "..." string with backslash escapes.
            if ch == '"':
                i += 1
                while i < n:
                    if text[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if text[i] == '"':
                        i += 1
                        break
                    i += 1
                continue
            if ch in "([{)]}":
                yield i, ch
            i += 1


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
    indent_resolver=MelIndentResolver(),
    source_type="mel",
    shelf_config=ShelfConfig(
        source_type="mel",
        label="MEL",
        icon="commandButton.png",
    ),
    highlighter_factory=_mel_highlighter_factory,
    context_menu_extender=mel_context_menu_extender,
    folding_strategy=MelFoldingStrategy(),
)


__all__ = ["MEL"]
