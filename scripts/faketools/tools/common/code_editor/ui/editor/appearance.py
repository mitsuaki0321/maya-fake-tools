"""Appearance mixin for the code editor.

Bundles the typography (font, line height) and layout (word wrap,
scroll-bar policies) knobs that aren't tied to a specific language
profile. The wheel-zoom and ``setPlainText`` overrides stay on the
editor widget itself and call into the helpers exposed here, mirroring
how :class:`MultiCursorMixin` provides ``handle_*`` helpers that the
widget's Qt overrides dispatch to.
"""

from ......lib_ui.qt_compat import QBrush, QPalette, QPlainTextEdit, Qt, QTextBlockFormat, QTextCursor
from ...themes import AppTheme

# Editor constants
DEFAULT_TAB_SIZE = 4

# Font size bounds — chosen to match the toolbar zoom range.
_MIN_FONT_SIZE = 6
_MAX_FONT_SIZE = 32


class EditorAppearanceMixin:
    """Mixin providing typography / layout helpers for the editor."""

    def _init_appearance(self, font_size: int) -> None:
        """One-shot visual setup. Called from the widget constructor.

        Sets the monospace font, tab stop, caret width, line height,
        and the default word-wrap mode (on, with horizontal scrollbar
        suppressed). The editor calls :meth:`_apply_placeholder_text`
        separately because the placeholder is language-driven.
        """
        self.setFont(AppTheme.make_monospace_font(font_size))

        # Preserve per-token syntax colors inside a selection.
        # Qt's native selection rendering overrides each character's foreground
        # with QPalette.HighlightedText. Setting that brush to NoBrush makes
        # QTextDocumentLayout skip the override, so the syntax highlighter's
        # QTextCharFormat foreground stays visible behind the selection
        # background — matching VSCode's "selection keeps token colors" look.
        palette = self.palette()
        palette.setBrush(QPalette.HighlightedText, QBrush(Qt.NoBrush))
        self.setPalette(palette)

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

    def _apply_line_height(self) -> None:
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

    def handle_zoom_wheel(self, event) -> bool:
        """Apply Ctrl+wheel font zoom; return True when the event was consumed.

        The widget's ``wheelEvent`` checks for Ctrl and forwards here;
        non-Ctrl wheels go to QPlainTextEdit's default scroll handling.
        """
        delta = event.angleDelta().y()
        if delta > 0:
            self.increase_font_size()
        elif delta < 0:
            self.decrease_font_size()
        event.accept()
        return True

    def increase_font_size(self) -> None:
        """Bump the font size by one (clamped at ``_MAX_FONT_SIZE``)."""
        self.set_font_size(min(self.current_font_size + 1, _MAX_FONT_SIZE))

    def decrease_font_size(self) -> None:
        """Drop the font size by one (clamped at ``_MIN_FONT_SIZE``)."""
        self.set_font_size(max(self.current_font_size - 1, _MIN_FONT_SIZE))

    def set_font_size(self, size: int) -> None:
        """Re-font the editor and tell the gutter to refit."""
        self.current_font_size = size
        self.setFont(AppTheme.make_monospace_font(size))
        if hasattr(self, "line_number_area"):
            self.line_number_area.refresh_width()

    def set_default_font_size(self, size: int) -> None:
        """Reset both the default and current size from settings."""
        self.default_font_size = size
        self.current_font_size = size
        self.set_font_size(size)

    def set_word_wrap(self, enabled: bool) -> None:
        """Toggle word-wrap mode and matching scrollbar policy.

        Args:
            enabled (bool): True to wrap at widget width, False for no wrap.
        """
        if enabled:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)


__all__ = ["EditorAppearanceMixin"]
