"""
Thin adapter over ``jedi`` for the Code Editor.

Everything jedi-specific lives here so the rest of the tree can treat
completion as a pure ``(code, cursor, namespaces) -> list[CompletionItem]``
function. If jedi is not installed the engine becomes a no-op: the ``complete``
and ``signatures`` methods return empty lists and the editor continues to
work, just without completion popups.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from logging import getLogger
import re
import time
from typing import Any, Optional

from .types import CompletionItem

logger = getLogger(__name__)

try:
    import jedi  # type: ignore
    from jedi.api.environment import InterpreterEnvironment  # type: ignore

    JEDI_AVAILABLE = True
except Exception as _exc:  # pragma: no cover — diagnostic path
    jedi = None  # type: ignore[assignment]
    InterpreterEnvironment = None  # type: ignore[assignment,misc]
    JEDI_AVAILABLE = False
    logger.info(f"jedi not available, autocomplete disabled: {_exc}")


# Size cap for source files fed to jedi. Above this, parse times dominate the
# debounce budget — return an empty list instead of freezing the editor.
_MAX_FILE_BYTES = 500 * 1024


# ---------------------------------------------------------------------------
# Maya alias configuration — the *only* place to touch when adding a name.
#
# To teach the editor about another local alias (e.g. ``import maya.cmds as
# mc`` or ``import maya.api.OpenMayaAnim as oma``), append the alias to the
# right tuple below. The stub-root detector (``_MAYA_STUB_ROOTS``), the
# alias → canonical-module table, and the virtual import shim fed to
# ``jedi.Script`` are all derived from these lists, so a one-word edit is
# all it takes. Reason this layer exists at all: ``maya.cmds`` and the
# ``maya.api.OpenMaya*`` family must be routed through ``jedi.Script``
# against the bundled stubs — their live ``dir()`` is nearly empty
# (lazy-load) and jedi.Interpreter's ``MixedObject`` layer favours the
# empty live side.
# ---------------------------------------------------------------------------
_CMDS_ALIASES: tuple[str, ...] = ("cmds", "mc")

# Each API submodule mapped to the aliases that should resolve to it. The
# first alias in each tuple is the canonical name — it's what the synthetic
# populate-source fed to jedi uses, so keep the bare module name first for
# the cleanest stub resolution.
_API_ALIASES: dict[str, tuple[str, ...]] = {
    "maya.api.OpenMaya": ("OpenMaya", "om2", "om"),
    "maya.api.OpenMayaAnim": ("OpenMayaAnim", "oma"),
    "maya.api.OpenMayaRender": ("OpenMayaRender", "omr"),
    "maya.api.OpenMayaUI": ("OpenMayaUI", "omu"),
}


def _build_alias_tables() -> tuple[dict[str, str], dict[str, str], frozenset[str]]:
    """Derive the alias → module, module → canonical, and stub-root tables.

    Drives the root-completion cache: every alias in ``_CMDS_ALIASES`` shares
    a single cache entry under ``maya.cmds``, so ``cmds.polyC|`` and
    ``mc.polyC|`` reuse the same populated list. Same idea for the API
    family — ``oma.MFn|`` and ``OpenMayaAnim.MFn|`` hit one entry.
    """
    module_by_alias: dict[str, str] = {alias: "maya.cmds" for alias in _CMDS_ALIASES}
    canonical_by_module: dict[str, str] = {"maya.cmds": _CMDS_ALIASES[0]}
    for module, aliases in _API_ALIASES.items():
        for alias in aliases:
            module_by_alias[alias] = module
        canonical_by_module[module] = aliases[0]
    stub_roots = frozenset({"maya", *module_by_alias.keys()})
    return module_by_alias, canonical_by_module, stub_roots


_MODULE_BY_ALIAS, _CANONICAL_ALIAS_BY_MODULE, _MAYA_STUB_ROOTS = _build_alias_tables()


def _build_maya_import_shim() -> str:
    """Render a ``.py`` snippet that binds every alias to its stub module.

    Prepended to the user's source before handing it to ``jedi.Script`` so
    they don't need to declare the imports themselves. Ordering doesn't
    matter; duplicates are fine because a user-declared import simply
    shadows the shim binding downstream.
    """
    lines: list[str] = []
    for alias in _CMDS_ALIASES:
        if alias == "cmds":
            lines.append("from maya import cmds")
        else:
            lines.append(f"from maya import cmds as {alias}")
    for module, aliases in _API_ALIASES.items():
        bare = module.rsplit(".", 1)[-1]
        for alias in aliases:
            if alias == bare:
                lines.append(f"from maya.api import {bare}")
            else:
                lines.append(f"from maya.api import {bare} as {alias}")
    return "\n".join(lines) + "\n"


_MAYA_IMPORT_SHIM = _build_maya_import_shim()
_MAYA_SHIM_LINES = _MAYA_IMPORT_SHIM.count("\n")


# Regex to pick the first identifier out of a dotted chain. Used after we've
# lopped off the text inside any unmatched trailing ``(`` so the callee is
# what we're matching, not the argument being typed.
_CHAIN_ROOT_RE = re.compile(r"([A-Za-z_]\w*)(?:\.[A-Za-z_]\w*)*\.?\w*$")

# Regex for the root-completion cache fast path. Only matches when the cursor
# is at ``<root>.<prefix>`` where ``<root>`` is a standalone identifier (not
# part of a longer dotted chain like ``cmds.polyCube.<cursor>`` and not a
# method call result like ``foo().<cursor>``). ``<prefix>`` may be empty.
_BARE_ROOT_RE = re.compile(r"(?:^|[^A-Za-z_.\)\]])([A-Za-z_]\w*)\.(\w*)$")


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
        # ``_cached_project`` is rebuilt only when ``set_extra_paths`` changes
        # the paths — the Project's sys_path is a snapshot, so reusing one
        # instance across every completion avoids a list copy + jedi-side
        # initialisation on each keystroke.
        self._cached_project: Any = None
        # Force jedi into same-process mode. Without this, ``jedi.Script``
        # spawns the interpreter (``mayapy.exe``) as a subprocess on first
        # call to query its environment — inside Maya that costs 7+ seconds
        # and is the single biggest factor in "first cmds. completion feels
        # frozen". InterpreterEnvironment reuses the live Python process
        # instead, dropping that cost to ~25 ms.
        self._env: Any = InterpreterEnvironment() if JEDI_AVAILABLE else None
        # Per-module completion list cache. Populated lazily on the first
        # ``<root>.<prefix>`` hit for each Maya stub module and reused for
        # every subsequent keystroke, so 150 ms of jedi inference collapses
        # into a ~1 ms Python-side prefix filter. Keyed by the *resolved*
        # module name (``maya.cmds``, not ``cmds``) so aliases share one entry.
        # Cleared when ``set_extra_paths`` changes the Project — stubs that
        # might have been swapped out are no longer authoritative.
        self._root_completion_cache: dict[str, list[CompletionItem]] = {}

    def set_extra_paths(self, paths: Sequence[str]) -> None:
        """Replace the extra sys.path list used when building jedi ``Project``s.

        Safe to call at any time; existing cached scripts aren't affected
        (a fresh Interpreter/Script is built per ``complete()`` call). The
        memoised :class:`jedi.Project` and the per-root completion cache are
        invalidated so the next call picks up the new sys_path and stubs.
        """
        self._extra_paths = [str(p) for p in paths if p]
        self._cached_project = None
        self._root_completion_cache.clear()

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
        mru: Optional[Mapping[str, int]] = None,
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
            mru:        Optional ``{name: count}`` tally of previously-accepted
                        items. Applied as a stable boost *before* the cap, so
                        that a frequently-picked command (``ls``) still rises
                        to the top even when ``cmds.`` would otherwise produce
                        1500 alphabetically-sorted items and truncate.

        Returns ``[]`` when jedi is unavailable or the source is too large.
        Errors inside jedi are swallowed and logged at debug level so one
        malformed file can't take the editor down.
        """
        if not JEDI_AVAILABLE:
            return []
        if not code or len(code) > self.max_file_bytes:
            return []

        t_start = time.perf_counter()

        # --- Fast path: cached Maya-root completions ---
        # When the cursor sits at ``<root>.<prefix>`` and ``<root>`` resolves
        # to a stubbed Maya module, the full attribute list is invariant for
        # the whole Maya session. We fetch it from jedi once (the "populate"
        # call) and answer every subsequent keystroke with a Python-side
        # prefix filter — ~1 ms instead of ~150 ms.
        cache_state = "bypass"
        if self._extra_paths:
            bare_hit = _match_bare_root(code, line, column)
            if bare_hit is not None:
                root_alias, prefix = bare_hit
                resolved_module = _MODULE_BY_ALIAS.get(root_alias)
                if resolved_module is not None:
                    all_items = self._root_completion_cache.get(resolved_module)
                    if all_items is None:
                        all_items = self._fetch_root_completions(resolved_module)
                        if all_items:
                            self._root_completion_cache[resolved_module] = all_items
                            cache_state = "populate"
                        else:
                            # Empty populate — fall through to the full path
                            # rather than cache an unauthoritative empty list.
                            all_items = None
                    else:
                        cache_state = "hit"
                    if all_items is not None:
                        return self._finalise_cached(all_items, prefix, root_alias, resolved_module, max_items, mru, t_start, cache_state)

        # --- Full path: hand the user's source to jedi ---
        try:
            script, effective_line = self._make_script(code, line, column, namespaces, path)
            t_script = time.perf_counter() - t_start
            completions = script.complete(effective_line, column)
        except Exception as exc:
            logger.debug(f"jedi.complete failed at {line}:{column}: {exc}")
            return []
        t_jedi = time.perf_counter() - t_start - t_script

        items = [CompletionItem.from_jedi(c) for c in completions]
        items.sort(key=_completion_sort_key)
        if mru:
            # Stable sort: items with a positive MRU count rise, ties keep
            # the prior alphabetic/category order. Runs before the cap so
            # MRU items in a long list don't get truncated off the end.
            items.sort(key=lambda it: -mru.get(it.name, 0))
        if len(items) > max_items:
            items = items[:max_items]

        t_total_ms = (time.perf_counter() - t_start) * 1000
        root = _expression_root(code, line, column) or "?"
        logger.debug(
            f"autocomplete.complete: total={t_total_ms:.1f}ms "
            f"(script={t_script * 1000:.1f}ms jedi={t_jedi * 1000:.1f}ms) "
            f"root={root} maya_rooted={root in _MAYA_STUB_ROOTS} cache=bypass items={len(items)}"
        )
        return items

    # -------------------- completion cache internals --------------------

    def _finalise_cached(
        self,
        all_items: list[CompletionItem],
        prefix: str,
        root_alias: str,
        resolved_module: str,
        max_items: int,
        mru: Optional[Mapping[str, int]],
        t_start: float,
        cache_state: str,
    ) -> list[CompletionItem]:
        """Apply case-insensitive substring filter + MRU + cap to cached items.

        Uses ``prefix.lower() in CompletionItem.name_lower`` (VSCode-style
        "contains") so typing ``cube`` still surfaces ``polyCube`` and
        ``fn`` inside OpenMaya surfaces ``MFnDagNode`` etc.
        ``AutoCompleteController._insert_completion`` removes the current
        partial word before inserting the chosen ``name``, so non-prefix
        matches insert correctly.

        After the filter, prefix-matches (names that *start* with the
        typed text) are stable-sorted to the top so the "obvious" match
        lands on the highlighted row. Without this, typing ``ls``
        highlights ``ActivateGlobalScreenSlider`` (which alphabetically
        precedes ``ls`` but is only a substring match), and Tab/Enter
        would commit the wrong item. Stable sort preserves the
        alphabetical ordering that ``_fetch_root_completions`` already
        established, so within each group items stay in name order.
        MRU ranking still runs after, and wins ties — a recently-picked
        substring-only match floats above a fresh prefix match.
        """
        if prefix:
            prefix_lower = prefix.lower()
            items = [c for c in all_items if prefix_lower in c.name_lower]
            items.sort(key=lambda c: 0 if c.name_lower.startswith(prefix_lower) else 1)
        else:
            items = list(all_items)
        if mru:
            items.sort(key=lambda it: -mru.get(it.name, 0))
        if len(items) > max_items:
            items = items[:max_items]

        t_total_ms = (time.perf_counter() - t_start) * 1000
        logger.debug(
            f"autocomplete.complete: total={t_total_ms:.1f}ms "
            f"root={root_alias} module={resolved_module} cache={cache_state} "
            f"prefix={prefix!r} items={len(items)}/{len(all_items)}"
        )
        return items

    def _fetch_root_completions(self, resolved_module: str) -> list[CompletionItem]:
        """Ask jedi for the full completion list of ``<resolved_module>.``.

        Runs jedi against a tiny synthetic source so the list doesn't depend
        on the user's document. Reuses the shared ``Project`` and
        ``InterpreterEnvironment`` so it's subject to the same
        subprocess-avoidance fix as the main path.
        """
        canonical = _CANONICAL_ALIAS_BY_MODULE.get(resolved_module)
        if canonical is None:
            return []
        snippet = _MAYA_IMPORT_SHIM + f"{canonical}."
        effective_line = _MAYA_SHIM_LINES + 1
        effective_column = len(canonical) + 1  # cursor immediately after the dot
        try:
            script = jedi.Script(
                code=snippet,
                project=self._build_project(),
                environment=self._env,
            )
            completions = script.complete(effective_line, effective_column)
        except Exception as exc:
            logger.debug(f"root cache populate failed for {resolved_module}: {exc}")
            return []
        # Cache populate is the one path where reading ``completion.type`` is
        # cheap: the bundled Maya stubs (`.pyi`) are on local disk, so the
        # category-rank sort (param > keyword > function > class > ...) is
        # worth the ~0.1 ms per item — especially for ``OpenMaya`` where
        # classes, methods and enum constants would otherwise mix into a
        # single alphabetical stream.
        items = [CompletionItem.from_jedi(c, fetch_type=True) for c in completions]
        items.sort(key=_completion_sort_key)
        return items

    def get_docstring(
        self,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]] = None,
        path: Optional[str] = None,
    ) -> str:
        """Docstring for the identifier at ``(line, column)``.

        Maya ``cmds.*`` names fall through to ``cmds.help(name)`` since
        the bundled stubs carry signatures only. Other names try the
        static jedi docstring first; on empty (e.g. C-implemented
        ufuncs like ``numpy.absolute`` whose docs live only on the
        runtime object) we fall back to live ``__doc__``. Cost:
        ~70 ms on file-less in-house modules, so callers must run
        this off the UI thread.
        """
        if not JEDI_AVAILABLE:
            return ""
        if not code or len(code) > self.max_file_bytes:
            return ""

        try:
            script, effective_line = self._make_script(code, line, column, namespaces, path)
            names = script.help(effective_line, column)
        except Exception as exc:
            logger.debug(f"jedi.help failed at {line}:{column}: {exc}")
            return ""

        # Pass 1 — Maya cmds.help() override, preferred when available.
        for name in names:
            full_name = getattr(name, "full_name", None) or ""
            if not full_name.startswith("maya.cmds."):
                continue
            text = _try_cmds_help(getattr(name, "name", ""))
            if text:
                return text

        # Pass 2 — jedi docstring. Use ``raw=True`` to decide whether the
        # stub actually has a body: ``raw=False`` synthesises a signature
        # line even for empty stubs (``getPoints(self, *args: Any) -> Any``),
        # which would block the live-doc fallback. We keep that synthetic
        # signature as a last resort.
        synthetic_fallback = ""
        for name in names:
            try:
                body = name.docstring(raw=True) or ""
            except Exception as exc:
                logger.debug(f"name.docstring(raw=True) failed for {name!r}: {exc}")
                continue
            if body.strip():
                try:
                    return name.docstring(raw=False) or body
                except Exception as exc:
                    logger.debug(f"name.docstring(raw=False) failed for {name!r}: {exc}")
                    return body
            if not synthetic_fallback:
                try:
                    synthetic_fallback = name.docstring(raw=False) or ""
                except Exception as exc:
                    logger.debug(f"name.docstring(raw=False) failed for {name!r}: {exc}")

        # Pass 3 — live ``__doc__`` for names whose stubs lack docs (numpy ufuncs, OpenMaya bindings, …).
        for name in names:
            full_name = getattr(name, "full_name", None) or ""
            text = _try_live_doc(full_name)
            if text.strip():
                return text
        return synthetic_fallback

    # -------------------- internals --------------------

    def _make_script(
        self,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]],
        path: Optional[str],
    ) -> tuple[Any, int]:
        """Return ``(script, effective_line)`` for the current cursor position.

        Two modes, picked per call based on what the user is completing:

        1. **Maya-rooted expression** (cursor under ``cmds.`` / ``OpenMaya.`` /
           their common aliases): use :class:`jedi.Script`. ``Script`` resolves
           imports purely through ``sys.path`` / the ``Project`` sys_path we
           build and ignores ``sys.modules``, so our bundled stub for
           ``maya.cmds`` wins. ``Interpreter`` here regresses to the empty-
           ``dir`` failure described in ``_MAYA_STUB_ROOTS``.

           To spare users from writing ``import maya.cmds as cmds`` at the top
           of every scratch buffer, the Maya shim is prepended to the source
           so jedi always has a binding for ``cmds`` / ``OpenMaya`` / ``om`` /
           ``om2``. The user's line number is shifted accordingly.
        2. **Everything else**: :class:`jedi.Interpreter` with the live
           ``exec_globals``. This covers user variables (``x = cmds.ls(); x.|``
           → real list methods) and any other runtime-populated module such as
           the in-house ``eST3``.

        When no stubs are registered or no live namespaces are provided we
        just hand jedi the simplest thing that still works.
        """
        project = self._build_project()
        if self._extra_paths and _is_maya_rooted(code, line, column):
            shimmed_code = _MAYA_IMPORT_SHIM + code
            return jedi.Script(code=shimmed_code, path=path, project=project, environment=self._env), line + _MAYA_SHIM_LINES

        if namespaces:
            return jedi.Interpreter(code, namespaces=list(namespaces), path=path, project=project), line
        return jedi.Script(code=code, path=path, project=project, environment=self._env), line

    def _build_project(self):
        """Return the (memoised) ``jedi.Project`` with our stubs at ``sys_path[0]``.

        Earlier attempts relied on ``added_sys_path`` alone, but in-Maya jedi
        still resolved ``maya.cmds`` to the live C-extension package because
        the auto-discovered environment path (``C:/.../Maya2025/bin``) landed
        ahead of the stub. Passing an explicit ``sys_path`` with
        ``smart_sys_path=False`` forces the order we need.

        The Project is cached across completions — its sys_path is a snapshot
        that only changes when :meth:`set_extra_paths` is called.
        """
        if not self._extra_paths:
            return None
        if self._cached_project is not None:
            return self._cached_project
        t_start = time.perf_counter()
        try:
            import sys

            forced_sys_path = list(self._extra_paths) + list(sys.path)
            self._cached_project = jedi.Project(
                path=".",
                sys_path=forced_sys_path,
                smart_sys_path=False,
            )
        except Exception as exc:
            logger.debug(f"jedi.Project construction failed: {exc}")
            self._cached_project = None
            return self._cached_project
        t_ms = (time.perf_counter() - t_start) * 1000
        logger.debug(f"autocomplete.project_built: {t_ms:.1f}ms (extra_paths={len(self._extra_paths)}, sys_path={len(forced_sys_path)})")
        return self._cached_project


def _is_maya_rooted(code: str, line: int, column: int) -> bool:
    """True iff the dotted expression at the cursor starts with a Maya stub root.

    Matches ``cmds.polyCube(|``, ``OpenMaya.MVector.|``, ``om2.MFn|``, etc. —
    anything whose leftmost identifier is in :data:`_MAYA_STUB_ROOTS`. A bare
    ``cmds`` (no dot yet) also counts so top-level ``cmds.<TAB>`` triggers
    stub resolution. Expressions starting with ``(`` or a function call
    (``get_cmds().polyCube(|``) fall through to ``False`` — we accept the
    small regression for those rare shapes in exchange for a simpler rule.
    """
    root = _expression_root(code, line, column)
    return root is not None and root in _MAYA_STUB_ROOTS


def _match_bare_root(code: str, line: int, column: int) -> Optional[tuple[str, str]]:
    """Return ``(root_alias, prefix)`` iff the cursor is at ``<root>.<prefix>``.

    "Bare" means ``<root>`` is a standalone identifier — not a deeper attribute
    chain like ``foo.bar.<cursor>``, not a method result like ``foo().<cursor>``,
    and not following another dotted expression. ``<prefix>`` may be empty.

    Used by the completion cache fast path; the caller further requires that
    ``root_alias`` be a known Maya stub alias.
    """
    start = 0
    for _ in range(line - 1):
        nl = code.find("\n", start)
        if nl < 0:
            return None
        start = nl + 1
    end = code.find("\n", start)
    line_text = code[start:end] if end >= 0 else code[start:]
    prefix_line = line_text[:column]

    match = _BARE_ROOT_RE.search(prefix_line)
    if not match:
        return None
    return match.group(1), match.group(2)


def _expression_root(code: str, line: int, column: int) -> Optional[str]:
    """Return the leftmost identifier of the dotted expression at the cursor.

    Used for both the Maya-stub routing decision and for timing logs so we can
    tell ``cmds.`` from ``om.`` from a user variable when comparing completion
    latency across environments.
    """
    # Walk to the start of the target line without materialising every
    # line of the document — ``code.splitlines()`` would allocate O(lines)
    # on every keystroke in a large file.
    start = 0
    for _ in range(line - 1):
        nl = code.find("\n", start)
        if nl < 0:
            return None
        start = nl + 1
    end = code.find("\n", start)
    line_text = code[start:end] if end >= 0 else code[start:]
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
        return None
    return match.group(1)


def _completion_sort_key(item: CompletionItem) -> tuple:
    """Sort: named parameters / keywords first, then by type rank, then alpha.

    jedi's default order isn't always ideal; this nudges the most useful
    items (``keyword`` like ``if``, ``param`` like kwarg names) to the top.
    """
    rank = _TYPE_RANK.get(item.type, _TYPE_RANK[""])
    # Hide dunders unless explicitly typed (they're noisy in autocomplete).
    dunder = 1 if item.name.startswith("_") else 0
    return (dunder, rank, item.name.lower())


def _try_live_doc(full_name: str) -> str:
    """Resolve ``full_name`` (e.g. ``maya.api.OpenMaya.MFnMesh.getPoints``) to a live object and return its ``__doc__``.

    Walks ``full_name`` by importing the longest dotted prefix that
    resolves as a module, then following the remainder with
    ``getattr``. Handles nested packages (``maya.api.OpenMaya.*``)
    where ``getattr`` alone from the top package doesn't see
    lazy-loaded subpackages. Any failure → ``""``.
    """
    if not full_name or "." not in full_name:
        return ""
    parts = full_name.split(".")

    import importlib

    module = None
    module_depth = 0
    for depth in range(1, len(parts) + 1):
        try:
            module = importlib.import_module(".".join(parts[:depth]))
            module_depth = depth
        except Exception:
            break
    if module is None:
        logger.debug(f"live doc: no importable prefix of {full_name!r}")
        return ""

    obj = module
    try:
        for attr in parts[module_depth:]:
            obj = getattr(obj, attr)
    except Exception as exc:
        logger.debug(f"live doc resolution of {full_name!r} failed: {exc}")
        return ""
    doc = getattr(obj, "__doc__", None)
    return doc if isinstance(doc, str) else ""


def _try_cmds_help(name: str) -> str:
    """``cmds.help(name)`` output, or ``""`` on any failure.

    Runs on the worker thread. ``cmds.help`` is a pure query (no scene
    mutation) so off-main-thread calls are safe in practice.
    """
    if not name:
        return ""
    try:
        import maya.cmds as cmds  # type: ignore
    except Exception as exc:
        logger.debug(f"maya.cmds import failed: {exc}")
        return ""
    try:
        text = cmds.help(name) or ""
    except Exception as exc:
        logger.debug(f"cmds.help({name!r}) failed: {exc}")
        return ""
    return text


__all__ = ["JEDI_AVAILABLE", "JediEngine"]
