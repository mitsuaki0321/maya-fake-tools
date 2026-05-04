"""
Multi-cursor state transitions.

Owns the pure logic half of the multi-cursor feature: adding / removing cursors,
rectangle selection bookkeeping, and merging duplicates after movement.
Drawing and event handling live in sibling modules.

The controller holds a reference to the editor widget and reads/writes the
multi-cursor state attributes (``all_cursors``, ``search_text``, etc.) stored
on the editor instance. State lives on the editor so existing external
callers (``FindReplaceDialog``, etc.) keep working.
"""

from __future__ import annotations

import contextlib

from .......lib_ui.qt_compat import Qt, QTextCursor  # noqa: F401 — imported for type hints / cursor flags


class MultiCursorController:
    def __init__(self, editor):
        self.editor = editor

    # -------------------- Basic lifecycle --------------------

    def clear(self):
        """Exit multi-cursor mode and restore the standard single-cursor view."""
        editor = self.editor
        if editor.all_cursors:
            editor.last_cursor_position = editor.all_cursors[0].position()
            cursor = QTextCursor(editor.document())
            cursor.setPosition(editor.last_cursor_position)
            editor.setTextCursor(cursor)

        editor.all_cursors.clear()
        editor.search_text = ""
        editor.initial_selection_done = False

        editor.setCursorWidth(getattr(editor, "original_cursor_width", 1))
        editor.viewport().update()

        with contextlib.suppress(Exception):
            editor.multi_cursor_status.emit("Multi-cursor cleared")

    def merge_overlapping(self):
        """Deduplicate cursors that collapsed to the same range after movement.

        E.g. two cursors on the same line both pressing Home end up at the same
        column — without merging we'd keep duplicates and paint a fat caret.
        """
        editor = self.editor
        if len(editor.all_cursors) <= 1:
            return

        seen = set()
        merged = []
        for cursor in editor.all_cursors:
            if cursor.hasSelection():
                key = (min(cursor.anchor(), cursor.position()), max(cursor.anchor(), cursor.position()))
            else:
                key = (cursor.position(), cursor.position())
            if key not in seen:
                seen.add(key)
                merged.append(cursor)

        if len(merged) < len(editor.all_cursors):
            editor.all_cursors = merged
            if len(editor.all_cursors) <= 1:
                self.clear()

    # -------------------- Add occurrences --------------------

    def add_next_occurrence(self):
        """Ctrl+D — add the next occurrence of the current selection/word."""
        editor = self.editor
        current = editor.textCursor()

        if not editor.all_cursors:
            editor.last_cursor_position = current.position()
            editor.setCursorWidth(0)  # Hide the standard caret in multi-cursor mode

        if not editor.search_text or not editor.initial_selection_done:
            if current.hasSelection():
                editor.search_text = current.selectedText()
            else:
                current.select(QTextCursor.WordUnderCursor)
                if not current.hasSelection():
                    return
                editor.search_text = current.selectedText()
                editor.setTextCursor(current)

            first_cursor = QTextCursor(editor.document())
            first_cursor.setPosition(current.selectionStart())
            first_cursor.setPosition(current.selectionEnd(), QTextCursor.KeepAnchor)
            editor.all_cursors = [first_cursor]
            editor.initial_selection_done = True

            doc = editor.document()
            found = doc.find(editor.search_text, current.selectionEnd())
            if found.isNull():
                found = doc.find(editor.search_text, 0)

            if not found.isNull() and found.selectionStart() != current.selectionStart():
                if not found.block().isVisible() and hasattr(editor, "fold_manager"):
                    editor.fold_manager.unfold_containing(found.block().blockNumber())
                new_cursor = QTextCursor(editor.document())
                new_cursor.setPosition(found.selectionStart())
                new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
                editor.all_cursors.append(new_cursor)

            editor.viewport().update()

            with contextlib.suppress(Exception):
                if len(editor.all_cursors) > 1:
                    editor.multi_cursor_status.emit(f"Selected: '{editor.search_text}' ({len(editor.all_cursors)} occurrences)")
                else:
                    editor.multi_cursor_status.emit(f"Selected: '{editor.search_text}'")
            return

        # Subsequent Ctrl+D — find the next occurrence past the last cursor.
        doc = editor.document()
        if editor.all_cursors:
            last_cursor = editor.all_cursors[-1]
            search_from = last_cursor.selectionEnd() if last_cursor.hasSelection() else last_cursor.position()
        else:
            search_from = current.position()

        found = doc.find(editor.search_text, search_from)
        if found.isNull():
            found = doc.find(editor.search_text, 0)
            if not found.isNull():
                for existing in editor.all_cursors:
                    if existing.selectionStart() == found.selectionStart() and existing.selectionEnd() == found.selectionEnd():
                        with contextlib.suppress(Exception):
                            editor.multi_cursor_status.emit("All occurrences selected")
                        return

        if not found.isNull():
            if not found.block().isVisible() and hasattr(editor, "fold_manager"):
                editor.fold_manager.unfold_containing(found.block().blockNumber())
            new_cursor = QTextCursor(editor.document())
            new_cursor.setPosition(found.selectionStart())
            new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
            editor.all_cursors.append(new_cursor)
            editor.setTextCursor(found)
            editor.viewport().update()
            with contextlib.suppress(Exception):
                editor.multi_cursor_status.emit(f"Cursors: {len(editor.all_cursors)}")
        else:
            with contextlib.suppress(Exception):
                editor.multi_cursor_status.emit("No more occurrences")

    def select_all_occurrences(self):
        """Ctrl+Shift+L — select every occurrence of the current word."""
        editor = self.editor
        current = editor.textCursor()
        if not current.hasSelection():
            current.select(QTextCursor.WordUnderCursor)

        text = current.selectedText()
        if not text:
            return

        editor.search_text = text
        editor.all_cursors.clear()

        doc = editor.document()
        pos = 0
        while True:
            found = doc.find(text, pos)
            if found.isNull():
                break
            if not found.block().isVisible() and hasattr(editor, "fold_manager"):
                editor.fold_manager.unfold_containing(found.block().blockNumber())
            new_cursor = QTextCursor(editor.document())
            new_cursor.setPosition(found.selectionStart())
            new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
            editor.all_cursors.append(new_cursor)
            pos = found.selectionEnd()

        if editor.all_cursors:
            editor.setTextCursor(editor.all_cursors[-1])

        editor.viewport().update()
        with contextlib.suppress(Exception):
            editor.multi_cursor_status.emit(f"Selected {len(editor.all_cursors)} occurrences")

    def add_cursors_to_line_ends(self):
        """Alt+Shift+I — add a cursor at the end of every line in the selection."""
        editor = self.editor
        current_cursor = editor.textCursor()
        if not current_cursor.hasSelection():
            with contextlib.suppress(Exception):
                editor.multi_cursor_status.emit("No selection for line ends")
            return

        start = current_cursor.selectionStart()
        end = current_cursor.selectionEnd()
        editor.all_cursors.clear()

        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)

        while cursor.position() <= end:
            line_end_cursor = QTextCursor(cursor)
            line_end_cursor.movePosition(QTextCursor.EndOfLine)
            if start <= line_end_cursor.position() <= end:
                new_cursor = QTextCursor(editor.document())
                new_cursor.setPosition(line_end_cursor.position())
                editor.all_cursors.append(new_cursor)
            if not cursor.movePosition(QTextCursor.Down):
                break

        editor.viewport().update()
        with contextlib.suppress(Exception):
            editor.multi_cursor_status.emit(f"Added {len(editor.all_cursors)} cursors at line ends")

    # -------------------- Rectangle selection --------------------

    def start_rectangle_selection(self, event):
        """Begin a middle-click rectangle selection."""
        editor = self.editor
        self.clear()
        editor.setCursorWidth(0)

        pos = self._event_pos(event)
        cursor = editor.cursorForPosition(pos)
        editor.rect_selection_start = cursor.position()
        editor.rect_selection_end = cursor.position()
        editor.is_rect_selecting = True
        editor.rect_start_col = self._virtual_column(pos, cursor.block())
        editor.rect_end_col = editor.rect_start_col
        editor.rect_selection_left_to_right = True

    def update_rectangle_selection(self, event):
        """Extend the active rectangle selection to the current cursor position."""
        editor = self.editor
        if not editor.is_rect_selecting:
            return

        pos = self._event_pos(event)
        cursor = editor.cursorForPosition(pos)
        editor.rect_selection_end = cursor.position()
        editor.rect_end_col = self._virtual_column(pos, cursor.block())
        editor.rect_selection_left_to_right = editor.rect_start_col <= editor.rect_end_col
        editor.viewport().update()

    def finalize_rectangle_selection(self, event):
        """Convert the selected rectangle into per-line cursors / selections."""
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

        editor.all_cursors.clear()
        for line_num in range(start_line, end_line + 1):
            block = editor.document().findBlockByNumber(line_num)
            line_text = block.text()
            line_len = len(line_text)
            if line_len == 0 or line_text.strip() == "":
                continue

            actual_left = min(left_col, line_len)
            actual_right = min(right_col, line_len)

            if actual_right > actual_left:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + actual_left)
                new_cursor.setPosition(block.position() + actual_right, QTextCursor.KeepAnchor)
                editor.all_cursors.append(new_cursor)
            elif left_col > line_len or actual_left == line_len and left_col < right_col:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + line_len)
                editor.all_cursors.append(new_cursor)

        editor.is_rect_selecting = False
        editor.rect_selection_start = None
        editor.rect_selection_end = None
        editor.rect_start_col = 0
        editor.rect_end_col = 0
        editor.viewport().update()

        with contextlib.suppress(Exception):
            editor.multi_cursor_status.emit(f"Added {len(editor.all_cursors)} cursors from rectangle selection")

    # -------------------- Event position helpers --------------------

    @staticmethod
    def _event_pos(event):
        """Return ``event.pos()`` equivalent across PySide2 (pos()) and PySide6 (position())."""
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _virtual_column(self, pos, block) -> int:
        """Compute the on-screen character column for ``pos`` relative to ``block``.

        Uses the width of a space character so rectangle selections can extend
        past the end of a short line (VSCode / Sublime behaviour).
        """
        editor = self.editor
        line_start_cursor = QTextCursor(block)
        line_start_cursor.movePosition(QTextCursor.StartOfLine)
        line_start_rect = editor.cursorRect(line_start_cursor)

        char_width = editor.fontMetrics().horizontalAdvance(" ")
        if char_width > 0:
            return max(0, (pos.x() - line_start_rect.x()) // char_width)
        return (editor.cursorForPosition(pos).position()) - block.position()
