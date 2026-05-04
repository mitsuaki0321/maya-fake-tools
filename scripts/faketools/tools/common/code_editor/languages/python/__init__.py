"""Python language profile assembly.

Acts as the "manifest" for the Python implementation: pulls each
concern (indent, folding, highlighting, autocomplete, right-click
actions) from a sibling module and binds them onto a single
:class:`LanguageProfile` instance. Adding a new Python feature means
adding one sibling module and wiring it here.
"""

from __future__ import annotations

from ..profile import LanguageProfile, ShelfConfig
from .actions import python_context_menu_extender
from .completion import python_completion_engine_factory
from .folding import PythonFoldingStrategy
from .highlighting import python_highlighter_factory
from .indent import PythonIndentResolver

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
    highlighter_factory=python_highlighter_factory,
    context_menu_extender=python_context_menu_extender,
    completion_engine_factory=python_completion_engine_factory,
    folding_strategy=PythonFoldingStrategy(),
    accent_color="#007acc",
)


__all__ = ["PYTHON"]
