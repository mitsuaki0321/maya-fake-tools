"""Auto-indent logic for the Return key.

Pure (Qt-free) helpers, plus :func:`compute_new_indent` which decides the
indent string for a freshly inserted line. The editor's ``handle_return_key``
does the cursor manipulation and calls :func:`compute_new_indent` for the
decision.

The algorithm:

1. **Hanging indent** — if there is an unclosed opening bracket on the
   current line *before* the cursor, align to the column right after that
   bracket.
2. **Closing bracket alignment** — if the current line begins (after
   whitespace) with ``)`` / ``]`` / ``}``, look back for the matching
   opener and reuse the leading whitespace of its line.
3. **Block opener** — language-driven via
   :attr:`LanguageProfile.extra_indent_trigger`. If the predicate returns
   ``True`` for the text before the cursor, keep the current indent and
   add four spaces. Languages that don't supply a predicate (or that
   leave it ``None`` because brackets cover all their block syntax, e.g.
   MEL) skip this rule entirely.
4. Otherwise reuse the current line's leading whitespace.
"""

from __future__ import annotations

from collections.abc import Iterator
import re
from typing import Optional

from ..languages import LanguageProfile


def iter_code_brackets(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(index, char)`` for bracket characters in ``text``.

    Skips Python single-line / triple-quoted string literals and ``#``
    comments so that brackets inside them are not reported.

    Args:
        text (str): Source text to scan.

    Yields:
        tuple[int, str]: ``(index, char)`` pairs where ``char`` is one of
            ``()[]{}``.
    """
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "#":
            return
        if ch in ('"', "'"):
            quote = ch
            if text[i : i + 3] == quote * 3:
                i += 3
                while i < n:
                    if text[i : i + 3] == quote * 3:
                        i += 3
                        break
                    if text[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    i += 1
                continue
            i += 1
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch in "([{)]}":
            yield i, ch
        i += 1


def find_hanging_indent_column(text_before_cursor: str) -> int:
    """Find the column right after the last unclosed opening bracket.

    Args:
        text_before_cursor (str): Text from the start of the current line
            up to the cursor position.

    Returns:
        int: Column index to align the next line to. ``-1`` when there is
            no unclosed bracket on the current line.
    """
    stack: list[int] = []
    for idx, ch in iter_code_brackets(text_before_cursor):
        if ch in "([{":
            stack.append(idx)
        elif stack:
            stack.pop()
    return -1 if not stack else stack[-1] + 1


def find_closing_bracket_alignment(document, current_block_number: int, current_line: str) -> Optional[str]:
    """Return the indent of the line containing the matching opener.

    Applies when ``current_line`` begins (after whitespace) with ``)`` /
    ``]`` / ``}``. Scans preceding blocks of ``document`` for the matching
    opener and returns the leading whitespace of that block.

    Args:
        document: ``QTextDocument`` providing ``findBlockByNumber``.
        current_block_number (int): Block index of the current line.
        current_line (str): Full text of the current line.

    Returns:
        str | None: Indent string to use, or ``None`` when the current
            line does not start with a closing bracket or no matching
            opener was found.
    """
    stripped = current_line.lstrip()
    if not stripped or stripped[0] not in ")]}":
        return None

    stack: list[int] = []
    for block_num in range(current_block_number):
        block = document.findBlockByNumber(block_num)
        if not block.isValid():
            continue
        for _idx, ch in iter_code_brackets(block.text()):
            if ch in "([{":
                stack.append(block_num)
            elif stack:
                stack.pop()

    if not stack:
        return None

    opener_block = document.findBlockByNumber(stack[-1])
    if not opener_block.isValid():
        return None

    match = re.match(r"^(\s*)", opener_block.text())
    return match.group(1) if match else ""


def compute_new_indent(
    document,
    block_number: int,
    current_line: str,
    text_before_cursor: str,
    language: Optional[LanguageProfile] = None,
) -> str:
    """Decide the indent string for a new line inserted at the cursor.

    Args:
        document: Active ``QTextDocument``.
        block_number (int): Block index of the current line.
        current_line (str): Full text of the current line.
        text_before_cursor (str): Text from the start of the current line
            up to the cursor.
        language (Optional[LanguageProfile]): Profile whose
            ``extra_indent_trigger`` decides whether Rule 3 fires. ``None``
            (or a profile with no predicate) skips Rule 3 — Rules 1, 2, and
            4 still apply.

    Returns:
        str: Whitespace to insert after the newline.
    """
    bracket_column = find_hanging_indent_column(text_before_cursor)
    if bracket_column >= 0:
        return " " * bracket_column

    closing_dedent = find_closing_bracket_alignment(document, block_number, current_line)
    if closing_dedent is not None:
        return closing_dedent

    indent_match = re.match(r"^(\s*)", current_line)
    current_indent = indent_match.group(1) if indent_match else ""

    if language is not None and language.extra_indent_trigger is not None:
        stripped_before = text_before_cursor.strip()
        if language.extra_indent_trigger(stripped_before):
            return current_indent + "    "
    return current_indent
