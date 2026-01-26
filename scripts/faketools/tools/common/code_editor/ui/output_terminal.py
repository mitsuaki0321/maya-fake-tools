"""
Output terminal widget for displaying script execution results.
Provides Script Editor-like output display functionality.
Supports both Maya native terminal and fallback QTextEdit.
"""

from .....lib_ui.qt_compat import QApplication, QColor, QFont, Qt, QTextCharFormat, QTextCursor, QTextEdit, QVBoxLayout, QWidget
from ..themes import AppTheme

# Terminal constants
DEFAULT_FONT_FAMILY = "Consolas"
MAX_OUTPUT_LINES = 1000

# Try to import Maya terminal widget
try:
    from .maya_terminal_widget import MAYA_AVAILABLE, MayaTerminalWidget
except ImportError:
    MayaTerminalWidget = None
    MAYA_AVAILABLE = False


class OutputTerminal(QWidget):
    """Terminal-like output widget for script results."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.output_display = None
        self.maya_terminal = None
        self.use_maya_terminal = False
        self.max_lines = MAX_OUTPUT_LINES

        # Font size management
        self.default_font_size = 9  # Will be set from settings
        self.current_font_size = self.default_font_size

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Try to create Maya native terminal first
        if MAYA_AVAILABLE and MayaTerminalWidget:
            self.maya_terminal = MayaTerminalWidget(self)
            if self.maya_terminal.is_available():
                self.use_maya_terminal = True
                layout.addWidget(self.maya_terminal)
                # Maya terminal will show its own welcome message
                return
            # Fallback if Maya terminal fails
            self.maya_terminal = None

        # Fallback to QTextEdit terminal
        self.create_fallback_terminal(layout)

    def create_fallback_terminal(self, layout):
        """Create fallback QTextEdit terminal for non-Maya environments."""
        # Create output display
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)

        # Disable line wrap to enable horizontal scrolling
        self.output_display.setLineWrapMode(QTextEdit.NoWrap)

        # Enable both horizontal and vertical scrollbars
        self.output_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Set font for terminal-like appearance
        font = QFont(DEFAULT_FONT_FAMILY, self.default_font_size)
        if not font.exactMatch():
            font = QFont("Courier New", self.default_font_size)
        self.output_display.setFont(font)

        # Set colors for terminal appearance with scrollbar styling
        scrollbar_style = AppTheme.get_scrollbar_stylesheet()

        terminal_stylesheet = f"""
            QTextEdit {{
                background-color: {AppTheme.BACKGROUND};
                color: {AppTheme.OUTPUT_TEXT};
                border: 1px solid #3c3c3c;
                selection-background-color: {AppTheme.SELECTION};
            }}
            
            {scrollbar_style}
        """

        self.output_display.setStyleSheet(terminal_stylesheet)

        layout.addWidget(self.output_display)

        # Add welcome message
        self.append_output("Code Editor - Output Terminal")
        self.append_output("-" * 40)

    def append_output(self, text: str, color: str = None):
        """Append text to the output display."""
        if not text:
            return

        # Use Maya terminal if available
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.append_output(text)
            return

        # Fallback to QTextEdit output (without timestamp for cleaner output)
        if not self.output_display:
            return

        # Move cursor to end
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Set text color if specified
        if color:
            char_format = QTextCharFormat()
            char_format.setForeground(QColor(color))
            cursor.setCharFormat(char_format)
        else:
            # Reset format to default
            char_format = QTextCharFormat()
            char_format.setForeground(QColor(AppTheme.OUTPUT_TEXT))
            cursor.setCharFormat(char_format)

        # Insert text
        cursor.insertText(text + "\n")

        # Auto-scroll to bottom
        scrollbar = self.output_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # Limit number of lines to prevent memory issues
        self.limit_output_lines()

        # Refresh display
        QApplication.processEvents()

    def append_error(self, text: str):
        """Append error text in red color."""
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.append_error(text)
        else:
            self.append_output(f"ERROR: {text}", color=AppTheme.OUTPUT_ERROR)

    def append_warning(self, text: str):
        """Append warning text in yellow color."""
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.append_warning(text)
        else:
            self.append_output(f"WARNING: {text}", color=AppTheme.OUTPUT_WARNING)

    def append_success(self, text: str):
        """Append success text in green color."""
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.append_success(text)
        else:
            self.append_output(f"SUCCESS: {text}", color=AppTheme.OUTPUT_SUCCESS)

    def append_command(self, command: str):
        """Append executed command in cyan color."""
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.append_command(command)
        else:
            self.append_output(command, color=AppTheme.OUTPUT_COMMAND)

    def clear(self):
        """Clear the output display."""
        if self.use_maya_terminal and self.maya_terminal:
            self.maya_terminal.clear()
        else:
            if self.output_display:
                self.output_display.clear()
                self.append_output("Output cleared.")

    def wheelEvent(self, event):
        """Handle mouse wheel events for font size changes."""
        # Maya terminal handles its own mouse events
        if self.use_maya_terminal:
            super().wheelEvent(event)
            return

        # Check if Ctrl is pressed for font size change
        if event.modifiers() == Qt.ControlModifier:
            # Get wheel delta
            delta = event.angleDelta().y()

            # Change font size
            if delta > 0:
                # Wheel up - increase font size
                self.increase_font_size()
            elif delta < 0:
                # Wheel down - decrease font size
                self.decrease_font_size()

            # Accept the event to prevent scrolling
            event.accept()
        else:
            # Normal scrolling
            super().wheelEvent(event)

    def increase_font_size(self):
        """Increase font size by 1."""
        new_size = min(self.current_font_size + 1, 24)  # Max size 24 for terminal
        self.set_font_size(new_size)

    def decrease_font_size(self):
        """Decrease font size by 1."""
        new_size = max(self.current_font_size - 1, 6)  # Min size 6
        self.set_font_size(new_size)

    def set_font_size(self, size):
        """Set font size for the terminal."""
        self.current_font_size = size

        # Maya terminal doesn't support font size changes
        if self.use_maya_terminal:
            return

        # Update terminal font
        if self.output_display:
            font = QFont(DEFAULT_FONT_FAMILY, size)
            if not font.exactMatch():
                font = QFont("Courier New", size)
            self.output_display.setFont(font)

    def reset_font_size(self):
        """Reset font size to default."""
        self.set_font_size(self.default_font_size)

    def set_default_font_size(self, size):
        """Set default font size from settings."""
        self.default_font_size = size
        self.current_font_size = size
        self.set_font_size(size)

    def limit_output_lines(self):
        """Limit the number of lines in output to prevent memory issues."""
        # Maya terminal handles its own memory management
        if self.use_maya_terminal:
            return

        if not self.output_display:
            return

        document = self.output_display.document()

        if document.blockCount() > self.max_lines:
            # Remove old lines from the top
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start)

            # Calculate how many lines to remove
            lines_to_remove = document.blockCount() - self.max_lines + 100

            # Select and delete old lines
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()  # Remove the newline

    def get_output_text(self) -> str:
        """Get all output text."""
        if self.use_maya_terminal and self.maya_terminal:
            return self.maya_terminal.get_output_text()
        if self.output_display:
            return self.output_display.toPlainText()
        return ""

    def save_output(self, file_path: str) -> bool:
        """Save output to a file."""
        if self.use_maya_terminal and self.maya_terminal:
            return self.maya_terminal.save_output(file_path)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.get_output_text())
            return True
        except Exception as e:
            self.append_error(f"Failed to save output: {e!s}")
            return False

    def closeEvent(self, event):
        """Handle widget close event."""
        if self.maya_terminal:
            self.maya_terminal.cleanup()
        super().closeEvent(event)
