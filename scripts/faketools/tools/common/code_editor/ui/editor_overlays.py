"""Viewport overlays drawn on top of the editor's normal text rendering.

Two decorations:

- :func:`paint_fold_placeholders` writes the ``...`` indicator at the
  end of folded header lines.
- :func:`paint_indent_guides` draws faint vertical rules at each indent
  level so wide indentation stays scannable.

Both run after the editor's parent ``paintEvent`` has rendered the
text and before the multi-cursor painter draws caret highlights.
"""

from __future__ import annotations

from .....lib_ui.qt_compat import QColor, QPainter, QPen, Qt
from ..themes import AppTheme

_INDENT_SIZE = 4


def paint_fold_placeholders(editor, event) -> None:
    """Draw ``...`` placeholders after every folded header on screen.

    Args:
        editor: The ``PythonEditor`` instance whose ``viewport`` to paint.
        event: The Qt ``QPaintEvent`` that triggered the parent paint.
    """
    fold_manager = editor.fold_manager
    if not fold_manager._folded_headers:
        return

    painter = QPainter(editor.viewport())
    painter.setPen(QColor(AppTheme.FOLD_PLACEHOLDER_COLOR))
    painter.setFont(editor.font())

    metrics = editor.fontMetrics()
    line_height = metrics.height()
    viewport_width = editor.viewport().width()

    block = editor.firstVisibleBlock()
    while block.isValid():
        geometry = editor.blockBoundingGeometry(block).translated(editor.contentOffset())
        if geometry.top() > event.rect().bottom():
            break

        block_number = block.blockNumber()
        if block.isVisible() and fold_manager.is_folded(block_number):
            text_width = metrics.horizontalAdvance(block.text())
            placeholder = fold_manager.get_placeholder_text(block_number)
            x = text_width + 4
            y = int(geometry.top())
            painter.drawText(x, y, viewport_width - x, line_height, Qt.AlignLeft, placeholder)

        block = block.next()

    painter.end()


def paint_indent_guides(editor, event) -> None:
    """Draw a vertical guide line at each indent level on every visible block."""
    painter = QPainter(editor.viewport())
    painter.setPen(QPen(QColor(AppTheme.INDENT_GUIDE_COLOR), 1))

    char_width = editor.fontMetrics().horizontalAdvance(" ")
    tab_width = char_width * _INDENT_SIZE

    block = editor.firstVisibleBlock()
    while block.isValid():
        geometry = editor.blockBoundingGeometry(block).translated(editor.contentOffset())
        if geometry.top() > event.rect().bottom():
            break

        text = block.text()
        if text.strip():
            indent = len(text) - len(text.lstrip())
            indent_levels = indent // _INDENT_SIZE
        else:
            indent_levels = _next_block_indent_level(block)

        for level in range(indent_levels):
            x = int(level * tab_width)
            painter.drawLine(x, int(geometry.top()), x, int(geometry.bottom()))

        block = block.next()

    painter.end()


def _next_block_indent_level(current_block) -> int:
    """Return the indent level of the next non-empty visible block.

    Used so guide lines on blank lines extend down to the next code line
    rather than dropping to zero.
    """
    block = current_block.next()
    while block.isValid():
        if not block.isVisible():
            block = block.next()
            continue
        text = block.text()
        if text.strip():
            indent = len(text) - len(text.lstrip())
            return indent // _INDENT_SIZE
        block = block.next()
    return 0
