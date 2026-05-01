"""Python language profile.

The profile assembly lives here; right-click menu / inspection / reload
implementations are in :mod:`.python_actions` so this module stays a small,
readable record of how Python plugs into the :class:`LanguageProfile`
framework.
"""

from __future__ import annotations

from .python_actions import python_context_menu_extender
from .types import LanguageProfile, ShelfConfig


def _python_extra_indent_trigger(stripped_text_before_cursor: str) -> bool:
    """Mirror the historic ``auto_indent.py`` rule: a non-comment line ending in ``:`` opens a block."""
    return stripped_text_before_cursor.endswith(":") and not stripped_text_before_cursor.startswith("#")


def _python_highlighter_factory(document):
    """Construct the Python syntax highlighter on demand.

    Imported lazily so that ``import faketools.tools.common.code_editor.languages``
    does not pull Qt in non-editor contexts (smoke tests, lint runs).
    """
    from ..highlighting.python_highlighter import PythonHighlighter

    return PythonHighlighter(document)


# block_comment is intentionally omitted: Python has no true block comments.
# `"""..."""` is a string literal (often a docstring), not a comment —
# toggling it would corrupt code and trip linter rule B018.
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
    highlighter_factory=_python_highlighter_factory,
    context_menu_extender=python_context_menu_extender,
)


__all__ = ["PYTHON"]
