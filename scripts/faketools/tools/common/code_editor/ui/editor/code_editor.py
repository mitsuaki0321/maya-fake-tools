"""Per-tab code editor widget.

Hosts a single editor view inside a tab. Language behaviour (syntax
highlighting, future indent / run / completion hooks) is driven by an
injected :class:`~..languages.LanguageProfile`; tabs default to
:data:`~..languages.PYTHON` so existing call sites keep their original
behaviour.
"""

from logging import getLogger
from typing import Optional

from ......lib_ui.qt_compat import (
    QPainter,
    QPlainTextEdit,
    Qt,
    QTextCursor,
    Signal,
)
from ...languages import PYTHON, LanguageProfile
from ..autocomplete import AutocompleteController
from . import auto_close, auto_indent, context_menu, overlays
from .appearance import EditorAppearanceMixin
from .bracket_match_highlighter import BracketMatchHighlighter
from .code_folding import CodeFoldingManager
from .line_number_area import LineNumberArea
from .multi_cursor import MultiCursorMixin
from .shortcuts import EditorShortcuts
from .text_operations import EditorTextOperationsMixin

logger = getLogger(__name__)


class CodeEditor(QPlainTextEdit, EditorTextOperationsMixin, MultiCursorMixin, EditorAppearanceMixin):
    """Plain text editor view driven by a :class:`LanguageProfile`."""

    # Signal for focus lost (triggers session.json save)
    focus_lost = Signal()
    # Real content change — fires only when characters actually changed.
    # Use this instead of ``textChanged`` for anything that should NOT react to
    # QSyntaxHighlighter format reapplication (which also fires textChanged via
    # markContentsDirty and would otherwise flip is_modified back on after save).
    contentChanged = Signal()

    def __init__(self, parent=None, language: LanguageProfile = PYTHON):
        super().__init__(parent)

        self.language = language
        self.file_path = None
        self.is_modified = False
        self.highlighter = None

        # Font size management
        self.default_font_size = 10  # Will be set from settings
        self.current_font_size = self.default_font_size

        # Create line number area
        self.line_number_area = LineNumberArea(self)

        # Initialize shortcut manager
        self.shortcuts = EditorShortcuts()

        self.init_editor()
        self.setup_syntax_highlighting()

        # Initialize multi-cursor functionality
        self.init_multi_cursor()

        # Initialize code folding
        self.fold_manager = CodeFoldingManager(self)

        self.bracket_match_highlighter = BracketMatchHighlighter(self)

        # Autocomplete controller is built only for languages whose profile
        # supplies a completion_engine_factory. MEL and any future
        # language without one get no controller at all -- jedi is never
        # invoked on non-Python source.
        self.autocomplete: Optional[AutocompleteController] = None
        self._reconfigure_autocomplete()

        self.line_number_area.attach()
        self.connect_signals()

    def init_editor(self):
        """Initialize editor settings (appearance + language placeholder)."""
        self._init_appearance(self.current_font_size)
        self._apply_placeholder_text()

    def setup_syntax_highlighting(self):
        """Attach the language profile's highlighter, if any.

        Profiles without a ``highlighter_factory`` leave ``self.highlighter``
        at ``None`` so the editor falls back to plain unstyled text.

        Detaches any previously-installed highlighter first. ``QSyntaxHighlighter``
        instances stay registered against the document via Qt's parent/child
        relationship, so simply rebinding ``self.highlighter`` would leave the
        old highlighter listening to ``contentsChange`` and competing with the
        new one — most visibly, ``PythonHighlighter``'s debounced ``rehighlight()``
        would erase MEL formats roughly 30 ms after every keystroke.
        """
        if self.highlighter is not None:
            self.highlighter.setDocument(None)
            self.highlighter.setParent(None)
            self.highlighter.deleteLater()
            self.highlighter = None
        if self.language.highlighter_factory is None:
            return
        self.highlighter = self.language.highlighter_factory(self.document())

    def setPlainText(self, text):
        """Override to (re-)apply our proportional line height after every reset.

        ``setPlainText`` rebuilds the document from scratch, which loses any
        block format we applied earlier — so every external caller (file load,
        session restore, tab restore, …) would otherwise revert to Qt's default
        tight line spacing. Applying here keeps callers simple.
        """
        super().setPlainText(text)
        self._apply_line_height()

    def connect_signals(self):
        """Connect editor signals.

        All content-change tracking (modified flag, autocomplete, the
        ``contentChanged`` re-emission) goes through ``contentsChange`` rather
        than ``textChanged``. The latter also fires when QSyntaxHighlighter
        reapplies formats via ``markContentsDirty``, which would otherwise
        flip ``is_modified`` back to True right after save (visible as the
        tab "*" briefly disappearing then re-appearing on a saved file with
        any highlightable content) and feedback-loop into jedi.
        """
        self.document().contentsChange.connect(self._on_contents_change)
        self.cursorPositionChanged.connect(lambda: overlays.update_current_line_highlight(self))
        # selectionChanged covers shrink/expand within the same block, which
        # cursorPositionChanged + update_current_line_highlight short-circuits
        # past. The whitespace-dot overlay depends on a full repaint whenever
        # selection bounds shift, so force one here. Wrapped in a lambda for
        # consistency with the ``cursorPositionChanged`` connection above.
        self.selectionChanged.connect(lambda: self.viewport().update())
        overlays.update_current_line_highlight(self)

    def _on_contents_change(self, position: int, removed: int, added: int):
        """Bookkeeping for real edits; format-only notifications are filtered."""
        if removed == 0 and added == 0:
            return  # Formatting-only notification from the syntax highlighter.
        if not self.is_modified:
            self.is_modified = True
        self.contentChanged.emit()
        if getattr(self, "autocomplete", None) is not None:
            self.autocomplete.on_text_changed()

    def focusOutEvent(self, event):
        """Emit ``focus_lost`` so session.json can be saved."""
        super().focusOutEvent(event)
        self.focus_lost.emit()

    def shutdown(self):
        """Release per-tab resources before the widget is deleted on tab close.

        Qt deletes the editor's child QObjects — highlighter, completer, timers,
        fold manager, line-number area — automatically when ``deleteLater`` runs,
        so this only covers the two things the parent/child cascade does not:

        * an in-flight jedi worker, which would otherwise emit into a controller
          bound to a now-deleted editor (``teardown`` cancels it);
        * the highlighter's document link, detached so its 30 ms debounce timer
          can't run one last tokenize pass against a document being torn down.

        Defensive throughout: closing a tab must never raise from teardown.
        """
        try:
            if self.autocomplete is not None:
                self.autocomplete.teardown()
        except Exception:
            logger.debug("autocomplete teardown failed during shutdown", exc_info=True)
        try:
            if self.highlighter is not None:
                self.highlighter.setDocument(None)
        except Exception:
            logger.debug("highlighter detach failed during shutdown", exc_info=True)

    def set_language(self, language: LanguageProfile) -> None:
        """Rebind the editor to ``language`` and refresh language-driven UI.

        Re-runs the highlighter factory, the placeholder text, and the
        autocomplete controller so a tab that was created with one
        profile (e.g. the default) and later associated with a file of
        another language picks up the new highlighter / hint and stops
        / starts pulling completions through the right engine.
        """
        self.language = language
        self.setup_syntax_highlighting()
        self._apply_placeholder_text()
        self._reconfigure_autocomplete()

    def _apply_placeholder_text(self) -> None:
        """Set the placeholder hint based on the bound :class:`LanguageProfile`.

        Profiles without a ``line_comment`` skip the comment prefix so the hint
        stays a plain sentence rather than a stray ``Start typing X code...``.
        """
        prefix = self.language.line_comment_with_space or ""
        self.setPlaceholderText(f"{prefix}Start typing {self.language.display_name} code...")

    def _reconfigure_autocomplete(self) -> None:
        """(Re)build the autocomplete controller for the current language.

        Tears down any existing controller (uninstalls its event filters
        via ``set_enabled(False)``) before consulting
        ``language.completion_engine_factory``. A profile that leaves the
        factory at ``None`` ends with ``self.autocomplete = None`` so
        every consumer's existing ``getattr(editor, "autocomplete", None)``
        guard short-circuits cleanly -- no popup, no jedi calls, no
        cost on MEL tabs.
        """
        if self.autocomplete is not None:
            self.autocomplete.set_enabled(False)
            self.autocomplete = None

        factory = self.language.completion_engine_factory
        if factory is None:
            return

        engine = factory()
        self.autocomplete = AutocompleteController(self, engine)

    def wheelEvent(self, event):
        """Forward Ctrl+wheel to the appearance mixin for font zoom."""
        if event.modifiers() == Qt.ControlModifier:
            self.handle_zoom_wheel(event)
            return
        super().wheelEvent(event)

    def fold_current(self):
        """Fold the block at the current cursor position."""
        block_number = self.textCursor().blockNumber()
        if self.fold_manager.is_fold_header(block_number):
            self.fold_manager.fold(block_number)

    def unfold_current(self):
        """Unfold the block at the current cursor position."""
        block_number = self.textCursor().blockNumber()
        if self.fold_manager.is_fold_header(block_number):
            self.fold_manager.unfold(block_number)

    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        self.line_number_area.layout_for_resize()

    def insertFromMimeData(self, source):
        """Override to ensure plain text paste only."""
        # Get plain text from the clipboard
        text = source.text()
        if text:
            # Insert as plain text without any formatting
            cursor = self.textCursor()
            cursor.insertText(text)
        # Don't call super() to avoid default formatting behavior

    def keyPressEvent(self, event):
        """Handle key press events using the shortcut manager."""
        # Give autocomplete first dibs: when the popup is visible it claims
        # Enter / Tab / Escape / arrow keys before anything else looks at them.
        if getattr(self, "autocomplete", None) is not None and self.autocomplete.handle_key_press(event):
            return

        # Handle numpad Enter key (Key_Enter) for running script
        # Note: Qt.Key_Enter is numpad Enter with KeypadModifier, Qt.Key_Return is main keyboard Enter
        if event.key() == Qt.Key_Enter and event.modifiers() == Qt.KeypadModifier:
            # Run current script (same as toolbar Run button)
            # Find the main window to access execution_manager
            main_window = self.window()
            if hasattr(main_window, "execution_manager"):
                main_window.execution_manager.run_current_script()
                return

            # Alternative: try through parent chain
            parent_widget = self.parent()
            while parent_widget:
                if hasattr(parent_widget, "execution_manager"):
                    parent_widget.execution_manager.run_current_script()
                    return
                parent_widget = parent_widget.parent()

        # Handle Escape key: exit multi-cursor mode
        if event.key() == Qt.Key_Escape and self.all_cursors:
            self.clear_multi_cursors()
            return

        # Try to handle multi-cursor keyboard events first
        if self.handle_multi_cursor_keys(event):
            return

        # Auto-close brackets / quotes / surround-selection. Runs before the
        # shortcut manager so the empty-pair Backspace shortcut wins over the
        # smart-indent Backspace registered in ``EditorShortcuts``. Skips
        # itself entirely when multi-cursor is active.
        if auto_close.handle_key(self, event):
            return

        # Handle Home key with smart home behavior (single-cursor mode)
        # Toggles between first non-whitespace position and line start on repeated presses
        if event.key() == Qt.Key_Home and not (event.modifiers() & Qt.ControlModifier):
            cursor = self.textCursor()
            smart_home_pos = self.get_first_non_whitespace_position(cursor)
            line_start_pos = cursor.block().position()
            target_pos = line_start_pos if cursor.position() == smart_home_pos else smart_home_pos
            if event.modifiers() & Qt.ShiftModifier:
                cursor.setPosition(target_pos, QTextCursor.KeepAnchor)
            else:
                cursor.setPosition(target_pos)
            self.setTextCursor(cursor)
            return

        # Try to handle the event with the shortcut manager
        if self.shortcuts.handle_key_event(event, self):
            return

        # If not handled by shortcuts, delegate to parent
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Dispatch mouse presses (middle-button rect, Ctrl+click) to multi-cursor."""
        if self.handle_multi_cursor_mouse_press(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Dispatch mouse moves (rect drag, Ctrl+drag) to multi-cursor."""
        if self.handle_multi_cursor_mouse_move(event):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Dispatch mouse releases (rect finalize, Ctrl+click commit) to multi-cursor."""
        if self.handle_multi_cursor_mouse_release(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Paint text, then editor overlays, then multi-cursor indicators.

        ``paint_current_line_border`` runs *before* ``super()`` so the row's
        top/bottom rules sit behind the text and caret — otherwise Qt's text
        painter (which fires inside ``super()``) would render glyph descenders
        on top of the lines while the lines would themselves clip the caret's
        first/last pixel.
        """
        overlays.paint_current_line_border(self, event)
        super().paintEvent(event)
        overlays.paint_indent_guides(self, event)
        overlays.paint_fold_placeholders(self, event)
        overlays.paint_selected_whitespace_dots(self, event)
        self.bracket_match_highlighter.paint(event)

        painter = QPainter(self.viewport())
        self.paint_multi_cursors(painter)
        painter.end()

    def contextMenuEvent(self, event):
        """Show the editor's right-click menu."""
        context_menu.build_context_menu(self, event).exec_(event.globalPos())

    def handle_return_key(self):
        """Handle Return/Enter key press for auto-indentation."""
        block_number = self.textCursor().blockNumber()
        if self.fold_manager.is_folded(block_number):
            # Prevents inserting into hidden blocks.
            self.fold_manager.unfold(block_number)

        cursor = self.textCursor()
        current_position = cursor.position()

        cursor.movePosition(QTextCursor.StartOfLine)
        line_start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        current_line = cursor.selectedText()

        cursor.setPosition(line_start)
        cursor.setPosition(current_position, QTextCursor.KeepAnchor)
        text_before_cursor = cursor.selectedText()

        cursor.setPosition(current_position)
        self.setTextCursor(cursor)

        new_indent = auto_indent.compute_indent(
            self.document(),
            block_number,
            current_line,
            text_before_cursor,
            self.language,
        )
        self.insertPlainText("\n" + new_indent)
