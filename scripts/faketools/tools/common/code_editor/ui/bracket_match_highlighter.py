"""Sublime-style bracket pair highlight.

Outlines the brackets that *contain* the cursor (not just the adjacent
pair) — equivalent to Sublime's ``match_brackets_content``. Brackets inside
``#`` line comments and string literals are skipped; f-string interpolation
expressions are treated as opaque, matching Sublime's own approximation.

Renders via custom ``QPainter`` rectangles in :meth:`paint` (called from the
editor's ``paintEvent``) rather than ``QTextCharFormat`` background — Qt has
no per-character border format, so a rectangle outline around the bracket
cell needs direct painting.
"""

from logging import getLogger

from .....lib_ui.qt_compat import (
    QColor,
    QPainter,
    QPen,
    QRect,
    QTextCursor,
)
from ..themes import AppTheme

logger = getLogger(__name__)

_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
_OPEN_CHARS = frozenset(_OPEN_TO_CLOSE)
_CLOSE_CHARS = frozenset(_OPEN_TO_CLOSE.values())


class BracketMatchHighlighter:
    """Outlines the bracket pair surrounding (or adjacent to) the cursor.

    A single full-text scan builds a sorted list of ``(open_pos, close_pos)``
    pairs, ignoring brackets inside comments and strings. The scan is cached
    until the document content changes.
    """

    def __init__(self, editor):
        self._editor = editor
        self._pairs = None
        self._border_color = QColor(AppTheme.BRACKET_MATCH_BORDER)

        editor.cursorPositionChanged.connect(self._on_cursor_moved)
        editor.document().contentsChanged.connect(self._on_contents_changed)

    # ---------- Signal handlers ----------

    def _on_contents_changed(self):
        self._pairs = None
        self._editor.viewport().update()

    def _on_cursor_moved(self):
        self._editor.viewport().update()

    # ---------- Scanner ----------

    def _scan(self, text: str) -> list:
        """Return a sorted list of ``(open_pos, close_pos)`` pairs.

        Brackets inside ``#`` line comments and string literals (single,
        double, raw, triple) are skipped. Unmatched closers and unclosed
        openers do not produce entries.
        """
        pairs = []
        stack = []
        n = len(text)
        i = 0
        while i < n:
            ch = text[i]
            if ch == "#":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if ch == '"' or ch == "'":
                i = self._skip_string(text, i)
                continue
            if ch in _OPEN_CHARS:
                stack.append((i, _OPEN_TO_CLOSE[ch]))
            elif ch in _CLOSE_CHARS and stack and stack[-1][1] == ch:
                op, _ = stack.pop()
                pairs.append((op, i))
            i += 1
        pairs.sort()
        return pairs

    @staticmethod
    def _skip_string(text: str, i: int) -> int:
        """Return the index past the end of the string literal starting at ``i``."""
        n = len(text)
        quote = text[i]
        if text[i : i + 3] == quote * 3:
            j = i + 3
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if text[j : j + 3] == quote * 3:
                    return j + 3
                j += 1
            return n
        j = i + 1
        while j < n:
            ch = text[j]
            if ch == "\\" and j + 1 < n:
                j += 2
                continue
            if ch == quote:
                return j + 1
            if ch == "\n":
                return j
            j += 1
        return n

    # ---------- Pair lookup ----------

    def _find_pair_at(self, pos: int, text: str):
        if not self._pairs:
            return None
        n = len(text)
        if pos > 0:
            left = text[pos - 1]
            if left in _OPEN_CHARS:
                for op, cp in self._pairs:
                    if op == pos - 1:
                        return op, cp
            elif left in _CLOSE_CHARS:
                for op, cp in self._pairs:
                    if cp == pos - 1:
                        return op, cp
        if pos < n:
            right = text[pos]
            if right in _OPEN_CHARS:
                for op, cp in self._pairs:
                    if op == pos:
                        return op, cp
            elif right in _CLOSE_CHARS:
                for op, cp in self._pairs:
                    if cp == pos:
                        return op, cp
        innermost = None
        for op, cp in self._pairs:
            if op >= pos:
                break
            if cp > pos and (innermost is None or op > innermost[0]):
                innermost = (op, cp)
        return innermost

    # ---------- Paint ----------

    def paint(self, event):
        """Draw 1px rectangles around the cursor's matching bracket pair."""
        text = self._editor.document().toPlainText()
        if self._pairs is None:
            self._pairs = self._scan(text)
        pair = self._find_pair_at(self._editor.textCursor().position(), text)
        if pair is None:
            return

        rects = [r for r in (self._char_rect(p) for p in pair) if r is not None]
        if not rects:
            return

        event_rect = event.rect()
        painter = QPainter(self._editor.viewport())
        painter.setPen(QPen(self._border_color, 1))
        for rect in rects:
            if not rect.intersects(event_rect):
                continue
            # Qt's drawRect with a cosmetic pen renders one pixel taller and
            # wider than the rect's dimensions; subtracting 1 from w/h aligns
            # the visible edges with the character cell boundaries.
            painter.drawRect(rect.x(), rect.y(), rect.width() - 1, rect.height() - 1)
        painter.end()

    def _char_rect(self, pos: int):
        """Return the viewport rectangle occupied by the character at ``pos``.

        Returns ``None`` if the bracket character is not visible (folded, or
        wrapped across two visual lines).
        """
        doc = self._editor.document()
        c1 = QTextCursor(doc)
        c1.setPosition(pos)
        c2 = QTextCursor(doc)
        c2.setPosition(pos + 1)
        r1 = self._editor.cursorRect(c1)
        r2 = self._editor.cursorRect(c2)
        if r1.top() != r2.top():
            return None
        width = r2.left() - r1.left()
        if width <= 0:
            return None
        return QRect(r1.left(), r1.top(), width, r1.height())
