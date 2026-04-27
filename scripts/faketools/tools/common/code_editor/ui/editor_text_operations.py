"""
Text operations mixin for the Python editor.

Single-cursor line-wise operations: duplicate, delete, move up/down, select
line, the Smart Home helper, and Tab / Shift+Tab / Backspace indent editing.
Multi-cursor equivalents live in the ``multi_cursor`` package.
"""

from .....lib_ui.qt_compat import QTextCursor


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

    def move_line_up(self):
        """Move current line or selection up (Ctrl+Shift+Up)."""
        self._unfold_at_cursor()
        cursor = self.textCursor()

        # Use single undo transaction for atomic operation
        cursor.beginEditBlock()

        # Determine if we have a selection
        if cursor.hasSelection():
            # Get selection boundaries and expand to full lines
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()

            # Move to start of first selected line
            cursor.setPosition(start_pos)
            cursor.movePosition(QTextCursor.StartOfLine)
            first_line_start = cursor.position()

            # Check if we're already at the first line
            if first_line_start == 0:
                cursor.endEditBlock()
                return

            # Move to start of line after last selected line
            cursor.setPosition(end_pos)
            if cursor.positionInBlock() > 0:  # If not at start of line, move to next line
                cursor.movePosition(QTextCursor.Down)
            cursor.movePosition(QTextCursor.StartOfLine)
            line_after_end = cursor.position()

            # Select complete lines including final newline
            cursor.setPosition(first_line_start)
            cursor.setPosition(line_after_end, QTextCursor.KeepAnchor)
            selected_text = cursor.selectedText()

            # Remove selected lines
            cursor.removeSelectedText()

            # Move up one line and insert
            cursor.movePosition(QTextCursor.Up)
            cursor.movePosition(QTextCursor.StartOfLine)
            insert_pos = cursor.position()
            cursor.insertText(selected_text)

            # Position cursor at start of moved text with proper selection
            cursor.setPosition(insert_pos)
            cursor.setPosition(insert_pos + len(selected_text) - 1, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)

        else:
            # Single line mode
            cursor = self.textCursor()

            # Save cursor position in line
            cursor.movePosition(QTextCursor.StartOfLine)
            line_start = cursor.position()
            cursor = self.textCursor()  # Restore original position
            offset_in_line = cursor.position() - line_start

            # Check if already at first line
            cursor.movePosition(QTextCursor.StartOfLine)
            if cursor.position() == 0:
                cursor.endEditBlock()
                return

            # Select current line completely
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()

            # Remove current line
            cursor.removeSelectedText()

            # Insert line above previous line
            cursor.movePosition(QTextCursor.Up)
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.insertText(line_text)

            # Restore cursor position on the moved line
            cursor.movePosition(QTextCursor.Up)  # Go back to the inserted line
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, offset_in_line)
            self.setTextCursor(cursor)

        # End the undo transaction
        cursor.endEditBlock()

    def move_line_down(self):
        """Move current line or selection down (Ctrl+Shift+Down)."""
        self._unfold_at_cursor()
        cursor = self.textCursor()

        # Use single undo transaction for atomic operation
        cursor.beginEditBlock()

        # Determine if we have a selection
        if cursor.hasSelection():
            # Get selection boundaries and expand to full lines
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()

            # Move to start of first selected line
            cursor.setPosition(start_pos)
            cursor.movePosition(QTextCursor.StartOfLine)
            first_line_start = cursor.position()

            # Move to start of line after last selected line
            cursor.setPosition(end_pos)
            if cursor.positionInBlock() > 0:  # If not at start of line, move to next line
                cursor.movePosition(QTextCursor.Down)
            cursor.movePosition(QTextCursor.StartOfLine)
            line_after_end = cursor.position()

            # Check if we're at the last line
            if cursor.atEnd():
                cursor.endEditBlock()
                return

            # Select complete lines including final newline
            cursor.setPosition(first_line_start)
            cursor.setPosition(line_after_end, QTextCursor.KeepAnchor)
            selected_text = cursor.selectedText()

            # Remove selected lines
            cursor.removeSelectedText()

            # Move down one line and insert
            cursor.movePosition(QTextCursor.Down)
            cursor.movePosition(QTextCursor.StartOfLine)
            insert_pos = cursor.position()
            cursor.insertText(selected_text)

            # Position cursor at start of moved text with proper selection
            cursor.setPosition(insert_pos)
            cursor.setPosition(insert_pos + len(selected_text) - 1, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)

        else:
            # Single line mode
            cursor = self.textCursor()

            # Save cursor position in line
            cursor.movePosition(QTextCursor.StartOfLine)
            line_start = cursor.position()
            cursor = self.textCursor()  # Restore original position
            offset_in_line = cursor.position() - line_start

            # Check if already at last line
            cursor.movePosition(QTextCursor.EndOfLine)
            if cursor.atEnd():
                cursor.endEditBlock()
                return

            # Select current line completely
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()

            # Remove current line
            cursor.removeSelectedText()

            # Insert line below next line
            cursor.movePosition(QTextCursor.Down)
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.insertText(line_text)

            # Restore cursor position on the moved line
            cursor.movePosition(QTextCursor.Up)  # Go back to the inserted line
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, offset_in_line)
            self.setTextCursor(cursor)

        # End the undo transaction
        cursor.endEditBlock()

    def select_next_occurrence(self):
        """Ctrl+D — thin alias that forwards to the multi-cursor implementation."""
        # PythonEditor always inherits from MultiCursorMixin, so add_next_occurrence
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
