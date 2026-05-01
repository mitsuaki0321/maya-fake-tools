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


def _python_highlighter_factory(document):
    """Construct the Python syntax highlighter on demand.

    Imported lazily so that ``import faketools.tools.common.code_editor.languages``
    does not pull Qt in non-editor contexts (smoke tests, lint runs).
    """
    from ..highlighting.python_highlighter import PythonHighlighter

    return PythonHighlighter(document)


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
)


__all__ = ["PYTHON"]
