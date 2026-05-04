"""MEL syntax-highlighter factory for the language profile.

Lazy import inside :func:`mel_highlighter_factory` so importing
``code_editor.languages`` doesn't pull Qt -- smoke tests, lint runs,
and any other non-editor context can introspect the profile without
a Qt dependency.
"""

from __future__ import annotations


def mel_highlighter_factory(document):
    """Construct the MEL syntax highlighter on demand."""
    from ...highlighting.mel_highlighter import MelHighlighter

    return MelHighlighter(document)


__all__ = ["mel_highlighter_factory"]
