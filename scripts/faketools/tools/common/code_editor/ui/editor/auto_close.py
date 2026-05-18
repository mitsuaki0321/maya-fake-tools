"""Auto-close brackets / quotes and surround-selection helper.

Hooks into ``CodeEditor.keyPressEvent`` between the multi-cursor handler
and ``EditorShortcuts`` so a single-cursor caret gets VSCode-style
auto-pairing:

* Typing ``(`` ``[`` ``{`` ``"`` ``'`` inserts the matching closer and
  parks the caret between the pair.
* Typing one of those with a selection wraps the selection (and re-selects
  the wrapped range so the user can chain).
* Typing a closer that already sits to the right of the caret is
  swallowed and the caret steps over it -- no duplicate ``))``.
* Backspace at an empty ``()`` / ``[]`` / ``{}`` / ``""`` / ``''`` pair
  removes both halves in one ``beginEditBlock`` so a single undo
  restores them together.

Quotes are skipped (the keystroke falls through to plain insertion) when
the *next* char is a word character -- avoids splitting an identifier
when the caret is parked inside one -- or when the *previous* char is
the same quote, so the user can still type a triple-double-quote prefix
without it expanding to six quotes. The rule deliberately ignores the
previous char being a letter so that ``f"..."`` / ``r"..."`` / ``b"..."``
string prefixes auto-close as expected.

Multi-cursor mode short-circuits the handler entirely; the existing
multi-cursor input pipeline keeps full control of synchronized edits.
"""

from __future__ import annotations

from ......lib_ui.qt_compat import Qt, QTextCursor

# Open char -> close char. Quote chars are self-paired.
_PAIRS: dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    '"': '"',
    "'": "'",
}
_OPENERS = frozenset(_PAIRS.keys())
_CLOSERS = frozenset(_PAIRS.values())
_QUOTES = frozenset({'"', "'"})

# Modifiers that should *disable* auto-close. Shift is intentionally absent
# because most keyboard layouts produce ``(``/``{``/``"`` only with Shift held.
_SUPPRESS_MODIFIERS = Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier


def handle_key(editor, event) -> bool:
    """Try to consume ``event`` with auto-close logic.

    Args:
        editor: The :class:`CodeEditor` receiving the key press.
        event: The ``QKeyEvent`` to inspect.

    Returns:
        bool: True iff the keystroke was fully handled and the caller
        should skip further processing.
    """
    # Defer to the multi-cursor handler whenever an extra caret is active.
    if getattr(editor, "all_cursors", None) and len(editor.all_cursors) > 1:
        return False

    modifiers = event.modifiers()

    if event.key() == Qt.Key_Backspace and not (modifiers & _SUPPRESS_MODIFIERS):
        return _handle_backspace(editor)

    if modifiers & _SUPPRESS_MODIFIERS:
        return False

    text = event.text()
    if len(text) != 1:
        return False

    char = text

    if char in _OPENERS:
        return _handle_opener(editor, char)

    if char in _CLOSERS:
        return _handle_closer(editor, char)

    return False


def _handle_opener(editor, char: str) -> bool:
    cursor = editor.textCursor()
    close = _PAIRS[char]

    if cursor.hasSelection():
        anchor, position = cursor.anchor(), cursor.position()
        start, end = sorted((anchor, position))
        selected = cursor.selectedText()
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(char + selected + close)
        cursor.endEditBlock()
        # Re-select the wrapped text so the user can chain wraps. Preserve the
        # original anchor/position orientation so Shift-extending afterwards
        # behaves the way the user expects.
        new_cursor = QTextCursor(editor.document())
        if anchor <= position:
            new_cursor.setPosition(start + 1)
            new_cursor.setPosition(end + 1, QTextCursor.KeepAnchor)
        else:
            new_cursor.setPosition(end + 1)
            new_cursor.setPosition(start + 1, QTextCursor.KeepAnchor)
        editor.setTextCursor(new_cursor)
        return True

    if char in _QUOTES:
        next_char = _char_after(cursor)

        # Step over an existing matching quote rather than duplicate it.
        if next_char == char:
            _step_over(editor, cursor)
            return True

        # Don't split an identifier the caret happens to sit inside. Tested on
        # the *next* char rather than the previous one so that ``f"..."`` /
        # ``r"..."`` / ``b"..."`` prefixes still auto-close after the leading
        # letter.
        if next_char.isalnum() or next_char == "_":
            return False
        # Avoid interfering with triple-quote typing (e.g. typing the third
        # ``"`` of a Python docstring).
        if _char_before(cursor) == char:
            return False

    pos = cursor.position()
    cursor.insertText(char + close)
    cursor.setPosition(pos + 1)
    editor.setTextCursor(cursor)
    return True


def _handle_closer(editor, char: str) -> bool:
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    if _char_after(cursor) != char:
        return False
    _step_over(editor, cursor)
    return True


def _handle_backspace(editor) -> bool:
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return False
    prev_char = _char_before(cursor)
    if prev_char not in _PAIRS:
        return False
    if _char_after(cursor) != _PAIRS[prev_char]:
        return False
    cursor.beginEditBlock()
    cursor.deletePreviousChar()
    cursor.deleteChar()
    cursor.endEditBlock()
    return True


def _char_before(cursor) -> str:
    """Return the single character immediately before ``cursor``, or ''."""
    pos = cursor.position()
    if pos <= 0:
        return ""
    probe = QTextCursor(cursor.document())
    probe.setPosition(pos - 1)
    probe.setPosition(pos, QTextCursor.KeepAnchor)
    text = probe.selectedText()
    return text[0] if text else ""


def _char_after(cursor) -> str:
    """Return the single character immediately after ``cursor``, or ''."""
    pos = cursor.position()
    doc = cursor.document()
    if pos >= doc.characterCount() - 1:
        return ""
    probe = QTextCursor(doc)
    probe.setPosition(pos)
    probe.setPosition(pos + 1, QTextCursor.KeepAnchor)
    text = probe.selectedText()
    return text[0] if text else ""


def _step_over(editor, cursor) -> None:
    cursor.setPosition(cursor.position() + 1)
    editor.setTextCursor(cursor)
