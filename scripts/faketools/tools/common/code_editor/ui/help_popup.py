"""Floating docstring popup for the Code Editor. Qt shell only — content rendering lives in :mod:`.help_renderer`."""

from __future__ import annotations

from logging import getLogger

from .....lib_ui.qt_compat import (
    QApplication,
    QFrame,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTextEdit,
    QVBoxLayout,
)
from .help_renderer import SURFACE_BG, render_docstring, render_loading

logger = getLogger(__name__)

_MIN_WIDTH_PX = 360
_MIN_HEIGHT_PX = 120
_MAX_WIDTH_PX = 640
_MAX_HEIGHT_PX = 420
_ANCHOR_GAP_PX = 6


class HelpPopup(QFrame):
    """Non-activating docstring window. One instance serves every editor tab."""

    def __init__(self):
        # parent=None: parenting to Maya main would re-raise it and sink
        # the autocomplete popup (itself parent-less) behind it.
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)

        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._text_view = QTextEdit(self)
        self._text_view.setReadOnly(True)
        # setTextInteractionFlags rewrites focusPolicy to ClickFocus; pin
        # it back to NoFocus so mouse selection doesn't close the
        # autocomplete list.
        self._text_view.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._text_view.setFocusPolicy(Qt.NoFocus)
        self._text_view.setLineWrapMode(QTextEdit.WidgetWidth)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self._text_view)

        self.resize(
            QSize(
                (_MIN_WIDTH_PX + _MAX_WIDTH_PX) // 2,
                (_MIN_HEIGHT_PX + _MAX_HEIGHT_PX) // 2,
            )
        )
        self._apply_style()

    def _apply_style(self) -> None:
        try:
            from ..themes import AppTheme

            border = AppTheme.BORDER
            selection = AppTheme.SELECTION
        except Exception:
            border = "#3e3e42"
            selection = "#264f78"

        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {SURFACE_BG};
                border: 1px solid {border};
            }}
            QTextEdit {{
                background-color: {SURFACE_BG};
                border: none;
                selection-background-color: {selection};
            }}
            """
        )

    def set_loading(self, identifier: str = "") -> None:
        self._text_view.setHtml(render_loading(identifier))

    def set_text(self, text: str) -> None:
        self._text_view.setHtml(render_docstring(text))
        cursor = self._text_view.textCursor()
        cursor.setPosition(0)
        self._text_view.setTextCursor(cursor)

    def show_at(self, anchor_rect: QRect) -> None:
        """Show next to ``anchor_rect`` (global coords). Prefers right of anchor, flips left if overflowing."""
        screen = self._screen_geometry(anchor_rect.topLeft())
        size = self.size()

        right_x = anchor_rect.right() + _ANCHOR_GAP_PX
        left_x = anchor_rect.left() - _ANCHOR_GAP_PX - size.width()

        if right_x + size.width() <= screen.right():
            x = right_x
        elif left_x >= screen.left():
            x = left_x
        else:
            x = max(screen.left(), screen.right() - size.width())

        y = anchor_rect.top()
        y = min(y, screen.bottom() - size.height())
        y = max(y, screen.top())

        self.move(QPoint(x, y))
        if not self.isVisible():
            self.show()
        else:
            self.raise_()

    @staticmethod
    def _screen_geometry(point: QPoint) -> QRect:
        app = QApplication.instance()
        if app is None:
            return QRect(0, 0, 1920, 1080)
        screen = app.screenAt(point)
        if screen is None:
            screen = app.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)


__all__ = ["HelpPopup"]
