"""
Multi-cursor functionality mixin for PythonEditor.
Provides VSCode-style multi-cursor editing capabilities.
"""

import contextlib

from .....lib_ui.qt_compat import QApplication, QColor, QKeySequence, QRect, QShortcut, Qt, QTextCursor, Signal


class MultiCursorMixin:
    """
    Mixin class that adds multi-cursor functionality to QPlainTextEdit-based editors.

    Features:
        - Ctrl+Click to add cursors
        - Ctrl+D to add next occurrence
        - Ctrl+Shift+L to select all occurrences
        - Alt+Shift+I to add cursors to line ends
        - Synchronized editing across all cursors
    """

    # Signal for status updates
    multi_cursor_status = Signal(str)

    def init_multi_cursor(self):
        """Initialize multi-cursor functionality."""
        # Store all cursors
        self.all_cursors = []
        self.search_text = ""
        self.initial_selection_done = False
        self.last_cursor_position = None

        # Ctrl+drag selection tracking
        self.ctrl_drag_start = None
        self.is_ctrl_dragging = False
        self.ctrl_drag_cursor = None

        # Rectangle selection tracking (middle-click)
        self.rect_selection_start = None
        self.rect_selection_end = None
        self.is_rect_selecting = False
        self.rect_selection_left_to_right = True
        # Virtual column positions for rectangle selection
        self.rect_start_col = 0
        self.rect_end_col = 0

        # Visual settings for cursors
        self.multi_cursor_color = QColor(255, 255, 255, 200)  # White cursor
        self.multi_selection_color = QColor(60, 120, 200, 100)  # Blue selection
        self.rect_selection_color = QColor(100, 150, 255, 80)  # Rectangle selection

        # Store original cursor width for restoration
        self.original_cursor_width = self.cursorWidth()

        # Setup shortcuts
        self.setup_multi_cursor_shortcuts()

    def setup_multi_cursor_shortcuts(self):
        """Setup keyboard shortcuts for multi-cursor operations."""
        # Note: Ctrl+D is handled differently to integrate with existing shortcut system
        # It will be connected in the main editor class

        # Ctrl+Shift+L - Select all occurrences
        shortcut_all = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        shortcut_all.activated.connect(self.select_all_occurrences)

        # Alt+Shift+I - Add cursors to line ends
        shortcut_line_ends = QShortcut(QKeySequence("Alt+Shift+I"), self)
        shortcut_line_ends.activated.connect(self.add_cursors_to_line_ends)

    def clear_multi_cursors(self):
        """Clear all additional cursors and return to single cursor mode."""
        # Save the position of the first cursor before clearing
        if self.all_cursors:
            self.last_cursor_position = self.all_cursors[0].position()
            # Set the main cursor to this position
            cursor = QTextCursor(self.document())
            cursor.setPosition(self.last_cursor_position)
            self.setTextCursor(cursor)

        self.all_cursors.clear()
        self.search_text = ""
        self.initial_selection_done = False

        # Restore original cursor visibility
        if hasattr(self, "original_cursor_width"):
            self.setCursorWidth(self.original_cursor_width)
        else:
            self.setCursorWidth(1)  # Default width

        self.viewport().update()

        # Clear any existing extra selections from old multi-selection system
        if hasattr(self, "_multi_selections"):
            self._multi_selections = []
            self.setExtraSelections([])

        # Emit status if the signal is connected
        with contextlib.suppress(Exception):
            self.multi_cursor_status.emit("Multi-cursor cleared")

    def add_next_occurrence(self):
        """Add next occurrence of selected text (Ctrl+D)."""
        current = self.textCursor()

        # Save current cursor position before starting multi-cursor
        if not self.all_cursors:
            self.last_cursor_position = current.position()
            # Hide the normal cursor when entering multi-cursor mode
            self.setCursorWidth(0)

        # First Ctrl+D: Initialize with current selection or word
        if not self.search_text or not self.initial_selection_done:
            if current.hasSelection():
                self.search_text = current.selectedText()
            else:
                # Select word under cursor
                current.select(QTextCursor.WordUnderCursor)
                if not current.hasSelection():
                    return
                self.search_text = current.selectedText()
                self.setTextCursor(current)

            # Store first cursor
            first_cursor = QTextCursor(self.document())
            first_cursor.setPosition(current.selectionStart())
            first_cursor.setPosition(current.selectionEnd(), QTextCursor.KeepAnchor)
            self.all_cursors = [first_cursor]
            self.initial_selection_done = True

            # Immediately find and add next occurrence on first Ctrl+D
            doc = self.document()
            search_from = current.selectionEnd()
            found = doc.find(self.search_text, search_from)

            # Wrap around if needed
            if found.isNull():
                found = doc.find(self.search_text, 0)

            # Add next occurrence if found and different from current
            if not found.isNull() and found.selectionStart() != current.selectionStart():
                new_cursor = QTextCursor(self.document())
                new_cursor.setPosition(found.selectionStart())
                new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
                self.all_cursors.append(new_cursor)

            self.viewport().update()

            try:
                if len(self.all_cursors) > 1:
                    self.multi_cursor_status.emit(f"Selected: '{self.search_text}' ({len(self.all_cursors)} occurrences)")
                else:
                    self.multi_cursor_status.emit(f"Selected: '{self.search_text}'")
            except Exception:
                pass
            return

        # Subsequent Ctrl+D: Add next occurrence
        doc = self.document()

        # Find search start position
        if self.all_cursors:
            last_cursor = self.all_cursors[-1]
            search_from = last_cursor.selectionEnd() if last_cursor.hasSelection() else last_cursor.position()
        else:
            search_from = current.position()

        # Search for next occurrence
        found = doc.find(self.search_text, search_from)

        # Wrap around if needed
        if found.isNull():
            found = doc.find(self.search_text, 0)

            # Check if we've wrapped to an existing selection
            if not found.isNull():
                for existing in self.all_cursors:
                    if existing.selectionStart() == found.selectionStart() and existing.selectionEnd() == found.selectionEnd():
                        with contextlib.suppress(Exception):
                            self.multi_cursor_status.emit("All occurrences selected")
                        return

        if not found.isNull():
            # Create new cursor
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(found.selectionStart())
            new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)

            # Add new cursor
            self.all_cursors.append(new_cursor)

            # Move main cursor to latest selection
            self.setTextCursor(found)

            self.viewport().update()
            with contextlib.suppress(Exception):
                self.multi_cursor_status.emit(f"Cursors: {len(self.all_cursors)}")
        else:
            with contextlib.suppress(Exception):
                self.multi_cursor_status.emit("No more occurrences")

    def select_all_occurrences(self):
        """Select all occurrences of current word (Ctrl+Shift+L)."""
        current = self.textCursor()

        if not current.hasSelection():
            current.select(QTextCursor.WordUnderCursor)

        text = current.selectedText()
        if not text:
            return

        self.search_text = text
        self.all_cursors.clear()

        # Find all occurrences
        doc = self.document()
        pos = 0

        while True:
            found = doc.find(text, pos)
            if found.isNull():
                break
            # Create new cursor for each occurrence
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(found.selectionStart())
            new_cursor.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
            self.all_cursors.append(new_cursor)
            pos = found.selectionEnd()

        if self.all_cursors:
            # Set main cursor to last found
            self.setTextCursor(self.all_cursors[-1])

        self.viewport().update()
        with contextlib.suppress(Exception):
            self.multi_cursor_status.emit(f"Selected {len(self.all_cursors)} occurrences")

    def add_cursors_to_line_ends(self):
        """Add cursor to end of each line in selection (Alt+Shift+I)."""
        current_cursor = self.textCursor()

        if not current_cursor.hasSelection():
            with contextlib.suppress(Exception):
                self.multi_cursor_status.emit("No selection for line ends")
            return

        # Get selection bounds
        start = current_cursor.selectionStart()
        end = current_cursor.selectionEnd()

        # Clear existing cursors
        self.all_cursors.clear()

        # Create cursor for iteration
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)

        # Move to start of first line
        cursor.movePosition(QTextCursor.StartOfLine)

        # Add cursor at end of each line in selection
        while cursor.position() <= end:
            # Move to end of current line
            line_end_cursor = QTextCursor(cursor)
            line_end_cursor.movePosition(QTextCursor.EndOfLine)

            # Check if this line end is within selection
            if line_end_cursor.position() >= start and line_end_cursor.position() <= end:
                # Create new cursor at line end
                new_cursor = QTextCursor(self.document())
                new_cursor.setPosition(line_end_cursor.position())
                self.all_cursors.append(new_cursor)

            # Move to next line
            if not cursor.movePosition(QTextCursor.Down):
                break

        self.viewport().update()
        with contextlib.suppress(Exception):
            self.multi_cursor_status.emit(f"Added {len(self.all_cursors)} cursors at line ends")

    def handle_multi_cursor_mouse(self, event):
        """Handle mouse events for multi-cursor. Returns True if handled."""
        if event.modifiers() & Qt.ControlModifier:
            # Get click position (PySide2/6 compatibility)
            try:
                click_pos = event.position().toPoint()  # PySide6
            except AttributeError:
                click_pos = event.pos()  # PySide2

            cursor = self.cursorForPosition(click_pos)

            # Check if this is the start of a drag operation
            if event.buttons() & Qt.LeftButton:
                # Start Ctrl+drag selection
                self.ctrl_drag_start = cursor.position()
                self.is_ctrl_dragging = True

                # If this is the first Ctrl action and we have no cursors,
                # add the current cursor position first
                if not self.all_cursors:
                    main_cursor = self.textCursor()
                    # Hide the normal cursor when entering multi-cursor mode
                    self.setCursorWidth(0)

                    if main_cursor.hasSelection():
                        # Add current selection as first cursor
                        first_cursor = QTextCursor(self.document())
                        first_cursor.setPosition(main_cursor.anchor())
                        first_cursor.setPosition(main_cursor.position(), QTextCursor.KeepAnchor)
                        self.all_cursors.append(first_cursor)
                    else:
                        # Add current position as first cursor
                        first_cursor = QTextCursor(self.document())
                        first_cursor.setPosition(main_cursor.position())
                        self.all_cursors.append(first_cursor)

                # Create new cursor for drag selection
                self.ctrl_drag_cursor = QTextCursor(self.document())
                self.ctrl_drag_cursor.setPosition(self.ctrl_drag_start)

                self.viewport().update()
                return True
            # Simple Ctrl+Click to add cursor (no drag)
            # If this is the first Ctrl+Click and we have no cursors,
            # add the current cursor position first
            if not self.all_cursors:
                main_cursor = self.textCursor()
                first_cursor = QTextCursor(self.document())
                first_cursor.setPosition(main_cursor.position())
                self.all_cursors.append(first_cursor)

            # Add cursor at click position
            new_cursor = QTextCursor(self.document())
            new_cursor.setPosition(cursor.position())
            self.all_cursors.append(new_cursor)

            self.viewport().update()
            with contextlib.suppress(Exception):
                self.multi_cursor_status.emit(f"Added cursor (total: {len(self.all_cursors)})")
            return True
        if self.all_cursors:
            # Normal click - clear multi-cursors
            self.clear_multi_cursors()
            self.is_ctrl_dragging = False
            self.ctrl_drag_cursor = None
        return False

    def handle_multi_cursor_keys(self, event):
        """Handle keyboard events for multi-cursor. Returns True if handled."""
        if len(self.all_cursors) <= 1:
            return False

        # Handle Escape to clear
        if event.key() == Qt.Key_Escape:
            self.clear_multi_cursors()
            return True

        # Handle text input and editing operations
        text = event.text()
        handled = False

        # Store current position for undo
        undo_cursor = self.textCursor()
        if self.all_cursors:
            undo_cursor.setPosition(self.all_cursors[0].position())
            self.setTextCursor(undo_cursor)

        # Begin edit block for undo/redo
        doc_cursor = QTextCursor(self.document())
        doc_cursor.beginEditBlock()

        # Create new cursor objects to ensure proper tracking
        new_cursors = []
        for c in self.all_cursors:
            new_c = QTextCursor(self.document())
            new_c.setPosition(c.anchor())
            new_c.setPosition(c.position(), QTextCursor.KeepAnchor if c.hasSelection() else QTextCursor.MoveAnchor)
            new_cursors.append(new_c)

        # Sort cursors by position (reverse to maintain positions)
        sorted_cursors = sorted(new_cursors, key=lambda c: c.position(), reverse=True)

        # Check for Ctrl+V paste operation
        is_paste = event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier
        paste_text = ""
        if is_paste:
            clipboard = QApplication.clipboard()
            if clipboard:
                paste_text = clipboard.text()

        for cursor in sorted_cursors:
            if is_paste and paste_text:
                # Paste text at each cursor
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertText(paste_text)
                handled = True

            elif text and text.isprintable():
                # Insert text at each cursor
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertText(text)
                handled = True

            elif event.key() == Qt.Key_Backspace:
                # Delete character before each cursor
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                else:
                    cursor.deletePreviousChar()
                handled = True

            elif event.key() == Qt.Key_Delete:
                # Delete character after each cursor
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                else:
                    cursor.deleteChar()
                handled = True

            elif event.key() == Qt.Key_Return:
                # Insert newline with proper indentation at each cursor
                current_line_text = cursor.block().text()
                indent = len(current_line_text) - len(current_line_text.lstrip())
                indent_text = current_line_text[:indent] if indent > 0 else ""

                # Check if we need extra indentation (after colon)
                trimmed = current_line_text.rstrip()
                if trimmed and trimmed[-1] == ":":
                    indent_text += "    "  # Add 4 spaces for new block

                cursor.insertText("\n" + indent_text)
                handled = True

            elif event.key() == Qt.Key_Tab:
                # Tab key handling is special - we need to process it differently
                # because we need to maintain cursor positions properly
                continue  # Skip this in the loop, handle it after

            # Movement keys
            elif event.key() == Qt.Key_Left:
                if event.modifiers() & Qt.ControlModifier:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.WordLeft, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(min(cursor.position(), cursor.anchor()))
                        else:
                            cursor.movePosition(QTextCursor.WordLeft)
                else:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(min(cursor.position(), cursor.anchor()))
                        else:
                            cursor.movePosition(QTextCursor.Left)
                handled = True

            elif event.key() == Qt.Key_Right:
                if event.modifiers() & Qt.ControlModifier:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.WordRight, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(max(cursor.position(), cursor.anchor()))
                        else:
                            cursor.movePosition(QTextCursor.WordRight)
                else:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(max(cursor.position(), cursor.anchor()))
                        else:
                            cursor.movePosition(QTextCursor.Right)
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
                if event.modifiers() & Qt.ControlModifier:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.clearSelection()
                            cursor.setPosition(cursor.position())
                        cursor.movePosition(QTextCursor.Start)
                else:
                    # Smart Home: move to first non-whitespace character
                    smart_home_pos = self.get_first_non_whitespace_position(cursor)
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.setPosition(smart_home_pos, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.clearSelection()
                        cursor.setPosition(smart_home_pos)
                handled = True

            elif event.key() == Qt.Key_End:
                if event.modifiers() & Qt.ControlModifier:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(cursor.position())
                        cursor.movePosition(QTextCursor.End)
                else:
                    if event.modifiers() & Qt.ShiftModifier:
                        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                    else:
                        if cursor.hasSelection():
                            cursor.setPosition(cursor.position())
                        cursor.movePosition(QTextCursor.EndOfLine)
                handled = True

            elif event.key() == Qt.Key_PageUp:
                if event.modifiers() & Qt.ShiftModifier:
                    cursor.movePosition(QTextCursor.PreviousBlock, QTextCursor.KeepAnchor, 10)
                else:
                    cursor.movePosition(QTextCursor.PreviousBlock, QTextCursor.MoveAnchor, 10)
                handled = True

            elif event.key() == Qt.Key_PageDown:
                if event.modifiers() & Qt.ShiftModifier:
                    cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor, 10)
                else:
                    cursor.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor, 10)
                handled = True

        # End edit block
        doc_cursor.endEditBlock()

        # Special handling for Tab/Shift+Tab
        if event.key() == Qt.Key_Tab:
            doc_cursor = QTextCursor(self.document())
            doc_cursor.beginEditBlock()

            if event.modifiers() & Qt.ShiftModifier:
                # Unindent - process each cursor line
                processed_lines = set()
                for cursor in self.all_cursors:
                    line_num = cursor.blockNumber()
                    if line_num not in processed_lines:
                        processed_lines.add(line_num)
                        temp_cursor = QTextCursor(self.document())
                        temp_cursor.movePosition(QTextCursor.Start)
                        for _ in range(line_num):
                            temp_cursor.movePosition(QTextCursor.NextBlock)
                        temp_cursor.movePosition(QTextCursor.StartOfLine)

                        line_text = temp_cursor.block().text()
                        if line_text.startswith("    "):
                            temp_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                            temp_cursor.removeSelectedText()
                        elif line_text.startswith("\t"):
                            temp_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                            temp_cursor.removeSelectedText()
                        elif line_text.startswith("  "):
                            temp_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)
                            temp_cursor.removeSelectedText()
                        elif line_text.startswith(" "):
                            temp_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                            temp_cursor.removeSelectedText()
            else:
                # Indent - insert at each cursor
                for _i, cursor in enumerate(sorted_cursors[::-1]):
                    cursor.insertText("    ")

            doc_cursor.endEditBlock()
            handled = True
            self.viewport().update()
            return True

        # Update display if handled
        if handled:
            # Create new cursor objects to store
            updated_cursors = []
            for cursor in sorted_cursors[::-1]:  # Reverse back to original order
                new_cursor = QTextCursor(self.document())
                if cursor.hasSelection():
                    new_cursor.setPosition(cursor.anchor())
                    new_cursor.setPosition(cursor.position(), QTextCursor.KeepAnchor)
                else:
                    new_cursor.setPosition(cursor.position())
                updated_cursors.append(new_cursor)

            self.all_cursors = updated_cursors

            # Set the main text cursor to the first multi-cursor position
            if self.all_cursors:
                main_cursor = QTextCursor(self.document())
                main_cursor.setPosition(self.all_cursors[0].position())
                self.setTextCursor(main_cursor)

            self.viewport().update()

        return handled

    def paint_multi_cursors(self, painter):
        """Paint multi-cursor indicators. Call from paintEvent."""
        # Check if we need to draw anything
        if len(self.all_cursors) <= 1 and not self.is_ctrl_dragging and not self.is_rect_selecting:
            return

        # Draw rectangle selection if active
        if self.is_rect_selecting and self.rect_selection_start is not None and self.rect_selection_end is not None:
            self._draw_rectangle_selection(painter)

        # Draw dragging selection if active
        if self.is_ctrl_dragging and self.ctrl_drag_cursor and self.ctrl_drag_cursor.hasSelection():
            self._draw_cursor_selection(painter, self.ctrl_drag_cursor)

        # Draw all cursors and their selections
        for cursor in self.all_cursors:
            # Get cursor rectangle
            cursor_rect = self.cursorRect(cursor)

            # Draw cursor line (2 pixels wide)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.multi_cursor_color)

            cursor_line_rect = QRect(cursor_rect.x(), cursor_rect.y(), 2, cursor_rect.height())
            painter.fillRect(cursor_line_rect, painter.brush())

            # Draw selection if exists
            if cursor.hasSelection():
                self._draw_cursor_selection(painter, cursor)

    def _draw_cursor_selection(self, painter, cursor):
        """Helper method to draw selection for a cursor."""
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()

        # Get rectangles for selection
        start_cursor = QTextCursor(self.document())
        start_cursor.setPosition(selection_start)
        end_cursor = QTextCursor(self.document())
        end_cursor.setPosition(selection_end)

        start_rect = self.cursorRect(start_cursor)
        end_rect = self.cursorRect(end_cursor)

        # Check if selection spans multiple lines
        start_block = start_cursor.blockNumber()
        end_block = end_cursor.blockNumber()

        if start_block == end_block:
            # Single line selection
            selection_rect = QRect(start_rect.x(), start_rect.y(), end_rect.x() - start_rect.x(), start_rect.height())
            painter.fillRect(selection_rect, self.multi_selection_color)
        else:
            # Multi-line selection
            temp_cursor = QTextCursor(self.document())

            # Draw first line
            temp_cursor.setPosition(selection_start)
            temp_cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            first_line_end = self.cursorRect(temp_cursor)
            painter.fillRect(
                QRect(start_rect.x(), start_rect.y(), first_line_end.x() - start_rect.x(), start_rect.height()),
                self.multi_selection_color,
            )

            # Draw middle lines
            for block_num in range(start_block + 1, end_block):
                temp_cursor.setPosition(self.document().findBlockByNumber(block_num).position())
                line_start_rect = self.cursorRect(temp_cursor)
                temp_cursor.movePosition(QTextCursor.EndOfLine)
                line_end_rect = self.cursorRect(temp_cursor)
                painter.fillRect(
                    QRect(line_start_rect.x(), line_start_rect.y(), line_end_rect.x() - line_start_rect.x(), line_start_rect.height()),
                    self.multi_selection_color,
                )

            # Draw last line
            temp_cursor.setPosition(self.document().findBlockByNumber(end_block).position())
            last_line_start = self.cursorRect(temp_cursor)
            painter.fillRect(
                QRect(last_line_start.x(), last_line_start.y(), end_rect.x() - last_line_start.x(), last_line_start.height()),
                self.multi_selection_color,
            )

    def start_rectangle_selection(self, event):
        """Start rectangle selection with middle-click."""
        # Clear existing multi-cursors
        self.clear_multi_cursors()

        # Hide the normal cursor during rectangle selection
        self.setCursorWidth(0)

        # Get start position
        try:
            pos = event.position().toPoint()  # PySide6
        except AttributeError:
            pos = event.pos()  # PySide2

        cursor = self.cursorForPosition(pos)
        self.rect_selection_start = cursor.position()
        self.rect_selection_end = cursor.position()
        self.is_rect_selecting = True

        # Calculate virtual column position based on X coordinate
        block = cursor.block()
        line_start_cursor = QTextCursor(block)
        line_start_cursor.movePosition(QTextCursor.StartOfLine)
        line_start_rect = self.cursorRect(line_start_cursor)

        # Calculate column based on pixel position from start of line
        char_width = self.fontMetrics().horizontalAdvance(" ")
        if char_width > 0:
            x_offset = pos.x() - line_start_rect.x()
            self.rect_start_col = max(0, x_offset // char_width)
        else:
            # Fallback to actual text position
            self.rect_start_col = cursor.position() - block.position()

        self.rect_end_col = self.rect_start_col

        # Initialize direction (will be updated on move)
        self.rect_selection_left_to_right = True

    def update_rectangle_selection(self, event):
        """Update rectangle selection during drag."""
        if not self.is_rect_selecting:
            return

        # Get current position
        try:
            pos = event.position().toPoint()  # PySide6
        except AttributeError:
            pos = event.pos()  # PySide2

        cursor = self.cursorForPosition(pos)
        self.rect_selection_end = cursor.position()

        # Calculate the virtual column position based on X coordinate
        # This allows selection beyond the end of lines
        block = cursor.block()
        line_start_cursor = QTextCursor(block)
        line_start_cursor.movePosition(QTextCursor.StartOfLine)
        line_start_rect = self.cursorRect(line_start_cursor)

        # Calculate column based on pixel position from start of line
        char_width = self.fontMetrics().horizontalAdvance(" ")
        if char_width > 0:
            # Calculate virtual column from X position
            x_offset = pos.x() - line_start_rect.x()
            self.rect_end_col = max(0, x_offset // char_width)
        else:
            # Fallback to actual text position
            self.rect_end_col = cursor.position() - block.position()

        # Check horizontal direction
        self.rect_selection_left_to_right = self.rect_start_col <= self.rect_end_col

        # Update display
        self.viewport().update()

    def finalize_rectangle_selection(self, event):
        """Finalize rectangle selection and add cursors."""
        if not self.is_rect_selecting:
            return

        # Get start and end cursors
        start_cursor = QTextCursor(self.document())
        start_cursor.setPosition(self.rect_selection_start)
        end_cursor = QTextCursor(self.document())
        end_cursor.setPosition(self.rect_selection_end)

        # Use the stored virtual column positions
        # These represent the actual rectangle boundaries, not limited by text length
        left_col = min(self.rect_start_col, self.rect_end_col)
        right_col = max(self.rect_start_col, self.rect_end_col)

        # Get line range
        start_line = min(start_cursor.blockNumber(), end_cursor.blockNumber())
        end_line = max(start_cursor.blockNumber(), end_cursor.blockNumber())

        # Clear existing cursors
        self.all_cursors.clear()

        # Add cursor with selection for each line in rectangle
        for line_num in range(start_line, end_line + 1):
            block = self.document().findBlockByNumber(line_num)
            line_text = block.text()
            line_len = len(line_text)

            # Skip empty lines and lines with only whitespace (VSCode/Sublime behavior)
            if line_len == 0 or line_text.strip() == "":
                continue

            # Calculate actual positions for this line
            actual_left = min(left_col, line_len)
            actual_right = min(right_col, line_len)

            # Add cursor based on how the rectangle intersects with the line
            if actual_right > actual_left:
                # Line has text in the selection range
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + actual_left)
                new_cursor.setPosition(block.position() + actual_right, QTextCursor.KeepAnchor)

                # Add cursor with selection (cursor will be at end of selection)
                self.all_cursors.append(new_cursor)
            elif left_col > line_len:
                # Rectangle starts beyond the end of the line
                # Place cursor at the end of the line (like VSCode/Sublime)
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + line_len)
                self.all_cursors.append(new_cursor)
            elif actual_left == line_len and left_col < right_col:
                # Line ends exactly at the left edge of rectangle
                # and rectangle extends beyond - place cursor at end
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + line_len)
                self.all_cursors.append(new_cursor)

        # Reset rectangle selection state
        self.is_rect_selecting = False
        self.rect_selection_start = None
        self.rect_selection_end = None
        self.rect_start_col = 0
        self.rect_end_col = 0

        # Update display
        self.viewport().update()

        with contextlib.suppress(Exception):
            self.multi_cursor_status.emit(f"Added {len(self.all_cursors)} cursors from rectangle selection")

    def _draw_rectangle_selection(self, painter):
        """Draw rectangle selection area during drag."""
        if not self.is_rect_selecting:
            return

        # Get start and end positions
        start_cursor = QTextCursor(self.document())
        start_cursor.setPosition(self.rect_selection_start)
        end_cursor = QTextCursor(self.document())
        end_cursor.setPosition(self.rect_selection_end)

        # Use virtual column positions for the rectangle
        left_col = min(self.rect_start_col, self.rect_end_col)
        right_col = max(self.rect_start_col, self.rect_end_col)

        # Get line range
        start_line = min(start_cursor.blockNumber(), end_cursor.blockNumber())
        end_line = max(start_cursor.blockNumber(), end_cursor.blockNumber())

        # Draw selection for each line in rectangle
        for line_num in range(start_line, end_line + 1):
            block = self.document().findBlockByNumber(line_num)
            line_text = block.text()
            line_len = len(line_text)

            # Skip empty lines completely
            if line_len == 0:
                continue

            # Calculate actual selection range for this line
            actual_left = min(left_col, line_len)
            actual_right = min(right_col, line_len)

            if actual_right > actual_left:
                # Line has text in the selection range
                left_cursor = QTextCursor(block)
                left_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_left)
                left_rect = self.cursorRect(left_cursor)

                right_cursor = QTextCursor(block)
                right_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_right)
                right_rect = self.cursorRect(right_cursor)

                # Draw selection rectangle
                selection_rect = QRect(left_rect.x(), left_rect.y(), right_rect.x() - left_rect.x(), left_rect.height())
                # Draw with normal selection color
                painter.fillRect(selection_rect, self.multi_selection_color)
            elif left_col > line_len or (actual_left == line_len and left_col < right_col):
                # Rectangle is beyond the end of the line or at the end
                # Draw a thin cursor at the end of the line
                end_cursor = QTextCursor(block)
                end_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, line_len)
                end_rect = self.cursorRect(end_cursor)

                selection_rect = QRect(
                    end_rect.x(),
                    end_rect.y(),
                    2,  # Thin cursor width
                    end_rect.height(),
                )
                # Draw with normal selection color
                painter.fillRect(selection_rect, self.multi_selection_color)
