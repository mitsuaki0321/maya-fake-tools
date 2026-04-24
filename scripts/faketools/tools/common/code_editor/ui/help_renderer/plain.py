"""Fallback renderer: signature (if any) + paragraph-split body."""

from __future__ import annotations

from . import blocks, detect


def render(text: str, theme: dict[str, str]) -> str:
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
