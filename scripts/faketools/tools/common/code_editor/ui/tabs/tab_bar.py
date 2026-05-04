"""
Custom tab bar for the code editor.
Handles tab-specific behaviors and per-language accent colour drawing.
"""

from ......lib_ui.qt_compat import QColor, QPainter, Qt, QTabBar


class EditableTabBar(QTabBar):
    """Custom tab bar that paints a per-language accent line on top of every tab.

    The Qt stylesheet on this widget (defined in
    :func:`AppTheme.get_tab_widget_stylesheet`) reserves a 2 px transparent
    top border on every tab to keep the layout stable; this widget then
    paints that band with the tab's editor language ``accent_color`` so
    Python tabs and MEL tabs can be distinguished at a glance.
    """

    _ACCENT_HEIGHT = 2

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

    def paintEvent(self, event):
        """Default tab rendering, then per-tab accent strip overlay."""
        super().paintEvent(event)

        # The tab widget is the parent QTabWidget; its ``widget(index)``
        # gives us the editor whose ``language.accent_color`` we want.
        parent = self.parent()
        if not hasattr(parent, "widget"):
            return

        painter = QPainter(self)
        try:
            painter.setPen(Qt.NoPen)
            for i in range(self.count()):
                editor = parent.widget(i)
                language = getattr(editor, "language", None)
                accent = getattr(language, "accent_color", None) if language is not None else None
                if not accent:
                    continue
                rect = self.tabRect(i)
                painter.setBrush(QColor(accent))
                painter.drawRect(rect.left(), rect.top(), rect.width(), self._ACCENT_HEIGHT)
        finally:
            painter.end()
