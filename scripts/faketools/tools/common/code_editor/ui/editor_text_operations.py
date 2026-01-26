"""
Text operations mixin for the Python editor.
Handles line operations, multi-selection, and text manipulation.
"""

from .....lib_ui.qt_compat import QTextCharFormat, QTextCursor, QTextEdit

# SimpleRenameDialog import removed - F2 feature removed


class EditorTextOperationsMixin:
    """Mixin providing text operation methods for the editor."""

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
        """Select next occurrence of current selection (Ctrl+D)."""
        # Delegate to the new multi-cursor implementation
        if hasattr(self, "add_next_occurrence"):
            self.add_next_occurrence()
        else:
            # Fallback to old implementation if multi-cursor mixin not available
            cursor = self.textCursor()

            # Initialize multiple selections if not exists
            if not hasattr(self, "_multi_selections"):
                self._multi_selections = []

            # If no selection, select word under cursor AND find next occurrence
            if not cursor.hasSelection():
                cursor.select(QTextCursor.WordUnderCursor)
                if not cursor.hasSelection():  # Nothing to select
                    return

                # Set the cursor with the selection to make it visible
                self.setTextCursor(cursor)

                # Get the selected text
                selected_text = cursor.selectedText()
                if not selected_text.strip():  # Empty or whitespace only
                    return

                # Initialize first selection
                self._multi_selections = [
                    {
                        "start": cursor.selectionStart(),
                        "end": cursor.selectionEnd(),
                        "text": selected_text,
                    },
                ]

                # Immediately find and add the next occurrence
                document = self.document()
                next_cursor = document.find(selected_text, cursor.selectionEnd())

                # If not found after current position, try from beginning
                if next_cursor.isNull():
                    next_cursor = document.find(selected_text, 0)

                # Add next occurrence if found and different from current
                if not next_cursor.isNull():
                    next_start = next_cursor.selectionStart()
                    next_end = next_cursor.selectionEnd()

                    # Check if it's not the same as current selection
                    if next_start != cursor.selectionStart():
                        self._multi_selections.append(
                            {
                                "start": next_start,
                                "end": next_end,
                                "text": selected_text,
                            },
                        )

                self._highlight_selections()
                return

            # Get currently selected text
            selected_text = cursor.selectedText()
            if not selected_text.strip():
                return

            # If this is the first Ctrl+D on a selection, initialize multi-selection AND find next
            if not self._multi_selections:
                self._multi_selections = [
                    {
                        "start": cursor.selectionStart(),
                        "end": cursor.selectionEnd(),
                        "text": selected_text,
                    },
                ]

                # Immediately find and add the next occurrence on first Ctrl+D
                document = self.document()
                next_cursor = document.find(selected_text, cursor.selectionEnd())

                # If not found after current position, try from beginning
                if next_cursor.isNull():
                    next_cursor = document.find(selected_text, 0)

                # Add next occurrence if found and different from current
                if not next_cursor.isNull():
                    next_start = next_cursor.selectionStart()
                    next_end = next_cursor.selectionEnd()

                    # Check if it's not the same as current selection
                    if next_start != cursor.selectionStart():
                        self._multi_selections.append(
                            {
                                "start": next_start,
                                "end": next_end,
                                "text": selected_text,
                            },
                        )

                self._highlight_selections()
                return

            # Find next occurrence after the last selection (for subsequent Ctrl+D presses)
            last_selection = max(self._multi_selections, key=lambda x: x["end"])
            search_from = last_selection["end"]

            # Search for next occurrence
            document = self.document()
            next_cursor = document.find(selected_text, search_from)

            # If not found from current position, search from beginning
            if next_cursor.isNull():
                next_cursor = document.find(selected_text, 0)

            # If still not found or it's one we already have, do nothing
            if next_cursor.isNull():
                return

            # Check if this occurrence is already selected
            new_start = next_cursor.selectionStart()
            new_end = next_cursor.selectionEnd()

            for selection in self._multi_selections:
                if selection["start"] == new_start and selection["end"] == new_end:
                    return  # Already selected

            # Add new selection
            self._multi_selections.append({"start": new_start, "end": new_end, "text": selected_text})

            # Update visual highlighting
            self._highlight_selections()

    def _highlight_selections(self):
        """Highlight all multi-selections."""
        if not hasattr(self, "_multi_selections") or not self._multi_selections:
            return

        # Clear previous extra selections
        self.setExtraSelections([])

        # Create highlight format
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(self.palette().color(self.palette().ColorRole.Highlight))
        highlight_format.setForeground(self.palette().color(self.palette().ColorRole.HighlightedText))

        # Create extra selections for highlighting
        extra_selections = []
        for selection in self._multi_selections:
            extra_selection = QTextEdit.ExtraSelection()
            extra_selection.format = highlight_format

            cursor = self.textCursor()
            cursor.setPosition(selection["start"])
            cursor.setPosition(selection["end"], QTextCursor.KeepAnchor)
            extra_selection.cursor = cursor

            extra_selections.append(extra_selection)

        self.setExtraSelections(extra_selections)

        # Set main cursor to last selection
        if self._multi_selections:
            last_selection = self._multi_selections[-1]
            cursor = self.textCursor()
            cursor.setPosition(last_selection["start"])
            cursor.setPosition(last_selection["end"], QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)

        # Clear selections after rename
        self._clear_multi_selections()

    def _replace_multi_selections_with_text(self, replacement_text):
        """Replace all multi-selected text with the given text."""
        if not hasattr(self, "_multi_selections") or not self._multi_selections:
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()

        try:
            # Sort selections by position (from end to start to avoid position shifts)
            sorted_selections = sorted(self._multi_selections, key=lambda x: x["start"], reverse=True)

            # Replace each selection
            for selection in sorted_selections:
                # Create cursor for this selection
                sel_cursor = self.textCursor()
                sel_cursor.setPosition(selection["start"])
                sel_cursor.setPosition(selection["end"], QTextCursor.KeepAnchor)

                # Replace the selected text
                sel_cursor.insertText(replacement_text)

        finally:
            cursor.endEditBlock()

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

    def _clear_multi_selections(self):
        """Clear all multi-selections."""
        if hasattr(self, "_multi_selections"):
            self._multi_selections = []
        self.setExtraSelections([])
