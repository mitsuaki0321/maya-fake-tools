"""Python syntax-highlighter factory for the language profile.

Lazy import inside :func:`python_highlighter_factory` so importing
``code_editor.languages`` doesn't pull Qt -- smoke tests, lint runs,
and any other non-editor context can introspect the profile without
a Qt dependency.
"""

from __future__ import annotations


def python_highlighter_factory(document):
    """Construct the Python syntax highlighter on demand."""
    from ...highlighting.python_highlighter import PythonHighlighter

    return PythonHighlighter(document)


__all__ = ["python_highlighter_factory"]
