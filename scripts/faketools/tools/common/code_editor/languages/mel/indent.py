"""MEL indent resolver.

Adds Rule 0 to the bracket-based default: a line ending in ``{`` (any
brace block) or ``:`` (``case``/``default`` inside ``switch``) opens a
4-space block. Without Rule 0, the bracket-based Rule 1 would line-wrap
to the column right after ``{`` -- not what MEL code conventionally
looks like.

Also overrides :meth:`_iter_code_brackets` so the bracket scanner skips
MEL ``//`` line comments, ``/* ... */`` block comments and ``"..."``
string literals; otherwise a commented-out ``{`` would leak into Rule 1
/ Rule 2 stacks and produce nonsense indent.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

from ..indent_resolver import IndentResolver


class MelIndentResolver(IndentResolver):
    """Brace- and colon-aware indent resolver for MEL."""

    def _indent_on_enter(self, *, text_before_cursor: str, current_indent: str, **_) -> Optional[str]:
        stripped = text_before_cursor.strip()
        if stripped.startswith("//"):
            return None
        if stripped.endswith("{") or stripped.endswith(":"):
            return current_indent + "    "
        return None

    def _iter_code_brackets(self, text: str) -> Iterator[tuple[int, str]]:
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            # // line comment -- nothing on the rest of the line is code.
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                return
            # /* block comment */ -- skip to closer (or rest of line).
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                end = text.find("*/", i + 2)
                if end < 0:
                    return
                i = end + 2
                continue
            # "..." string with backslash escapes.
            if ch == '"':
                i += 1
                while i < n:
                    if text[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if text[i] == '"':
                        i += 1
                        break
                    i += 1
                continue
            if ch in "([{)]}":
                yield i, ch
            i += 1


__all__ = ["MelIndentResolver"]
