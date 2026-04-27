"""
Code editor widget with tab support.
Provides tabbed interface for editing multiple Python files.
"""

from logging import getLogger
import os
import time

from .....lib_ui.qt_compat import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPlainTextEdit,
    Qt,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
    Signal,
)
from ..command import file_io
from ..command.autocomplete import JediEngine
from ..highlighting.python_highlighter import PythonHighlighter
from ..themes import AppTheme
from . import auto_indent, editor_context_menu
from .autocomplete import AutocompleteController
from .code_folding import CodeFoldingManager
from .dialog_base import CodeEditorMessageBox
from .editor_shortcuts import EditorShortcuts
from .editor_text_operations import EditorTextOperationsMixin
from .line_number_area import LineNumberArea
from .multi_cursor import MultiCursorMixin

logger = getLogger(__name__)

# Editor constants
DEFAULT_FONT_FAMILY = "Consolas"
DEFAULT_TAB_SIZE = 4

# Shared across all PythonEditor instances — jedi has internal caches keyed by
# source hash that we want to reuse across tabs. Stateless, so safe to share.
_SHARED_JEDI_ENGINE = JediEngine()
_STUB_PATHS_CONFIGURED = False


def _configure_engine_stub_paths():
    """Point the shared jedi engine at the bundled Maya stubs.

    Runs lazily on the first editor construction so we only pay for the
    ``maya.cmds.about`` call when someone actually opens the Code Editor.
    Stubs live under ``faketools/resources/maya_stubs/maya{version}/`` and
    are committed with the repo — there's no per-user generator step. If we
    haven't shipped stubs for this Maya version yet (or we're outside Maya),
    this is a silent no-op and jedi falls back to live introspection via
    ``exec_globals``.
    """
    global _STUB_PATHS_CONFIGURED
    if _STUB_PATHS_CONFIGURED:
        return
    _STUB_PATHS_CONFIGURED = True

    t_start = time.perf_counter()

    try:
        import maya.cmds as _cmds  # type: ignore

        maya_version = str(_cmds.about(version=True))
    except Exception:
        return

    try:
        from ..command import stub_generator as stub_command
    except Exception as exc:
        logger.debug(f"stub_generator unavailable: {exc}")
        return

    t_exist_start = time.perf_counter()
    stubs_ok = stub_command.stubs_exist(maya_version)
    t_exist_ms = (time.perf_counter() - t_exist_start) * 1000
    if not stubs_ok:
        logger.info(f"Maya {maya_version} stubs not bundled with this build — cmds / OpenMaya autocomplete will fall back to live introspection.")
        return

    # Pin the stub dir at ``sys.path[0]`` *and* on the jedi ``Project`` so
    # ``import maya`` resolves to the bundled ``maya-stubs`` package before
    # Maya's real install (which otherwise wins because its path is
    # auto-discovered by jedi's environment detection).
    import sys

    stubs_root = stub_command.get_package_root(maya_version)
    stubs_root_str = str(stubs_root)
    if stubs_root_str not in sys.path:
        sys.path.insert(0, stubs_root_str)

    _SHARED_JEDI_ENGINE.set_extra_paths([stubs_root_str])
    t_total_ms = (time.perf_counter() - t_start) * 1000
    logger.info(f"Autocomplete stubs active: {stubs_root} (setup={t_total_ms:.1f}ms stubs_exist={t_exist_ms:.1f}ms)")


class PythonEditor(QPlainTextEdit, EditorTextOperationsMixin, MultiCursorMixin):
    """Plain text editor optimized for Python code."""

    # Signal for object inspection
    inspect_object = Signal(str, str)  # (object_name, inspection_type)
    # Signal for focus lost (triggers backup flush for network HDD performance)
    focus_lost = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_path = None
        self.is_modified = False
        self.custom_name = None  # For renamed tabs
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

        # Autocomplete controller (jedi-backed). Silently inert if jedi is missing.
        _configure_engine_stub_paths()
        self.autocomplete = AutocompleteController(
            self,
            _SHARED_JEDI_ENGINE,
            namespace_provider=self._get_exec_namespaces,
        )

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
            if isinstance(main_dict, dict) and main_dict not in namespaces:
                namespaces.append(main_dict)
        except Exception as exc:
            logger.debug(f"failed to attach __main__ to namespaces: {exc}")

        return namespaces

    def init_editor(self):
        """Initialize editor settings."""
        # Set font using current font size
        font = QFont(DEFAULT_FONT_FAMILY, self.current_font_size)
        if not font.exactMatch():
            font = QFont("Courier New", self.current_font_size)
        self.setFont(font)

        # Set tab width (4 spaces * 10 pixels = 40)
        tab_stop_distance = DEFAULT_TAB_SIZE * 10
        try:
            # PySide6/Qt6
            self.setTabStopDistance(tab_stop_distance)
        except AttributeError:
            # PySide2/Qt5 fallback
            self.setTabStopWidth(tab_stop_distance)

        # Word wrap enabled by default
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Set placeholder text
        self.setPlaceholderText("# Start typing Python code...")

    def setup_syntax_highlighting(self):
        """Setup Python syntax highlighting."""
        self.highlighter = PythonHighlighter(self.document())

    def setup_line_numbers(self):
        """Setup line number area."""
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def connect_signals(self):
        """Connect editor signals."""
        self.textChanged.connect(self.on_text_changed)
        # Route *actual* content edits (not pure formatting repaints) to the
        # autocomplete controller via ``contentsChange``. ``textChanged`` also
        # fires when QSyntaxHighlighter reapplies formats via
        # ``markContentsDirty``, which would otherwise feedback-loop into jedi
        # once the popup is up.
        self.document().contentsChange.connect(self._on_contents_change)

    def on_text_changed(self):
        """Handle text changes — bookkeeping only (modified flag)."""
        if not self.is_modified:
            self.is_modified = True

    def _on_contents_change(self, position: int, removed: int, added: int):
        """Bridge to autocomplete: fires only when characters actually changed."""
        if removed == 0 and added == 0:
            return  # Formatting-only notification from the syntax highlighter.
        if getattr(self, "autocomplete", None) is not None:
            self.autocomplete.on_text_changed()

    def focusOutEvent(self, event):
        """Handle focus out - trigger backup flush for network HDD performance."""
        super().focusOutEvent(event)
        self.focus_lost.emit()

    def load_file(self, file_path: str) -> bool:
        """Load ``file_path`` into the editor via the command-layer reader."""
        content, error = file_io.read_text(file_path)
        if content is None:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to load file: {error}")
            return False
        self.setPlainText(content)
        self.file_path = file_path
        self.is_modified = False
        return True

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

        # Use custom name if set, otherwise use file name
        if self.custom_name:
            name = self.custom_name
        elif hasattr(self, "is_draft") and self.is_draft:
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

    def set_custom_name(self, name: str):
        """Set custom name for this editor tab."""
        self.custom_name = name

    def clear_custom_name(self):
        """Clear custom name and use file name."""
        self.custom_name = None

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
        # Set editor font size
        self.current_font_size = size

        # Get current font to preserve family
        current_font = self.font()

        # Create new font with same family but new size
        font = QFont(current_font.family(), size)

        # If no font family set yet, use defaults
        if not font.family() or font.family() == "":
            font = QFont(DEFAULT_FONT_FAMILY, size)
            if not font.exactMatch():
                font = QFont("Courier New", size)

        self.setFont(font)

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

    def reset_font_size(self):
        """Reset font size to default."""
        self.set_font_size(self.default_font_size)

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
        """Highlight the current line."""
        # Get existing extra selections (including error highlights)
        existing_selections = self.extraSelections()

        # Filter out previous current line selections
        filtered_selections = []
        for selection in existing_selections:
            # Keep selections that are not current line highlights
            if not (hasattr(selection.format, "background") and selection.format.property(QTextCharFormat.FullWidthSelection)):
                filtered_selections.append(selection)

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            line_color = QColor(AppTheme.CURRENT_LINE_HIGHLIGHT)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            filtered_selections.append(selection)

        self.setExtraSelections(filtered_selections)

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
        """Paint the editor with multi-cursor support, indent guides, and fold placeholders."""
        # First, let the parent class paint everything normally
        super().paintEvent(event)

        # Paint indent guides
        self._paint_indent_guides(event)

        # Paint fold placeholder text on folded headers
        self._paint_fold_placeholders(event)

        # Then paint multi-cursor indicators on top
        painter = QPainter(self.viewport())
        self.paint_multi_cursors(painter)
        painter.end()

    def _paint_fold_placeholders(self, event):
        """Paint '...' placeholder text at the end of folded header lines."""
        if not self.fold_manager._folded_headers:
            return

        painter = QPainter(self.viewport())
        painter.setPen(QColor(AppTheme.FOLD_PLACEHOLDER_COLOR))
        font = self.font()
        painter.setFont(font)

        block = self.firstVisibleBlock()
        while block.isValid():
            geometry = self.blockBoundingGeometry(block).translated(self.contentOffset())
            if geometry.top() > event.rect().bottom():
                break

            block_number = block.blockNumber()
            if block.isVisible() and self.fold_manager.is_folded(block_number):
                # Get the visual end position of the block text
                text = block.text()
                text_width = self.fontMetrics().horizontalAdvance(text)
                placeholder = self.fold_manager.get_placeholder_text(block_number)

                # Draw placeholder after the line text
                x = text_width + 4
                y = int(geometry.top())
                h = self.fontMetrics().height()
                painter.drawText(x, y, self.viewport().width() - x, h, Qt.AlignLeft, placeholder)

            block = block.next()

        painter.end()

    def _paint_indent_guides(self, event):
        """Paint vertical indent guide lines."""
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor(AppTheme.INDENT_GUIDE_COLOR), 1))

        char_width = self.fontMetrics().horizontalAdvance(" ")
        tab_width = char_width * 4  # 4 spaces per indent level

        block = self.firstVisibleBlock()
        while block.isValid():
            geometry = self.blockBoundingGeometry(block).translated(self.contentOffset())
            if geometry.top() > event.rect().bottom():
                break

            text = block.text()
            if text.strip():
                # Non-empty line: draw guides based on its indentation
                indent = len(text) - len(text.lstrip())
                indent_levels = indent // 4
            else:
                # Empty line: find next non-empty line's indentation
                indent_levels = self._get_next_block_indent_level(block)

            for level in range(indent_levels):
                x = int(level * tab_width)
                painter.drawLine(x, int(geometry.top()), x, int(geometry.bottom()))

            block = block.next()

        painter.end()

    def _get_next_block_indent_level(self, current_block):
        """Get the indent level of the next non-empty visible block."""
        block = current_block.next()
        while block.isValid():
            if not block.isVisible():
                block = block.next()
                continue
            text = block.text()
            if text.strip():
                indent = len(text) - len(text.lstrip())
                return indent // 4
            block = block.next()
        return 0

    def contextMenuEvent(self, event):
        """Show the editor's right-click menu."""
        editor_context_menu.build_context_menu(self, event).exec_(event.globalPos())

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

        new_indent = auto_indent.compute_new_indent(self.document(), block_number, current_line, text_before_cursor)
        self.insertPlainText("\n" + new_indent)


# Re-exported from the new module so existing imports keep working.
from .editor_tab_widget import CodeEditorWidget  # noqa: E402, F401
