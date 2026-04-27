"""
Shortcut handler for Code Editor.
Manages all keyboard shortcuts and their associated functionality.
"""

from .....lib_ui.qt_compat import QApplication, QKeySequence, QShortcut, Qt, QTextCursor
from .find_replace_dialog import FindReplaceDialog


class ShortcutHandler:
    """Handler for all keyboard shortcuts in the Code Editor."""

    def __init__(self, main_window):
        """Initialize the shortcut handler with reference to main window."""
        self.main_window = main_window
        self.find_replace_dialog = None

    def _is_code_editor_tab_focused(self):
        """Check if one of the code editor tabs (not explorer or other areas) has focus."""
        try:
            if not self.main_window.code_editor:
                return False

            focused_widget = QApplication.focusWidget()
            if not focused_widget:
                return False

            # Check if focus is on any of the editor tabs (actual editor widgets)
            code_editor = self.main_window.code_editor

            # Check if focus is on any of the editor tabs
            for i in range(code_editor.count()):
                editor = code_editor.widget(i)
                if editor and (focused_widget == editor):
                    return True

                # Check if focused widget is a child of this specific editor
                try:
                    if editor:
                        parent = focused_widget.parent()
                        while parent:
                            if parent == editor:
                                return True
                            try:
                                parent = parent.parent()
                            except RuntimeError:
                                break
                except RuntimeError:
                    continue

            return False

        except RuntimeError:
            # Any widget access failed, assume not focused
            return False

    def setup_shortcuts(self):
        """Setup global keyboard shortcuts (VSCode-like)."""
        # Search shortcuts - only active within code editor tabs
        self.find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.main_window)
        self.find_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.find_shortcut.activated.connect(self._handle_show_find_dialog)

        self.replace_shortcut = QShortcut(QKeySequence("Ctrl+H"), self.main_window)
        self.replace_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.replace_shortcut.activated.connect(self._handle_show_replace_dialog)

        self.find_next_shortcut = QShortcut(QKeySequence("F3"), self.main_window)
        self.find_next_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.find_next_shortcut.activated.connect(self._handle_find_next)

        self.find_prev_shortcut = QShortcut(QKeySequence("Shift+F3"), self.main_window)
        self.find_prev_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.find_prev_shortcut.activated.connect(self._handle_find_previous)

        # File shortcuts (only active within code editor tabs)
        self.new_file_shortcut = QShortcut(QKeySequence("Ctrl+N"), self.main_window)
        self.new_file_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.new_file_shortcut.activated.connect(self._handle_new_file)

        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.main_window)
        self.save_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self._handle_save_file)

        self.save_all_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self.main_window)
        self.save_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.save_all_shortcut.activated.connect(self._handle_save_all_files)

        # Execution shortcuts (VSCode-like) - only active within code editor tabs
        self.run_line_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.main_window)  # Ctrl+Enter
        self.run_line_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.run_line_shortcut.activated.connect(self._handle_run_current_line_or_selection)

        self.run_file_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Return"), self.main_window)  # Ctrl+Shift+Enter
        self.run_file_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.run_file_shortcut.activated.connect(self._handle_run_entire_file)

        # Note: Numpad Enter is handled directly in PythonEditor.keyPressEvent
        # to ensure it takes precedence over default text editing behavior

        # Comment toggle (VSCode-like, only active within code editor tabs)
        self.toggle_comment_shortcut = QShortcut(QKeySequence("Ctrl+/"), self.main_window)
        self.toggle_comment_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.toggle_comment_shortcut.activated.connect(self._handle_toggle_line_comment)

        # Clear terminal - changed from Ctrl+Shift+L to Ctrl+K for multi-cursor support
        self.clear_terminal_shortcut = QShortcut(QKeySequence("Ctrl+K"), self.main_window)
        self.clear_terminal_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.clear_terminal_shortcut.activated.connect(self._handle_clear_terminal)

        # Fold all / Unfold all shortcuts
        self.fold_all_shortcut = QShortcut(QKeySequence("Ctrl+Alt+["), self.main_window)
        self.fold_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.fold_all_shortcut.activated.connect(self._handle_fold_all)

        self.unfold_all_shortcut = QShortcut(QKeySequence("Ctrl+Alt+]"), self.main_window)
        self.unfold_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.unfold_all_shortcut.activated.connect(self._handle_unfold_all)

        # Autocomplete toggle. Ctrl+Space collides with Maya's "Toggle Maximize
        # Panel Size" when the shortcut uses Qt.WindowShortcut / Qt.ApplicationShortcut
        # — scoping it to WidgetWithChildrenShortcut lets Qt dispatch the event
        # before Maya's global hotkey handler sees it, same trick Ctrl+N uses
        # to co-exist with Maya's "New Scene".
        self.toggle_autocomplete_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self.main_window)
        self.toggle_autocomplete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.toggle_autocomplete_shortcut.activated.connect(self._handle_toggle_autocomplete)

        # Help popup toggle. Paired with Ctrl+Space (+Shift) so users
        # only need to remember one base key. Opens the floating doc
        # window for the autocomplete list's highlighted candidate, or
        # — when the list is closed — for the identifier at the caret.
        # jedi stays silent until this shortcut fires.
        self.toggle_help_popup_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Space"), self.main_window)
        self.toggle_help_popup_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.toggle_help_popup_shortcut.activated.connect(self._handle_toggle_help_popup)

    # Editor tab-scoped shortcut handlers (requires focus check)
    def _handle_new_file(self):
        """Handle new file shortcut - only when code editor widget has focus."""
        self.main_window.file_ops.new_file()

    def _handle_save_file(self):
        """Handle save file shortcut - only when code editor widget has focus."""
        self.main_window.file_ops.save_current_file()

    def _handle_save_all_files(self):
        """Handle save all files shortcut - only when code editor widget has focus."""
        self.main_window.file_ops.save_all_files()

    def _handle_toggle_line_comment(self):
        """Handle toggle line comment shortcut - only when code editor widget has focus."""
        self.toggle_line_comment()

    def _handle_run_current_line_or_selection(self):
        """Handle run current line or selection shortcut - only when code editor widget has focus."""
        self.run_current_line_or_selection()

    def _handle_run_entire_file(self):
        """Handle run entire file shortcut - only when code editor widget has focus."""
        self.run_entire_file()

    def _handle_show_find_dialog(self):
        """Handle show find dialog shortcut - only when code editor widget has focus."""
        self.show_find_dialog()

    def _handle_show_replace_dialog(self):
        """Handle show replace dialog shortcut - only when code editor widget has focus."""
        self.show_replace_dialog()

    def _handle_find_next(self):
        """Handle find next shortcut - only when code editor widget has focus."""
        self.find_next()

    def _handle_find_previous(self):
        """Handle find previous shortcut - only when code editor widget has focus."""
        self.find_previous()

    def _handle_clear_terminal(self):
        """Handle clear terminal shortcut - only when code editor widget has focus."""
        self.main_window.layout_manager.clear_terminal()

    def _handle_fold_all(self):
        """Handle fold all shortcut."""
        self.main_window.fold_all()

    def _handle_unfold_all(self):
        """Handle unfold all shortcut."""
        self.main_window.unfold_all()

    def _handle_toggle_autocomplete(self):
        """Flip the autocomplete toggle and keep the toolbar button in sync.

        Routes through the toolbar's ``autocomplete_toggled`` signal rather
        than calling ``main_window.toggle_autocomplete`` directly so the
        existing signal path (button state, settings persistence, etc.)
        runs exactly like a user click would.
        """
        toolbar = getattr(self.main_window, "toolbar", None)
        if toolbar is None:
            return
        button = getattr(toolbar, "autocomplete_button", None)
        if button is None or not button.isEnabled():
            # jedi missing → button disabled; do nothing so the shortcut is
            # a no-op rather than silently toggling a setting nobody can see.
            return
        button.set_active(not button.is_active())
        toolbar.autocomplete_toggled.emit(button.is_active())

    def _handle_toggle_help_popup(self):
        """Toggle the floating docstring popup (Ctrl+Shift+Space).

        Lazily constructs the :class:`HelpPopupController` on first use
        so jedi / the help popup widget don't load until someone asks.
        The controller decides whether to target the autocomplete
        selection or the identifier at the caret based on popup state.
        """
        controller = self._get_or_create_help_popup_controller()
        if controller is None:
            return
        controller.toggle()

    def _get_or_create_help_popup_controller(self):
        """Return the shared ``HelpPopupController``, lazily building it.

        Returns ``None`` when autocomplete isn't wired up (jedi missing,
        no editor, etc.). The controller is attached to the main window
        so it lives as long as the window does.
        """
        existing = getattr(self.main_window, "_help_popup_controller", None)
        if existing is not None:
            return existing

        engine = self._shared_engine()
        if engine is None:
            return None

        from .help.controller import HelpPopupController

        controller = HelpPopupController(self.main_window, engine)
        self.main_window._help_popup_controller = controller
        return controller

    def _shared_engine(self):
        """Find the ``JediEngine`` used by the current editor's autocomplete.

        Reusing the already-configured engine means we inherit its
        ``sys.path`` / stubs / subprocess avoidance settings. Returns
        ``None`` when no editor is available yet (tool just opened,
        headless, jedi missing).
        """
        get_current_editor = getattr(self.main_window, "get_current_editor", None)
        if get_current_editor is None:
            return None
        editor = get_current_editor()
        if editor is None:
            return None
        ac = getattr(editor, "autocomplete", None)
        if ac is None:
            return None
        return getattr(ac, "engine", None)

    def show_find_dialog(self):
        """Show the find dialog."""
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            return

        # Create dialog if it doesn't exist
        if self.find_replace_dialog is None:
            self.find_replace_dialog = FindReplaceDialog(current_editor, self.main_window)

        # Update dialog's editor reference
        self.find_replace_dialog.editor = current_editor

        # Get selected text if any
        selected_text = current_editor.textCursor().selectedText()

        # Show dialog in find mode
        self.find_replace_dialog.show_find_mode(selected_text)

    def show_replace_dialog(self):
        """Show the replace dialog."""
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            return

        # Create dialog if it doesn't exist
        if self.find_replace_dialog is None:
            self.find_replace_dialog = FindReplaceDialog(current_editor, self.main_window)

        # Update dialog's editor reference
        self.find_replace_dialog.editor = current_editor

        # Get selected text if any
        selected_text = current_editor.textCursor().selectedText()

        # Show dialog in replace mode
        self.find_replace_dialog.show_replace_mode(selected_text)

    def find_next(self):
        """Find next occurrence using existing dialog."""
        if self.find_replace_dialog and self.find_replace_dialog.isVisible():
            self.find_replace_dialog.find_next()
        else:
            # Show find dialog if not visible
            self.show_find_dialog()

    def find_previous(self):
        """Find previous occurrence using existing dialog."""
        if self.find_replace_dialog and self.find_replace_dialog.isVisible():
            self.find_replace_dialog.find_previous()
        else:
            # Show find dialog if not visible
            self.show_find_dialog()

    def run_current_line_or_selection(self):
        """Run current line or selected text (Ctrl+Enter)."""
        # Run current line or selection
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            return

        cursor = current_editor.textCursor()

        if cursor.hasSelection():
            # Execute selected text
            selected_text = cursor.selectedText().replace("\u2029", "\n")  # Handle paragraph separators
            if selected_text.strip():
                self.main_window.execution_manager.is_selection_execution = True
                self.main_window.execution_manager.is_full_execution = False
                self.main_window.execution_manager.execute_python_code(selected_text)
        else:
            # Execute current line
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText().strip()
            if line_text:
                self.main_window.execution_manager.is_selection_execution = True
                self.main_window.execution_manager.is_full_execution = False
                self.main_window.execution_manager.execute_python_code(line_text)
            else:
                self.main_window.output_terminal.append_warning("Current line is empty")

    def run_entire_file(self):
        """Run entire file (Ctrl+Shift+Enter)."""
        # Run entire file
        if not self.main_window.code_editor:
            return

        code = self.main_window.code_editor.get_current_code()
        if code.strip():
            self.main_window.execution_manager.is_selection_execution = False
            self.main_window.execution_manager.is_full_execution = True
            self.main_window.execution_manager.execute_python_code(code)
        else:
            self.main_window.output_terminal.append_warning("File is empty")

    def toggle_line_comment(self):
        """Toggle line comment (Ctrl+/)."""
        # Toggle line comment
        current_editor = self.main_window.get_current_editor()
        if not current_editor:
            return

        # Check if we have multi-cursors
        if hasattr(current_editor, "all_cursors") and current_editor.all_cursors:
            # Handle multi-cursor comment toggle
            self._toggle_comment_multi_cursor(current_editor)
            return

        cursor = current_editor.textCursor()

        # Get selected lines or current line
        if cursor.hasSelection():
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
        else:
            start_pos = cursor.position()
            end_pos = cursor.position()

        # Move to start of first selected line
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        # Move to end of last selected line
        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        # Begin edit block for undo
        cursor.beginEditBlock()

        try:
            # Check if all lines are commented
            all_commented = True
            for line_num in range(start_line, end_line + 1):
                cursor.movePosition(QTextCursor.Start)
                for _ in range(line_num):
                    cursor.movePosition(QTextCursor.NextBlock)
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                line_text = cursor.selectedText().lstrip()

                if line_text and not line_text.startswith("#"):
                    all_commented = False
                    break

            # Toggle comments
            for line_num in range(start_line, end_line + 1):
                cursor.movePosition(QTextCursor.Start)
                for _ in range(line_num):
                    cursor.movePosition(QTextCursor.NextBlock)
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                line_text = cursor.selectedText()

                if not line_text.strip():  # Skip empty lines
                    continue

                cursor.movePosition(QTextCursor.StartOfLine)

                if all_commented:
                    # Remove comment
                    stripped = line_text.lstrip()
                    if stripped.startswith("# "):
                        # Find position of '# '
                        comment_pos = line_text.find("# ")
                        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, comment_pos)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)  # Select '# '
                        cursor.removeSelectedText()
                    elif stripped.startswith("#"):
                        # Find position of '#'
                        comment_pos = line_text.find("#")
                        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, comment_pos)
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)  # Select '#'
                        cursor.removeSelectedText()
                else:
                    # Add comment
                    first_non_space = len(line_text) - len(line_text.lstrip())
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, first_non_space)
                    cursor.insertText("# ")

        finally:
            cursor.endEditBlock()

    def _toggle_comment_multi_cursor(self, editor):
        """Toggle comments for multi-cursor lines."""
        doc = editor.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        # Get all unique line numbers with cursors
        lines_with_cursors = set()
        for c in editor.all_cursors:
            lines_with_cursors.add(c.blockNumber())

        # Check if all lines are commented
        all_commented = True
        for line_num in lines_with_cursors:
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            line_text = cursor.block().text().lstrip()
            if line_text and not line_text.startswith("#"):
                all_commented = False
                break

        # Toggle comments on all lines with cursors
        for line_num in sorted(lines_with_cursors):
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            cursor.movePosition(QTextCursor.StartOfLine)

            # Get line text
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()
            cursor.movePosition(QTextCursor.StartOfLine)

            # Skip empty lines
            if not line_text.strip():
                continue

            # Toggle comment
            if all_commented:
                # Remove comment
                if line_text.lstrip().startswith("#"):
                    spaces = len(line_text) - len(line_text.lstrip())
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, spaces)
                    cursor.deleteChar()
                    if cursor.block().text() and cursor.block().text()[0] == " ":
                        cursor.deleteChar()
            else:
                # Add comment
                leading_spaces = len(line_text) - len(line_text.lstrip())
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, leading_spaces)
                cursor.insertText("# ")

        cursor.endEditBlock()

        # Update multi-cursor positions
        editor.viewport().update()
