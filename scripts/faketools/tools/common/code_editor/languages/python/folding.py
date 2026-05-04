"""Python folding strategy.

Detects three kinds of foldable region in a Python document:

1. **Colon blocks** -- ``def`` / ``class`` / ``if`` / ``for`` / ``while``
   / ``try`` / ``with`` / ... whose subsequent lines are indented
   deeper than the header.
2. **Multi-line triple-quoted strings** (typically docstrings).
3. **Consecutive ``import`` / ``from`` statements** uninterrupted by
   blank lines.

Lifted out of :class:`~..ui.code_folding.CodeFoldingManager` so each
language owns its detection algorithm. The manager keeps the per-tab
fold state and lifecycle.
"""

from __future__ import annotations

from typing import Any

from ..folding_strategy import FoldingStrategy


class PythonFoldingStrategy(FoldingStrategy):
    """Indent + triple-quote + import-group detector for Python."""

    def detect(self, document: Any) -> dict[int, int]:
        regions: dict[int, int] = {}
        block = document.begin()
        import_start = -1  # Track start of consecutive import block
        import_end = -1
        skip_until = -1  # Skip blocks inside a detected triple-quote region

        while block.isValid():
            text = block.text()
            stripped = text.rstrip()
            block_num = block.blockNumber()

            # Skip lines inside an already-detected triple-quote region
            if block_num <= skip_until:
                block = block.next()
                continue

            if stripped:
                lstripped = stripped.lstrip()

                # --- Triple-quote docstring detection ---
                triple = None
                if '"""' in lstripped:
                    triple = '"""'
                elif "'''" in lstripped:
                    triple = "'''"

                if triple:
                    count = lstripped.count(triple)
                    if count == 1:
                        # Opening triple quote without close on same line.
                        end_num = self._find_triple_quote_end(document, block_num, triple)
                        if end_num > block_num:
                            regions[block_num] = end_num
                            skip_until = end_num

                # --- Colon block detection ---
                code_part = self._strip_comment(stripped)
                if code_part.endswith(":"):
                    header_indent = len(text) - len(text.lstrip())
                    end_num = self._find_fold_end(document, block_num, header_indent)
                    if end_num > block_num:
                        regions[block_num] = end_num

                # --- Consecutive import detection ---
                if lstripped.startswith("import ") or lstripped.startswith("from "):
                    if import_start < 0:
                        import_start = block_num
                    import_end = block_num
                else:
                    # Non-import line: flush any accumulated import block
                    if import_start >= 0 and import_end > import_start:
                        regions[import_start] = import_end
                    import_start = -1
                    import_end = -1
            else:
                # Empty line: flush import block (empty lines break import groups)
                if import_start >= 0 and import_end > import_start:
                    regions[import_start] = import_end
                import_start = -1
                import_end = -1

            block = block.next()

        # Flush any remaining import block at end of document
        if import_start >= 0 and import_end > import_start:
            regions[import_start] = import_end

        return regions

    @staticmethod
    def _find_triple_quote_end(document: Any, start_num: int, triple: str) -> int:
        """Find the closing line of a multi-line triple-quoted string.

        Returns ``start_num`` if no closer is found.
        """
        block = document.findBlockByNumber(start_num + 1)
        while block.isValid():
            if triple in block.text():
                return block.blockNumber()
            block = block.next()
        return start_num

    @staticmethod
    def _find_fold_end(document: Any, header_num: int, header_indent: int) -> int:
        """Find the last block belonging to a fold region.

        Walks forward until a non-empty line at indent ``<= header_indent``
        ends the region.
        """
        last_content = header_num
        block = document.findBlockByNumber(header_num + 1)
        while block.isValid():
            text = block.text()
            if text.strip():
                indent = len(text) - len(text.lstrip())
                if indent <= header_indent:
                    break
                last_content = block.blockNumber()
            block = block.next()
        return last_content

    @staticmethod
    def _strip_comment(line: str) -> str:
        """Remove trailing ``#`` comment from a line, respecting strings."""
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                return line[:i].rstrip()
            i += 1
        return line


__all__ = ["PythonFoldingStrategy"]
