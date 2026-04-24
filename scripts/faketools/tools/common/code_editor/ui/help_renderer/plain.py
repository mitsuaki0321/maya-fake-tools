"""
Ultimate-fallback renderer.

Used when the input doesn't look like Maya ``cmds.help()`` output AND
``docstring_parser`` is unavailable, or when the structured renderer
itself fails. We still pull off the leading signature line so it gets
the highlighted-code-block treatment, and the rest goes through
:func:`blocks.paragraphs` so blank-line breaks are respected.
"""

from __future__ import annotations

from . import blocks, detect


def render(text: str, theme: dict[str, str]) -> str:
    """Signature (if any) + paragraph-split body."""
    sig_line, rest = detect.extract_signature_line(text.lstrip())
    parts: list[str] = []
    if sig_line:
        parts.append(blocks.signature(sig_line, theme))
        if rest.strip():
            parts.append(blocks.paragraphs(rest, theme))
    else:
        parts.append(blocks.paragraphs(text, theme))
    return "\n".join(parts)


__all__ = ["render"]
