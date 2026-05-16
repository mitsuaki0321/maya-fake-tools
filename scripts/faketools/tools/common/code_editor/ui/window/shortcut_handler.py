"""
Shortcut handler for Code Editor.
Manages all keyboard shortcuts and their associated functionality.
"""

from ......lib_ui.qt_compat import QKeySequence, QShortcut, Qt
from ..dialogs import (
    find_next as _find_next_in_dialog,
    find_previous as _find_previous_in_dialog,
    show_find_dialog as _show_find_dialog,
    show_replace_dialog as _show_replace_dialog,
)


class ShortcutHandler:
    """Handler for all keyboard shortcuts in the Code Editor."""

    def __init__(self, main_window):
        """Initialize the shortcut handler with reference to main window."""
        self.main_window = main_window

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

        # Note: Numpad Enter is handled directly in CodeEditor.keyPressEvent
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

        # Symbol rename (VSCode F2). Python-only — gated on the language
        # profile exposing a completion engine factory, which is the
        # same signal used to decide whether jedi is available for the
        # active document. Silent no-op for MEL / cursor-not-on-symbol.
        self.rename_symbol_shortcut = QShortcut(QKeySequence("F2"), self.main_window)
        self.rename_symbol_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.rename_symbol_shortcut.activated.connect(self._handle_rename_symbol)

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
        """Forward Ctrl+/ to the active editor's language-aware toggle."""
        editor = self.main_window.get_current_editor()
        if editor is not None:
            editor.toggle_line_comment()

    def _handle_run_current_line_or_selection(self):
        """Forward Ctrl+Enter to ExecutionManager."""
        self.main_window.execution_manager.run_current_line_or_selection()

    def _handle_run_entire_file(self):
        """Forward Ctrl+Shift+Enter to ExecutionManager."""
        self.main_window.execution_manager.run_entire_file()

    def _handle_show_find_dialog(self):
        """Forward Ctrl+F to the dialogs package (lazy-creates the dialog)."""
        _show_find_dialog(self.main_window)

    def _handle_show_replace_dialog(self):
        """Forward Ctrl+H to the dialogs package (lazy-creates the dialog)."""
        _show_replace_dialog(self.main_window)

    def _handle_find_next(self):
        """Forward F3: advance the cached search, or open the dialog if hidden."""
        _find_next_in_dialog(self.main_window)

    def _handle_find_previous(self):
        """Forward Shift+F3: step back through the cached search, or open the dialog."""
        _find_previous_in_dialog(self.main_window)

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
        """Forward Ctrl+Space to the toolbar so the button click path runs."""
        toolbar = getattr(self.main_window, "toolbar", None)
        if toolbar is None:
            return
        toolbar.toggle_autocomplete()

    def _handle_toggle_help_popup(self):
        """Forward Ctrl+Shift+Space to the help package.

        Lazy-imports ``toggle_help_popup`` so jedi / the help popup widget
        don't load until the user actually presses the shortcut.
        """
        from ..help.controller import toggle_help_popup

        toggle_help_popup(self.main_window)

    def _handle_rename_symbol(self):
        """F2 → inline rename of the identifier at the caret.

        Gated on the language profile exposing a completion engine factory
        (the same condition that decides whether jedi runs for this tab)
        so MEL files are a silent no-op. Lazy-imports the refactor logic
        and overlay so neither jedi nor the overlay widget loads until
        someone actually presses F2.
        """
        editor = self.main_window.get_current_editor()
        if editor is None or editor.language.completion_engine_factory is None:
            return

        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1  # jedi is 1-indexed
        column = cursor.columnNumber()

        from ...command.refactor import find_symbol_references
        from ..editor.rename_overlay import RenameOverlay

        code = editor.toPlainText()
        references = find_symbol_references(code=code, line=line, column=column, path=editor.file_path)
        if not references:
            return

        first = references[0]
        old_name = code[first.start : first.end]
        RenameOverlay(editor, references, old_name, cursor_offset=cursor.position())
