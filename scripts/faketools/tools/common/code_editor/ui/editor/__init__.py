"""Per-tab code-editor widget and its internal concerns.

Public exports for the rest of the editor:

* :class:`CodeEditor` -- the editor widget
* :data:`PythonEditor` -- legacy alias kept for downstream
  ``isinstance(editor, PythonEditor)`` checks across the tree

The tab widget (``CodeEditorWidget`` in ``ui/editor_tab_widget.py``)
is intentionally NOT re-exported here -- importing it through this
package would create a circular dependency (the tab widget imports
:class:`PythonEditor` from this package). Callers that need
``CodeEditorWidget`` should import it directly from its module.

Internals (auto-indent dispatcher, fold-state manager, syntax overlay
painters, multi-cursor mixin, etc.) are sibling modules; consumers
within the package import them directly.
"""

from __future__ import annotations

from .code_editor import CodeEditor, PythonEditor

__all__ = ["CodeEditor", "PythonEditor"]
