"""
VSCode-style inline Go to Line overlay.

Parents a ``QLineEdit`` to the editor's viewport, floating at the top of
the visible area. Enter jumps the caret to the entered line; Esc /
focus-out / scroll cancels.

Single-shot — each Ctrl+G press builds a fresh overlay that deletes
itself on dismiss, same pattern as :class:`.rename_overlay.RenameOverlay`.

Lifecycle, key routing, focus-out / scroll cancel, and theming live in
:class:`.inline_overlay.EditorInlineOverlay`; this module only owns the
top-center positioning and the line-jump Enter commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ......lib_ui.qt_compat import QIntValidator, QTextCursor
from .inline_overlay import EditorInlineOverlay

if TYPE_CHECKING:
    from .code_editor import CodeEditor


# Distance from the top of the viewport to the overlay. Matches the
# breathing room VSCode leaves around its command-palette inputs.
_TOP_MARGIN = 8

# Fixed width — wide enough for "Go to line (1 - 99999)" placeholder
# without clipping at the common font size, narrow enough not to obscure
# the top of the visible code.
_WIDTH = 240

# Padding added around the font's natural line height to size the box.
_HEIGHT_PAD = 6


class GoToLineOverlay(EditorInlineOverlay):
    """Inline line-number input. Created fresh per Ctrl+G invocation."""

    def __init__(self, editor: CodeEditor):
        super().__init__(editor)

        max_line = max(editor.document().blockCount(), 1)
        self._max_line = max_line

        self.setValidator(QIntValidator(1, max_line, self))
        self.setPlaceholderText(f"Go to line (1 - {max_line})")

        current_line = editor.textCursor().blockNumber() + 1
        self.setText(str(current_line))
        self.selectAll()

        self._position()
        self._finish_setup()

    # -------------------- positioning --------------------

    def _position(self) -> None:
        # Centre over the editor as a whole (line-number gutter + text), not
        # just the text viewport. ``editor.viewport()`` sits inside Qt's
        # viewport margins, so its coordinate origin is already offset to the
        # right of the gutter — subtracting the gutter width shifts the box
        # back so it lines up with the editor's visual centre.
        editor_width = self._editor.width()
        gutter_width = editor_width - self._editor.viewport().width()
        metrics = self._editor.fontMetrics()
        height = metrics.height() + _HEIGHT_PAD * 2
        x = max(0, (editor_width - _WIDTH) // 2 - gutter_width)
        self.setGeometry(x, _TOP_MARGIN, _WIDTH, height)

    # -------------------- Enter commit --------------------

    def _commit(self) -> None:
        text = self.text().strip()
        if not text:
            self._dismiss()
            return
        try:
            line = int(text)
        except ValueError:
            self._dismiss()
            return

        doc = self._editor.document()
        line = max(1, min(line, self._max_line))
        block = doc.findBlockByNumber(line - 1)
        if not block.isValid():
            self._dismiss()
            return

        if not block.isVisible() and hasattr(self._editor, "fold_manager"):
            self._editor.fold_manager.unfold_containing(block.blockNumber())

        # Tear down BEFORE moving the caret. ``centerCursor()`` scrolls the
        # viewport, which would re-fire the scroll-dismiss handler while
        # we're already mid-commit if we left them wired up.
        self._dismissed = True
        self._disconnect_scroll()
        self.hide()
        self.deleteLater()

        cursor = QTextCursor(block)
        self._editor.setTextCursor(cursor)
        self._editor.centerCursor()
        self._editor.setFocus()


__all__ = ["GoToLineOverlay"]
