"""
Colour palette and sizing defaults for the help popup rendering.

Kept as a plain dict rather than a dataclass so callers can pass a
subset of keys to override individual colours without having to
reconstruct the whole object. Anything missing from a caller-supplied
theme falls back to :data:`DEFAULT_THEME`.

Colours mirror the editor's own syntax theme (see
``themes/syntax_colors.json``, "VS Code Dark Modern"), so the help
popup speaks the same visual vocabulary as the source under the
caret.
"""

from __future__ import annotations

DEFAULT_THEME: dict[str, str] = {
    "foreground": "#d4d4d4",
    "muted": "#a0a0a0",
    "accent": "#4fc3f7",  # section headers + left accent bar
    # Code blocks are rendered DARKER than the surrounding surface so
    # they read as "inset" into the prose rather than "raised" out of
    # it. The caller (``QTextEdit.setStyleSheet(...)``) paints the body
    # background, which we assume is a slightly lighter dark grey
    # (e.g. ``SURFACE_BG`` below). ``code_bg`` / ``code_pill_bg`` are
    # tuned against that.
    "code_bg": "#1a1a1a",
    "code_border": "#3e3e42",
    "code_pill_bg": "#1a1a1a",
    # Parameter / return names share the editor's "variable" colour so
    # they look identical to how parameter names read in the signature
    # block and in normal source code.
    "param_name": "#9cdcfe",
    "param_type": "#4ec9b0",  # type annotations after ``name :``
    "function": "#dcdcaa",  # method / function-like names (cmds.polyCube)
    "raise_accent": "#e6c07b",  # Raises header uses a warmer bar
    "literal": "#d19a66",  # default values / (-e) CLI flags
    "prompt_green": "#98c379",  # doctest ">>>" prompt
    "font_family_mono": "Consolas, 'Courier New', monospace",
    "font_family_body": "inherit",
    "font_size_pt": "10",
}


# Recommended widget background for hosts rendering this HTML. The
# caller's ``QTextEdit.setStyleSheet(...)`` should use this value so
# the outer surface sits slightly lighter than the code blocks and the
# "inset" effect reads correctly.
SURFACE_BG = "#262626"


__all__ = ["DEFAULT_THEME", "SURFACE_BG"]
