"""
Code folding manager for the Python code editor.
Provides indent-based fold detection and fold/unfold operations.
"""

from logging import getLogger

from .....lib_ui.qt_compat import QTimer

logger = getLogger(__name__)


class CodeFoldingManager:
    """Manages code folding state and operations for a PythonEditor instance.

    Fold regions are detected by Python indent structure: any line ending with ':'
    whose subsequent lines are indented deeper forms a foldable region.
    """

    # Debounce delay for fold region recalculation (ms)
    _UPDATE_DELAY_MS = 300

    def __init__(self, editor):
        self.editor = editor

        # {header_block_number: end_block_number} — all detected foldable regions
        self._fold_regions = {}

        # Set of block numbers that are currently folded
        self._folded_headers = set()

        # Debounce timer for recalculation
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_update)

        # Connect to document changes
        self.editor.document().contentsChanged.connect(self._schedule_update)

        # Initial calculation
        QTimer.singleShot(0, self._do_update)

    # ------------------------------------------------------------------
    # Public API — queries
    # ------------------------------------------------------------------

    def is_fold_header(self, block_number):
        """Return True if the given block is a foldable region header."""
        return block_number in self._fold_regions

    def is_folded(self, block_number):
        """Return True if the given fold header is currently folded."""
        return block_number in self._folded_headers

    def get_fold_range(self, block_number):
        """Return (start, end) block numbers for a fold region, or None.

        Args:
            block_number (int): The fold header block number.

        Returns:
            tuple[int, int] | None: (header, last_child) or None if not a fold header.
        """
        if block_number in self._fold_regions:
            return (block_number, self._fold_regions[block_number])
        return None

    def get_fold_regions(self):
        """Return a copy of the current fold regions dict."""
        return dict(self._fold_regions)

    # ------------------------------------------------------------------
    # Public API — fold operations
    # ------------------------------------------------------------------

    def toggle_fold(self, block_number):
        """Toggle fold state for the given fold header."""
        if block_number not in self._fold_regions:
            return
        if block_number in self._folded_headers:
            self.unfold(block_number)
        else:
            self.fold(block_number)

    def fold(self, block_number):
        """Fold (collapse) a region."""
        if block_number not in self._fold_regions:
            return
        if block_number in self._folded_headers:
            return  # already folded

        end = self._fold_regions[block_number]
        doc = self.editor.document()

        for i in range(block_number + 1, end + 1):
            block = doc.findBlockByNumber(i)
            if block.isValid():
                block.setVisible(False)

        self._folded_headers.add(block_number)
        self._notify_layout_changed()

    def unfold(self, block_number):
        """Unfold (expand) a region."""
        if block_number not in self._folded_headers:
            return

        end = self._fold_regions.get(block_number)
        if end is None:
            self._folded_headers.discard(block_number)
            return

        doc = self.editor.document()

        for i in range(block_number + 1, end + 1):
            block = doc.findBlockByNumber(i)
            if block.isValid():
                block.setVisible(True)

        self._folded_headers.discard(block_number)

        # Re-fold any nested regions that are still in _folded_headers
        for nested_header in sorted(self._folded_headers):
            if nested_header <= block_number or nested_header > end:
                continue
            nested_end = self._fold_regions.get(nested_header)
            if nested_end is None:
                continue
            for i in range(nested_header + 1, min(nested_end, end) + 1):
                block = doc.findBlockByNumber(i)
                if block.isValid():
                    block.setVisible(False)

        self._notify_layout_changed()

    def toggle_fold_recursive(self, block_number):
        """Toggle fold state recursively for a region and all nested regions."""
        if block_number not in self._fold_regions:
            return
        if block_number in self._folded_headers:
            self.unfold_recursive(block_number)
        else:
            self.fold_recursive(block_number)

    def fold_recursive(self, block_number):
        """Fold a region and all nested regions within it."""
        if block_number not in self._fold_regions:
            return
        end = self._fold_regions[block_number]
        # Fold nested regions first (deepest first), then the parent
        for header in sorted(self._fold_regions.keys()):
            if block_number < header <= end and header not in self._folded_headers:
                self.fold(header)
        if block_number not in self._folded_headers:
            self.fold(block_number)

    def unfold_recursive(self, block_number):
        """Unfold a region and all nested regions within it."""
        if block_number not in self._folded_headers:
            return
        end = self._fold_regions.get(block_number)
        if end is None:
            return
        # Unfold parent first, then nested
        self.unfold(block_number)
        for header in sorted(self._folded_headers.copy()):
            if block_number < header <= end:
                self.unfold(header)

    def unfold_containing(self, block_number):
        """Unfold any region that contains the given block number.

        Used by find/replace and multi-cursor when a match lands inside a folded region.
        """
        for header in sorted(self._folded_headers):
            end = self._fold_regions.get(header)
            if end is None:
                continue
            if header < block_number <= end:
                self.unfold(header)
                return True
        return False

    def fold_all(self):
        """Fold all detected regions (outermost only to avoid conflicts)."""
        for header in sorted(self._fold_regions.keys()):
            # Skip if already inside a folded region
            already_hidden = False
            for h in self._folded_headers:
                r = self._fold_regions.get(h)
                if r and h < header <= r:
                    already_hidden = True
                    break
            if not already_hidden:
                self.fold(header)

    def unfold_all(self):
        """Unfold all folded regions."""
        doc = self.editor.document()
        block = doc.begin()
        while block.isValid():
            if not block.isVisible():
                block.setVisible(True)
            block = block.next()
        self._folded_headers.clear()
        self._notify_layout_changed()

    # ------------------------------------------------------------------
    # Public API — placeholder text
    # ------------------------------------------------------------------

    def get_placeholder_text(self, block_number):
        """Return placeholder summary for a folded region (e.g. '...')."""
        if block_number not in self._folded_headers:
            return ""
        end = self._fold_regions.get(block_number, block_number)
        line_count = end - block_number
        return f" ... ({line_count} lines)"

    # ------------------------------------------------------------------
    # Fold region detection
    # ------------------------------------------------------------------

    def _schedule_update(self):
        """Schedule a debounced fold region recalculation."""
        self._update_timer.start(self._UPDATE_DELAY_MS)

    def _do_update(self):
        """Recalculate fold regions from document content."""
        new_regions = self._detect_fold_regions()

        # Prune folded headers that no longer exist as valid fold regions
        stale = self._folded_headers - set(new_regions.keys())
        if stale:
            doc = self.editor.document()
            for header in stale:
                old_end = self._fold_regions.get(header)
                if old_end is not None:
                    for i in range(header + 1, old_end + 1):
                        block = doc.findBlockByNumber(i)
                        if block.isValid() and not block.isVisible():
                            block.setVisible(True)
            self._folded_headers -= stale
            self._notify_layout_changed()

        # Update regions whose end has changed while still folded
        for header in list(self._folded_headers):
            old_end = self._fold_regions.get(header)
            new_end = new_regions.get(header)
            if new_end is None:
                continue
            if old_end != new_end:
                # Re-apply fold with new range
                doc = self.editor.document()
                # Show blocks that are no longer in range
                if old_end is not None:
                    for i in range(min(old_end, new_end) + 1, max(old_end, new_end) + 1):
                        block = doc.findBlockByNumber(i)
                        if block.isValid():
                            block.setVisible(i > new_end)
                # Hide blocks that are newly in range
                for i in range(header + 1, new_end + 1):
                    block = doc.findBlockByNumber(i)
                    if block.isValid():
                        block.setVisible(False)

        self._fold_regions = new_regions

    def _detect_fold_regions(self):
        """Walk document blocks to detect Python fold regions.

        Detects three types of foldable regions:
        1. Colon blocks (def, class, if, for, while, try, with, etc.)
        2. Multi-line triple-quoted strings (docstrings)
        3. Consecutive import statements

        Returns:
            dict[int, int]: {header_block_number: end_block_number}
        """
        regions = {}
        doc = self.editor.document()
        block = doc.begin()
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
                    # Count occurrences of the triple quote in this line
                    count = lstripped.count(triple)
                    if count == 1:
                        # Opening triple quote without close on same line → find closing
                        end_num = self._find_triple_quote_end(block_num, triple)
                        if end_num > block_num:
                            regions[block_num] = end_num
                            skip_until = end_num  # Skip closing line

                # --- Colon block detection ---
                code_part = self._strip_comment(stripped)
                if code_part.endswith(":"):
                    header_indent = len(text) - len(text.lstrip())
                    end_num = self._find_fold_end(block_num, header_indent)
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

    def _find_triple_quote_end(self, start_num, triple):
        """Find the closing line of a multi-line triple-quoted string.

        Args:
            start_num (int): Block number of the opening triple quote.
            triple (str): The triple quote style ('\"\"\"' or \"'''\").

        Returns:
            int: Block number of the closing line, or start_num if not found.
        """
        doc = self.editor.document()
        block = doc.findBlockByNumber(start_num + 1)

        while block.isValid():
            if triple in block.text():
                return block.blockNumber()
            block = block.next()

        return start_num

    def _find_fold_end(self, header_num, header_indent):
        """Find the last block belonging to a fold region.

        Args:
            header_num (int): Block number of the fold header.
            header_indent (int): Indent level (in spaces) of the header.

        Returns:
            int: Block number of the last line in the fold region.
        """
        doc = self.editor.document()
        last_content = header_num
        block = doc.findBlockByNumber(header_num + 1)

        while block.isValid():
            text = block.text()
            if text.strip():  # Non-empty line
                indent = len(text) - len(text.lstrip())
                if indent <= header_indent:
                    break  # Same or shallower indent → end of region
                last_content = block.blockNumber()
            block = block.next()

        return last_content

    @staticmethod
    def _strip_comment(line):
        """Remove trailing comment from a line, respecting strings.

        Args:
            line (str): Source line (already rstripped).

        Returns:
            str: Line with trailing comment removed, rstripped.
        """
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _notify_layout_changed(self):
        """Notify the editor that block layout has changed."""
        doc = self.editor.document()
        doc.markContentsDirty(0, doc.characterCount())
        self.editor.updateGeometry()
        self.editor.viewport().update()
        self.editor.update_line_number_area_width(0)
        if hasattr(self.editor, "line_number_area"):
            self.editor.line_number_area.update()
