"""
Find and Replace dialog for the code editor.
Provides search and replace functionality with various options.
"""

from .....lib_ui.qt_compat import (
    QButtonGroup,
    QCheckBox,
    QColor,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QShortcut,
    QTextCursor,
    QTextEdit,
    QVBoxLayout,
)
from .dialog_base import CodeEditorDialog, CodeEditorMessageBox


class FindReplaceDialog(CodeEditorDialog):
    """Find and Replace dialog with advanced search options."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.parent_window = parent
        self.last_search_text = ""
        self.last_match_case = False
        self.last_whole_words = False
        self.last_use_regex = False
        self.highlighted_matches = []  # Store highlighted matches

        self.init_ui()
        self.connect_signals()
        self.setup_shortcuts()
        self.restore_search_settings()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Find and Replace")
        self.setModal(False)  # Allow interaction with main window
        self.setFixedSize(380, 180)  # Fixed size, not resizable

        layout = QVBoxLayout()
        layout.setSpacing(4)  # Reduce spacing
        layout.setContentsMargins(6, 6, 6, 6)  # Smaller margins

        # Input section (Find and Replace combined)
        input_frame = self.create_input_section()
        layout.addWidget(input_frame)

        # Options and Direction in one row
        options_frame = self.create_compact_options_section()
        layout.addWidget(options_frame)

        # Buttons section
        buttons_frame = self.create_compact_buttons_section()
        layout.addWidget(buttons_frame)

        self.setLayout(layout)

    def create_input_section(self):
        """Create the input section with find and replace fields."""
        frame = QFrame()
        layout = QGridLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        # Find label and input
        find_label = QLabel("Find:")
        find_label.setMinimumWidth(50)
        self.find_input = QLineEdit()
        self.find_input.setMinimumWidth(250)

        # Replace label and input
        replace_label = QLabel("Replace:")
        replace_label.setMinimumWidth(50)
        self.replace_input = QLineEdit()
        self.replace_input.setMinimumWidth(250)

        layout.addWidget(find_label, 0, 0)
        layout.addWidget(self.find_input, 0, 1)
        layout.addWidget(replace_label, 1, 0)
        layout.addWidget(self.replace_input, 1, 1)

        frame.setLayout(layout)
        return frame

    def create_compact_options_section(self):
        """Create the compact options and direction section."""
        frame = QFrame()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 4, 0, 4)

        # Options group
        options_group = QFrame()
        options_layout = QVBoxLayout()
        options_layout.setSpacing(2)
        options_layout.setContentsMargins(0, 0, 0, 0)

        self.match_case_cb = QCheckBox("Match case")
        self.whole_words_cb = QCheckBox("Whole words only")
        self.use_regex_cb = QCheckBox("Use regular expressions")

        options_layout.addWidget(self.match_case_cb)
        options_layout.addWidget(self.whole_words_cb)
        options_layout.addWidget(self.use_regex_cb)

        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)

        # Direction group
        direction_group = QFrame()
        direction_layout = QVBoxLayout()
        direction_layout.setSpacing(2)
        direction_layout.setContentsMargins(0, 0, 0, 0)

        direction_label = QLabel("Direction:")
        direction_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        direction_layout.addWidget(direction_label)

        self.direction_group = QButtonGroup()
        self.up_radio = QRadioButton("Up")
        self.down_radio = QRadioButton("Down")
        self.down_radio.setChecked(True)  # Default to down

        self.direction_group.addButton(self.up_radio)
        self.direction_group.addButton(self.down_radio)

        direction_radio_layout = QVBoxLayout()
        direction_radio_layout.setSpacing(2)
        direction_radio_layout.addWidget(self.up_radio)
        direction_radio_layout.addWidget(self.down_radio)
        direction_layout.addLayout(direction_radio_layout)

        direction_group.setLayout(direction_layout)
        main_layout.addWidget(direction_group)

        main_layout.addStretch()
        frame.setLayout(main_layout)
        return frame

    def create_compact_buttons_section(self):
        """Create the compact action buttons section."""
        frame = QFrame()
        layout = QHBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 4, 0, 0)

        # Create smaller buttons
        self.find_next_btn = QPushButton("Next")
        self.find_prev_btn = QPushButton("Prev")
        self.find_all_btn = QPushButton("Find All")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")

        # Make buttons smaller
        button_height = 24
        for btn in [self.find_next_btn, self.find_prev_btn, self.find_all_btn, self.replace_btn, self.replace_all_btn]:
            btn.setMaximumHeight(button_height)
            btn.setMinimumHeight(button_height)

        # Set button properties
        self.find_next_btn.setDefault(True)

        # Add buttons to layout with proper grouping
        layout.addWidget(self.find_next_btn)
        layout.addWidget(self.find_prev_btn)
        layout.addWidget(self.find_all_btn)

        # Add some spacing
        layout.addSpacing(8)

        layout.addWidget(self.replace_btn)
        layout.addWidget(self.replace_all_btn)

        # Add stretch
        layout.addStretch()

        frame.setLayout(layout)
        return frame

    def connect_signals(self):
        """Connect widget signals."""
        # Find input signals
        self.find_input.textChanged.connect(self.on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)

        # Replace input signals
        self.replace_input.returnPressed.connect(self.replace_current)

        # Button signals
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_all_btn.clicked.connect(self.find_all)
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_all_btn.clicked.connect(self.replace_all)

        # Options signals
        self.match_case_cb.toggled.connect(self.on_options_changed)
        self.whole_words_cb.toggled.connect(self.on_options_changed)
        self.use_regex_cb.toggled.connect(self.on_options_changed)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.close)

        # F3 for find next
        f3_shortcut = QShortcut(QKeySequence("F3"), self)
        f3_shortcut.activated.connect(self.find_next)

        # Shift+F3 for find previous
        shift_f3_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        shift_f3_shortcut.activated.connect(self.find_previous)

        # Ctrl+H for replace (when dialog is focused)
        ctrl_h_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        ctrl_h_shortcut.activated.connect(lambda: self.replace_input.setFocus())

    def show_find_mode(self, search_text=""):
        """Show dialog in find-only mode."""
        if search_text:
            self.find_input.setText(search_text)
            self.find_input.selectAll()

        self.find_input.setFocus()
        self.show()
        self.activateWindow()
        self.raise_()

    def show_replace_mode(self, search_text=""):
        """Show dialog in find-and-replace mode."""
        if search_text:
            self.find_input.setText(search_text)
            self.find_input.selectAll()

        self.find_input.setFocus()
        self.show()
        self.activateWindow()
        self.raise_()

    def on_find_text_changed(self):
        """Handle find text changes."""
        # Enable/disable buttons based on text content
        has_text = bool(self.find_input.text().strip())

        self.find_next_btn.setEnabled(has_text)
        self.find_prev_btn.setEnabled(has_text)
        self.find_all_btn.setEnabled(has_text)
        self.replace_btn.setEnabled(has_text)
        self.replace_all_btn.setEnabled(has_text)

    def on_options_changed(self):
        """Handle search options changes."""
        # Clear any existing search highlights when options change
        self.clear_highlights()

    def get_search_flags(self):
        """Get search flags based on current options."""
        try:
            # Try Qt6 first
            from PySide6.QtGui import QTextDocument  # type: ignore

            flags = QTextDocument.FindFlags()

            if self.match_case_cb.isChecked():
                flags |= QTextDocument.FindCaseSensitively

            if self.whole_words_cb.isChecked():
                flags |= QTextDocument.FindWholeWords

            if self.up_radio.isChecked():
                flags |= QTextDocument.FindBackward

        except ImportError:
            # Fallback to Qt5
            flags = 0

            if self.match_case_cb.isChecked():
                flags |= QTextCursor.FindCaseSensitively

            if self.whole_words_cb.isChecked():
                flags |= QTextCursor.FindWholeWords

            if self.up_radio.isChecked():
                flags |= QTextCursor.FindBackward

        return flags

    def find_next(self):
        """Find next occurrence."""
        search_text = self.find_input.text()
        if not search_text:
            return False

        # Clear multi-cursor mode if active
        self.clear_multi_cursor()

        # Force search direction to down for find next
        old_direction = self.down_radio.isChecked()
        self.down_radio.setChecked(True)

        result = self.perform_search(search_text, wrap_around=True)

        # Restore original direction if it was changed
        if not old_direction:
            self.up_radio.setChecked(True)

        return result

    def find_previous(self):
        """Find previous occurrence."""
        search_text = self.find_input.text()
        if not search_text:
            return False

        # Clear multi-cursor mode if active
        self.clear_multi_cursor()

        # Force search direction to up for find previous
        old_direction = self.up_radio.isChecked()
        self.up_radio.setChecked(True)

        result = self.perform_search(search_text, wrap_around=True)

        # Restore original direction if it was changed
        if not old_direction:
            self.down_radio.setChecked(True)

        return result

    def find_all(self):
        """Find all occurrences and select them."""
        search_text = self.find_input.text()
        if not search_text:
            return 0

        # Clear existing selections
        self.clear_highlights()

        # Find and select all occurrences
        count = self.select_all_matches(search_text)

        # Only show message if nothing found
        if count == 0:
            CodeEditorMessageBox.information(self, "Find All Results", f"'{search_text}' not found")

        return count

    def replace_current(self):
        """Replace current selection if it matches search text."""
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()

        if not search_text:
            return False

        # Clear multi-cursor mode if active
        self.clear_multi_cursor()

        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()

            # Check if selected text matches search text
            if self.text_matches(selected_text, search_text):
                cursor.insertText(replace_text)
                # Find next occurrence after replacement
                self.find_next()
                return True
        else:
            # No selection, try to find and select first occurrence
            if self.find_next():
                return self.replace_current()

        return False

    def replace_all(self):
        """Replace all occurrences without confirmation."""
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()

        if not search_text:
            return 0

        # Clear multi-cursor mode if active
        self.clear_multi_cursor()

        # Store original cursor position
        original_cursor = self.editor.textCursor()
        original_position = original_cursor.position()

        # Begin undo block for single undo
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()

        try:
            # Perform replacement
            count = self.perform_replace_all(search_text, replace_text)

            # Restore cursor position after replacement
            cursor.setPosition(min(original_position, self.editor.document().characterCount() - 1))
            self.editor.setTextCursor(cursor)
        finally:
            # End undo block
            cursor.endEditBlock()

        return count

    def perform_search(self, search_text, wrap_around=True):
        """Perform the actual search operation."""
        if not search_text:
            return False

        flags = self.get_search_flags()
        cursor = self.editor.textCursor()

        # Perform search
        if self.use_regex_cb.isChecked():
            # Use regex search (simplified implementation)
            found_cursor = self.regex_search(search_text, cursor, flags)
        else:
            # Use standard text search
            try:
                # Try with flags first
                found_cursor = self.editor.document().find(search_text, cursor, flags)
            except (TypeError, AttributeError):
                # Fallback without flags if there's a type error
                found_cursor = self.editor.document().find(search_text, cursor)

        if not found_cursor.isNull():
            self.editor.setTextCursor(found_cursor)
            return True
        elif wrap_around:
            # Try wrapping around
            return self.wrap_around_search(search_text, flags)
        else:
            CodeEditorMessageBox.information(self, "Find", f"'{search_text}' not found")
            return False

    def wrap_around_search(self, search_text, flags):
        """Search with wrap-around."""
        # Move cursor to start/end and search again
        cursor = self.editor.textCursor()

        # Check if searching backwards by examining the radio button state
        # since flags format may vary between Qt versions
        if self.up_radio.isChecked():
            # Searching backwards, start from end
            cursor.movePosition(QTextCursor.End)
        else:
            # Searching forwards, start from beginning
            cursor.movePosition(QTextCursor.Start)

        if self.use_regex_cb.isChecked():
            found_cursor = self.regex_search(search_text, cursor, flags)
        else:
            try:
                # Try with flags first
                found_cursor = self.editor.document().find(search_text, cursor, flags)
            except (TypeError, AttributeError):
                # Fallback without flags if there's a type error
                found_cursor = self.editor.document().find(search_text, cursor)

        if not found_cursor.isNull():
            self.editor.setTextCursor(found_cursor)
            return True
        else:
            CodeEditorMessageBox.information(self, "Find", f"'{search_text}' not found")
            return False

    def regex_search(self, pattern, cursor, flags):
        """Perform regex search (simplified implementation)."""
        # This is a simplified regex implementation
        # In a full implementation, you would use QRegularExpression
        import re

        # Get document text
        document = self.editor.document()
        text = document.toPlainText()

        # Determine search options
        re_flags = 0
        if not self.match_case_cb.isChecked():
            re_flags |= re.IGNORECASE

        # Compile pattern
        try:
            regex = re.compile(pattern, re_flags)
        except re.error:
            CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {pattern}")
            return QTextCursor()

        # Search from current position
        start_pos = cursor.position()

        # Check direction using radio button state instead of flags
        if self.up_radio.isChecked():
            # Search backwards
            match = None
            for m in regex.finditer(text[:start_pos]):
                match = m
            if match:
                new_cursor = QTextCursor(document)
                new_cursor.setPosition(match.start())
                new_cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                return new_cursor
        else:
            # Search forwards
            match = regex.search(text, start_pos)
            if match:
                new_cursor = QTextCursor(document)
                new_cursor.setPosition(match.start())
                new_cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                return new_cursor

        return QTextCursor()  # Not found

    def select_all_matches(self, search_text):
        """Select all matches in the editor using multi-cursor."""
        # If editor has multi-cursor handler, use it directly
        if hasattr(self.editor, "all_cursors"):
            # Clear existing cursors
            self.editor.all_cursors.clear()
            self.editor.search_text = search_text

            # Find all occurrences
            count = 0
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(0)
            flags = self.get_search_flags()

            # Remove FindBackward flag if present for find all
            try:
                from PySide6.QtGui import QTextDocument

                if flags & QTextDocument.FindBackward:
                    flags &= ~QTextDocument.FindBackward
            except ImportError:
                if flags & QTextCursor.FindBackward:
                    flags &= ~QTextCursor.FindBackward

            while True:
                if self.use_regex_cb.isChecked():
                    found_cursor = self.regex_search(search_text, cursor, flags)
                else:
                    try:
                        found_cursor = self.editor.document().find(search_text, cursor, flags)
                    except (TypeError, AttributeError):
                        found_cursor = self.editor.document().find(search_text, cursor)

                if found_cursor.isNull():
                    break

                # Create new cursor for each occurrence
                new_cursor = QTextCursor(self.editor.document())
                new_cursor.setPosition(found_cursor.selectionStart())
                new_cursor.setPosition(found_cursor.selectionEnd(), QTextCursor.KeepAnchor)
                self.editor.all_cursors.append(new_cursor)
                cursor = found_cursor
                count += 1

            if self.editor.all_cursors:
                # Set main cursor to last found
                self.editor.setTextCursor(self.editor.all_cursors[-1])
                # Update the viewport to show cursors
                self.editor.viewport().update()

            return count
        else:
            # Fallback if no multi-cursor support
            return 0

    def highlight_all_matches(self, search_text):
        """Highlight all matches in the editor."""
        count = 0
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(0)

        # Store cursors for all matches
        match_cursors = []
        flags = self.get_search_flags()

        # Remove FindBackward flag if present for find all
        try:
            from PySide6.QtGui import QTextDocument

            if flags & QTextDocument.FindBackward:
                flags &= ~QTextDocument.FindBackward
        except ImportError:
            if flags & QTextCursor.FindBackward:
                flags &= ~QTextCursor.FindBackward

        while True:
            if self.use_regex_cb.isChecked():
                found_cursor = self.regex_search(search_text, cursor, flags)
            else:
                try:
                    found_cursor = self.editor.document().find(search_text, cursor, flags)
                except (TypeError, AttributeError):
                    found_cursor = self.editor.document().find(search_text, cursor)

            if found_cursor.isNull():
                break

            match_cursors.append(QTextCursor(found_cursor))
            cursor = found_cursor
            count += 1

        # Apply highlighting to all matches
        if match_cursors:
            # Create extra selections for highlighting
            extra_selections = []
            highlight_color = QColor(255, 255, 0, 80)  # Yellow with transparency

            for match_cursor in match_cursors:
                selection = QTextEdit.ExtraSelection()
                selection.cursor = match_cursor
                selection.format.setBackground(highlight_color)
                extra_selections.append(selection)

            # Apply the extra selections to highlight all matches
            self.editor.setExtraSelections(extra_selections)
            self.highlighted_matches = extra_selections  # Store for later clearing

        return count

    def count_matches(self, search_text):
        """Count total number of matches."""
        if self.use_regex_cb.isChecked():
            return self.count_regex_matches(search_text)
        else:
            return self.count_text_matches(search_text)

    def count_text_matches(self, search_text):
        """Count text matches."""
        text = self.editor.toPlainText()

        if self.match_case_cb.isChecked():
            count = text.count(search_text)
        else:
            count = text.lower().count(search_text.lower())

        return count

    def count_regex_matches(self, pattern):
        """Count regex matches."""
        import re

        text = self.editor.toPlainText()
        re_flags = 0

        if not self.match_case_cb.isChecked():
            re_flags |= re.IGNORECASE

        try:
            regex = re.compile(pattern, re_flags)
            matches = regex.findall(text)
            return len(matches)
        except re.error:
            return 0

    def perform_replace_all(self, search_text, replace_text):
        """Perform replace all operation."""
        if self.use_regex_cb.isChecked():
            return self.regex_replace_all(search_text, replace_text)
        else:
            return self.text_replace_all(search_text, replace_text)

    def text_replace_all(self, search_text, replace_text):
        """Replace all text matches with proper undo support."""
        count = 0
        cursor = QTextCursor(self.editor.document())
        flags = self.get_search_flags()

        # Remove FindBackward flag for replace all
        try:
            from PySide6.QtGui import QTextDocument

            if flags & QTextDocument.FindBackward:
                flags &= ~QTextDocument.FindBackward
        except ImportError:
            if flags & QTextCursor.FindBackward:
                flags &= ~QTextCursor.FindBackward

        # Find and replace from end to beginning to preserve positions
        positions = []
        cursor.setPosition(0)

        # First, find all matches
        while True:
            try:
                found = self.editor.document().find(search_text, cursor, flags)
            except (TypeError, AttributeError):
                found = self.editor.document().find(search_text, cursor)

            if found.isNull():
                break

            positions.append((found.selectionStart(), found.selectionEnd()))
            cursor = found

        # Replace from end to beginning to maintain positions
        for start, end in reversed(positions):
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.insertText(replace_text)
            count += 1

        return count

    def regex_replace_all(self, pattern, replacement):
        """Replace all regex matches with proper undo support."""
        import re

        count = 0
        cursor = QTextCursor(self.editor.document())
        text = self.editor.toPlainText()
        re_flags = 0

        if not self.match_case_cb.isChecked():
            re_flags |= re.IGNORECASE

        try:
            regex = re.compile(pattern, re_flags)
            matches = list(regex.finditer(text))

            # Replace from end to beginning to maintain positions
            for match in reversed(matches):
                cursor.setPosition(match.start())
                cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                # Handle regex replacement groups
                if "\\" in replacement:
                    replace_text = match.expand(replacement)
                else:
                    replace_text = replacement
                cursor.insertText(replace_text)
                count += 1

            return count
        except re.error:
            CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {pattern}")
            return 0

    def text_matches(self, text1, text2):
        """Check if two texts match based on current options."""
        if self.match_case_cb.isChecked():
            return text1 == text2
        else:
            return text1.lower() == text2.lower()

    def clear_multi_cursor(self):
        """Clear multi-cursor mode if active."""
        if hasattr(self.editor, "all_cursors"):
            self.editor.all_cursors.clear()
            self.editor.search_text = ""
            self.editor.viewport().update()

    def clear_highlights(self):
        """Clear search result highlights."""
        # Clear any existing extra selections
        if hasattr(self, "highlighted_matches") and self.highlighted_matches:
            self.editor.setExtraSelections([])
            self.highlighted_matches = []

    def closeEvent(self, event):
        """Handle dialog close event."""
        self.clear_highlights()
        self.save_search_settings()
        super().closeEvent(event)

    def restore_search_settings(self):
        """Restore search settings from parent window."""
        if hasattr(self.parent_window, "settings_manager"):
            settings = self.parent_window.settings_manager.get_search_settings()

            self.match_case_cb.setChecked(settings.get("match_case", False))
            self.whole_words_cb.setChecked(settings.get("whole_words", False))
            self.use_regex_cb.setChecked(settings.get("use_regex", False))

            direction = settings.get("search_direction", "down")
            if direction == "up":
                self.up_radio.setChecked(True)
            else:
                self.down_radio.setChecked(True)

    def save_search_settings(self):
        """Save search settings to parent window."""
        if hasattr(self.parent_window, "settings_manager"):
            direction = "up" if self.up_radio.isChecked() else "down"

            self.parent_window.settings_manager.set_search_settings(
                self.match_case_cb.isChecked(), self.whole_words_cb.isChecked(), self.use_regex_cb.isChecked(), direction
            )
            # Save to file immediately
            self.parent_window.settings_manager.save_settings()
