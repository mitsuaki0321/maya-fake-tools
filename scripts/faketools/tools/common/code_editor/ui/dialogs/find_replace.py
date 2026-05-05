"""
Find and Replace dialog for the code editor.

UI layer only: builds the dialog, translates checkbox state into a
``SearchOptions``, and delegates pattern matching / replacement to
``command.search.SearchEngine``.
"""

from ......lib_ui.qt_compat import (
    QButtonGroup,
    QCheckBox,
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
    QVBoxLayout,
)
from ...command.search import InvalidRegexError, SearchEngine, SearchOptions
from ...themes import AppTheme
from .base import CodeEditorDialog, CodeEditorMessageBox


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

        self.init_ui()
        self.connect_signals()
        self.setup_shortcuts()
        self.restore_search_settings()

    # -------------------- SearchOptions helpers --------------------

    @property
    def _engine(self) -> SearchEngine:
        """Fresh engine bound to the editor's current document.

        Rebuilt on access so that swapping the underlying document (e.g.
        reloading a file) doesn't leave us holding a stale reference.
        """
        return SearchEngine(self.editor.document())

    def get_options(self) -> SearchOptions:
        """Build a ``SearchOptions`` from the current checkbox state."""
        return SearchOptions(
            match_case=self.match_case_cb.isChecked(),
            whole_words=self.whole_words_cb.isChecked(),
            use_regex=self.use_regex_cb.isChecked(),
        )

    def _is_backward(self) -> bool:
        return self.up_radio.isChecked()

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
        direction_label.setStyleSheet(AppTheme.get_emphasized_label_stylesheet())
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

    # -------------------- Find actions --------------------

    def find_next(self):
        """Find the next occurrence (forward), wrapping around at EOF."""
        search_text = self.find_input.text()
        if not search_text:
            return False
        self.clear_multi_cursor()
        return self._jump_to_next_match(search_text, backward=False)

    def find_previous(self):
        """Find the previous occurrence (backward), wrapping around at SOF."""
        search_text = self.find_input.text()
        if not search_text:
            return False
        self.clear_multi_cursor()
        return self._jump_to_next_match(search_text, backward=True)

    def find_all(self):
        """Populate multi-cursor selections from every forward match."""
        search_text = self.find_input.text()
        if not search_text:
            return 0

        count = self.select_all_matches(search_text)
        if count == 0:
            CodeEditorMessageBox.information(self, "Find All Results", f"'{search_text}' not found")
        return count

    def _jump_to_next_match(self, search_text: str, backward: bool) -> bool:
        """Move the editor cursor to the next match in the given direction.

        Tries from the current cursor first; if that fails, wraps to the
        opposite end of the document before giving up.
        """
        options = self.get_options()
        cursor = self.editor.textCursor()

        try:
            found = self._engine.find_from(search_text, cursor, options, backward=backward)
        except InvalidRegexError as exc:
            CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {exc}")
            return False

        if found.isNull():
            # Wrap around
            wrap_cursor = QTextCursor(self.editor.document())
            wrap_cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            try:
                found = self._engine.find_from(search_text, wrap_cursor, options, backward=backward)
            except InvalidRegexError as exc:
                CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {exc}")
                return False

        if found.isNull():
            CodeEditorMessageBox.information(self, "Find", f"'{search_text}' not found")
            return False

        block = found.block()
        if not block.isVisible() and hasattr(self.editor, "fold_manager"):
            self.editor.fold_manager.unfold_containing(block.blockNumber())
        self.editor.setTextCursor(found)
        return True

    # -------------------- Replace actions --------------------

    def replace_current(self):
        """Replace the active selection if it matches the search text, then advance."""
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not search_text:
            return False

        self.clear_multi_cursor()

        options = self.get_options()
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            if SearchEngine.texts_equal(cursor.selectedText(), search_text, options):
                cursor.insertText(replace_text)
                self.find_next()
                return True
        elif self.find_next():
            return self.replace_current()

        return False

    def replace_all(self):
        """Replace every forward match in a single undo block."""
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not search_text:
            return 0

        self.clear_multi_cursor()

        original_position = self.editor.textCursor().position()
        options = self.get_options()

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        try:
            try:
                count = self._engine.replace_all(search_text, replace_text, options)
            except InvalidRegexError as exc:
                CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {exc}")
                return 0

            clamped = min(original_position, self.editor.document().characterCount() - 1)
            cursor.setPosition(max(clamped, 0))
            self.editor.setTextCursor(cursor)
        finally:
            cursor.endEditBlock()
        return count

    # -------------------- Multi-cursor / highlight helpers --------------------

    def select_all_matches(self, search_text: str) -> int:
        """Populate ``editor.all_cursors`` with a cursor per forward match."""
        if not hasattr(self.editor, "all_cursors"):
            return 0

        self.editor.all_cursors.clear()
        self.editor.search_text = search_text

        options = self.get_options()
        try:
            match_cursors = list(self._engine.iter_matches(search_text, options))
        except InvalidRegexError as exc:
            CodeEditorMessageBox.warning(self, "Regex Error", f"Invalid regular expression: {exc}")
            return 0

        if not match_cursors:
            return 0

        self.editor.all_cursors.extend(match_cursors)
        self.editor.setTextCursor(match_cursors[-1])
        self.editor.viewport().update()
        return len(match_cursors)

    def count_matches(self, search_text: str) -> int:
        """Return the total number of forward matches (0 for invalid regex)."""
        options = self.get_options()
        try:
            return self._engine.count_matches(search_text, options)
        except InvalidRegexError:
            return 0

    def clear_multi_cursor(self):
        """Clear multi-cursor mode if active."""
        if hasattr(self.editor, "all_cursors"):
            self.editor.all_cursors.clear()
            self.editor.search_text = ""
            self.editor.viewport().update()

    def closeEvent(self, event):
        """Handle dialog close event."""
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
                self.match_case_cb.isChecked(),
                self.whole_words_cb.isChecked(),
                self.use_regex_cb.isChecked(),
                direction,
            )
            # Save to file immediately
            self.parent_window.settings_manager.save_settings()


# -------------------- Window-level entry points --------------------
#
# These bridge the QShortcut layer (``ShortcutHandler``) to the dialog without
# making the handler responsible for the dialog's lifecycle. The dialog is
# cached as ``main_window.find_replace_dialog`` on first use so subsequent
# Ctrl+F / Ctrl+H / F3 / Shift+F3 reuse it (preserving search history).


def _ensure_dialog(main_window):
    """Return ``(dialog, editor)`` for the active editor, lazy-creating the dialog.

    Returns ``(None, None)`` when no editor is available so callers can no-op.
    Re-binds ``dialog.editor`` to the current editor on every call: tabs change,
    but the dialog instance does not.
    """
    current_editor = main_window.get_current_editor()
    if not current_editor:
        return None, None

    dialog = getattr(main_window, "find_replace_dialog", None)
    if dialog is None:
        dialog = FindReplaceDialog(current_editor, main_window)
        main_window.find_replace_dialog = dialog

    dialog.editor = current_editor
    return dialog, current_editor


def show_find_dialog(main_window):
    """Show the find dialog, lazy-creating it on first use."""
    dialog, editor = _ensure_dialog(main_window)
    if dialog is None:
        return
    dialog.show_find_mode(editor.textCursor().selectedText())


def show_replace_dialog(main_window):
    """Show the replace dialog, lazy-creating it on first use."""
    dialog, editor = _ensure_dialog(main_window)
    if dialog is None:
        return
    dialog.show_replace_mode(editor.textCursor().selectedText())


def find_next(main_window):
    """Advance the cached dialog's search, or open the find dialog if hidden."""
    dialog = getattr(main_window, "find_replace_dialog", None)
    if dialog is not None and dialog.isVisible():
        dialog.find_next()
    else:
        show_find_dialog(main_window)


def find_previous(main_window):
    """Step back through the cached dialog's search, or open it if hidden."""
    dialog = getattr(main_window, "find_replace_dialog", None)
    if dialog is not None and dialog.isVisible():
        dialog.find_previous()
    else:
        show_find_dialog(main_window)
