"""
Refactor command layer for the Code Editor.

Currently exposes a single entry point — :func:`find_symbol_references` —
that asks jedi for every in-file usage of the symbol at the cursor. The
UI layer (``ui/editor/rename_overlay.py``) consumes the returned offsets
to drive a VSCode-style inline rename: one undo block, all occurrences.

Kept Qt-free so the rename logic can be exercised without spinning up an
editor widget, and so the same backbone could later serve other refactors
(extract variable, etc.) without dragging the UI into the test path.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from typing import Optional

logger = getLogger(__name__)

try:
    import jedi  # type: ignore

    _JEDI_AVAILABLE = True
except Exception as _exc:  # pragma: no cover — diagnostic path
    jedi = None  # type: ignore[assignment]
    _JEDI_AVAILABLE = False
    logger.info(f"jedi not available, symbol rename disabled: {_exc}")


@dataclass(frozen=True)
class SymbolReference:
    """Absolute character offsets of one occurrence of a symbol.

    ``start`` / ``end`` are positions inside the full document text — the
    form ``QTextCursor.setPosition`` expects — so the UI doesn't have to
    redo (line, column) math when applying the rename.
    """

    start: int
    end: int


def find_symbol_references(
    code: str,
    line: int,
    column: int,
    path: Optional[str] = None,
) -> list[SymbolReference]:
    """Return every in-file reference to the symbol at ``(line, column)``.

    Args:
        code: Full document text.
        line: 1-indexed line (jedi convention).
        column: 0-indexed column within the line.
        path: Optional file path so jedi can resolve sibling imports.

    Returns:
        Offsets sorted by ``start``. Empty when jedi is unavailable, the
        cursor isn't on an identifier, or the symbol has no in-file usages
        (e.g. an imported name whose definition lives elsewhere). Callers
        treat ``[]`` as "no-op" — there is no error path to surface.

    ``scope='file'`` keeps the search inside the current document; we
    intentionally don't follow references into other files in this
    refactor (single-file rename only). ``include_builtins=False`` keeps
    F2 on ``print`` from listing every builtin definition jedi knows.
    """
    if not _JEDI_AVAILABLE or not code:
        return []

    try:
        script = jedi.Script(code=code, path=path)
        names = script.get_references(
            line=line,
            column=column,
            include_builtins=False,
            scope="file",
        )
    except Exception as exc:
        logger.debug(f"jedi.get_references failed at {line}:{column}: {exc}")
        return []

    if not names:
        return []

    # Precompute line-start offsets once so (line, column) → absolute offset
    # is O(1) per reference instead of re-scanning ``code`` each time.
    line_starts = _line_start_offsets(code)
    references: list[SymbolReference] = []
    for name in names:
        ref_line = getattr(name, "line", None)
        ref_column = getattr(name, "column", None)
        ref_name = getattr(name, "name", None) or ""
        if ref_line is None or ref_column is None or not ref_name:
            continue
        if ref_line < 1 or ref_line > len(line_starts):
            continue
        start = line_starts[ref_line - 1] + ref_column
        end = start + len(ref_name)
        if end > len(code):
            continue
        # jedi can report stale positions for synthesised names; sanity-check
        # by reading back the source slice. Mismatches are silently dropped
        # rather than mis-renamed.
        if code[start:end] != ref_name:
            logger.debug(f"reference text mismatch at {ref_line}:{ref_column} ({ref_name!r} vs {code[start:end]!r})")
            continue
        references.append(SymbolReference(start=start, end=end))

    references.sort(key=lambda r: r.start)
    return references


def _line_start_offsets(code: str) -> list[int]:
    """Return a list where index ``i`` is the absolute offset of line ``i+1``.

    Built once per :func:`find_symbol_references` call. Each ``\\n`` contributes
    one entry pointing at the character immediately after it.
    """
    starts = [0]
    for idx, ch in enumerate(code):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


__all__ = ["SymbolReference", "find_symbol_references"]
