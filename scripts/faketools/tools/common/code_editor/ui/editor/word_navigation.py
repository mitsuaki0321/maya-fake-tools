"""VSCode/Sublime-style word boundary navigation.

Replaces Qt's per-transition word jumps (which stop on every whitespace and
punctuation transition) with the IDE-conventional behavior: each Ctrl+Left /
Ctrl+Right press skips horizontal whitespace once and then moves past one
contiguous run of either word characters or non-word symbols, stopping at
line boundaries so newlines always require their own keypress to cross.

Used by both single-cursor shortcuts (``shortcuts.py`` →
``EditorTextOperationsMixin``) and the multi-cursor input handler so the two
modes stay in sync.
"""

from __future__ import annotations

# Qt may report block boundaries as U+2029 instead of '\n' depending on the
# code path. Treat both as newlines.
_NEWLINES = ("\n", " ")


def _char_class(ch: str) -> str:
    """Bucket a single character into ``nl`` / ``ws`` / ``word`` / ``sym``."""
    if not ch or ch in _NEWLINES:
        return "nl"
    if ch == " " or ch == "\t":
        return "ws"
    if ch.isalnum() or ch == "_":
        return "word"
    return "sym"


def next_word_position(text: str, pos: int) -> int:
    """Return the position Ctrl+Right should land on, starting from ``pos``."""
    n = len(text)
    if pos >= n:
        return n

    # Sitting on a newline → step over it and stop (don't gobble next line's content).
    if _char_class(text[pos]) == "nl":
        return pos + 1

    # Skip horizontal whitespace once.
    while pos < n and _char_class(text[pos]) == "ws":
        pos += 1

    if pos >= n:
        return n

    # If whitespace led us straight to a newline, stop here so the next press
    # crosses the newline rather than jumping past it silently.
    if _char_class(text[pos]) == "nl":
        return pos

    # Move past the current run (word or symbol), stopping at line breaks.
    run_cls = _char_class(text[pos])
    while pos < n:
        c = _char_class(text[pos])
        if c != run_cls or c == "nl":
            break
        pos += 1

    return pos


def previous_word_position(text: str, pos: int) -> int:
    """Return the position Ctrl+Left should land on, starting from ``pos``."""
    if pos <= 0:
        return 0
    n = len(text)
    if pos > n:
        pos = n

    # If we're sitting just past a newline, step back over it and stop.
    if _char_class(text[pos - 1]) == "nl":
        return pos - 1

    # Skip horizontal whitespace backward once.
    while pos > 0 and _char_class(text[pos - 1]) == "ws":
        pos -= 1

    if pos <= 0:
        return 0

    if _char_class(text[pos - 1]) == "nl":
        return pos

    # Move back over the previous run, stopping at line breaks.
    run_cls = _char_class(text[pos - 1])
    while pos > 0:
        c = _char_class(text[pos - 1])
        if c != run_cls or c == "nl":
            break
        pos -= 1

    return pos
