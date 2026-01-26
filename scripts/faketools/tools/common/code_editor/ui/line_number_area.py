"""
Line number area widget for the code editor.
Displays line numbers alongside the code editor.
"""

from .....lib_ui.qt_compat import QWidget


class LineNumberArea(QWidget):
    """Widget that displays line numbers for the code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        """Return the size hint for the line number area."""
        return self.code_editor.lineNumberAreaWidth()

    def paintEvent(self, event):
        """Paint the line numbers."""
        self.code_editor.lineNumberAreaPaintEvent(event)
