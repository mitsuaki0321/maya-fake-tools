"""
Thin adapter over ``jedi`` for the Code Editor.

Everything jedi-specific lives here so the rest of the tree can treat
completion as a pure ``(code, cursor, namespaces) -> list[CompletionItem]``
function. If jedi is not installed the engine becomes a no-op: the ``complete``
and ``signatures`` methods return empty lists and the editor continues to
work, just without completion popups.
"""

from __future__ import annotations

from collections.abc import Sequence
from logging import getLogger
from typing import Any, Optional

from .types import CompletionItem

logger = getLogger(__name__)

try:
    import jedi  # type: ignore

    JEDI_AVAILABLE = True
except Exception as _exc:  # pragma: no cover — diagnostic path
    jedi = None  # type: ignore[assignment]
    JEDI_AVAILABLE = False
    logger.info(f"jedi not available, autocomplete disabled: {_exc}")


# Size cap for source files fed to jedi. Above this, parse times dominate the
# debounce budget — return an empty list instead of freezing the editor.
_MAX_FILE_BYTES = 500 * 1024


# A "category priority" for sort order when the popup mixes types. Lower is
# higher on-screen. Tunable without touching the UI.
_TYPE_RANK = {
    "param": 0,
    "keyword": 1,
    "property": 2,
    "function": 3,
    "method": 3,
    "class": 4,
    "module": 5,
    "instance": 6,
    "statement": 7,
    "": 8,
}


class JediEngine:
    """Stateless-ish wrapper around ``jedi.Interpreter`` / ``jedi.Script``.

    The engine holds no mutable state — every call re-creates a fresh jedi
    Script/Interpreter. jedi maintains its own parse cache internally keyed by
    source hash, so repeated identical calls are cheap. A single engine
    instance can therefore be safely shared between editor tabs and threads.
    """

    def __init__(self, max_file_bytes: int = _MAX_FILE_BYTES):
        self.max_file_bytes = max_file_bytes

    @property
    def available(self) -> bool:
        """True iff jedi was importable at module load time."""
        return JEDI_AVAILABLE

    def complete(
        self,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]] = None,
        path: Optional[str] = None,
        max_items: int = 50,
    ) -> list[CompletionItem]:
        """Compute completions at ``(line, column)`` in ``code``.

        Args:
            code:       Full document text.
            line:       1-indexed line (jedi convention).
            column:     0-indexed column within the line.
            namespaces: Live dicts (typically ``[exec_globals]``) used by
                        ``jedi.Interpreter`` to introspect runtime values —
                        this is what makes ``cmds.`` and ``np.`` work
                        without touching the filesystem.
            path:       Optional file path so jedi can resolve sibling
                        imports. Safe to omit.
            max_items:  Hard cap on returned items to keep the popup snappy.

        Returns ``[]`` when jedi is unavailable or the source is too large.
        Errors inside jedi are swallowed and logged at debug level so one
        malformed file can't take the editor down.
        """
        if not JEDI_AVAILABLE:
            return []
        if not code or len(code) > self.max_file_bytes:
            return []

        try:
            script = self._make_script(code, namespaces, path)
            completions = script.complete(line, column)
        except Exception as exc:
            logger.debug(f"jedi.complete failed at {line}:{column}: {exc}")
            return []

        items = [CompletionItem.from_jedi(c) for c in completions]
        items.sort(key=_completion_sort_key)
        if len(items) > max_items:
            items = items[:max_items]
        return items

    def signatures(
        self,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]] = None,
        path: Optional[str] = None,
    ) -> list[str]:
        """Return callable signatures near the cursor as plain display strings.

        Used for the parameter-hint popup (optional Phase B5). Each string is
        the function name with its parameter list — e.g. ``polyCube(width,
        height, ...)``. Returns ``[]`` on any error or when jedi is missing.
        """
        if not JEDI_AVAILABLE:
            return []
        if not code or len(code) > self.max_file_bytes:
            return []

        try:
            script = self._make_script(code, namespaces, path)
            sigs = script.get_signatures(line, column)
        except Exception as exc:
            logger.debug(f"jedi.get_signatures failed at {line}:{column}: {exc}")
            return []

        return [_format_signature(sig) for sig in sigs]

    # -------------------- internals --------------------

    def _make_script(
        self,
        code: str,
        namespaces: Optional[Sequence[dict]],
        path: Optional[str],
    ) -> Any:
        """Return a ``jedi.Interpreter`` when we have live namespaces, else a ``Script``.

        ``Interpreter`` is strictly more capable (it can introspect live
        objects), but requires a namespace list. Falling back to ``Script``
        keeps things working for static-only completion in non-Maya contexts.
        """
        if namespaces:
            return jedi.Interpreter(code, namespaces=list(namespaces), path=path)
        return jedi.Script(code=code, path=path)


def _completion_sort_key(item: CompletionItem) -> tuple:
    """Sort: named parameters / keywords first, then by type rank, then alpha.

    jedi's default order isn't always ideal; this nudges the most useful
    items (``keyword`` like ``if``, ``param`` like kwarg names) to the top.
    """
    rank = _TYPE_RANK.get(item.type, _TYPE_RANK[""])
    # Hide dunders unless explicitly typed (they're noisy in autocomplete).
    dunder = 1 if item.name.startswith("_") else 0
    return (dunder, rank, item.name.lower())


def _format_signature(sig) -> str:
    """Stringify a jedi ``Signature`` as ``name(param1, param2, ...)``."""
    try:
        params = ", ".join(p.to_string() for p in sig.params)
    except Exception:
        params = ""
    return f"{sig.name}({params})"


__all__ = ["JEDI_AVAILABLE", "JediEngine"]
