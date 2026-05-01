"""Python language profile.

Defined in its own module (rather than directly in ``__init__.py``) so that
each language profile lives next to language-specific helpers when those
appear in later phases (extender callbacks, inspection snippets, etc.).
"""

from __future__ import annotations

from ._types import LanguageProfile, ShelfConfig


def _python_extra_indent_trigger(stripped_text_before_cursor: str) -> bool:
    """Mirror the historic ``auto_indent.py`` rule: a non-comment line ending in ``:`` opens a block."""
    return stripped_text_before_cursor.endswith(":") and not stripped_text_before_cursor.startswith("#")


PYTHON = LanguageProfile(
    id="python",
    display_name="Python",
    extensions=(".py",),
    default_extension=".py",
    line_comment="#",
    extra_indent_trigger=_python_extra_indent_trigger,
    source_type="python",
    shelf_config=ShelfConfig(
        source_type="python",
        label="Python",
        icon="pythonFamily.png",
    ),
)


__all__ = ["PYTHON"]
