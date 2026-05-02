"""Auto-indent resolver framework.

The :class:`IndentResolver` base class encapsulates the four-rule
auto-indent algorithm so each language profile can plug in its own
behaviour by subclassing rather than passing one-off callbacks. The
default implementation handles bracket-based languages (hanging indent,
closing bracket alignment, default carry-over); language subclasses
override :meth:`_indent_on_enter` for Rule 0 (block opener detection),
and may override :meth:`_iter_code_brackets` or any of the rule helpers
when their syntax differs from the Python-flavoured default.

Lives under ``languages/`` rather than ``ui/`` so that
``languages/python.py`` / ``languages/mel.py`` can subclass it without
creating an import cycle (the editor's auto-indent entry point in
``ui/auto_indent.py`` imports this module too, and that direction is
fine).
"""

from __future__ import annotations

from collections.abc import Iterator
import re
from typing import Any, Optional


class IndentResolver:
    """Compute the indent for a new line inserted on Enter.

    Rule order applied by :meth:`compute`:

    0. Language predicate via :meth:`_indent_on_enter` -- returning a
       string short-circuits the chain. The default hook returns
       ``None`` so the base class behaves like a bracket-only language.
    1. **Hanging indent** -- if the line before the cursor has an
       unclosed opening bracket, align to the column right after that
       bracket.
    2. **Closing bracket alignment** -- if the current line begins
       (after whitespace) with ``)``/``]``/``}``, find the matching
       opener and reuse the leading whitespace of its line.
    3. **Default** -- reuse the current line's leading whitespace.

    Subclasses typically only override :meth:`_indent_on_enter`. Override
    :meth:`_iter_code_brackets` if the language uses different comment
    or string syntax than Python (e.g. MEL ``//`` instead of ``#``); the
    other helpers compose on top of it. Override :meth:`compute` itself
    only when a language needs an entirely different algorithm
    (e.g. Markdown's structural rules).
    """

    # ----- Public entry point -----

    def compute(self, document: Any, block_number: int, current_line: str, text_before_cursor: str) -> str:
        """Return the indent string for the line about to be inserted.

        Args:
            document: Active ``QTextDocument`` (duck-typed; only
                ``findBlockByNumber`` is invoked here).
            block_number (int): Block index of the line being split.
            current_line (str): Full text of the line being split.
            text_before_cursor (str): Text on that line up to the cursor.

        Returns:
            str: Whitespace (or, for bullet-style languages, leading
                prefix) to insert immediately after the newline.
        """
        current_indent = self._current_indent(current_line)

        result = self._indent_on_enter(
            document=document,
            block_number=block_number,
            current_line=current_line,
            text_before_cursor=text_before_cursor,
            current_indent=current_indent,
        )
        if result is not None:
            return result

        bracket_column = self._find_hanging_indent_column(text_before_cursor)
        if bracket_column >= 0:
            return " " * bracket_column

        closing_dedent = self._find_closing_bracket_alignment(document, block_number, current_line)
        if closing_dedent is not None:
            return closing_dedent

        return current_indent

    # ----- Hook for language subclasses -----

    def _indent_on_enter(self, **kwargs: Any) -> Optional[str]:
        """Compute a language-specific indent for the new line.

        Args (all keyword-only -- subclasses can ignore unused names with
        a trailing ``**_``):
            document: Active ``QTextDocument``.
            block_number (int): Block index of the line being split.
            current_line (str): Full text of the line being split.
            text_before_cursor (str): Text on that line up to the cursor.
            current_indent (str): Pre-computed leading whitespace of
                ``current_line``.

        Returns:
            Optional[str]: Full indent for the new line, or ``None`` to
                fall through to Rules 1-4.
        """
        return None

    # ----- Generic helpers (override per language as needed) -----

    @staticmethod
    def _current_indent(line: str) -> str:
        """Return the leading whitespace of ``line``."""
        match = re.match(r"^(\s*)", line)
        return match.group(1) if match else ""

    def _iter_code_brackets(self, text: str) -> Iterator[tuple[int, str]]:
        """Yield ``(index, char)`` for bracket characters in ``text``.

        The default implementation skips Python-style ``#`` comments and
        single / double / triple-quoted string literals so brackets
        inside them are not reported. Languages with different comment
        or string syntax (MEL ``//`` and ``/* */``, shell ``#``, etc.)
        should override this method.
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

    def _find_hanging_indent_column(self, text_before_cursor: str) -> int:
        """Find the column right after the last unclosed opening bracket.

        Returns ``-1`` when there is no unclosed bracket on the line.
        """
        stack: list[int] = []
        for idx, ch in self._iter_code_brackets(text_before_cursor):
            if ch in "([{":
                stack.append(idx)
            elif stack:
                stack.pop()
        return -1 if not stack else stack[-1] + 1

    def _find_closing_bracket_alignment(self, document: Any, current_block_number: int, current_line: str) -> Optional[str]:
        """Return the indent of the line containing the matching opener.

        Applies when ``current_line`` begins (after whitespace) with
        ``)`` / ``]`` / ``}``. Scans preceding blocks of ``document``
        for the matching opener and returns the leading whitespace of
        that block.
        """
        stripped = current_line.lstrip()
        if not stripped or stripped[0] not in ")]}":
            return None

        stack: list[int] = []
        for block_num in range(current_block_number):
            block = document.findBlockByNumber(block_num)
            if not block.isValid():
                continue
            for _idx, ch in self._iter_code_brackets(block.text()):
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


__all__ = ["IndentResolver"]
