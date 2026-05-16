"""
VSCode-style inline rename overlay.

A small ``QLineEdit`` parented to the editor's viewport that floats over
the symbol under the caret. Enter applies the new name to every in-file
reference in a single undo block; Esc / focus-out / scroll cancels.

The widget is single-shot: each F2 press builds a fresh overlay and
schedules ``deleteLater`` when it dismisses. That keeps cleanup obvious
— there's no long-lived state to invalidate when the editor reflows,
swaps documents, or the active tab changes.
"""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import TYPE_CHECKING

from ......lib_ui.qt_compat import QLineEdit, Qt, QTextCursor
from ...themes import AppTheme

if TYPE_CHECKING:
    from ...command.refactor import SymbolReference
    from .code_editor import CodeEditor

logger = getLogger(__name__)


# Padding around the symbol, in pixels. Picked to match the editor's
# bracket-match overlay so the rename box visually belongs to the same
# affordance family.
_PAD_X = 2
_PAD_Y = 2

# Min width for very short symbol names — gives the user room to type
# something longer without the box clipping mid-keystroke.
_MIN_WIDTH = 100


class RenameOverlay(QLineEdit):
    """Inline rename input. Created fresh per F2 invocation."""

    def __init__(self, editor: CodeEditor, references: list[SymbolReference], old_name: str, cursor_offset: int):
        super().__init__(editor.viewport())
        self._editor = editor
        self._references = references
        self._old_name = old_name
        # The reference the user was actually pointing at — drives both the
        # overlay position and where the caret lands after a commit, so the
        # focus stays at the call site rather than jumping to the definition.
        self._anchor = _anchor_reference(references, cursor_offset)
        # Guards against re-entry: ``hide()`` and ``setFocus()`` trigger
        # ``focusOutEvent`` synchronously, which would otherwise call
        # ``_dismiss`` again on a half-cleaned widget.
        self._dismissed = False

        self.setFont(editor.font())
        self.setText(old_name)
        self.selectAll()
        self.setStyleSheet(_stylesheet())

        self._position_over(self._anchor)

        # Cancel on scroll — the box would otherwise stay pinned to its
        # original viewport coordinate while the underlying symbol moves.
        editor.verticalScrollBar().valueChanged.connect(self._dismiss)
        editor.horizontalScrollBar().valueChanged.connect(self._dismiss)

        self.show()
        self.setFocus(Qt.PopupFocusReason)
        self.raise_()

    # -------------------- positioning --------------------

    def _position_over(self, reference: SymbolReference) -> None:
        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(reference.start)
        rect = self._editor.cursorRect(cursor)

        metrics = self._editor.fontMetrics()
        symbol_width = metrics.horizontalAdvance(self._old_name)
        # Give the user roughly double the original symbol's width to type
        # into — comfortable for the typical "shorten or slightly rename"
        # case without taking over the viewport.
        width = max(symbol_width * 2 + metrics.horizontalAdvance("    "), _MIN_WIDTH)
        height = rect.height() + _PAD_Y * 2
        self.setGeometry(rect.left() - _PAD_X, rect.top() - _PAD_Y, width, height)

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

    # -------------------- lifecycle --------------------

    def _commit(self) -> None:
        new_name = self.text()
        if not new_name or new_name == self._old_name:
            self._dismiss()
            return
        if not new_name.isidentifier():
            # No-op: keep the box open so the user can fix the typo.
            # Visible feedback would be nicer but a silent reject matches
            # the "Esc to back out, Enter to commit" simple model.
            return

        self._dismissed = True
        self._disconnect_scroll()

        doc = self._editor.document()
        delta = len(new_name) - len(self._old_name)
        # ``_anchor.start`` was captured pre-edit. The replacements ahead of
        # it (sorted-by-start, processed in reverse) leave it intact, but
        # the replacements *before* it shift it by ``delta`` each. The
        # adjustment lands the caret at the end of the renamed anchor
        # regardless of whether new_name is shorter or longer than the old.
        refs_before_anchor = sum(1 for r in self._references if r.start < self._anchor.start)
        final_pos = self._anchor.start + refs_before_anchor * delta + len(new_name)

        # Position the editor's cursor at the anchor BEFORE opening the edit
        # block. Qt records the position of the cursor that called
        # ``beginEditBlock`` as the post-undo restore target — without this
        # priming step a fresh ``QTextCursor(doc)`` would record position 0
        # and undoing the rename would jump the caret to the document start.
        pre_edit_cursor = self._editor.textCursor()
        pre_edit_cursor.setPosition(self._anchor.end)
        self._editor.setTextCursor(pre_edit_cursor)

        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        try:
            # Walk in reverse so each replacement's offsets are stable —
            # earlier references don't shift as later ones change length.
            for ref in reversed(self._references):
                cursor.setPosition(ref.start)
                cursor.setPosition(ref.end, QTextCursor.KeepAnchor)
                cursor.insertText(new_name)
        finally:
            cursor.endEditBlock()

        final_cursor = QTextCursor(doc)
        final_cursor.setPosition(final_pos)
        self._editor.setTextCursor(final_cursor)

        self._teardown()

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


def _anchor_reference(references: list[SymbolReference], cursor_offset: int) -> SymbolReference:
    """Pick the reference the user was pointing at.

    Prefers a reference whose ``[start, end]`` range contains the caret —
    that's the symbol the user actually clicked on. ``end`` is inclusive
    here so the caret being right after the last character (where typing
    would extend the identifier) still counts as "on" the symbol.

    Falls back to the first reference when the caret sits outside every
    range (rare: jedi found references but the user's caret moved before
    we read it). The list is sorted by ``start`` upstream.
    """
    for ref in references:
        if ref.start <= cursor_offset <= ref.end:
            return ref
    return references[0]


def _stylesheet() -> str:
    """Themed appearance for the rename input.

    Matches the editor's surface colour so the box visually overlays the
    text without clashing, with an accent-blue border to mark it as an
    active editing affordance (mirrors VSCode's rename popup).
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


__all__ = ["RenameOverlay"]
