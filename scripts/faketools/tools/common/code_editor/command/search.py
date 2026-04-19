"""
Search command layer for the Code Editor.

Owns all pattern matching and replacement logic against a ``QTextDocument``.
The UI dialog builds a ``SearchOptions`` from its checkboxes, hands it to a
``SearchEngine`` bound to the active document, and consumes cursors / counts.

Keeping this logic out of the dialog lets us (a) avoid repeated
``toPlainText()`` scans, (b) test pattern behaviour without a Qt dialog, and
(c) share the same engine with other callers (e.g. multi-cursor select-all).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import re

from .....lib_ui.qt_compat import QTextCursor, QTextDocument


class InvalidRegexError(ValueError):
    """Raised when a pattern fails to compile under the current options."""


@dataclass
class SearchOptions:
    """User-visible toggles that affect pattern matching.

    Direction is handled per-call (not stored here) because find-next / find-prev
    flip it temporarily without changing the persisted UI state.
    """

    match_case: bool = False
    whole_words: bool = False
    use_regex: bool = False

    def to_find_flags(self, backward: bool = False):
        """Translate the options into ``QTextDocument.FindFlags`` for ``document.find()``."""
        flags = QTextDocument.FindFlags()
        if self.match_case:
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_words:
            flags |= QTextDocument.FindWholeWords
        if backward:
            flags |= QTextDocument.FindBackward
        return flags

    def regex_flags(self) -> int:
        """Translate the options into ``re`` module flags."""
        flags = 0
        if not self.match_case:
            flags |= re.IGNORECASE
        return flags


def _compile_regex(pattern: str, options: SearchOptions):
    try:
        return re.compile(pattern, options.regex_flags())
    except re.error as exc:
        raise InvalidRegexError(str(exc)) from exc


def _cursor_for_range(document, start: int, end: int) -> QTextCursor:
    cursor = QTextCursor(document)
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    return cursor


class SearchEngine:
    """Pattern matching and replacement over a ``QTextDocument``.

    All methods are stateless w.r.t. the engine instance; the document itself
    provides the text. Methods that mutate (``replace_all``) expect the caller
    to wrap them in ``beginEditBlock()`` / ``endEditBlock()`` for single-undo.
    """

    def __init__(self, document: QTextDocument):
        self.document = document

    # -------------------- Single-shot finds --------------------

    def find_from(
        self,
        pattern: str,
        from_cursor: QTextCursor,
        options: SearchOptions,
        backward: bool = False,
    ) -> QTextCursor:
        """Return the next match starting at ``from_cursor``; ``isNull()`` if none."""
        if options.use_regex:
            return self._regex_find_from(pattern, from_cursor, options, backward)
        flags = options.to_find_flags(backward=backward)
        try:
            return self.document.find(pattern, from_cursor, flags)
        except (TypeError, AttributeError):
            return self.document.find(pattern, from_cursor)

    def _regex_find_from(
        self,
        pattern: str,
        from_cursor: QTextCursor,
        options: SearchOptions,
        backward: bool,
    ) -> QTextCursor:
        regex = _compile_regex(pattern, options)
        text = self.document.toPlainText()
        start_pos = from_cursor.position()

        if backward:
            match = None
            for candidate in regex.finditer(text[:start_pos]):
                match = candidate
            if match:
                return _cursor_for_range(self.document, match.start(), match.end())
        else:
            match = regex.search(text, start_pos)
            if match:
                return _cursor_for_range(self.document, match.start(), match.end())

        return QTextCursor()

    # -------------------- Iteration / counting --------------------

    def iter_matches(self, pattern: str, options: SearchOptions) -> Iterator[QTextCursor]:
        """Yield a fresh ``QTextCursor`` for each forward match.

        Callers that just want a count should prefer ``count_matches`` since it
        avoids the per-match cursor construction cost.
        """
        if options.use_regex:
            regex = _compile_regex(pattern, options)
            text = self.document.toPlainText()
            for match in regex.finditer(text):
                yield _cursor_for_range(self.document, match.start(), match.end())
            return

        flags = options.to_find_flags(backward=False)
        cursor = QTextCursor(self.document)
        cursor.setPosition(0)
        while True:
            try:
                found = self.document.find(pattern, cursor, flags)
            except (TypeError, AttributeError):
                found = self.document.find(pattern, cursor)
            if found.isNull():
                return
            yield QTextCursor(found)
            cursor = found

    def count_matches(self, pattern: str, options: SearchOptions) -> int:
        """Count total forward matches. Raises ``InvalidRegexError`` if regex is bad."""
        if options.use_regex:
            regex = _compile_regex(pattern, options)
            return len(regex.findall(self.document.toPlainText()))

        # Whole-word matching isn't reducible to str.count — fall back to iteration.
        if options.whole_words:
            return sum(1 for _ in self.iter_matches(pattern, options))

        text = self.document.toPlainText()
        if options.match_case:
            return text.count(pattern)
        return text.lower().count(pattern.lower())

    # -------------------- Replacement --------------------

    def replace_all(self, pattern: str, replacement: str, options: SearchOptions) -> int:
        """Replace every forward match and return the count.

        Wrap calls in ``cursor.beginEditBlock()`` / ``endEditBlock()`` for a
        single undo step. Replacement happens from the end of the document
        backwards so earlier match positions remain valid.
        """
        if options.use_regex:
            return self._regex_replace_all(pattern, replacement, options)
        return self._text_replace_all(pattern, replacement, options)

    def _text_replace_all(self, search_text: str, replace_text: str, options: SearchOptions) -> int:
        flags = options.to_find_flags(backward=False)
        positions = []
        cursor = QTextCursor(self.document)
        cursor.setPosition(0)
        while True:
            try:
                found = self.document.find(search_text, cursor, flags)
            except (TypeError, AttributeError):
                found = self.document.find(search_text, cursor)
            if found.isNull():
                break
            positions.append((found.selectionStart(), found.selectionEnd()))
            cursor = found

        if not positions:
            return 0

        cursor = QTextCursor(self.document)
        for start, end in reversed(positions):
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.insertText(replace_text)
        return len(positions)

    def _regex_replace_all(self, pattern: str, replacement: str, options: SearchOptions) -> int:
        regex = _compile_regex(pattern, options)
        text = self.document.toPlainText()
        matches = list(regex.finditer(text))
        if not matches:
            return 0

        cursor = QTextCursor(self.document)
        for match in reversed(matches):
            cursor.setPosition(match.start())
            cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
            if "\\" in replacement:
                expanded = match.expand(replacement)
            else:
                expanded = replacement
            cursor.insertText(expanded)
        return len(matches)

    # -------------------- Small helpers --------------------

    @staticmethod
    def texts_equal(a: str, b: str, options: SearchOptions) -> bool:
        """Compare two strings under the current case-sensitivity option.

        Used by replace-current to decide whether the active selection already
        matches the search text so a replace can happen in place.
        """
        if options.match_case:
            return a == b
        return a.lower() == b.lower()


def build_options_from_flags(match_case: bool, whole_words: bool, use_regex: bool) -> SearchOptions:
    """Convenience factory for callers that already have the three booleans."""
    return SearchOptions(match_case=match_case, whole_words=whole_words, use_regex=use_regex)


__all__ = [
    "InvalidRegexError",
    "SearchEngine",
    "SearchOptions",
    "build_options_from_flags",
]
