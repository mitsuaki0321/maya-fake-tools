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
import re
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


# Top-level names that must be resolved through the bundled Maya stubs rather
# than live introspection. ``maya.cmds`` is the problem child: it's in
# ``sys.modules`` as soon as Maya starts, but ``dir(cmds)`` stays nearly empty
# until a command is actually called (lazy loading), and jedi.Interpreter's
# ``MixedObject`` layer ends up favouring that empty live side over the stub.
# Routing these names through ``jedi.Script`` (which ignores sys.modules)
# forces the stub to win. Every other name — user variables, ``eST3``, etc. —
# goes through ``jedi.Interpreter`` so live ``dir()`` output drives the popup.
_MAYA_STUB_ROOTS = frozenset({"maya", "cmds", "OpenMaya", "om", "om2"})


# Regex to pick the first identifier out of a dotted chain. Used after we've
# lopped off the text inside any unmatched trailing ``(`` so the callee is
# what we're matching, not the argument being typed.
_CHAIN_ROOT_RE = re.compile(r"([A-Za-z_]\w*)(?:\.[A-Za-z_]\w*)*\.?\w*$")


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
            script = self._make_script(code, line, column, namespaces, path)
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
            script = self._make_script(code, line, column, namespaces, path)
            sigs = script.get_signatures(line, column)
        except Exception as exc:
            logger.debug(f"jedi.get_signatures failed at {line}:{column}: {exc}")
            return []

        return [_format_signature(sig) for sig in sigs]

    # -------------------- internals --------------------

    def _make_script(
        self,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]],
        path: Optional[str],
    ) -> Any:
        """Return the right jedi driver for the current cursor position.

        Two modes, picked per call based on what the user is completing:

        1. **Maya-rooted expression** (cursor under ``cmds.`` / ``OpenMaya.`` /
           their common aliases): use :class:`jedi.Script`. ``Script`` resolves
           imports purely through ``sys.path`` / the ``Project`` sys_path we
           build and ignores ``sys.modules``, so our bundled stub for
           ``maya.cmds`` wins. ``Interpreter`` here regresses to the empty-
           ``dir`` failure described in ``_MAYA_STUB_ROOTS``.
        2. **Everything else**: :class:`jedi.Interpreter` with the live
           ``exec_globals``. This covers user variables (``x = cmds.ls(); x.|``
           → real list methods) and any other runtime-populated module such as
           the in-house ``eST3``.

        When no stubs are registered or no live namespaces are provided we
        just hand jedi the simplest thing that still works.
        """
        project = self._build_project()
        if self._extra_paths and _is_maya_rooted(code, line, column):
            return jedi.Script(code=code, path=path, project=project)

        if namespaces:
            return jedi.Interpreter(code, namespaces=list(namespaces), path=path, project=project)
        return jedi.Script(code=code, path=path, project=project)

    def _build_project(self):
        """Construct a ``jedi.Project`` that puts our stub paths at ``sys_path[0]``.

        Earlier attempts relied on ``added_sys_path`` alone, but in-Maya jedi
        still resolved ``maya.cmds`` to the live C-extension package because
        the auto-discovered environment path (``C:/.../Maya2025/bin``) landed
        ahead of the stub. Passing an explicit ``sys_path`` with
        ``smart_sys_path=False`` forces the order we need.
        """
        if not self._extra_paths:
            return None
        try:
            import sys

            forced_sys_path = list(self._extra_paths) + list(sys.path)
            return jedi.Project(
                path=".",
                sys_path=forced_sys_path,
                smart_sys_path=False,
            )
        except Exception as exc:
            logger.debug(f"jedi.Project construction failed: {exc}")
            return None


def _is_maya_rooted(code: str, line: int, column: int) -> bool:
    """True iff the dotted expression at the cursor starts with a Maya stub root.

    Matches ``cmds.polyCube(|``, ``OpenMaya.MVector.|``, ``om2.MFn|``, etc. —
    anything whose leftmost identifier is in :data:`_MAYA_STUB_ROOTS`. A bare
    ``cmds`` (no dot yet) also counts so top-level ``cmds.<TAB>`` triggers
    stub resolution. Expressions starting with ``(`` or a function call
    (``get_cmds().polyCube(|``) fall through to ``False`` — we accept the
    small regression for those rare shapes in exchange for a simpler rule.
    """
    try:
        line_text = code.splitlines()[line - 1]
    except IndexError:
        return False
    prefix = line_text[:column]

    # If the cursor is inside an unclosed call (e.g. ``cmds.polyCube(widt|``)
    # we want to classify based on the callee, not the argument being typed.
    depth = 0
    for i in range(len(prefix) - 1, -1, -1):
        ch = prefix[i]
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth == 0:
                prefix = prefix[:i]
                break
            depth -= 1

    match = _CHAIN_ROOT_RE.search(prefix)
    if not match:
        return False
    return match.group(1) in _MAYA_STUB_ROOTS


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
