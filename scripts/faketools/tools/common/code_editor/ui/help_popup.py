"""
Floating help popup for the Code Editor.

Shows the docstring of a symbol next to the autocomplete list (when
open) or near the caret. Triggered via ``Ctrl+Shift+Space`` — see
:mod:`help_popup_controller` for the decision of *what* symbol to
display.

Content rendering is delegated to :mod:`.help_renderer` — this
module is only the Qt-level shell (window flags, positioning, the
loading placeholder, theme-surface wiring). The renderer returns an
HTML string we hand to ``QTextEdit.setHtml``.

Design rationale — why ``parent=None``:

The autocomplete popup (``QCompleter.popup()``) is a top-level window
with no Qt parent. If we parent this help popup to Maya's main window,
``HelpPopup.show()`` raises the main window in z-order, which then
shoves the autocomplete popup *behind* the main window — the user sees
the list vanish. Keeping the help popup parent-less makes both popups
independent top-levels; neither raises Maya main when shown, so their
relative z-order stays stable.

Following Maya's window state (minimise / hide / deactivate) is handled
explicitly by :class:`_OwnerWindowWatcher` in
:mod:`help_popup_controller`, not via Qt parent ownership.

Interaction model:

- ``Qt.Tool | FramelessWindowHint``: borderless, no taskbar entry,
  follows app-level z-order without staying above other applications.
- ``Qt.WindowDoesNotAcceptFocus`` + ``Qt.WA_ShowWithoutActivating``:
  keeps keyboard focus on the editor so the autocomplete popup's own
  key handlers (arrows, Tab, Enter) keep working while the help popup
  is visible.
- ``setTextInteractionFlags(Qt.TextSelectableByMouse)`` *before*
  ``setFocusPolicy(Qt.NoFocus)``: the flags setter implicitly rewrites
  focusPolicy to ``ClickFocus``; we pin it back to ``NoFocus``
  afterwards so mouse selection works without pulling focus off the
  editor (which would close the autocomplete list).
"""

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
from .help_renderer import DEFAULT_THEME, SURFACE_BG, render_docstring

logger = getLogger(__name__)

_LOADING_PLACEHOLDER = "Loading…"

# Dimensions. Docstrings run long — keep the popup generous enough that
# the internal scroll bar does the work rather than clipping content.
_MIN_WIDTH_PX = 360
_MIN_HEIGHT_PX = 120
_MAX_WIDTH_PX = 640
_MAX_HEIGHT_PX = 420

# Padding between the anchor (autocomplete popup or caret rect) and this
# window, so the two visual elements don't visually touch.
_ANCHOR_GAP_PX = 6


class HelpPopup(QFrame):
    """Floating, non-activating docstring window.

    Single shared instance per main window — :meth:`show_at` repositions
    and :meth:`set_text` replaces content, so one popup serves every
    editor tab.
    """

    def __init__(self):
        # parent=None is a deliberate choice — see the module docstring
        # for why it's required to keep z-order with the autocomplete
        # popup stable.
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)

        # Belt-and-braces against activating on show. The window flag
        # alone isn't reliably honoured on all platforms.
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._text_view = QTextEdit(self)
        self._text_view.setReadOnly(True)
        # Order matters: ``setTextInteractionFlags`` rewrites
        # ``focusPolicy`` under the hood (to ``ClickFocus`` when
        # ``TextSelectableByMouse`` is set). Calling it first and then
        # hard-pinning to ``NoFocus`` gives us the combination we want:
        # mouse selection works (hit-testing doesn't require focus) but
        # clicking the popup never moves keyboard focus off the editor,
        # which is what would otherwise close the autocomplete list.
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
        """Set the widget surface so the renderer's HTML sits on a uniform,
        slightly-lighter surface than the code blocks inside the HTML
        (``SURFACE_BG`` vs ``theme["code_bg"]``) — the "inset" effect
        needs the widget's own background to be the lighter of the two.

        Border / selection colours come from the editor's ``AppTheme``
        when it's importable so the popup visually matches the rest of
        the Code Editor; otherwise we fall back to hard-coded neutrals.
        """
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
                color: {DEFAULT_THEME["foreground"]};
                border: none;
                selection-background-color: {selection};
            }}
            """
        )

    # -------------------- content --------------------

    def set_loading(self, identifier: str = "") -> None:
        """Show a placeholder while the docstring fetch is in flight.

        Rendered as the same minimal HTML shell the real content uses
        so there's no font flicker when the fetched docstring
        eventually replaces this placeholder.
        """
        label = _LOADING_PLACEHOLDER if not identifier else f"{_LOADING_PLACEHOLDER}  {identifier}"
        theme = DEFAULT_THEME
        self._text_view.setHtml(
            f'<div style="color:{theme["muted"]};'
            f"font-family:{theme['font_family_body']};"
            f"font-size:{theme['font_size_pt']}pt;"
            f'font-style:italic;padding:10px;">{label}</div>'
        )

    def set_text(self, text: str) -> None:
        """Replace the popup body with the rendered docstring HTML."""
        self._text_view.setHtml(render_docstring(text))
        # Scroll back to the top so a long docstring starts from its
        # beginning rather than wherever the previous scroll landed.
        cursor = self._text_view.textCursor()
        cursor.setPosition(0)
        self._text_view.setTextCursor(cursor)

    # -------------------- positioning --------------------

    def show_at(self, anchor_rect: QRect) -> None:
        """Show next to ``anchor_rect`` (global screen coords).

        Prefers placing on the right of the anchor; flips to the left if
        the right side overflows the screen. Vertical position is
        clamped so the popup stays on-screen.
        """
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
        """Available geometry of the screen containing ``point``."""
        app = QApplication.instance()
        if app is None:
            return QRect(0, 0, 1920, 1080)
        screen = app.screenAt(point)
        if screen is None:
            screen = app.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)


__all__ = ["HelpPopup"]
