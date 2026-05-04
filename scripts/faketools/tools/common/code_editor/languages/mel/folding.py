"""MEL folding strategy.

Brace-based detection: each ``{`` opens a region whose end is the line
**before** the matching ``}``, so the closing brace remains visible
when the region is collapsed -- VSCode-style folding where both
``if (x) {`` and ``}`` are shown.

Skips ``//`` line comments, ``/* */`` block comments (multi-line) and
``"..."`` string literals so braces inside them do not influence the
brace stack. Block-comment state threads through the per-line scanner
because ``/* ... */`` may span multiple lines.
"""

from __future__ import annotations

from typing import Any

from ..folding_strategy import FoldingStrategy


class MelFoldingStrategy(FoldingStrategy):
    """Brace-based fold detector for MEL."""

    def detect(self, document: Any) -> dict[int, int]:
        regions: dict[int, int] = {}
        stack: list[int] = []  # block numbers where '{' was pushed
        in_block_comment = False

        block = document.begin()
        while block.isValid():
            in_block_comment = self._scan_line(
                block.text(),
                block.blockNumber(),
                stack,
                regions,
                in_block_comment,
            )
            block = block.next()

        return regions

    @staticmethod
    def _scan_line(
        text: str,
        block_num: int,
        stack: list[int],
        regions: dict[int, int],
        in_block_comment: bool,
    ) -> bool:
        """Scan one line, mutating ``stack`` / ``regions``.

        Returns the new ``in_block_comment`` state to thread into the
        next line.
        """
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]

            if in_block_comment:
                # Look for the */ closer; everything else is comment.
                if ch == "*" and i + 1 < n and text[i + 1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            # // line comment -- rest of line is non-code.
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                return in_block_comment

            # /* block comment opener.
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                in_block_comment = True
                i += 2
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

            if ch == "{":
                stack.append(block_num)
            elif ch == "}" and stack:
                open_block_num = stack.pop()
                # End at the line BEFORE the closer so the '}' stays
                # visible after fold (VSCode behaviour). Skip empty
                # ranges where { and } are adjacent or on the same
                # line -- nothing to hide there.
                end_line = block_num - 1
                if end_line > open_block_num:
                    regions[open_block_num] = end_line
            i += 1

        return in_block_comment


__all__ = ["MelFoldingStrategy"]
