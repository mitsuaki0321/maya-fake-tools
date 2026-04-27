"""
Multi-cursor input handler.

Drives the mouse and keyboard event interpretation for multi-cursor mode:
Ctrl+click to drop extra cursors, synchronized editing at every cursor, and
movement keys that keep all cursors in lock-step.

The handler doesn't own state; it reads/writes the multi-cursor attributes on
the editor and delegates lifecycle operations to ``MultiCursorController``.
"""

from __future__ import annotations

import contextlib

from ......lib_ui.qt_compat import QApplication, Qt, QTextCursor


class MultiCursorInputHandler:
    def __init__(self, editor, controller):
        self.editor = editor
        self.controller = controller

    # -------------------- Mouse --------------------

    def handle_mouse(self, event) -> bool:
        """Handle a mouse press. Returns True when the event was consumed."""
        editor = self.editor
        if not (event.modifiers() & Qt.ControlModifier):
            if editor.all_cursors:
                self.controller.clear()
                editor.is_ctrl_dragging = False
                editor.ctrl_drag_cursor = None
            return False

        try:
            click_pos = event.position().toPoint()  # PySide6
        except AttributeError:
            click_pos = event.pos()  # PySide2

        cursor = editor.cursorForPosition(click_pos)

        if event.buttons() & Qt.LeftButton:
            # Start a Ctrl+drag selection; register the current caret as the first cursor
            # so the drag adds a second one rather than replacing it.
            editor.ctrl_drag_start = cursor.position()
            editor.is_ctrl_dragging = True

            if not editor.all_cursors:
                main_cursor = editor.textCursor()
                editor.setCursorWidth(0)

                if main_cursor.hasSelection():
                    first_cursor = QTextCursor(editor.document())
                    first_cursor.setPosition(main_cursor.anchor())
                    first_cursor.setPosition(main_cursor.position(), QTextCursor.KeepAnchor)
                    editor.all_cursors.append(first_cursor)
                else:
                    first_cursor = QTextCursor(editor.document())
                    first_cursor.setPosition(main_cursor.position())
                    editor.all_cursors.append(first_cursor)

            editor.ctrl_drag_cursor = QTextCursor(editor.document())
            editor.ctrl_drag_cursor.setPosition(editor.ctrl_drag_start)

            editor.viewport().update()
            return True

        # Simple Ctrl+click (no drag) — drop a new cursor at the click point.
        if not editor.all_cursors:
            main_cursor = editor.textCursor()
            first_cursor = QTextCursor(editor.document())
            first_cursor.setPosition(main_cursor.position())
            editor.all_cursors.append(first_cursor)

        new_cursor = QTextCursor(editor.document())
        new_cursor.setPosition(cursor.position())
        editor.all_cursors.append(new_cursor)

        editor.viewport().update()
        with contextlib.suppress(Exception):
            editor.multi_cursor_status.emit(f"Added cursor (total: {len(editor.all_cursors)})")
        return True

    # -------------------- Keyboard --------------------

    def handle_keys(self, event) -> bool:
        """Dispatch text input and movement to every active cursor.

        Returns True when the event was consumed — the editor's ``keyPressEvent``
        must skip default handling in that case, otherwise Qt applies the key to
        the primary cursor on top of our per-cursor edits.
        """
        editor = self.editor
        if len(editor.all_cursors) <= 1:
            return False

        if event.key() == Qt.Key_Escape:
            self.controller.clear()
            return True

        text = event.text()
        handled = False

        undo_cursor = editor.textCursor()
        if editor.all_cursors:
            undo_cursor.setPosition(editor.all_cursors[0].position())
            editor.setTextCursor(undo_cursor)

        doc_cursor = QTextCursor(editor.document())
        doc_cursor.beginEditBlock()

        # Snapshot cursors into fresh objects so edits tracked by Qt update
        # positions without aliasing the stored list.
        new_cursors = []
        for c in editor.all_cursors:
            new_c = QTextCursor(editor.document())
            new_c.setPosition(c.anchor())
            new_c.setPosition(c.position(), QTextCursor.KeepAnchor if c.hasSelection() else QTextCursor.MoveAnchor)
            new_cursors.append(new_c)

        # Process from the end of the document backwards so earlier positions
        # don't shift under edits applied at later positions.
        sorted_cursors = sorted(new_cursors, key=lambda c: c.position(), reverse=True)

        is_paste = event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier
        paste_text = ""
        if is_paste:
            clipboard = QApplication.clipboard()
            if clipboard:
                paste_text = clipboard.text()

        for cursor in sorted_cursors:
            if is_paste and paste_text:
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertText(paste_text)
                handled = True

            elif text and text.isprintable():
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertText(text)
                handled = True

            elif event.key() == Qt.Key_Backspace:
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                else:
                    cursor.deletePreviousChar()
                handled = True

            elif event.key() == Qt.Key_Delete:
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                else:
                    cursor.deleteChar()
                handled = True

            elif event.key() == Qt.Key_Return:
                current_line_text = cursor.block().text()
                indent = len(current_line_text) - len(current_line_text.lstrip())
                indent_text = current_line_text[:indent] if indent > 0 else ""
                trimmed = current_line_text.rstrip()
                if trimmed and trimmed[-1] == ":":
                    indent_text += "    "
                cursor.insertText("\n" + indent_text)
                handled = True

            elif event.key() == Qt.Key_Tab:
                # Tab is applied as a separate pass outside this loop.
                continue

            elif event.key() == Qt.Key_Left:
                self._move_horizontal(cursor, event, QTextCursor.Left, QTextCursor.WordLeft, pick_start=True)
                handled = True

            elif event.key() == Qt.Key_Right:
                self._move_horizontal(cursor, event, QTextCursor.Right, QTextCursor.WordRight, pick_start=False)
                handled = True

            elif event.key() == Qt.Key_Up:
                if event.modifiers() & Qt.ShiftModifier:
                    cursor.movePosition(QTextCursor.Up, QTextCursor.KeepAnchor)
                else:
                    if cursor.hasSelection():
                        cursor.setPosition(cursor.position())
                    cursor.movePosition(QTextCursor.Up)
                handled = True

            elif event.key() == Qt.Key_Down:
                if event.modifiers() & Qt.ShiftModifier:
                    cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                else:
                    if cursor.hasSelection():
                        cursor.setPosition(cursor.position())
                    cursor.movePosition(QTextCursor.Down)
                handled = True

            elif event.key() == Qt.Key_Home:
                self._move_home(cursor, event)
                handled = True

            elif event.key() == Qt.Key_End:
                self._move_end(cursor, event)
                handled = True

            elif event.key() == Qt.Key_PageUp:
                mode = QTextCursor.KeepAnchor if event.modifiers() & Qt.ShiftModifier else QTextCursor.MoveAnchor
                cursor.movePosition(QTextCursor.PreviousBlock, mode, 10)
                handled = True

            elif event.key() == Qt.Key_PageDown:
                mode = QTextCursor.KeepAnchor if event.modifiers() & Qt.ShiftModifier else QTextCursor.MoveAnchor
                cursor.movePosition(QTextCursor.NextBlock, mode, 10)
                handled = True

        doc_cursor.endEditBlock()

        if event.key() == Qt.Key_Tab:
            self._handle_tab(event, sorted_cursors)
            return True

        if handled:
            updated_cursors = []
            for cursor in sorted_cursors[::-1]:
                new_cursor = QTextCursor(editor.document())
                if cursor.hasSelection():
                    new_cursor.setPosition(cursor.anchor())
                    new_cursor.setPosition(cursor.position(), QTextCursor.KeepAnchor)
                else:
                    new_cursor.setPosition(cursor.position())
                updated_cursors.append(new_cursor)

            editor.all_cursors = updated_cursors
            self.controller.merge_overlapping()

            if editor.all_cursors:
                main_cursor = QTextCursor(editor.document())
                main_cursor.setPosition(editor.all_cursors[0].position())
                editor.setTextCursor(main_cursor)

            editor.viewport().update()

        return handled

    # -------------------- Key helpers --------------------

    @staticmethod
    def _move_horizontal(cursor, event, char_op, word_op, pick_start: bool):
        """Unified Left/Right handling with word-jump and shift-select variants."""
        use_word = bool(event.modifiers() & Qt.ControlModifier)
        keep_anchor = bool(event.modifiers() & Qt.ShiftModifier)

        if keep_anchor:
            cursor.movePosition(word_op if use_word else char_op, QTextCursor.KeepAnchor)
            return

        if cursor.hasSelection():
            pivot = min(cursor.position(), cursor.anchor()) if pick_start else max(cursor.position(), cursor.anchor())
            cursor.setPosition(pivot)
        else:
            cursor.movePosition(word_op if use_word else char_op)

    def _move_home(self, cursor, event):
        """Home / Ctrl+Home with optional Shift-select and smart-Home toggle."""
        editor = self.editor
        keep_anchor = bool(event.modifiers() & Qt.ShiftModifier)
        use_document = bool(event.modifiers() & Qt.ControlModifier)

        if use_document:
            if keep_anchor:
                cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
            else:
                if cursor.hasSelection():
                    cursor.clearSelection()
                    cursor.setPosition(cursor.position())
                cursor.movePosition(QTextCursor.Start)
            return

        smart_home_pos = editor.get_first_non_whitespace_position(cursor)
        line_start_pos = cursor.block().position()
        target_pos = line_start_pos if cursor.position() == smart_home_pos else smart_home_pos

        if keep_anchor:
            cursor.setPosition(target_pos, QTextCursor.KeepAnchor)
        else:
            if cursor.hasSelection():
                cursor.clearSelection()
            cursor.setPosition(target_pos)

    @staticmethod
    def _move_end(cursor, event):
        """End / Ctrl+End with optional Shift-select."""
        keep_anchor = bool(event.modifiers() & Qt.ShiftModifier)
        use_document = bool(event.modifiers() & Qt.ControlModifier)

        if use_document:
            if keep_anchor:
                cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            else:
                if cursor.hasSelection():
                    cursor.setPosition(cursor.position())
                cursor.movePosition(QTextCursor.End)
            return

        if keep_anchor:
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        else:
            if cursor.hasSelection():
                cursor.setPosition(cursor.position())
            cursor.movePosition(QTextCursor.EndOfLine)

    def _handle_tab(self, event, sorted_cursors):
        """Tab / Shift+Tab applied across every cursor in a single undo block."""
        editor = self.editor
        doc_cursor = QTextCursor(editor.document())
        doc_cursor.beginEditBlock()

        if event.modifiers() & Qt.ShiftModifier:
            processed_lines = set()
            for cursor in editor.all_cursors:
                line_num = cursor.blockNumber()
                if line_num in processed_lines:
                    continue
                processed_lines.add(line_num)

                temp_cursor = QTextCursor(editor.document())
                temp_cursor.movePosition(QTextCursor.Start)
                for _ in range(line_num):
                    temp_cursor.movePosition(QTextCursor.NextBlock)
                temp_cursor.movePosition(QTextCursor.StartOfLine)

                line_text = temp_cursor.block().text()
                # Try 4-space, tab, 2-space, 1-space prefixes in order.
                for prefix_len, prefix in ((4, "    "), (1, "\t"), (2, "  "), (1, " ")):
                    if line_text.startswith(prefix):
                        temp_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, prefix_len)
                        temp_cursor.removeSelectedText()
                        break
        else:
            for cursor in sorted_cursors[::-1]:
                cursor.insertText("    ")

        doc_cursor.endEditBlock()
        editor.viewport().update()
