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


def _cached_indent_step(editor) -> int:
    """Return ``_INDENT_SIZE * char_width`` cached against the editor's font.

    paintEvent fires on every cursor blink / scroll / keystroke, so reaching
    into ``fontMetrics().horizontalAdvance(' ')`` each time is wasteful — the
    value only changes when the font does (Ctrl+wheel zoom, theme reload).
    """
    font_key = (editor.font().family(), editor.font().pointSizeF(), editor.font().pixelSize())
    cached = getattr(editor, "_indent_guide_step_cache", None)
    if cached is not None and cached[0] == font_key:
        return cached[1]
    step = editor.fontMetrics().horizontalAdvance(" ") * _INDENT_SIZE
    editor._indent_guide_step_cache = (font_key, step)
    return step


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


def paint_current_line_border(editor, event) -> None:
    """Draw thin 1px rules at the top and bottom of the cursor's line.

    Aligned to ``cursorRect`` rather than ``blockBoundingGeometry`` so the
    rules touch the caret's visible top/bottom — the block geometry includes
    line-leading padding, leaving a 1–2px gap above/below the caret otherwise.
    Suppressed while a selection is active — the selection itself signals
    where the cursor is, so an extra decoration would be visual noise.
    """
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return

    rect = editor.cursorRect()
    top = rect.top()
    bottom = rect.top() + rect.height() - 1

    if bottom < event.rect().top() or top > event.rect().bottom():
        return

    painter = QPainter(editor.viewport())
    painter.setPen(QPen(QColor(AppTheme.CURRENT_LINE_BORDER), 1))
    width = editor.viewport().width()
    painter.drawLine(0, top, width, top)
    painter.drawLine(0, bottom, width, bottom)
    painter.end()


def paint_indent_guides(editor, event) -> None:
    """Draw a vertical guide line at each indent level on every visible block."""
    tab_width = _cached_indent_step(editor)
    event_bottom = event.rect().bottom()
    content_offset = editor.contentOffset()

    painter = QPainter(editor.viewport())
    painter.setPen(QPen(QColor(AppTheme.INDENT_GUIDE_COLOR), 1))

    block = editor.firstVisibleBlock()
    while block.isValid():
        geometry = editor.blockBoundingGeometry(block).translated(content_offset)
        if geometry.top() > event_bottom:
            break

        text = block.text()
        if text.strip():
            stripped_len = len(text.lstrip())
            if stripped_len == len(text):
                # Non-empty but no leading whitespace — no guides on this row.
                block = block.next()
                continue
            indent_levels = (len(text) - stripped_len) // _INDENT_SIZE
        else:
            indent_levels = _next_block_indent_level(block)

        if indent_levels:
            top = int(geometry.top())
            bottom = int(geometry.bottom())
            for level in range(indent_levels):
                x = int(level * tab_width)
                painter.drawLine(x, top, x, bottom)

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
