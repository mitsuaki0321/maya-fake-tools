"""Code folding state manager for the editor.

Owns the per-tab fold state (which regions are detected, which are
currently collapsed, debounce timer, layout-change notifications) and
delegates the per-language detection to
:attr:`LanguageProfile.folding_strategy`. Languages whose profile leaves
``folding_strategy=None`` get graceful no-folding behaviour -- the
manager keeps an empty region map and every public op short-circuits.
"""

from logging import getLogger

from .....lib_ui.qt_compat import QTimer

logger = getLogger(__name__)


class CodeFoldingManager:
    """Manages code folding state and operations for an editor instance.

    Detection of foldable regions is delegated to
    :attr:`LanguageProfile.folding_strategy` (a :class:`FoldingStrategy`
    subclass). The manager owns the per-tab state -- which regions
    exist, which are folded, debouncing, and layout notifications.
    """

    # Debounce delay for fold region recalculation (ms)
    _UPDATE_DELAY_MS = 300

    def __init__(self, editor):
        self.editor = editor

        # {header_block_number: end_block_number} — all detected foldable regions
        self._fold_regions = {}

        # Set of block numbers that are currently folded
        self._folded_headers = set()

        # Debounce timer for recalculation. Parent to the editor so Qt destroys
        # the timer when the editor's C++ object dies — otherwise a pending fire
        # can reach _do_update after the editor is gone and raise RuntimeError.
        self._update_timer = QTimer(self.editor)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_update)

        # Listen to ``contentsChange`` (positional) rather than ``contentsChanged``:
        # the no-args variant also fires when QSyntaxHighlighter applies formats,
        # which during file load can repeatedly reset our 300 ms debounce so
        # ``_do_update`` never gets a quiet window. Filtering ``removed == 0 and
        # added == 0`` lets format-only notifications through without restarting
        # the timer, the same pattern ``code_editor._on_contents_change`` uses.
        self.editor.document().contentsChange.connect(self._on_contents_change)

        # Initial calculation — use the editor-parented timer so it's cancelled
        # if the editor is closed before the first update fires.
        self._update_timer.start(0)

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

    def _on_contents_change(self, position: int, removed: int, added: int):
        """Schedule a debounced fold rescan only on real content edits.

        Filters out format-only notifications (the syntax highlighter's
        ``setFormat`` calls fire with ``removed == 0 and added == 0``); without
        this, the highlighter's own rehighlight pass during file load resets
        the 300 ms debounce on every block, starving ``_do_update``.
        """
        if removed == 0 and added == 0:
            return
        self._update_timer.start(self._UPDATE_DELAY_MS)

    def _do_update(self):
        """Recalculate fold regions by delegating to the language's strategy."""
        strategy = self.editor.language.folding_strategy
        if strategy is None:
            # Language without a folding strategy — drop any stale regions and exit.
            if self._fold_regions or self._folded_headers:
                self._fold_regions = {}
                self._folded_headers.clear()
            return

        try:
            new_regions = strategy.detect(self.editor.document())
        except RuntimeError:
            # Editor's C++ object was deleted while a recalculation was pending.
            # Nothing to update — drop the stale state so later callbacks exit fast.
            self._fold_regions = {}
            self._folded_headers.clear()
            return

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
