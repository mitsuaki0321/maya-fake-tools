"""
Custom tab bar for the code editor.
Handles tab-specific behaviors and per-language accent colour drawing.
"""

from ......lib_ui.qt_compat import QColor, QPainter, Qt, QTabBar

# Inactive tabs render the accent at reduced saturation and value so the
# active tab visually pops while still telegraphing its language. Picked
# to keep the band recognisable as "the same colour family" without
# competing with the active strip for attention.
_INACTIVE_SATURATION_RATIO = 0.5
_INACTIVE_VALUE_RATIO = 0.35


class EditableTabBar(QTabBar):
    """Custom tab bar that paints a per-language accent line on top of every tab.

    The Qt stylesheet on this widget (defined in
    :func:`AppTheme.get_tab_widget_stylesheet`) reserves a 2 px transparent
    top border on every tab to keep the layout stable; this widget then
    paints that band with the tab's editor language ``accent_color`` so
    Python tabs and MEL tabs can be distinguished at a glance. The active
    tab's strip is drawn at full strength; inactive tabs get a desaturated,
    darkened variant from :func:`_muted_accent`.
    """

    _ACCENT_HEIGHT = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_indices = set()  # Track which tabs are previews

        # Qt repaints the changed tab regions on selection change, but the
        # accent strips on *other* tabs need to refresh too (the previous
        # active tab must downgrade to muted, the new one must brighten),
        # so force a full update whenever the current index moves.
        self.currentChanged.connect(self._on_current_changed)

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

    def _on_current_changed(self, _index):
        self.update()

    def paintEvent(self, event):
        """Default tab rendering, then per-tab accent strip overlay."""
        super().paintEvent(event)

        # The tab widget is the parent QTabWidget; its ``widget(index)``
        # gives us the editor whose ``language.accent_color`` we want.
        parent = self.parent()
        if not hasattr(parent, "widget"):
            return

        current = self.currentIndex()
        painter = QPainter(self)
        try:
            painter.setPen(Qt.NoPen)
            for i in range(self.count()):
                editor = parent.widget(i)
                language = getattr(editor, "language", None)
                accent = getattr(language, "accent_color", None) if language is not None else None
                if not accent:
                    continue
                color = QColor(accent) if i == current else _muted_accent(QColor(accent))
                rect = self.tabRect(i)
                painter.setBrush(color)
                painter.drawRect(rect.left(), rect.top(), rect.width(), self._ACCENT_HEIGHT)
        finally:
            painter.end()


def _muted_accent(color: QColor) -> QColor:
    """Return a desaturated, darkened variant of ``color`` for inactive tabs.

    Drops both saturation (less colourful) and value (darker) in HSV so the
    band stays in the same hue family as the active strip — same language,
    just visually subdued.
    """
    h, s, v, a = color.getHsv()
    return QColor.fromHsv(h, int(s * _INACTIVE_SATURATION_RATIO), int(v * _INACTIVE_VALUE_RATIO), a)
