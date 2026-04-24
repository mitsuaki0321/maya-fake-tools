"""
Docstring → HTML rendering for the Code Editor's help popup.

Qt-independent: :func:`render_docstring` takes a raw docstring string
and a theme-colour override dict, and returns an HTML string suitable
for ``QTextEdit.setHtml``. The popup module pumps the returned string
into the widget; all visual policy (colours, spacing, section
ordering) lives in this package so the prototype launcher in
``scripts/debug/`` shares the exact same code path as production.

The package is split by concern so "which file do I open to change
X?" has a one-line answer:

- :mod:`.theme`      — colour palette & sizing defaults
- :mod:`.syntax`     — Pygments style + function-call filter (editor-
                       matching syntax highlighting)
- :mod:`.detect`     — format detection heuristics, signature / section
                       text extraction
- :mod:`.blocks`     — shared HTML primitives (section headers, code
                       blocks, paragraphs, inline code pills, …)
- :mod:`.structured` — numpydoc / Google / RST renderer via
                       ``docstring_parser``
- :mod:`.maya`       — Maya ``cmds.help()`` renderer, with each section
                       (Synopsis / Flags / Return value / Modes /
                       Examples) getting its own sub-renderer
- :mod:`.plain`      — bare fallback (signature + paragraph-split body)

Caller widget responsibilities:

- Set the widget background via stylesheet. Use
  :data:`SURFACE_BG` as the surface colour so the code blocks render
  as "inset" against a slightly-lighter body.
- ``QTextEdit.setHtml(render_docstring(text))`` is the only call
  callers make.

Optional dependencies:

- ``pygments`` — signature / Examples syntax highlighting. Missing →
  plain escaped text for code blocks.
- ``docstring_parser`` — structured section parsing. Missing → the
  whole thing falls back to :mod:`.plain`.
"""

from __future__ import annotations

from typing import Optional

from . import blocks, detect, maya, plain, structured
from .theme import DEFAULT_THEME, SURFACE_BG

_LOADING_PLACEHOLDER = "Loading…"


def render_loading(identifier: str = "", theme: Optional[dict[str, str]] = None) -> str:
    """HTML for the "fetch in flight" placeholder.

    Matches the body font / size used by :func:`render_docstring` so
    swapping the placeholder for the real content doesn't flicker.
    """
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
    """Convert ``text`` (a raw docstring) to HTML for ``QTextEdit.setHtml``.

    Picks a backend based on the input:

    - Looks like Maya ``cmds.help()`` output → :mod:`.maya`
    - ``docstring_parser`` available → :mod:`.structured`
    - Otherwise → :mod:`.plain`

    Empty / whitespace-only input returns a muted "(no documentation)"
    placeholder.
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
