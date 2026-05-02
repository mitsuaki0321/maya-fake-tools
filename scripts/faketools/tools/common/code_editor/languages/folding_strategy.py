"""Code-folding strategy framework.

The :class:`FoldingStrategy` base class encapsulates the per-language
algorithm that scans a document and reports which line ranges can be
collapsed. Each language profile carries an instance via
:attr:`LanguageProfile.folding_strategy`; the editor's
:class:`~..ui.code_folding.CodeFoldingManager` calls
:meth:`FoldingStrategy.detect` on every debounced rescan and continues
to own the per-tab fold state.

The split mirrors :class:`IndentResolver`:
    * Strategies are *stateless*  -- one shared instance per language
      can serve every open tab.
    * Per-tab state (which regions are currently folded, debounce
      timer, layout-change notifications) stays in the manager.

The default implementation reports no regions, so a language whose
profile leaves ``folding_strategy=None`` (or sets the base class
directly) gets graceful no-folding behaviour rather than an error.
"""

from __future__ import annotations

from typing import Any


class FoldingStrategy:
    """Detect collapsible regions in a document.

    Subclasses override :meth:`detect` to implement their language's
    folding rules (Python's ``:`` blocks + docstrings + import groups,
    MEL's brace blocks, Markdown's heading hierarchy, ...).
    """

    def detect(self, document: Any) -> dict[int, int]:
        """Return ``{header_block_number: end_block_number}`` for the document.

        Each entry marks a foldable region; the header block is the
        line shown when the region is collapsed, and the end block is
        the last line covered by the fold.

        Args:
            document: Active ``QTextDocument`` (duck-typed; only
                ``begin``/``findBlockByNumber`` style traversal is used
                by typical implementations).

        Returns:
            dict[int, int]: Mapping of header block to end block. The
                base class returns an empty mapping (no folding).
        """
        return {}


__all__ = ["FoldingStrategy"]
