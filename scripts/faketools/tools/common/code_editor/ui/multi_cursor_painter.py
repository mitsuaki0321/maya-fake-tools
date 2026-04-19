"""
Multi-cursor painter.

Owns all ``QPainter`` calls for multi-cursor mode: the extra carets, the
per-cursor selections, and the in-progress Ctrl+drag / middle-click rectangle
selection overlays. Called from the editor's ``paintEvent``.
"""

from __future__ import annotations

from .....lib_ui.qt_compat import QRect, Qt, QTextCursor


class MultiCursorPainter:
    def __init__(self, editor):
        self.editor = editor

    def paint(self, painter):
        """Draw all multi-cursor visuals. Safe to call unconditionally."""
        editor = self.editor
        if len(editor.all_cursors) <= 1 and not editor.is_ctrl_dragging and not editor.is_rect_selecting:
            return

        if editor.is_rect_selecting and editor.rect_selection_start is not None and editor.rect_selection_end is not None:
            self._draw_rectangle_selection(painter)

        if editor.is_ctrl_dragging and editor.ctrl_drag_cursor and editor.ctrl_drag_cursor.hasSelection():
            self._draw_cursor_selection(painter, editor.ctrl_drag_cursor)

        for cursor in editor.all_cursors:
            cursor_rect = editor.cursorRect(cursor)

            painter.setPen(Qt.NoPen)
            painter.setBrush(editor.multi_cursor_color)

            cursor_line_rect = QRect(cursor_rect.x(), cursor_rect.y(), 2, cursor_rect.height())
            painter.fillRect(cursor_line_rect, painter.brush())

            if cursor.hasSelection():
                self._draw_cursor_selection(painter, cursor)

    def _draw_cursor_selection(self, painter, cursor):
        """Fill the highlight for one cursor's selection, across line breaks."""
        editor = self.editor
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()

        start_cursor = QTextCursor(editor.document())
        start_cursor.setPosition(selection_start)
        end_cursor = QTextCursor(editor.document())
        end_cursor.setPosition(selection_end)

        start_rect = editor.cursorRect(start_cursor)
        end_rect = editor.cursorRect(end_cursor)

        start_block = start_cursor.blockNumber()
        end_block = end_cursor.blockNumber()

        if start_block == end_block:
            selection_rect = QRect(
                start_rect.x(),
                start_rect.y(),
                end_rect.x() - start_rect.x(),
                start_rect.height(),
            )
            painter.fillRect(selection_rect, editor.multi_selection_color)
            return

        temp_cursor = QTextCursor(editor.document())

        # First line: from selection start to EOL
        temp_cursor.setPosition(selection_start)
        temp_cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        first_line_end = editor.cursorRect(temp_cursor)
        painter.fillRect(
            QRect(start_rect.x(), start_rect.y(), first_line_end.x() - start_rect.x(), start_rect.height()),
            editor.multi_selection_color,
        )

        # Interior lines: full line width
        for block_num in range(start_block + 1, end_block):
            temp_cursor.setPosition(editor.document().findBlockByNumber(block_num).position())
            line_start_rect = editor.cursorRect(temp_cursor)
            temp_cursor.movePosition(QTextCursor.EndOfLine)
            line_end_rect = editor.cursorRect(temp_cursor)
            painter.fillRect(
                QRect(
                    line_start_rect.x(),
                    line_start_rect.y(),
                    line_end_rect.x() - line_start_rect.x(),
                    line_start_rect.height(),
                ),
                editor.multi_selection_color,
            )

        # Last line: from SOL to selection end
        temp_cursor.setPosition(editor.document().findBlockByNumber(end_block).position())
        last_line_start = editor.cursorRect(temp_cursor)
        painter.fillRect(
            QRect(
                last_line_start.x(),
                last_line_start.y(),
                end_rect.x() - last_line_start.x(),
                last_line_start.height(),
            ),
            editor.multi_selection_color,
        )

    def _draw_rectangle_selection(self, painter):
        """Shade the in-progress rectangle-selection bounds during middle-drag."""
        editor = self.editor
        if not editor.is_rect_selecting:
            return

        start_cursor = QTextCursor(editor.document())
        start_cursor.setPosition(editor.rect_selection_start)
        end_cursor = QTextCursor(editor.document())
        end_cursor.setPosition(editor.rect_selection_end)

        left_col = min(editor.rect_start_col, editor.rect_end_col)
        right_col = max(editor.rect_start_col, editor.rect_end_col)
        start_line = min(start_cursor.blockNumber(), end_cursor.blockNumber())
        end_line = max(start_cursor.blockNumber(), end_cursor.blockNumber())

        for line_num in range(start_line, end_line + 1):
            block = editor.document().findBlockByNumber(line_num)
            line_text = block.text()
            line_len = len(line_text)
            if line_len == 0:
                continue

            actual_left = min(left_col, line_len)
            actual_right = min(right_col, line_len)

            if actual_right > actual_left:
                left_cursor = QTextCursor(block)
                left_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_left)
                left_rect = editor.cursorRect(left_cursor)

                right_cursor = QTextCursor(block)
                right_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_right)
                right_rect = editor.cursorRect(right_cursor)

                selection_rect = QRect(
                    left_rect.x(),
                    left_rect.y(),
                    right_rect.x() - left_rect.x(),
                    left_rect.height(),
                )
                painter.fillRect(selection_rect, editor.multi_selection_color)
            elif left_col > line_len or (actual_left == line_len and left_col < right_col):
                end_rect_cursor = QTextCursor(block)
                end_rect_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, line_len)
                end_rect = editor.cursorRect(end_rect_cursor)
                painter.fillRect(
                    QRect(end_rect.x(), end_rect.y(), 2, end_rect.height()),
                    editor.multi_selection_color,
                )
