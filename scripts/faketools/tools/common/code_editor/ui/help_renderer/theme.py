"""Colour palette and sizing for the help popup.

Mirrors the editor's VS Code Dark Modern syntax theme. Plain dict so
callers can override a subset of keys.
"""

from __future__ import annotations

DEFAULT_THEME: dict[str, str] = {
    "foreground": "#d4d4d4",
    "muted": "#a0a0a0",
    "accent": "#4fc3f7",
    # Code blocks are darker than the surface (SURFACE_BG) so they read as "inset".
    "code_bg": "#1a1a1a",
    "code_border": "#3e3e42",
    "code_pill_bg": "#1a1a1a",
    "param_name": "#9cdcfe",
    "param_type": "#4ec9b0",
    "function": "#dcdcaa",
    "raise_accent": "#e6c07b",
    "literal": "#d19a66",
    "prompt_green": "#98c379",
    "font_family_mono": "Consolas, 'Courier New', monospace",
    "font_family_body": "inherit",
    "font_size_pt": "10",
}


# Recommended widget background — keep slightly lighter than ``code_bg``.
SURFACE_BG = "#262626"


__all__ = ["DEFAULT_THEME", "SURFACE_BG"]
