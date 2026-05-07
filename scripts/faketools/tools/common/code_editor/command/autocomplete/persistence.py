"""Per-user persistent MRU store for autocomplete ranking.

The autocomplete controller boosts recently-accepted candidates so the
"obvious" pick lands on row 0 of the popup. Without persistence that
ranking is lost the moment Maya restarts; with this store it survives
across sessions on disk as ``autocomplete_mru.json``.

Design choices baked in here:

- **Context-aware keys**: an item picked under ``cmds.`` is stored as
  ``"cmds.polyCube"``, not bare ``"polyCube"``. That keeps
  ``cmds.polyCube`` and ``pymel.core.polyCube`` ranked independently
  even though their leaf names collide. ``view_for_root`` rebuilds a
  bare-name dict on demand for the engine, which only ever consults
  ``mru.get(item.name, ...)``.
- **Dirty-flag I/O**: writes happen at session-save boundaries
  (focus-out, tab events, Maya exit). If no completion has been
  accepted since the last save, ``save_if_dirty`` is a no-op so we
  never touch disk on idle ticks.
- **Bounded size**: cap at :data:`MAX_ENTRIES`. When over budget we
  keep the highest-count entries — count is the only signal we have
  that an entry is still useful, since we don't track per-entry
  timestamps.
- **Qt-free**: this module sits under ``command/`` and may run before
  the Qt event loop or in a unit-test context. ``settings_dir`` is
  injected so we don't reach into ``lib_ui``.
"""

from __future__ import annotations

import json
from logging import getLogger
import os
from typing import Optional

logger = getLogger(__name__)


MAX_ENTRIES = 100
MRU_FILE_NAME = "autocomplete_mru.json"


def make_key(root: Optional[str], name: str) -> str:
    """Compose the storage key for a ``(root, name)`` pair.

    A non-empty ``root`` (the leftmost identifier of the dotted
    expression at the cursor — ``cmds`` for ``cmds.polyCu|``) yields
    ``"<root>.<name>"``; an empty / missing root yields ``name`` alone
    so bare keywords (``import``, ``lambda``, …) and free-floating
    identifiers don't get a phantom prefix.
    """
    if not root:
        return name
    return f"{root}.{name}"


class AutocompleteMruStore:
    """Process-wide MRU store backing :class:`AutocompleteController`.

    One instance per editor process — see ``ui/autocomplete/_stubs.py``
    for the shared accessor. The controller only ever reads through
    :meth:`view_for_root` and writes through :meth:`increment`; it does
    not see the on-disk format directly.

    Thread safety: writes are confined to the Qt main thread (the
    controller mutates here from ``_insert_completion``). Reads from
    the QThreadPool worker go through :meth:`view_for_root`, which
    returns a fresh dict copy — workers never share state with the
    UI thread mutations.
    """

    def __init__(self, path: Optional[str] = None, max_entries: int = MAX_ENTRIES):
        self._path = path
        self._max_entries = max_entries
        self._counts: dict[str, int] = {}
        self._dirty = False
        if path is not None:
            self.load()

    # -------------------- I/O --------------------

    def load(self) -> None:
        """Read ``autocomplete_mru.json`` if present.

        Tolerant: corrupt JSON, wrong types, OS errors all degrade
        silently to an empty store. The user's autocomplete still
        works, just without the historical ranking. Entries with
        non-int values are dropped during sanitisation.
        """
        if self._path is None or not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to load autocomplete MRU ({self._path}): {exc}")
            return
        if not isinstance(data, dict):
            logger.warning(f"autocomplete MRU: expected dict at top level, got {type(data).__name__}")
            return
        sanitised: dict[str, int] = {}
        for key, value in data.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, bool):
                # ``bool`` is a subclass of int; explicit reject so True/False
                # don't sneak in as 1/0.
                continue
            if isinstance(value, int) and value > 0:
                sanitised[key] = value
        self._counts = sanitised

    def save_if_dirty(self) -> bool:
        """Persist if there have been increments since the last save.

        Returns True iff a write happened. Trims to ``max_entries``
        before writing — entries beyond the cap are the lowest-count
        ones, so the surviving set still represents the user's most-
        used picks. ``dirty`` is cleared on success only; an OS error
        leaves it set so the next save attempt retries.
        """
        if not self._dirty or self._path is None:
            return False
        if len(self._counts) > self._max_entries:
            self._counts = self._trim()
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._counts, f, indent=2, ensure_ascii=False, sort_keys=True)
        except OSError as exc:
            logger.error(f"Failed to save autocomplete MRU ({self._path}): {exc}")
            return False
        self._dirty = False
        return True

    # -------------------- mutation / queries --------------------

    def increment(self, root: Optional[str], name: str) -> None:
        """Record a fresh accept for ``(root, name)``. Marks the store dirty."""
        if not name:
            return
        key = make_key(root, name)
        self._counts[key] = self._counts.get(key, 0) + 1
        self._dirty = True

    def view_for_root(self, root: Optional[str]) -> dict[str, int]:
        """Build a ``{leaf_name: count}`` view for the given ``root``.

        Returned dict is a fresh copy — the worker may keep it across
        a jedi call without worrying about the controller mutating
        the underlying store mid-flight. Empty dict is fine; the
        engine treats an empty / None mru identically.
        """
        prefix = f"{root}." if root else None
        view: dict[str, int] = {}
        if prefix is None:
            # Root-less context: only consult bare-name entries
            # (no dot in the key) to avoid mixing in counts that were
            # recorded under a specific module.
            for key, count in self._counts.items():
                if "." not in key:
                    view[key] = count
            return view
        plen = len(prefix)
        for key, count in self._counts.items():
            if key.startswith(prefix):
                leaf = key[plen:]
                if leaf:
                    view[leaf] = count
        return view

    # -------------------- introspection (testing / debug) --------------------

    @property
    def dirty(self) -> bool:
        return self._dirty

    def snapshot(self) -> dict[str, int]:
        """Copy of the underlying dict for tests/diagnostics."""
        return dict(self._counts)

    # -------------------- internals --------------------

    def _trim(self) -> dict[str, int]:
        """Keep the top ``max_entries`` by count, breaking ties on key.

        Tie-break on key (alphabetic) keeps the trim deterministic
        across runs — useful when comparing two saved files for
        regression tests.
        """
        ordered = sorted(self._counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return dict(ordered[: self._max_entries])


__all__ = ["AutocompleteMruStore", "MAX_ENTRIES", "MRU_FILE_NAME", "make_key"]
