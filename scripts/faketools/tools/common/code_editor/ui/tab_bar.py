"""
Custom tab bar for the code editor.
Handles tab-specific behaviors and interactions.
"""

from .qt_compat import QTabBar


class EditableTabBar(QTabBar):
    """Custom tab bar that supports special preview tab styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_indices = set()  # Track which tabs are previews

    def mouseDoubleClickEvent(self, event):
        """Handle double-click on tab (disabled - no rename functionality)."""
        # Rename functionality disabled per user request
        super().mouseDoubleClickEvent(event)

    def set_preview_tab(self, index, is_preview=True):
        """Mark a tab as preview or regular."""
        if is_preview:
            self.preview_indices.add(index)
        else:
            self.preview_indices.discard(index)
        self.update()
