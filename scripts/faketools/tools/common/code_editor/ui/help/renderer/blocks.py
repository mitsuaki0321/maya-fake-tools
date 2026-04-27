"""Shared HTML building blocks. Each function takes a ``theme`` dict and returns HTML.

Qt rich-text quirks this file works around:
- ``padding`` only works on ``<td>`` — code blocks use a single-cell
  ``<table cellpadding=...>``.
- ``width: 100%`` as CSS is flaky on tables; the HTML attribute form
  ``<table width="100%">`` is honoured.
- :func:`wrap` leaves background to the host widget — painting one here
  makes ``<p>`` gaps flash through and look like row stripes.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from . import syntax

# --- Document wrapper --------------------------------------------------------


def wrap(body: str, theme: dict[str, str]) -> str:
    """Outer font / colour wrapper. No background — see module docstring."""
    return f'<div style="color:{theme["foreground"]};font-family:{theme["font_family_body"]};font-size:{theme["font_size_pt"]}pt;">{body}</div>'


def empty_placeholder(theme: dict[str, str]) -> str:
    return f'<p style="color:{theme["muted"]};font-style:italic;">(no documentation)</p>'


# --- Section header ---------------------------------------------------------


def section_header(title: str, theme: dict[str, str], accent: Optional[str] = None) -> str:
    """Left-accent-bar + uppercase letter-spaced title. Raises uses a warmer accent."""
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
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n".join(f"<p>{inline_format(p, theme)}</p>" for p in paras)


def inline_format(text: str, theme: dict[str, str]) -> str:
    """Escape + convert ``\\`foo\\``` spans to monospace pills."""
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
    """Highlighted signature block."""
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
    """Preserved-whitespace code block. ``highlight_python`` toggles Pygments vs doctest-prompts-only."""
    stripped = text.rstrip()
    if highlight_python:
        inner = syntax.highlight_python(stripped)
    else:
        inner = highlight_doctest_prompts(html.escape(stripped), theme)
    return wrap_code_block(inner, theme)


def wrap_code_block(inner_html: str, theme: dict[str, str]) -> str:
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
