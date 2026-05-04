"""Python indent resolver.

Adds Rule 0 to the bracket-based default: a non-comment line ending in
``:`` (``def`` / ``class`` / ``if`` / ``for`` / ``while`` / ``try`` /
...) opens a 4-space block. Comment lines starting with ``#`` are
suppressed so a trailing colon inside a comment doesn't trigger the
extra indent.
"""

from __future__ import annotations

from typing import Optional

from ..indent_resolver import IndentResolver


class PythonIndentResolver(IndentResolver):
    """Add Rule 0: a non-comment line ending in ``:`` opens a 4-space block."""

    def _indent_on_enter(self, *, text_before_cursor: str, current_indent: str, **_) -> Optional[str]:
        stripped = text_before_cursor.strip()
        if stripped.startswith("#"):
            return None
        if stripped.endswith(":"):
            return current_indent + "    "
        return None


__all__ = ["PythonIndentResolver"]
