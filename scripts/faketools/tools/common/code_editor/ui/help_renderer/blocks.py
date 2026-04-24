"""
Shared HTML building blocks used by every renderer.

Everything here takes a ``theme`` dict (see :mod:`.theme`) and returns
an HTML string. Functions are grouped roughly by scope:

- Document-level:  :func:`wrap`, :func:`empty_placeholder`
- Section-level:   :func:`section_header`, :func:`paragraphs`
- Code surfaces:   :func:`signature`, :func:`code_block`,
                   :func:`wrap_code_block`
- Inline spans:    :func:`inline_format` (pill-styled ``\\`code\\```)

Qt rich-text quirks worth remembering when editing this file:

- ``padding`` only works on ``<td>`` — not on ``<div>`` / ``<pre>``.
  Code blocks therefore go through a single-cell table with
  ``cellpadding``.
- CSS ``width: 100%`` on a ``<table>`` is flaky; the HTML attribute
  form ``<table width="100%">`` is honoured reliably.
- ``<p>`` blocks inherit the widget's palette for their background —
  if the outer ``wrap`` tried to paint a colour behind the document,
  gaps between ``<p>`` blocks would flash the widget background and
  read as row stripes. :func:`wrap` therefore leaves background to the
  host widget's stylesheet.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from . import syntax

# --- Document wrapper --------------------------------------------------------


def wrap(body: str, theme: dict[str, str]) -> str:
    """Outer font / colour wrapper around a rendered body.

    Deliberately leaves background to the host widget — see the
    module docstring for why.
    """
    return f'<div style="color:{theme["foreground"]};font-family:{theme["font_family_body"]};font-size:{theme["font_size_pt"]}pt;">{body}</div>'


def empty_placeholder(theme: dict[str, str]) -> str:
    """Body used when the incoming text is empty / all whitespace."""
    return f'<p style="color:{theme["muted"]};font-style:italic;">(no documentation)</p>'


# --- Section header ---------------------------------------------------------


def section_header(title: str, theme: dict[str, str], accent: Optional[str] = None) -> str:
    """Small left-accent-bar + uppercase letter-spaced title.

    ``accent`` defaults to ``theme["accent"]``. The Raises section
    passes the warmer ``raise_accent`` colour to hint at "this is an
    error pathway" at a glance.
    """
    bar_colour = accent or theme["accent"]
    return (
        f'<p style="color:{bar_colour};font-weight:bold;font-size:8pt;'
        f"text-transform:uppercase;letter-spacing:1px;"
        f"border-left:3px solid {bar_colour};"
        f"padding-left:8px;"
        f'margin-top:16px;margin-bottom:6px;">{html.escape(title)}</p>'
    )


# --- Paragraphs with inline code spans --------------------------------------


CODE_SPAN_RE = re.compile(r"``([^`]+)``|`([^`]+)`")


def paragraphs(text: str, theme: dict[str, str]) -> str:
    """Split ``text`` on blank lines; wrap each paragraph in ``<p>``."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n".join(f"<p>{inline_format(p, theme)}</p>" for p in paras)


def inline_format(text: str, theme: dict[str, str]) -> str:
    """Escape + convert ``\\`foo\\``` / ``\\`\\`foo\\`\\``` spans to monospace pills."""
    escaped = html.escape(text)

    def replace(match: re.Match) -> str:
        content = match.group(1) or match.group(2)
        return (
            f'<code style="font-family:{theme["font_family_mono"]};'
            f"background-color:{theme['code_pill_bg']};"
            f"color:{theme['foreground']};"
            f'padding:1px 5px;">{content}</code>'
        )

    return CODE_SPAN_RE.sub(replace, escaped)


# --- Code surfaces ----------------------------------------------------------


def signature(sig: str, theme: dict[str, str]) -> str:
    """Highlighted code block for a function signature.

    Wrapped in a single-cell ``<table>`` because Qt's rich-text engine
    honours ``padding`` only on table cells. The ``cellpadding``
    attribute gives us the inner breathing room; ``width="100%"`` as
    an HTML attribute (not CSS) makes the box stretch the full width
    of the container.
    """
    body_html = syntax.highlight_python(sig)
    return (
        f'<table width="100%" cellpadding="8" cellspacing="0" '
        f'style="background-color:{theme["code_bg"]};'
        f"border:1px solid {theme['code_border']};"
        f"margin:6px 0 10px 0;"
        f'font-family:{theme["font_family_mono"]};">'
        f'<tr><td style="color:{theme["foreground"]};">{body_html}</td></tr>'
        f"</table>"
    )


def code_block(text: str, theme: dict[str, str], *, highlight_python: bool = False) -> str:
    """Preserved-whitespace code block.

    With ``highlight_python=True`` the content goes through the
    Pygments highlighter (used for Examples / Maya's Examples section
    / any case where the block is actual Python). Without it we only
    colour the ``>>>`` doctest prompts — enough for most docstring
    Examples and avoids lexer overhead on content that isn't really
    code (e.g. Maya's flag table).
    """
    stripped = text.rstrip()
    if highlight_python:
        inner = syntax.highlight_python(stripped)
    else:
        inner = highlight_doctest_prompts(html.escape(stripped), theme)
    return wrap_code_block(inner, theme)


def wrap_code_block(inner_html: str, theme: dict[str, str]) -> str:
    """Apply the standard code-block shell (table + pre)."""
    return (
        f'<table width="100%" cellpadding="8" cellspacing="0" '
        f'style="background-color:{theme["code_bg"]};'
        f"border:1px solid {theme['code_border']};"
        f'margin:4px 0 10px 0;">'
        f"<tr><td>"
        f'<pre style="font-family:{theme["font_family_mono"]};'
        f"margin:0;"
        f'white-space:pre-wrap;color:{theme["foreground"]};">{inner_html}</pre>'
        f"</td></tr>"
        f"</table>"
    )


def highlight_doctest_prompts(escaped_text: str, theme: dict[str, str]) -> str:
    """Colour ``&gt;&gt;&gt;`` prompts green. Input must already be HTML-escaped."""
    prompt = "&gt;&gt;&gt;"
    return re.sub(
        f"^([ \\t]*){re.escape(prompt)}",
        lambda m: f'{m.group(1)}<span style="color:{theme["prompt_green"]};">{prompt}</span>',
        escaped_text,
        flags=re.MULTILINE,
    )


__all__ = [
    "CODE_SPAN_RE",
    "code_block",
    "empty_placeholder",
    "highlight_doctest_prompts",
    "inline_format",
    "paragraphs",
    "section_header",
    "signature",
    "wrap",
    "wrap_code_block",
]
