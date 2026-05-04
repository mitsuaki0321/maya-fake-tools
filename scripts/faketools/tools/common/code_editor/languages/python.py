"""Python language profile.

The profile assembly lives here; right-click menu / inspection / reload
implementations are in :mod:`.python_actions` so this module stays a small,
readable record of how Python plugs into the :class:`LanguageProfile`
framework.
"""

from __future__ import annotations

from typing import Optional

from .indent_resolver import IndentResolver
from .python_actions import python_context_menu_extender
from .python_folding import PythonFoldingStrategy
from .types import LanguageProfile, ShelfConfig


class PythonIndentResolver(IndentResolver):
    """Add Rule 0: a non-comment line ending in ``:`` opens a 4-space block."""

    def _indent_on_enter(self, *, text_before_cursor: str, current_indent: str, **_) -> Optional[str]:
        stripped = text_before_cursor.strip()
        if stripped.startswith("#"):
            return None
        if stripped.endswith(":"):
            return current_indent + "    "
        return None


def _python_highlighter_factory(document):
    """Construct the Python syntax highlighter on demand.

    Imported lazily so that ``import faketools.tools.common.code_editor.languages``
    does not pull Qt in non-editor contexts (smoke tests, lint runs).
    """
    from ..highlighting.python_highlighter import PythonHighlighter

    return PythonHighlighter(document)


def _python_completion_engine_factory():
    """Return the process-wide :class:`JediEngine` for Python autocomplete.

    Imported lazily so the languages package stays Qt- and jedi-free at
    module import time. ``get_shared_engine`` configures Maya stub paths
    on its first call and caches the engine for every subsequent caller.
    """
    from ..ui.autocomplete import get_shared_engine

    return get_shared_engine()


PYTHON = LanguageProfile(
    id="python",
    display_name="Python",
    extensions=(".py",),
    default_extension=".py",
    line_comment="#",
    indent_resolver=PythonIndentResolver(),
    source_type="python",
    shelf_config=ShelfConfig(
        source_type="python",
        label="Python",
        icon="pythonFamily.png",
    ),
    highlighter_factory=_python_highlighter_factory,
    context_menu_extender=python_context_menu_extender,
    completion_engine_factory=_python_completion_engine_factory,
    folding_strategy=PythonFoldingStrategy(),
    accent_color="#007acc",
)


__all__ = ["PYTHON"]
