"""
Shared base for single-shot inline editor overlays.

A small ``QLineEdit`` parented to the editor's viewport, used as a
VSCode-style affordance over the live code: F2 rename
(:mod:`.rename_overlay`) and Ctrl+G go-to-line
(:mod:`.goto_line_overlay`).

Subclasses keep the bits that actually differ — where the box appears
(``_position()`` or their own positioning helper) and what Enter does
(``_commit()``). Everything shared lives here: the re-entry guard, the
Esc/Enter key routing, focus-out and scroll-cancel handling, themed
appearance, and the show/focus/raise sequence.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from ......lib_ui.qt_compat import QLineEdit, Qt
from ...themes import AppTheme

if TYPE_CHECKING:
    from .code_editor import CodeEditor


class EditorInlineOverlay(QLineEdit):
    """Base class for short-lived inline overlays over the editor viewport.

    Lifecycle contract for subclasses:

    1. Call ``super().__init__(editor)`` first. This parents the widget
       to ``editor.viewport()``, copies the editor's font, applies the
       shared stylesheet, and arms the re-entry guard.
    2. Set up subclass-specific state (validators, text, anchors, etc.).
    3. Position the widget (``setGeometry`` directly, or via a helper).
    4. Call ``self._finish_setup()`` last. It wires the scroll-cancel
       handler, then shows / focuses / raises the widget.

    Subclasses implement ``_commit()`` for Enter behavior. When a commit
    will scroll the viewport (e.g. ``centerCursor()`` or a multi-block
    edit), set ``self._dismissed = True`` and call
    ``self._disconnect_scroll()`` *before* the scrolling action so the
    cancel handler doesn't fire recursively.
    """

    def __init__(self, editor: CodeEditor):
        super().__init__(editor.viewport())
        self._editor = editor
        # Re-entry guard. ``hide()`` and ``setFocus()`` trigger
        # ``focusOutEvent`` synchronously, which would otherwise call
        # ``_dismiss`` again on a half-cleaned widget.
        self._dismissed = False

        self.setFont(editor.font())
        self.setStyleSheet(_stylesheet())

    # -------------------- setup hook --------------------

    def _finish_setup(self) -> None:
        """Wire scroll-cancel and bring the widget forward.

        Subclasses call this once after positioning and seeding text /
        validators. Scroll signals are connected here (not in ``__init__``)
        so any layout-induced scroll during widget construction can't
        fire the cancel handler before the widget is even visible.
        """
        editor = self._editor
        # Cancel on scroll — the box would otherwise stay pinned to its
        # original viewport coordinate while the underlying code moves.
        editor.verticalScrollBar().valueChanged.connect(self._dismiss)
        editor.horizontalScrollBar().valueChanged.connect(self._dismiss)

        self.show()
        self.setFocus(Qt.PopupFocusReason)
        self.raise_()

    # -------------------- input handling --------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._dismiss()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._commit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Defer through the guard rather than checking ``isVisible`` —
        # focusOut fires *during* ``hide()``, so a visibility check would
        # still allow the recursive dismiss path.
        if not self._dismissed:
            self._dismiss()

    # -------------------- subclass hook --------------------

    def _commit(self) -> None:
        """Implement Enter behavior. See class docstring for the scroll-
        before-commit teardown ordering."""
        raise NotImplementedError

    # -------------------- lifecycle --------------------

    def _dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self._disconnect_scroll()
        self._teardown()

    def _disconnect_scroll(self) -> None:
        for bar in (self._editor.verticalScrollBar(), self._editor.horizontalScrollBar()):
            with contextlib.suppress(TypeError, RuntimeError):
                bar.valueChanged.disconnect(self._dismiss)

    def _teardown(self) -> None:
        self.hide()
        self.deleteLater()
        self._editor.setFocus()


def _stylesheet() -> str:
    """Shared themed appearance for inline editor overlays.

    Editor surface colour with an accent-blue border so both F2 rename
    and Ctrl+G visually belong to the same family of active editing
    affordances.
    """
    return (
        "QLineEdit {"
        f"  background-color: {AppTheme.BACKGROUND};"
        f"  color: {AppTheme.FOREGROUND};"
        f"  border: 1px solid {AppTheme.ACCENT_BLUE};"
        "  border-radius: 2px;"
        "  padding: 1px 3px;"
        "  selection-background-color: " + AppTheme.SELECTION + ";"
        "}"
    )


__all__ = ["EditorInlineOverlay"]
