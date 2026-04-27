"""Pygments-backed Python highlighting matched to the editor palette.

Falls back to ``html.escape`` when Pygments is unavailable.
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
        """Mirrors the editor's own syntax colours (VS Code Dark Modern)."""

        default_style = ""
        styles = {
            Text: "#d4d4d4",
            Comment: "#6a9955",
            Keyword: "#c586c0",
            Keyword.Constant: "#559ad3",
            Keyword.Declaration: "#569cd6",
            Keyword.Namespace: "#c586c0",
            Operator: "#d4d4d4",
            Operator.Word: "#c586c0",
            Name: "#9cdcfe",
            Name.Function: "#dcdcaa",
            Name.Class: "#4ec9b0",
            Name.Decorator: "#c586c0",
            Name.Builtin: "#9cdcfe",
            Name.Builtin.Pseudo: "#559ad3",
            String: "#ce9178",
            String.Escape: "#d7ba7d",
            Number: "#b5cea8",
            Punctuation: "#d4d4d4",
        }

    class FunctionCallFilter(Filter):
        """Promote ``Name (`` pairs to ``Name.Function`` — Pygments only tags definitions by default."""

        def filter(self, lexer, stream):  # type: ignore[override]
            tokens = list(stream)
            name_token_types = {Name, Name.Builtin}
            for i, (ttype, value) in enumerate(tokens):
                if ttype in name_token_types:
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
    """HTML-highlighted ``source``. Falls back to ``html.escape`` on error / missing Pygments."""
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
