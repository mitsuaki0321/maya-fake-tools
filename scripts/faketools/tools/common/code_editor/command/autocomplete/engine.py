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


# Names that live in the bundled Maya stubs. When stubs are registered we
# filter these out of the ``namespaces`` dict handed to ``jedi.Interpreter``
# so jedi resolves them statically via ``added_sys_path`` instead — the
# live ``maya.cmds`` module is lazy-loaded and its ``dir()`` output is
# largely empty until a command has been called at least once.
_STUB_BACKED_NAMES = frozenset({"cmds", "maya", "om", "om2", "OpenMaya"})


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

    ``extra_paths`` lets the caller inject additional ``sys.path`` entries
    that jedi will search when resolving imports — used to point jedi at
    the Maya-version-specific stub package from ``stub_generator`` so that
    ``cmds.polyCube(|)`` can surface its flag names as kwargs.
    """

    def __init__(self, max_file_bytes: int = _MAX_FILE_BYTES):
        self.max_file_bytes = max_file_bytes
        self._extra_paths: list[str] = []

    def set_extra_paths(self, paths: Sequence[str]) -> None:
        """Replace the extra sys.path list used when building jedi ``Project``s.

        Safe to call at any time; existing cached scripts aren't affected
        (a fresh Interpreter/Script is built per ``complete()`` call).
        """
        self._extra_paths = [str(p) for p in paths if p]

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

        When stubs are registered (via :meth:`set_extra_paths`), we build a
        :class:`jedi.Project` that surfaces them on ``sys.path`` and strip
        the Maya module aliases out of the namespaces so jedi resolves
        ``cmds.`` against the rich stub instead of the lazy-loaded live
        object (whose ``dir()`` returns little before commands are called).
        """
        project = self._build_project()
        effective_namespaces = self._namespaces_for_jedi(namespaces)
        if effective_namespaces:
            return jedi.Interpreter(code, namespaces=list(effective_namespaces), path=path, project=project)
        return jedi.Script(code=code, path=path, project=project)

    def _namespaces_for_jedi(self, namespaces: Optional[Sequence[dict]]) -> Optional[Sequence[dict]]:
        """Strip stub-backed module aliases from the live namespaces.

        Only runs when stubs are actually registered; otherwise the caller
        gets ``exec_globals`` back untouched so in-Maya introspection of
        user variables keeps working.
        """
        if not namespaces or not self._extra_paths:
            return namespaces
        cleaned = []
        for ns in namespaces:
            filtered = {k: v for k, v in ns.items() if k not in _STUB_BACKED_NAMES}
            cleaned.append(filtered)
        return cleaned

    def _build_project(self):
        """Construct a ``jedi.Project`` that includes our stub paths (or ``None``)."""
        if not self._extra_paths:
            return None
        # ``path`` must point somewhere; "." is jedi's convention for "use CWD"
        # when the caller doesn't have a meaningful project root.
        try:
            return jedi.Project(path=".", added_sys_path=list(self._extra_paths))
        except Exception as exc:
            logger.debug(f"jedi.Project construction failed: {exc}")
            return None


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
