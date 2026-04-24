"""
Pygments-backed Python syntax highlighting matched to the editor palette.

:func:`highlight_python` is the only function callers should use. It
wraps Pygments with:

- a custom :class:`EditorStyle` that mirrors
  ``themes/syntax_colors.json`` (VS Code Dark Modern) — so the help
  popup and the editor speak the same colour vocabulary.
- a :class:`FunctionCallFilter` that promotes bare ``name(`` token
  pairs to ``Name.Function``. Pygments by default only emits
  ``Name.Function`` for function *definitions* (``def foo(...)``), so
  call sites like ``fetch_user(42)`` would otherwise render as plain
  ``Name``. Promoting them matches the editor's own highlighter which
  colours every ``name(`` as a method/function.

If Pygments itself is unavailable the highlighter degrades to
``html.escape()`` — callers get plain text without crashing.
"""

from __future__ import annotations

import html
from logging import getLogger

logger = getLogger(__name__)


try:
    from pygments import highlight as _pygments_highlight  # type: ignore
    from pygments.filter import Filter  # type: ignore
    from pygments.formatters import HtmlFormatter  # type: ignore
    from pygments.lexers import PythonLexer  # type: ignore
    from pygments.style import Style  # type: ignore
    from pygments.token import (  # type: ignore
        Comment,
        Keyword,
        Name,
        Number,
        Operator,
        Punctuation,
        String,
        Text,
    )

    class EditorStyle(Style):
        """Pygments style matching the Code Editor's own syntax colours.

        Notable choices:

        - ``Name.Builtin`` is left at the default identifier colour so
          calls like ``abs(x)`` / ``print(x)`` don't get a special tint
          the editor doesn't apply.
        - ``Name.Function`` uses the method colour; a custom filter
          (:class:`FunctionCallFilter`) promotes bare ``name(`` tokens
          to ``Name.Function`` before they reach the formatter so
          ``fetch_user(42)`` / ``cmds.polyCube(w=2)`` pick up the same
          yellow the editor's highlighter gives them.
        """

        default_style = ""
        styles = {
            Text: "#d4d4d4",
            Comment: "#6a9955",
            Keyword: "#c586c0",
            Keyword.Constant: "#559ad3",  # True / False / None
            Keyword.Declaration: "#569cd6",  # def / class
            Keyword.Namespace: "#c586c0",  # import / from / as
            Operator: "#d4d4d4",
            Operator.Word: "#c586c0",  # and / or / not / in / is
            Name: "#9cdcfe",  # editor's "variable" colour
            Name.Function: "#dcdcaa",
            Name.Class: "#4ec9b0",
            Name.Decorator: "#c586c0",
            Name.Builtin: "#9cdcfe",  # builtins treated as plain identifiers
            Name.Builtin.Pseudo: "#559ad3",  # self / cls — close to boolean
            String: "#ce9178",
            String.Escape: "#d7ba7d",
            Number: "#b5cea8",
            Punctuation: "#d4d4d4",
        }

    class FunctionCallFilter(Filter):
        """Promote ``Name (`` token pairs to ``Name.Function (``.

        One-token-lookahead walk: whenever a ``Name``/``Name.Builtin``
        is immediately followed by an optional whitespace run and an
        open-paren, we relabel it so the formatter applies the method
        colour.
        """

        def filter(self, lexer, stream):  # type: ignore[override]
            tokens = list(stream)
            name_token_types = {Name, Name.Builtin}
            for i, (ttype, value) in enumerate(tokens):
                if ttype in name_token_types:
                    # Look ahead, skipping any whitespace between the
                    # identifier and a potential '('.
                    j = i + 1
                    while j < len(tokens):
                        nt, nv = tokens[j]
                        if nt in Text and nv.isspace():
                            j += 1
                            continue
                        break
                    if j < len(tokens):
                        nt, nv = tokens[j]
                        if nt is Punctuation and nv == "(":
                            yield Name.Function, value
                            continue
                yield ttype, value

    PYGMENTS_AVAILABLE = True
except Exception as exc:  # pragma: no cover — diagnostic only
    PYGMENTS_AVAILABLE = False
    EditorStyle = None  # type: ignore[assignment]
    FunctionCallFilter = None  # type: ignore[assignment]
    logger.debug(f"pygments unavailable, signature highlighting disabled: {exc}")


def highlight_python(source: str) -> str:
    """Return ``source`` as HTML with editor-matching syntax colours.

    Falls back to ``html.escape(source)`` when Pygments or the custom
    style is unavailable so callers don't need to branch on
    :data:`PYGMENTS_AVAILABLE` themselves.
    """
    if EditorStyle is None:
        return html.escape(source)
    try:
        lexer = PythonLexer(stripall=False)
        if FunctionCallFilter is not None:
            lexer.add_filter(FunctionCallFilter())
        formatter = HtmlFormatter(noclasses=True, nowrap=True, style=EditorStyle)
        return _pygments_highlight(source, lexer, formatter).rstrip("\n")
    except Exception as exc:
        logger.debug(f"pygments highlight failed: {exc}")
        return html.escape(source)


__all__ = [
    "EditorStyle",
    "FunctionCallFilter",
    "PYGMENTS_AVAILABLE",
    "highlight_python",
]
