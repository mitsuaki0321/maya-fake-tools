"""Docstring → HTML rendering for the help popup. Qt-independent.

The help popup is reached only from the autocomplete path, which Phase
4 confirmed as Python-only. Everything in this subpackage therefore
assumes Python source / docstring shapes (``def`` signatures,
numpydoc / Google / RST docstring layouts, Pygments ``PythonLexer``).
The one exception is :mod:`.maya`, which renders ``cmds.help(name)``
output -- that text is language-agnostic since Maya's help format
doesn't depend on the calling language.

Modules:

* :mod:`.theme`      — palette & sizing
* :mod:`.syntax`     — Pygments-backed Python highlighter
* :mod:`.detect`     — format detection + signature / section extraction
                       (``SIGNATURE_RE`` is Python-shaped)
* :mod:`.blocks`     — shared HTML primitives
* :mod:`.structured` — numpydoc / Google / RST via ``docstring_parser``
* :mod:`.maya`       — ``cmds.help()`` output (language-agnostic)
* :mod:`.plain`      — fallback
"""

from __future__ import annotations

from typing import Optional

from . import blocks, detect, maya, plain, structured
from .theme import DEFAULT_THEME, SURFACE_BG

_LOADING_PLACEHOLDER = "Loading…"


def render_loading(identifier: str = "", theme: Optional[dict[str, str]] = None) -> str:
    """HTML placeholder shown while the docstring fetch is in flight."""
    merged_theme = dict(DEFAULT_THEME)
    if theme:
        merged_theme.update(theme)
    label = _LOADING_PLACEHOLDER if not identifier else f"{_LOADING_PLACEHOLDER}  {identifier}"
    return (
        f'<div style="color:{merged_theme["muted"]};'
        f"font-family:{merged_theme['font_family_body']};"
        f"font-size:{merged_theme['font_size_pt']}pt;"
        f'font-style:italic;padding:10px;">{label}</div>'
    )


def render_docstring(text: Optional[str], theme: Optional[dict[str, str]] = None) -> str:
    """Convert ``text`` to HTML for ``QTextEdit.setHtml``.

    Maya help → :mod:`.maya`; ``docstring_parser`` available →
    :mod:`.structured`; otherwise → :mod:`.plain`.
    """
    merged_theme = dict(DEFAULT_THEME)
    if theme:
        merged_theme.update(theme)

    if not text or not text.strip():
        return blocks.wrap(blocks.empty_placeholder(merged_theme), merged_theme)

    if detect.looks_like_maya_help(text):
        body = maya.render(text, merged_theme)
    elif structured.AVAILABLE:
        body = structured.render(text, merged_theme)
    else:
        body = plain.render(text, merged_theme)

    return blocks.wrap(body, merged_theme)


__all__ = ["DEFAULT_THEME", "SURFACE_BG", "render_docstring", "render_loading"]
