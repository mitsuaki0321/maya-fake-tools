"""Per-tab code editor widget.

Hosts a single editor view inside a tab. Language behaviour (syntax
highlighting, future indent / run / completion hooks) is driven by an
injected :class:`~..languages.LanguageProfile`; tabs default to
:data:`~..languages.PYTHON` so existing call sites keep their original
behaviour.
"""

from logging import getLogger
import os
from typing import Optional

from ......lib_ui.qt_compat import (
    QPainter,
    QPlainTextEdit,
    Qt,
    QTextBlockFormat,
    QTextCursor,
    Signal,
)
from ...command import file_io
from ...languages import PYTHON, LanguageProfile, get_profile_for_path
from ...themes import AppTheme
from ..autocomplete import AutocompleteController
from ..dialogs import CodeEditorMessageBox
from . import auto_indent, context_menu, overlays
from .bracket_match_highlighter import BracketMatchHighlighter
from .code_folding import CodeFoldingManager
from .line_number_area import LineNumberArea
from .multi_cursor import MultiCursorMixin
from .shortcuts import EditorShortcuts
from .text_operations import EditorTextOperationsMixin

logger = getLogger(__name__)

# Editor constants
DEFAULT_TAB_SIZE = 4


class CodeEditor(QPlainTextEdit, EditorTextOperationsMixin, MultiCursorMixin):
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

        self.setup_line_numbers()
        self.connect_signals()

    def _get_exec_namespaces(self) -> list[dict]:
        """Return the live namespaces jedi.Interpreter should consult.

        Two sources, in priority order:

        1. The editor's own ``exec_globals`` (populated by
           :func:`build_exec_globals` with ``cmds`` / ``om2`` / ``om`` and
           whatever the user's Run has added since).
        2. Maya's ``__main__.__dict__``. This catches modules the user
           imported in Maya's Script Editor but never executed inside our
           editor — without it, ``import eST3`` done at the Maya prompt
           would be invisible to the popup until the user ran *any* code
           through our Run button (which syncs ``__main__`` into
           ``exec_globals``).
        """
        namespaces: list[dict] = []
        node = self.parent()
        while node is not None:
            exec_globals = getattr(node, "exec_globals", None)
            if isinstance(exec_globals, dict):
                namespaces.append(exec_globals)
                break
            node = node.parent() if hasattr(node, "parent") else None

        try:
            import __main__

            main_dict = getattr(__main__, "__dict__", None)
            # Identity check, not ``in`` — value comparison would compare every
            # key/value pair across exec_globals and __main__.__dict__, which
            # both can be large in a Maya session and which gets called on every
            # autocomplete dispatch.
            if isinstance(main_dict, dict) and all(d is not main_dict for d in namespaces):
                namespaces.append(main_dict)
        except Exception as exc:
            logger.debug(f"failed to attach __main__ to namespaces: {exc}")

        return namespaces

    def init_editor(self):
        """Initialize editor settings."""
        self.setFont(AppTheme.make_monospace_font(self.current_font_size))

        # Set tab width (4 spaces * 10 pixels = 40)
        tab_stop_distance = DEFAULT_TAB_SIZE * 10
        try:
            # PySide6/Qt6
            self.setTabStopDistance(tab_stop_distance)
        except AttributeError:
            # PySide2/Qt5 fallback
            self.setTabStopWidth(tab_stop_distance)

        # Wider caret so it stays visible when sitting on the bracket-match
        # rectangle's 1px border (e.g. cursor at ``)|``).
        self.setCursorWidth(2)

        self._apply_line_height()

        # Word wrap enabled by default
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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

    def _apply_line_height(self):
        """Apply ``AppTheme.LINE_HEIGHT_PERCENT`` to every block in the document.

        Qt's default line spacing follows the font's natural metrics, which is
        noticeably tighter than VSCode at the same font. Setting a proportional
        line height on every block — including the cursor's current block, so
        new blocks inherit it on Enter — gives VSCode-equivalent breathing room.
        """
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        block_format = QTextBlockFormat()
        # PySide6 expects (float, int); the enum value 1 is ``ProportionalHeight``.
        # Hardcoded int avoids ``LineHeightTypes`` not accepted by the strict overload.
        block_format.setLineHeight(float(AppTheme.LINE_HEIGHT_PERCENT), 1)
        cursor.mergeBlockFormat(block_format)

    def setup_line_numbers(self):
        """Setup line number area."""
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

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

    def load_file(self, file_path: str) -> bool:
        """Load ``file_path`` into the editor via the command-layer reader.

        Re-binds the editor to the language profile resolved from the file's
        extension. The tab widget creates editors with the default profile and
        only learns the file path here, so without this rebind a ``foo.mel``
        loaded into a freshly-constructed editor would stay bound to Python
        and dispatch Run / placeholder / highlighter to the wrong language.
        """
        content, error = file_io.read_text(file_path)
        if content is None:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to load file: {error}")
            return False
        new_language = get_profile_for_path(file_path)
        if new_language is not self.language:
            self.set_language(new_language)
        self.setPlainText(content)
        self.file_path = file_path
        self.is_modified = False
        return True

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
        self.autocomplete = AutocompleteController(
            self,
            engine,
            namespace_provider=self._get_exec_namespaces,
        )

    def save_file(self, file_path: str = None) -> bool:
        """Save the editor contents via the command-layer writer."""
        if file_path is None:
            file_path = self.file_path
        if file_path is None:
            return False

        error = file_io.write_text(file_path, self.toPlainText())
        if error:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to save file: {error}")
            return False

        self.file_path = file_path
        self.is_modified = False
        self.document().setModified(False)
        return True

    def get_display_name(self) -> str:
        """Get display name for tab."""
        # Special handling for preview tabs
        if hasattr(self, "is_preview") and self.is_preview:
            # For preview tabs, use the preview_title without any modifications
            if hasattr(self, "preview_title"):
                return self.preview_title
            return "Preview"

        if hasattr(self, "is_draft") and self.is_draft:
            name = "Draft"  # Draft tab never shows asterisk
        elif self.file_path:
            name = os.path.basename(self.file_path)
        else:
            name = "Untitled"

        # Add asterisk for modified files (but not for Draft tab)
        # Check both custom property and QTextDocument modified state
        is_modified = (self.is_modified or self.document().isModified()) and not (hasattr(self, "is_draft") and self.is_draft)
        if is_modified:
            name += "*"

        return name

    def wheelEvent(self, event):
        """Handle mouse wheel events for font size changes."""
        # Handle wheel event for font size changes
        # Check if Ctrl is pressed for font size change
        if event.modifiers() == Qt.ControlModifier:
            # Get wheel delta
            delta = event.angleDelta().y()
            # Ctrl+wheel detected for font size adjustment

            # Change font size
            if delta > 0:
                # Wheel up - increase font size
                # Increase font size
                self.increase_font_size()
            elif delta < 0:
                # Wheel down - decrease font size
                # Decrease font size
                self.decrease_font_size()

            # Accept the event to prevent scrolling
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)

    def increase_font_size(self):
        """Increase font size by 1."""
        new_size = min(self.current_font_size + 1, 32)  # Max size 32
        self.set_font_size(new_size)

    def decrease_font_size(self):
        """Decrease font size by 1."""
        new_size = max(self.current_font_size - 1, 6)  # Min size 6
        self.set_font_size(new_size)

    def set_font_size(self, size):
        """Set font size for the editor."""
        self.current_font_size = size
        self.setFont(AppTheme.make_monospace_font(size))

        # Update line number area width and force repaint with new font size
        if hasattr(self, "line_number_area"):
            self.update_line_number_area_width(0)
            self.line_number_area.update()

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

    def set_word_wrap(self, enabled):
        """Set word wrap mode.

        Args:
            enabled (bool): True to wrap at widget width, False for no wrap.
        """
        if enabled:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def set_default_font_size(self, size):
        """Set default font size from settings."""
        self.default_font_size = size
        self.current_font_size = size
        self.set_font_size(size)

    def update_line_number_area_width(self, new_block_count):
        """Update the editor's left margin to fit the line number area."""
        self.setViewportMargins(self.line_number_area.calculate_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update the line number area when scrolling or resizing."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, int(rect.y()), int(self.line_number_area.width()), int(rect.height()))

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area.calculate_width(), cr.height())

    def highlight_current_line(self):
        """Repaint the viewport when the caret's line or selection state flips.

        The actual decoration is drawn in
        :func:`overlays.paint_current_line_border` (top/bottom rules) —
        this hook just invalidates the viewport so the rules move with the
        caret. Short-circuited when neither the line nor the selection state
        changed, since intra-line cursor moves don't need a full repaint.
        """
        cursor = self.textCursor()
        cursor_line = cursor.blockNumber()
        has_selection = cursor.hasSelection()
        if cursor_line == getattr(self, "_last_highlight_line", -1) and has_selection == getattr(self, "_last_had_selection", False):
            return
        self._last_highlight_line = cursor_line
        self._last_had_selection = has_selection
        self.viewport().update()

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


# Deprecated alias kept while call sites continue to refer to ``PythonEditor`` —
# every existing ``isinstance(editor, PythonEditor)`` check still succeeds.
PythonEditor = CodeEditor
