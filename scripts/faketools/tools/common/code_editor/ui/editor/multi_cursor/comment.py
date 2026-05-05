"""Multi-cursor variant of the per-language line comment toggle.

Single-cursor logic lives in
:meth:`EditorTextOperationsMixin.toggle_line_comment`; this module is invoked
from there when the editor is in multi-cursor mode (``editor.all_cursors``
non-empty). Comment prefixes come from the editor's
:class:`~..languages.LanguageProfile` and are passed in by the caller so the
core logic stays language-agnostic.
"""

from __future__ import annotations

from .......lib_ui.qt_compat import QTextCursor


def toggle_line_comment_multi_cursor(editor, prefix: str, prefix_with_space: str) -> None:
    """Toggle line comments on every line that hosts a multi-cursor."""
    doc = editor.document()
    cursor = QTextCursor(doc)
    cursor.beginEditBlock()

    lines_with_cursors = {c.blockNumber() for c in editor.all_cursors}

    all_commented = True
    for line_num in lines_with_cursors:
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line_num):
            cursor.movePosition(QTextCursor.NextBlock)
        line_text = cursor.block().text().lstrip()
        if line_text and not line_text.startswith(prefix):
            all_commented = False
            break

    for line_num in sorted(lines_with_cursors):
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line_num):
            cursor.movePosition(QTextCursor.NextBlock)
        cursor.movePosition(QTextCursor.StartOfLine)

        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.movePosition(QTextCursor.StartOfLine)

        if not line_text.strip():
            continue

        if all_commented:
            if line_text.lstrip().startswith(prefix):
                spaces = len(line_text) - len(line_text.lstrip())
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, spaces)
                for _ in range(len(prefix)):
                    cursor.deleteChar()
                if cursor.block().text() and cursor.block().text()[0] == " ":
                    cursor.deleteChar()
        else:
            leading_spaces = len(line_text) - len(line_text.lstrip())
            cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, leading_spaces)
            cursor.insertText(prefix_with_space)

    cursor.endEditBlock()
    editor.viewport().update()
