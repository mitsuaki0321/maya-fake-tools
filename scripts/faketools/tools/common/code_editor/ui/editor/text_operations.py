"""
Text operations mixin for the Python editor.

Single-cursor line-wise operations: duplicate, delete, move up/down, select
line, the Smart Home helper, and Tab / Shift+Tab / Backspace indent editing.
Multi-cursor equivalents live in the ``multi_cursor`` package.
"""

from ......lib_ui.qt_compat import QTextCursor
from .word_navigation import next_word_position, previous_word_position


class EditorTextOperationsMixin:
    """Mixin providing text operation methods for the editor."""

    def _unfold_at_cursor(self):
        """Unfold any fold region at the current cursor position.

        Called before line operations to prevent operating on hidden blocks.
        """
        if hasattr(self, "fold_manager"):
            block_number = self.textCursor().blockNumber()
            if self.fold_manager.is_folded(block_number):
                self.fold_manager.unfold(block_number)

    def get_first_non_whitespace_position(self, cursor):
        """
        Get the position of the first non-whitespace character in the current line.

        Args:
            cursor: QTextCursor positioned on the target line

        Returns:
            int: Position of first non-whitespace character, or line start if line is all whitespace
        """
        # Get the current block (line)
        block = cursor.block()
        line_text = block.text()
        line_start = block.position()

        # Find the first non-whitespace character
        for i, char in enumerate(line_text):
            if char not in (" ", "\t"):
                return line_start + i

        # If line is all whitespace, return line start
        return line_start

    def duplicate_current_line(self):
        """Duplicate the current line (Ctrl+D)."""
        self._unfold_at_cursor()
        cursor = self.textCursor()

        # Save current position
        original_position = cursor.position()

        # Select the entire current line
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)

        # Get the line text
        line_text = cursor.selectedText()

        # Move to end of line and insert newline + duplicated text
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.insertText("\n" + line_text)

        # Restore cursor to original position (on the original line)
        cursor.setPosition(original_position)
        self.setTextCursor(cursor)

    def delete_current_line(self):
        """Delete the current line (Ctrl+Shift+K)."""
        self._unfold_at_cursor()
        cursor = self.textCursor()

        # Select the entire current line including newline
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)

        # If we're at the last line, select to end of document
        if cursor.atEnd():
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)

        # Delete the selected text
        cursor.removeSelectedText()
        self.setTextCursor(cursor)

    def _move_blocks(self, delta):
        """Move the current line or block-selection up (delta=-1) or down (+1) by one block.

        Works on whole blocks via :class:`QTextBlock` rather than ``QTextCursor.Down``,
        which fails or stops short at the last block (especially when the document
        has no trailing newline) and used to corrupt the swap near document edges.
        """
        self._unfold_at_cursor()
        cursor = self.textCursor()
        doc = self.document()
        has_selection = cursor.hasSelection()
        forward_selection = cursor.position() >= cursor.anchor()

        if has_selection:
            sel_start = cursor.selectionStart()
            sel_end = cursor.selectionEnd()
            first_no = doc.findBlock(sel_start).blockNumber()
            end_block = doc.findBlock(sel_end)
            # Selection ending exactly at the start of the next block (caret placed
            # right after the trailing paragraph separator) must not pull that
            # block into the move range.
            if sel_end > sel_start and end_block.position() == sel_end:
                last_no = end_block.blockNumber() - 1
            else:
                last_no = end_block.blockNumber()
        else:
            first_no = last_no = cursor.block().blockNumber()
            offset_in_block = cursor.positionInBlock()

        if delta < 0:
            target_no = first_no - 1
            if target_no < 0:
                return
            range_start_no = target_no
            range_end_no = last_no
        else:
            target_no = last_no + 1
            if target_no >= doc.blockCount():
                return
            range_start_no = first_no
            range_end_no = target_no

        block_texts = [doc.findBlockByNumber(i).text() for i in range(range_start_no, range_end_no + 1)]
        if delta < 0:
            # Target was the first block; rotate it to the end.
            block_texts.append(block_texts.pop(0))
        else:
            # Target was the last block; rotate it to the front.
            block_texts.insert(0, block_texts.pop())
        new_text = " ".join(block_texts)

        range_start_block = doc.findBlockByNumber(range_start_no)
        range_end_block = doc.findBlockByNumber(range_end_no)

        edit_cursor = QTextCursor(range_start_block)
        end_cursor = QTextCursor(range_end_block)
        end_cursor.movePosition(QTextCursor.EndOfBlock)
        edit_cursor.beginEditBlock()
        edit_cursor.setPosition(end_cursor.position(), QTextCursor.KeepAnchor)
        edit_cursor.insertText(new_text)
        edit_cursor.endEditBlock()

        new_first_block = doc.findBlockByNumber(first_no + delta)
        new_last_block = doc.findBlockByNumber(last_no + delta)
        new_cursor = self.textCursor()
        if has_selection:
            start_pos = new_first_block.position()
            end_pos = new_last_block.position() + len(new_last_block.text())
            if forward_selection:
                new_cursor.setPosition(start_pos)
                new_cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
            else:
                new_cursor.setPosition(end_pos)
                new_cursor.setPosition(start_pos, QTextCursor.KeepAnchor)
        else:
            new_pos = new_first_block.position() + min(offset_in_block, len(new_first_block.text()))
            new_cursor.setPosition(new_pos)
        self.setTextCursor(new_cursor)

    def move_line_up(self):
        """Move current line or selection up (Ctrl+Shift+Up)."""
        self._move_blocks(-1)

    def move_line_down(self):
        """Move current line or selection down (Ctrl+Shift+Down)."""
        self._move_blocks(1)

    def select_next_occurrence(self):
        """Ctrl+D — thin alias that forwards to the multi-cursor implementation."""
        # CodeEditor always inherits from MultiCursorMixin, so add_next_occurrence
        # is defined. Kept as a separate method purely because ``editor_shortcuts``
        # binds Ctrl+D to this name and we don't want to touch the shortcut table.
        self.add_next_occurrence()

    def select_current_line(self):
        """Select the entire current line (Ctrl+L). If lines already selected, extend selection."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # If there's already a selection, extend it to include the next line
            # Save the start position
            selection_start = cursor.selectionStart()

            # Move to end of current selection
            cursor.setPosition(cursor.selectionEnd())
            cursor.movePosition(QTextCursor.EndOfLine)

            # Move to next line if possible
            if not cursor.atEnd():
                cursor.movePosition(QTextCursor.Right)  # Move to start of next line
                cursor.movePosition(QTextCursor.EndOfLine)  # Move to end of next line
                # Include newline if not at end of document
                if not cursor.atEnd():
                    cursor.movePosition(QTextCursor.Right)

            # Create selection from start to new end position
            new_end = cursor.position()
            cursor.setPosition(selection_start)
            cursor.setPosition(new_end, QTextCursor.KeepAnchor)

        else:
            # No selection, select current line
            # Move to start of current line
            cursor.movePosition(QTextCursor.StartOfLine)

            # Select to end of line, including the newline character
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)

            # Include newline if not at end of document
            if not cursor.atEnd():
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)

        self.setTextCursor(cursor)

    # -------------------- Indent editing (Tab / Shift+Tab / Backspace) --------------------

    def handle_tab_key(self):
        """Handle Tab key press."""
        if self.textCursor().hasSelection():
            self.indent_selection()
        else:
            self.insertPlainText("    ")

    def handle_backtab_key(self):
        """Handle Shift+Tab key press."""
        if self.textCursor().hasSelection():
            self.unindent_selection()
        else:
            self.remove_indent_at_cursor()

    def indent_selection(self):
        """Indent all selected lines by four spaces."""
        cursor = self.textCursor()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        cursor.beginEditBlock()
        for line_num in range(start_line, end_line + 1):
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.insertText("    ")
        cursor.endEditBlock()

    def unindent_selection(self):
        """Unindent all selected lines (up to 4 leading spaces per line)."""
        cursor = self.textCursor()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        cursor.beginEditBlock()
        for line_num in range(start_line, end_line + 1):
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            cursor.movePosition(QTextCursor.StartOfLine)

            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()

            spaces_to_remove = 0
            for char in line_text:
                if char == " " and spaces_to_remove < 4:
                    spaces_to_remove += 1
                else:
                    break

            if spaces_to_remove > 0:
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, spaces_to_remove)
                cursor.removeSelectedText()
        cursor.endEditBlock()

    def remove_indent_at_cursor(self):
        """Remove up to four leading spaces between line start and the cursor."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)

        original_pos = self.textCursor().position()
        line_start = cursor.position()

        spaces_count = 0
        pos = line_start
        while pos < original_pos and pos < line_start + 4:
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            if cursor.selectedText() == " ":
                spaces_count += 1
                pos += 1
            else:
                break

        if spaces_count > 0:
            cursor.setPosition(line_start)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, spaces_count)
            cursor.removeSelectedText()

    # -------------------- Word navigation (Ctrl+Left/Right) --------------------

    def _word_step(self, forward: bool, keep_anchor: bool):
        """Move the caret one IDE-style word step, replacing Qt's default jumps."""
        cursor = self.textCursor()
        text = self.toPlainText()
        pos = cursor.position()
        target = next_word_position(text, pos) if forward else previous_word_position(text, pos)

        if keep_anchor:
            cursor.setPosition(target, QTextCursor.KeepAnchor)
        else:
            cursor.setPosition(target)
        self.setTextCursor(cursor)

    def move_word_left(self):
        self._word_step(forward=False, keep_anchor=False)

    def move_word_right(self):
        self._word_step(forward=True, keep_anchor=False)

    def select_word_left(self):
        self._word_step(forward=False, keep_anchor=True)

    def select_word_right(self):
        self._word_step(forward=True, keep_anchor=True)

    def handle_backspace_key(self):
        """Handle Backspace with smart indent removal (4-space groups)."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            cursor.deletePreviousChar()
            return

        current_pos = cursor.position()

        cursor.movePosition(QTextCursor.StartOfLine)
        line_start_pos = cursor.position()

        cursor.setPosition(line_start_pos)
        cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
        text_before_cursor = cursor.selectedText()

        if text_before_cursor and all(c == " " for c in text_before_cursor):
            spaces_count = len(text_before_cursor)
            if spaces_count > 0:
                spaces_to_remove = min(4, spaces_count % 4 if spaces_count % 4 != 0 else 4)
                cursor = self.textCursor()
                cursor.setPosition(current_pos - spaces_to_remove)
                cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                return

        cursor = self.textCursor()
        cursor.deletePreviousChar()

    # -------------------- Comment toggle (Ctrl+/) --------------------

    def toggle_line_comment(self):
        """Toggle line comments using the editor's :class:`LanguageProfile`.

        Graceful no-op for languages whose profile leaves
        ``line_comment`` / ``line_comment_with_space`` at ``None``. Dispatches
        to :func:`multi_cursor.comment.toggle_line_comment_multi_cursor` when
        extra cursors are active so multi-cursor edits stay synchronized.
        """
        prefix = self.language.line_comment
        prefix_with_space = self.language.line_comment_with_space
        if prefix is None or prefix_with_space is None:
            return

        if getattr(self, "all_cursors", None):
            from .multi_cursor.comment import toggle_line_comment_multi_cursor

            toggle_line_comment_multi_cursor(self, prefix, prefix_with_space)
            return

        cursor = self.textCursor()

        if cursor.hasSelection():
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
        else:
            start_pos = cursor.position()
            end_pos = cursor.position()

        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        cursor.beginEditBlock()

        try:
            all_commented = True
            for line_num in range(start_line, end_line + 1):
                cursor.movePosition(QTextCursor.Start)
                for _ in range(line_num):
                    cursor.movePosition(QTextCursor.NextBlock)
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                line_text = cursor.selectedText().lstrip()

                if line_text and not line_text.startswith(prefix):
                    all_commented = False
                    break

            for line_num in range(start_line, end_line + 1):
                cursor.movePosition(QTextCursor.Start)
                for _ in range(line_num):
                    cursor.movePosition(QTextCursor.NextBlock)
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                line_text = cursor.selectedText()

                if not line_text.strip():
                    continue

                cursor.movePosition(QTextCursor.StartOfLine)

                if all_commented:
                    stripped = line_text.lstrip()
                    if stripped.startswith(prefix_with_space):
                        comment_pos = line_text.find(prefix_with_space)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, comment_pos)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(prefix_with_space))
                        cursor.removeSelectedText()
                    elif stripped.startswith(prefix):
                        comment_pos = line_text.find(prefix)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, comment_pos)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(prefix))
                        cursor.removeSelectedText()
                else:
                    first_non_space = len(line_text) - len(line_text.lstrip())
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, first_non_space)
                    cursor.insertText(prefix_with_space)

        finally:
            cursor.endEditBlock()
