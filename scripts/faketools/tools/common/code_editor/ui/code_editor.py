"""
Code editor widget with tab support.
Provides tabbed interface for editing multiple Python files.
"""

import contextlib
from logging import getLogger
import os
import re

from .....lib_ui.qt_compat import (
    QAction,
    QColor,
    QFileDialog,
    QFont,
    QPainter,
    QPen,
    QPlainTextEdit,
    Qt,
    QTabWidget,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
    QTimer,
    Signal,
)
from ..highlighting.python_highlighter import PythonHighlighter
from ..themes import AppTheme
from .dialog_base import CodeEditorMessageBox
from .editor_shortcuts import EditorShortcuts
from .editor_text_operations import EditorTextOperationsMixin
from .line_number_area import LineNumberArea
from .multi_cursor_handler import MultiCursorMixin
from .tab_bar import EditableTabBar

logger = getLogger(__name__)


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

        # Initialize multi-selection for legacy Ctrl+D
        self._multi_selections = []

        self.init_editor()
        self.setup_syntax_highlighting()

        # Initialize multi-cursor functionality
        self.init_multi_cursor()

        self.setup_line_numbers()
        self.connect_signals()

    def init_editor(self):
        """Initialize editor settings."""
        # Set font using current font size
        font = QFont("Consolas", self.current_font_size)
        if not font.exactMatch():
            font = QFont("Courier New", self.current_font_size)
        self.setFont(font)

        # Set tab width to 4 spaces
        try:
            # PySide6/Qt6
            self.setTabStopDistance(40)
        except AttributeError:
            # PySide2/Qt5 fallback
            self.setTabStopWidth(40)

        # Enable word wrap at widget width
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        # Enable vertical scrollbar (horizontal not needed with word wrap)
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

    def on_text_changed(self):
        """Handle text changes."""
        if not self.is_modified:
            self.is_modified = True

    def focusOutEvent(self, event):
        """Handle focus out - trigger backup flush for network HDD performance."""
        super().focusOutEvent(event)
        self.focus_lost.emit()

    def load_file(self, file_path: str) -> bool:
        """Load file content into the editor."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                self.setPlainText(content)

            self.file_path = file_path
            self.is_modified = False

            return True

        except Exception as e:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to load file: {e!s}")
            return False

    def save_file(self, file_path: str = None) -> bool:
        """Save editor content to file."""
        if file_path is None:
            file_path = self.file_path

        if file_path is None:
            return False

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())

            self.file_path = file_path
            self.is_modified = False
            self.document().setModified(False)  # Also set QTextDocument modified state
            return True

        except Exception as e:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to save file: {e!s}")
            return False

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
            font = QFont("Consolas", size)
            if not font.exactMatch():
                font = QFont("Courier New", size)

        self.setFont(font)

        # Update line number area width and force repaint with new font size
        if hasattr(self, "line_number_area"):
            self.update_line_number_area_width(0)
            self.line_number_area.update()

    def reset_font_size(self):
        """Reset font size to default."""
        self.set_font_size(self.default_font_size)

    def set_default_font_size(self, size):
        """Set default font size from settings."""
        self.default_font_size = size
        self.current_font_size = size
        self.set_font_size(size)

    # Line number area methods
    def lineNumberAreaWidth(self):
        """Calculate the width needed for line numbers."""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        # Add extra spacing between line numbers and code (2 characters worth)
        extra_spacing = self.fontMetrics().horizontalAdvance("  ")  # 2 spaces
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits + extra_spacing
        return space

    def update_line_number_area_width(self, new_block_count):
        """Update the width of the line number area."""
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update the line number area when scrolling or resizing."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            # Convert rect to integer values to avoid type errors
            self.line_number_area.update(0, int(rect.y()), int(self.line_number_area.width()), int(rect.height()))

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())

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

    def lineNumberAreaPaintEvent(self, event):
        """Paint the line numbers."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(AppTheme.LINE_NUMBER_BACKGROUND))

        # Set font to match editor font
        editor_font = self.font()
        painter.setFont(editor_font)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        current_block_number = self.textCursor().blockNumber()

        # Use current font metrics for single line height (for drawing)
        font_metrics = painter.fontMetrics()
        single_line_height = font_metrics.height()

        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                # Use different colors for current line vs other lines
                if block_number == current_block_number:
                    painter.setPen(QColor(AppTheme.LINE_NUMBER_ACTIVE))
                else:
                    painter.setPen(QColor(AppTheme.LINE_NUMBER_INACTIVE))
                # Leave spacing on the right side (between numbers and code)
                spacing = self.fontMetrics().horizontalAdvance("  ")  # 2 characters worth
                draw_width = self.line_number_area.width() - spacing
                # Draw line number at the top of the block (first visual line for wrapped blocks)
                painter.drawText(0, int(top), draw_width, single_line_height, Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

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

        # Handle Escape key
        if event.key() == Qt.Key_Escape:
            # First priority: clear multi-cursors
            if self.all_cursors:
                self.clear_multi_cursors()
                return
            # Third priority: clear old multi-selections
            if hasattr(self, "_multi_selections") and self._multi_selections:
                self._clear_multi_selections()
                return

        # Try to handle multi-cursor keyboard events first
        if self.handle_multi_cursor_keys(event):
            return

        # Clear old multi-selections on certain keys (if not in new multi-cursor mode)
        if (
            not self.all_cursors
            and hasattr(self, "_multi_selections")
            and self._multi_selections
            and (
                event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Home, Qt.Key_End]
                or (
                    event.key() not in [Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_F2]
                    and not (event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_D)
                )
            )
        ):
            self._clear_multi_selections()

        # Handle Home key with smart home behavior (single-cursor mode)
        if event.key() == Qt.Key_Home and not (event.modifiers() & Qt.ControlModifier):
            cursor = self.textCursor()
            smart_home_pos = self.get_first_non_whitespace_position(cursor)
            if event.modifiers() & Qt.ShiftModifier:
                cursor.setPosition(smart_home_pos, QTextCursor.KeepAnchor)
            else:
                cursor.setPosition(smart_home_pos)
            self.setTextCursor(cursor)
            return

        # Try to handle the event with the shortcut manager
        if self.shortcuts.handle_key_event(event, self):
            return

        # If not handled by shortcuts, delegate to parent
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press events for multi-cursor support."""
        # Handle middle-click for rectangle selection
        if event.button() == Qt.MiddleButton:
            self.start_rectangle_selection(event)
            event.accept()
            return

        # Try to handle multi-cursor mouse events first
        if self.handle_multi_cursor_mouse(event):
            event.accept()
            return

        # Clear multi-selections on mouse click (old system)
        if hasattr(self, "_multi_selections") and self._multi_selections:
            self._clear_multi_selections()

        # Delegate to parent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for Ctrl+drag and rectangle selection."""
        # Handle rectangle selection
        if hasattr(self, "is_rect_selecting") and self.is_rect_selecting and event.buttons() & Qt.MiddleButton:
            self.update_rectangle_selection(event)
            event.accept()
            return

        # Handle Ctrl+drag selection
        if hasattr(self, "is_ctrl_dragging") and self.is_ctrl_dragging and event.modifiers() & Qt.ControlModifier and event.buttons() & Qt.LeftButton:
            # Get current position
            try:
                current_pos = event.position().toPoint()  # PySide6
            except AttributeError:
                current_pos = event.pos()  # PySide2

            cursor = self.cursorForPosition(current_pos)

            # Update drag selection
            if self.ctrl_drag_cursor:
                self.ctrl_drag_cursor.setPosition(self.ctrl_drag_start)
                self.ctrl_drag_cursor.setPosition(cursor.position(), QTextCursor.KeepAnchor)

                # Update display to show selection
                self.viewport().update()

            event.accept()
            return

        # Delegate to parent
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events for Ctrl+drag and rectangle selection."""
        # Finalize rectangle selection
        if event.button() == Qt.MiddleButton and hasattr(self, "is_rect_selecting") and self.is_rect_selecting:
            self.finalize_rectangle_selection(event)
            event.accept()
            return

        # Handle Ctrl+click or Ctrl+drag
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier and hasattr(self, "is_ctrl_dragging") and self.is_ctrl_dragging:
            # Check if this was a drag or just a click
            if self.ctrl_drag_cursor:
                if self.ctrl_drag_cursor.hasSelection():
                    # It was a drag - add the selection
                    self.all_cursors.append(self.ctrl_drag_cursor)
                    with contextlib.suppress(Exception):
                        self.multi_cursor_status.emit(f"Added selection (total: {len(self.all_cursors)})")
                else:
                    # It was just a click - add cursor at click position
                    try:
                        click_pos = event.position().toPoint()  # PySide6
                    except AttributeError:
                        click_pos = event.pos()  # PySide2

                    cursor = self.cursorForPosition(click_pos)

                    # If this is the first Ctrl+click and we have no cursors,
                    # add the current cursor position first
                    if not self.all_cursors:
                        main_cursor = self.textCursor()
                        first_cursor = QTextCursor(self.document())
                        first_cursor.setPosition(main_cursor.position())
                        self.all_cursors.append(first_cursor)
                        # Hide the normal cursor when entering multi-cursor mode
                        self.setCursorWidth(0)

                    # Check if we already have a cursor at this position
                    cursor_exists = False
                    for existing_cursor in self.all_cursors:
                        if existing_cursor.position() == cursor.position() and not existing_cursor.hasSelection():
                            cursor_exists = True
                            break

                    if not cursor_exists:
                        # Add new cursor at click position
                        new_cursor = QTextCursor(self.document())
                        new_cursor.setPosition(cursor.position())
                        self.all_cursors.append(new_cursor)

                        with contextlib.suppress(Exception):
                            self.multi_cursor_status.emit(f"Added cursor {len(self.all_cursors)}")

            # Reset drag state
            self.is_ctrl_dragging = False
            self.ctrl_drag_cursor = None
            self.ctrl_drag_start = None

            # Update display
            self.viewport().update()
            event.accept()
            return

        # Delegate to parent
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Paint the editor with multi-cursor support and indent guides."""
        # First, let the parent class paint everything normally
        super().paintEvent(event)

        # Paint indent guides
        self._paint_indent_guides(event)

        # Then paint multi-cursor indicators on top
        painter = QPainter(self.viewport())
        self.paint_multi_cursors(painter)
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
        """Get the indent level of the next non-empty block."""
        block = current_block.next()
        while block.isValid():
            text = block.text()
            if text.strip():
                indent = len(text) - len(text.lstrip())
                return indent // 4
            block = block.next()
        return 0

    def contextMenuEvent(self, event):
        """Handle context menu events."""
        # Get the default context menu
        context_menu = self.createStandardContextMenu()

        # Apply theme to context menu
        context_menu.setStyleSheet(AppTheme.get_menu_stylesheet())

        # Check for Maya command at cursor position
        cursor_position = self.textCursor().position()
        text_content = self.toPlainText()

        # Get settings manager from parent
        settings_manager = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, "settings_manager"):
                settings_manager = parent_widget.settings_manager
                break
            parent_widget = parent_widget.parent()

        from ..utils.maya_help_detector import MayaHelpDetector

        maya_detector = MayaHelpDetector(settings_manager)
        maya_command = maya_detector.detect_maya_command_at_cursor(text_content, cursor_position)

        if maya_command:
            alias, command, full_match = maya_command
            context_menu.addSeparator()

            # Add Maya help action
            help_text = maya_detector.get_help_menu_text(alias, command)
            maya_help_action = QAction(help_text, self)
            maya_help_action.triggered.connect(lambda: maya_detector.open_help_url(alias, command))
            context_menu.addAction(maya_help_action)

        # Get selected text or word under cursor for inspection
        selected_text = self.textCursor().selectedText().strip()
        if not selected_text:
            # If no selection, try to get the word under cursor
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.WordUnderCursor)
            selected_text = cursor.selectedText().strip()

        # Add inspection actions if we have a valid identifier
        if selected_text and self.is_valid_identifier(selected_text):
            context_menu.addSeparator()

            # Inspect Object action
            inspect_action = QAction("Inspect Object '" + selected_text + "'", self)
            inspect_action.triggered.connect(lambda: self.inspect_object.emit(selected_text, "dir"))
            context_menu.addAction(inspect_action)

            # Inspect Object Help action
            inspect_help_action = QAction("Inspect Object Help '" + selected_text + "'", self)
            inspect_help_action.triggered.connect(lambda: self.inspect_object.emit(selected_text, "help"))
            context_menu.addAction(inspect_help_action)

            # Reload Module action - supports dotted module names like package.module
            # Check if it could be a module name (allows dots for package.module format)
            if self.is_valid_module_name(selected_text):
                reload_action = QAction("Reload Module '" + selected_text + "'", self)
                reload_action.triggered.connect(lambda: self.reload_module(selected_text))
                context_menu.addAction(reload_action)

        # Show the context menu
        context_menu.exec_(event.globalPos())

    def is_valid_identifier(self, text):
        """Check if the text is a valid Python identifier."""
        if not text:
            return False
        # Basic check for valid Python identifier
        return text.replace("_", "").replace(".", "").isalnum() and not text[0].isdigit()

    def is_valid_module_name(self, text):
        """Check if the text could be a valid module name (including dotted names)."""
        if not text:
            return False
        # Module names can have dots for packages (e.g., package.subpackage.module)
        # But shouldn't end with a dot or have consecutive dots
        if text.startswith(".") or text.endswith(".") or ".." in text:
            return False
        # Check each part of the module name
        parts = text.split(".")
        for part in parts:
            if not part:  # Empty part between dots
                return False
            # Each part should be a valid Python identifier
            if not (part.replace("_", "").isalnum() and not part[0].isdigit()):
                return False
        return True

    def reload_module(self, module_name):
        """Reload a Python module."""
        # Get the execution manager from parent
        exec_manager = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, "parent") and hasattr(parent_widget.parent(), "execution_manager"):
                exec_manager = parent_widget.parent().execution_manager
                break
            parent_widget = parent_widget.parent()

        if exec_manager:
            # Create reload code without using logger (which doesn't exist in the execution context)
            reload_code = f"""
import importlib
import sys

try:
    if '{module_name}' in sys.modules:
        importlib.reload(sys.modules['{module_name}'])
        print("Maya Code Editor: Module '{module_name}' reloaded successfully.")
    else:
        # Try to import first
        module = __import__('{module_name}')
        importlib.reload(module)
        print("Maya Code Editor: Module '{module_name}' imported and reloaded successfully.")
except ModuleNotFoundError:
    print("Maya Code Editor: Module '{module_name}' not found.")
except Exception as e:
    print(f"Maya Code Editor: Error reloading module '{module_name}': {{e}}")
"""
            # Execute the reload code silently like inspect object
            if hasattr(exec_manager, "execute_inspection_code"):
                # Add header message before execution
                if exec_manager.output_terminal:
                    exec_manager.output_terminal.append_output(f"\n=== Reloading Module: {module_name} ===")
                exec_manager.execute_inspection_code(reload_code)
            else:
                # Fallback to normal execution
                exec_manager.execute_python_code(reload_code)

    def handle_return_key(self):
        """Handle Return/Enter key press for auto-indentation."""
        cursor = self.textCursor()
        current_position = cursor.position()

        # Get current line text for indentation calculation
        cursor.movePosition(QTextCursor.StartOfLine)
        line_start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        current_line = cursor.selectedText()

        # Get the text before cursor on current line
        cursor.setPosition(line_start)
        cursor.setPosition(current_position, QTextCursor.KeepAnchor)
        text_before_cursor = cursor.selectedText()

        # Calculate current indentation
        indent_match = re.match(r"^(\s*)", current_line)
        current_indent = indent_match.group(1) if indent_match else ""

        # Check if current line ends with colon (function, class, if, etc.)
        # Only check the part before cursor for colon
        stripped_before = text_before_cursor.strip()
        needs_extra_indent = stripped_before.endswith(":") and not stripped_before.startswith("#")

        # Restore cursor to original position
        cursor.setPosition(current_position)
        self.setTextCursor(cursor)

        # Insert newline with indentation
        new_indent = current_indent
        if needs_extra_indent:
            new_indent += "    "  # Add 4 spaces for Python

        newline_text = "\n" + new_indent
        self.insertPlainText(newline_text)

    def handle_tab_key(self):
        """Handle Tab key press."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Indent selected lines
            self.indent_selection()
        else:
            # Insert 4 spaces
            self.insertPlainText("    ")

    def handle_backtab_key(self):
        """Handle Shift+Tab key press."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Unindent selected lines
            self.unindent_selection()
        else:
            # Remove up to 4 spaces before cursor
            self.remove_indent_at_cursor()

    def indent_selection(self):
        """Indent all selected lines."""
        cursor = self.textCursor()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        # Move to start of first line
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        # Move to end of last line
        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        # Indent each line
        cursor.beginEditBlock()
        for line_num in range(start_line, end_line + 1):
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.insertText("    ")
        cursor.endEditBlock()

    def unindent_selection(self):
        """Unindent all selected lines."""
        cursor = self.textCursor()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        # Move to start of first line
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        # Move to end of last line
        cursor.setPosition(end_pos)
        end_line = cursor.blockNumber()

        # Unindent each line
        cursor.beginEditBlock()
        for line_num in range(start_line, end_line + 1):
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line_num):
                cursor.movePosition(QTextCursor.NextBlock)
            cursor.movePosition(QTextCursor.StartOfLine)

            # Check if line starts with spaces and remove up to 4
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
        """Remove indentation at cursor position."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)

        # Count spaces at beginning of line up to cursor
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

        # Remove the spaces
        if spaces_count > 0:
            cursor.setPosition(line_start)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, spaces_count)
            cursor.removeSelectedText()

    def handle_backspace_key(self):
        """Handle Backspace key press for smart indentation removal."""
        cursor = self.textCursor()

        # Don't do smart backspace if there's a selection
        if cursor.hasSelection():
            # Use deletePreviousChar for simple deletion when there's a selection
            cursor.deletePreviousChar()
            return

        # Get current position
        current_pos = cursor.position()

        # Move to start of line
        cursor.movePosition(QTextCursor.StartOfLine)
        line_start_pos = cursor.position()

        # Get text from start of line to current position
        cursor.setPosition(line_start_pos)
        cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
        text_before_cursor = cursor.selectedText()

        # Check if text before cursor contains only spaces
        if text_before_cursor and all(c == " " for c in text_before_cursor):
            # Calculate how many spaces to remove (up to 4, or all if less than 4)
            spaces_count = len(text_before_cursor)

            if spaces_count > 0:
                # Remove spaces in groups of 4, or all remaining if less than 4
                spaces_to_remove = min(4, spaces_count % 4 if spaces_count % 4 != 0 else 4)

                # Position cursor at the end of spaces to remove
                cursor = self.textCursor()  # Get fresh cursor
                cursor.setPosition(current_pos - spaces_to_remove)
                cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                return

        # Default backspace behavior for other cases - use the simpler method
        cursor = self.textCursor()
        cursor.deletePreviousChar()

    # Removed enter/leave events - no longer needed for tooltips

    # Removed mouseMoveEvent - no longer needed for tooltips


class CodeEditorWidget(QTabWidget):
    """Tabbed code editor widget."""

    # Signals
    inspect_object = Signal(str, str)  # (object_name, inspection_type)
    textChanged = Signal()  # Emitted when any tab's text changes

    def __init__(self, parent=None):
        super().__init__(parent)

        self.untitled_counter = 1
        self.preview_tab_index = -1  # Index of current preview tab (-1 if none)
        self.preview_tab_editor = None  # Reference to preview tab editor

        # Set custom tab bar for renaming functionality
        self.custom_tab_bar = EditableTabBar()
        self.setTabBar(self.custom_tab_bar)

        self.init_ui()
        self.connect_signals()
        self.apply_close_button_styles()

        # Connect tab changed signal to update active tab styling
        self.currentChanged.connect(self.update_active_tab_styling)

        # Enable middle-click to close tabs
        self.setup_middle_click_close()

        # Create initial Draft tab
        self.new_file(is_draft=True)

    def wheelEvent(self, event):
        """Forward wheel events to current editor for font size changes."""
        # Forward wheel events to current editor
        current_editor = self.currentWidget()
        if current_editor and hasattr(current_editor, "wheelEvent"):
            # Forwarding wheel event to current editor
            current_editor.wheelEvent(event)
        else:
            # No current editor available
            super().wheelEvent(event)

    def init_ui(self):
        """Initialize the user interface."""
        self.setTabsClosable(False)  # Disable default close buttons
        self.setMovable(True)
        self.setDocumentMode(True)

    def connect_signals(self):
        """Connect widget signals."""
        self.tabCloseRequested.connect(self.close_tab)

    def new_file(self, is_draft=False) -> PythonEditor:
        """Create a new file tab."""
        editor = PythonEditor(self)

        if is_draft:
            tab_name = "Draft"
            editor.is_draft = True
            # Draft tab starts unmodified (no asterisk)
            editor.is_modified = False
        else:
            tab_name = f"Untitled{self.untitled_counter}.py"
            self.untitled_counter += 1
            editor.is_draft = False
            # Set as modified for new files (unsaved state)
            editor.is_modified = True

        editor.is_preview = False  # Regular tab by default

        index = self.addTab(editor, tab_name)
        self.setCurrentIndex(index)

        # Apply theme to new editor
        self.apply_editor_theme(editor)

        # Connect to update tab title when modified
        editor.textChanged.connect(lambda: self.update_tab_title(editor))

        # Visual state is handled by tab title asterisk

        # Connect text changed signal to widget's signal
        editor.textChanged.connect(self.textChanged.emit)

        # Connect inspection signal
        editor.inspect_object.connect(self.inspect_object.emit)

        # Update active tab styling after adding new tab
        QTimer.singleShot(0, self.update_active_tab_styling)

        # Initial state handled by tab title

        # Save session state after adding new tab
        QTimer.singleShot(100, self.save_session_if_available)

        return editor

    def open_preview(self, content: str, title: str = "Preview") -> PythonEditor:
        """Open content in a preview tab."""
        # If a preview tab exists, reuse it
        if self.preview_tab_index >= 0 and self.preview_tab_index < self.count():
            editor = self.widget(self.preview_tab_index)
            if editor and hasattr(editor, "is_preview") and editor.is_preview:
                # Temporarily disconnect text change signal to avoid conversion
                with contextlib.suppress(Exception):
                    editor.textChanged.disconnect()

                # Reuse existing preview tab
                editor.setPlainText(content)
                editor.is_modified = False
                editor.document().setModified(False)  # Also clear document modified state
                editor.preview_title = title
                self.setTabText(self.preview_tab_index, f"[Preview] {title}")
                self.setCurrentIndex(self.preview_tab_index)

                # Reconnect signals
                editor.textChanged.connect(lambda: self.on_preview_text_changed(editor))
                editor.textChanged.connect(self.textChanged.emit)

                return editor

        # Create new preview tab
        editor = PythonEditor(self)
        editor.is_preview = True
        editor.is_modified = False
        editor.preview_title = title

        # First add the tab, then set content
        tab_title = f"[Preview] {title}"
        index = self.addTab(editor, tab_title)

        # Now set the content without triggering modified state
        editor.setPlainText(content)
        editor.is_modified = False
        editor.document().setModified(False)

        # Track preview tab
        self.preview_tab_index = index
        self.preview_tab_editor = editor
        self.setCurrentIndex(index)

        # Apply theme
        self.apply_editor_theme(editor)

        # Connect signals
        editor.textChanged.connect(lambda: self.on_preview_text_changed(editor))
        editor.textChanged.connect(self.textChanged.emit)
        editor.inspect_object.connect(self.inspect_object.emit)

        # Apply preview tab styling
        self.style_preview_tab(index)

        # DON'T save preview tabs in session
        # No QTimer.singleShot for session save

        return editor

    def style_preview_tab(self, index):
        """Apply italic styling to preview tab."""
        # Disabled due to Maya crash issues with custom painting

    def on_preview_text_changed(self, editor):
        """Handle text changes in preview tab."""
        if hasattr(editor, "is_preview") and editor.is_preview and editor.is_modified:
            # Convert preview to regular tab on edit
            self.convert_preview_to_regular(editor)

    def convert_preview_to_regular(self, editor):
        """Convert a preview tab to a regular tab."""
        if not hasattr(editor, "is_preview") or not editor.is_preview:
            return

        editor.is_preview = False
        index = self.indexOf(editor)
        if index >= 0:
            # Update tab title (remove angle brackets)
            title = editor.preview_title if hasattr(editor, "preview_title") else "Untitled"
            if not title.endswith(".py"):
                title = f"{title}.py"
            # Check if tab is currently active
            if index == self.currentIndex():
                self.setTabText(index, f"● {title}")
            else:
                self.setTabText(index, title)

            # Clear preview tracking
            if index == self.preview_tab_index:
                self.preview_tab_index = -1
                self.preview_tab_editor = None

            # Remove preview styling
            if hasattr(self.custom_tab_bar, "set_preview_tab"):
                self.custom_tab_bar.set_preview_tab(index, False)

            # Now save as regular tab
            QTimer.singleShot(100, self.save_session_if_available)

    def apply_editor_theme(self, editor):
        """Apply theme styling to a specific editor instance."""
        editor_style = AppTheme.get_editor_stylesheet()
        editor.setStyleSheet(editor_style)

        # Update current line highlight color
        selection = QTextEdit.ExtraSelection()
        line_color = QColor(AppTheme.CURRENT_LINE)
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        selection.cursor = editor.textCursor()
        selection.cursor.clearSelection()
        editor.setExtraSelections([selection])

    def open_file_permanent(self, file_path: str):
        """Open a file in a new tab or switch to existing tab."""
        # Normalize the file path for comparison (handle Windows paths)
        file_path = os.path.normpath(os.path.abspath(file_path)).replace("\\", "/")

        # Check if file is already open (including preview tabs)
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor) and editor.file_path:
                # Compare normalized paths
                existing_path = os.path.normpath(os.path.abspath(editor.file_path)).replace("\\", "/")
                if existing_path == file_path:
                    # If it's a preview tab, convert to permanent
                    if i == self.preview_tab_index:
                        tab_text = self.tabText(i)
                        if tab_text.endswith(" (Preview)"):
                            self.setTabText(i, tab_text.replace(" (Preview)", ""))
                            self.preview_tab_index = -1
                    self.setCurrentIndex(i)
                    return True

        # Create new tab for file
        editor = PythonEditor(self)
        if editor.load_file(file_path):
            file_name = os.path.basename(file_path)
            index = self.addTab(editor, file_name)
            self.setCurrentIndex(index)

            # Apply theme to new editor
            self.apply_editor_theme(editor)

            # Connect signals
            editor.textChanged.connect(lambda: self.update_tab_title(editor))
            editor.textChanged.connect(self.textChanged.emit)
            editor.inspect_object.connect(self.inspect_object.emit)

            # Update active tab styling after adding new tab
            QTimer.singleShot(0, self.update_active_tab_styling)

            # Save session state after opening file
            QTimer.singleShot(100, self.save_session_if_available)

            return True
        return False

    def open_file_preview(self, file_path: str):
        """Open a file in preview mode (replace existing preview tab)."""
        # Normalize the file path for comparison (handle Windows paths)
        file_path = os.path.normpath(os.path.abspath(file_path)).replace("\\", "/")

        # Check if file is already open as permanent tab (including preview tabs)
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor) and editor.file_path:
                # Compare normalized paths
                existing_path = os.path.normpath(os.path.abspath(editor.file_path)).replace("\\", "/")
                if existing_path == file_path:
                    # File already open - just switch to it (don't create duplicate)
                    self.setCurrentIndex(i)
                    return True

        # Find ANY existing preview tab (not just by index, which might be stale)
        existing_preview_index = -1
        for i in range(self.count()):
            tab_text = self.tabText(i)
            if " (Preview)" in tab_text or tab_text.startswith("[Preview]"):
                existing_preview_index = i
                break

        # If we found a preview tab, replace it
        if existing_preview_index >= 0:
            preview_editor = self.widget(existing_preview_index)
            # Load new file into existing preview tab
            if preview_editor and preview_editor.load_file(file_path):
                file_name = os.path.basename(file_path)
                self.setTabText(existing_preview_index, file_name + " (Preview)")
                self.setCurrentIndex(existing_preview_index)
                # Update the tracked index
                self.preview_tab_index = existing_preview_index

                # Save session state after preview change
                QTimer.singleShot(100, self.save_session_if_available)
                return True

        # Create new preview tab
        editor = PythonEditor(self)
        if editor.load_file(file_path):
            file_name = os.path.basename(file_path)
            index = self.addTab(editor, file_name + " (Preview)")
            self.preview_tab_index = index
            self.setCurrentIndex(index)

            # Apply theme to new editor
            self.apply_editor_theme(editor)

            # Connect signals like permanent tabs
            editor.textChanged.connect(lambda: self.update_tab_title(editor))
            editor.textChanged.connect(self.textChanged.emit)
            editor.inspect_object.connect(self.inspect_object.emit)

            # Update active tab styling
            QTimer.singleShot(0, self.update_active_tab_styling)

            # Save session state after adding preview tab
            QTimer.singleShot(100, self.save_session_if_available)

            return True
        return False

    def make_preview_permanent(self, file_path: str = None):
        """Convert current preview tab to permanent tab."""
        if self.preview_tab_index >= 0 and self.preview_tab_index < self.count():
            editor = self.widget(self.preview_tab_index)
            if editor and isinstance(editor, PythonEditor):
                # Remove (Preview) from tab title
                current_text = self.tabText(self.preview_tab_index)
                if current_text.endswith(" (Preview)"):
                    permanent_title = current_text.replace(" (Preview)", "")
                    self.setTabText(self.preview_tab_index, permanent_title)

                # Clear preview tab index
                self.preview_tab_index = -1

                # Save session state after making permanent
                QTimer.singleShot(100, self.save_session_if_available)

                return True
        return False

    def apply_close_button_styles(self):
        """Apply basic tab styling (Maya-safe)."""
        try:
            # Simple, Maya-compatible stylesheet with improved design
            tab_style = """
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #242424;
                }
                
                QTabBar {
                    background-color: #242424;
                    padding-top: 4px;
                    border-bottom: 1px solid #0a0a0a;
                }
                
                QTabWidget::tab-bar {
                    background-color: #242424;
                }
                
                QTabBar::tab {
                    background-color: #242424;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                    padding: 8px 16px 8px 16px;
                    margin-right: 2px;
                    margin-top: 0px;
                }
                
                QTabBar::tab:selected {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border-top: 2px solid #0078d4;
                }
                
                QTabBar::tab:hover:!selected {
                    background-color: #2a2a2a;
                }
                
            """

            self.setStyleSheet(tab_style)

        except Exception as e:
            logger.error(f"Error applying tab styles - {e}")

    def update_active_tab_styling(self):
        """Simple active tab indication using text prefix and preview styling."""
        try:
            current_index = self.currentIndex()

            # Only proceed if we have tabs
            if self.count() == 0:
                return

            # Add visual indicator to active tab text
            for i in range(self.count()):
                text = self.tabText(i)
                editor = self.widget(i)
                is_preview = hasattr(editor, "is_preview") and editor.is_preview

                # Skip preview tabs - they manage their own styling
                if is_preview:
                    continue

                # Handle active indicator for non-preview tabs
                if i == current_index:
                    # Add active indicator if not present
                    if not text.startswith("● "):
                        text = f"● {text}"
                else:
                    # Remove active indicator from inactive tabs
                    text = text.removeprefix("● ")

                self.setTabText(i, text)

        except Exception as e:
            logger.error(f"Error updating active tab styling - {e}")

    def setup_middle_click_close(self):
        """Setup middle-click to close tabs."""
        try:
            # Install event filter on the tab bar to capture middle clicks
            self.tabBar().installEventFilter(self)
        except Exception as e:
            logger.error(f"Failed to setup middle-click close - {e}")

    def eventFilter(self, obj, event):
        """Handle mouse events for middle-click tab closing."""
        try:
            # Check if this is a mouse press event on the tab bar
            if obj == self.tabBar() and hasattr(event, "type"):
                from .....lib_ui.qt_compat import QtCore

                # Handle middle mouse button press
                if event.type() == QtCore.QEvent.MouseButtonPress and hasattr(event, "button") and event.button() == Qt.MiddleButton:
                    # Get the tab index at the click position
                    tab_index = self.tabBar().tabAt(event.pos())

                    if tab_index >= 0:
                        # Close the tab
                        self.close_tab(tab_index)
                        return True  # Event handled

            # Pass through other events
            return super().eventFilter(obj, event)

        except Exception as e:
            logger.error(f"Event filter error - {e}")
            return super().eventFilter(obj, event)

    def close_current_tab(self):
        """Close the current tab."""
        current_index = self.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def save_current_file(self) -> bool:
        """Save the currently active file."""
        editor = self.currentWidget()
        if not isinstance(editor, PythonEditor):
            return False

        # Cannot save Draft tab
        if hasattr(editor, "is_draft") and editor.is_draft:
            CodeEditorMessageBox.information(self, "Cannot Save Draft", "The Draft tab cannot be saved to file.")
            return False

        if editor.file_path is None:
            # Save as dialog for untitled files
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py)")
            if not file_path:
                return False
        elif not os.path.exists(editor.file_path):
            # File path exists but file was deleted - create new file
            file_path = editor.file_path
            # Ensure parent directory exists
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except OSError:
                    # If we can't create parent directory, use save as dialog
                    file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", editor.file_path, "Python Files (*.py)")
                    if not file_path:
                        return False
        else:
            file_path = editor.file_path

        success = editor.save_file(file_path)
        if success:
            self.update_tab_title(editor)

            # Save session state after file save
            QTimer.singleShot(100, self.save_session_if_available)

        return success

    def get_current_code(self) -> str:
        """Get code from the currently active editor."""
        editor = self.currentWidget()
        if isinstance(editor, PythonEditor):
            return editor.toPlainText()
        return ""

    def close_tab(self, index: int):
        """Close a tab after checking for unsaved changes."""
        editor = self.widget(index)
        if not isinstance(editor, PythonEditor):
            return

        # Prevent closing Draft tab - check this first
        if hasattr(editor, "is_draft") and editor.is_draft:
            CodeEditorMessageBox.warning(self, "Draft Tab", "The Draft tab cannot be closed.\n\nThis is a permanent workspace for temporary code.")
            return

        if editor.is_modified:
            file_name = editor.get_display_name().rstrip("*")
            reply = CodeEditorMessageBox.question(
                self,
                "Unsaved Changes",
                f"'{file_name}' has unsaved changes. Save before closing?",
                CodeEditorMessageBox.Yes | CodeEditorMessageBox.No | CodeEditorMessageBox.Cancel,
            )

            if reply == CodeEditorMessageBox.Yes:
                if not self.save_file_at_index(index):
                    return  # Cancel close if save failed
            elif reply == CodeEditorMessageBox.Cancel:
                return  # Cancel close

        self.removeTab(index)

        # Update active tab styling after removing tab
        QTimer.singleShot(0, self.update_active_tab_styling)

        # Save session state after removing tab
        QTimer.singleShot(100, self.save_session_if_available)

        # Create new Draft tab if all tabs are closed
        if self.count() == 0:
            self.new_file(is_draft=True)

    def save_file_at_index(self, index: int) -> bool:
        """Save file at specific tab index."""
        current_index = self.currentIndex()
        self.setCurrentIndex(index)
        success = self.save_current_file()
        self.setCurrentIndex(current_index)
        return success

    def update_tab_title(self, editor: PythonEditor):
        """Update tab title based on editor state."""
        # Skip updating preview tabs - they manage their own titles
        if hasattr(editor, "is_preview") and editor.is_preview:
            return

        for i in range(self.count()):
            if self.widget(i) == editor:
                self.setTabText(i, editor.get_display_name())
                break

    # Tab visual state is handled by asterisk in tab title

    def save_session_if_available(self):
        """Save session state if main window is available."""
        # Find main window (parent)
        parent = self.parent()
        while parent:
            if hasattr(parent, "save_session_state"):
                parent.save_session_state()
                break
            parent = parent.parent()

    def get_current_editor(self):
        """Get the currently active editor."""
        return self.currentWidget()

    def get_current_file_path(self):
        """Get the file path of the currently active editor."""
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, "file_path"):
            return current_editor.file_path
        return None
