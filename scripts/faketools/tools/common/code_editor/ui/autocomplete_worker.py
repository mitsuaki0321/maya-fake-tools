"""
QThreadPool runnable that drives ``JediEngine.complete`` off the UI thread.

The editor's main thread submits a :class:`CompletionRunnable` each time a
completion is wanted; results come back via a Qt signal. If a newer request
is submitted before the previous one finishes, the controller flips
``_cancel`` on the in-flight runnable so its result is dropped when it
eventually emits — this keeps stale completions from overwriting fresher
ones in out-of-order execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from logging import getLogger
from typing import Optional

from .....lib_ui.qt_compat import QObject, QRunnable, Signal
from ..command.autocomplete import CompletionItem, JediEngine

logger = getLogger(__name__)


class CompletionSignals(QObject):
    """Signal carrier for :class:`CompletionRunnable`.

    ``QRunnable`` isn't a ``QObject`` and so can't own signals directly; we
    compose a separate ``QObject`` and the controller connects to its signal
    before submitting the runnable.
    """

    # (request_id, items)
    completed = Signal(int, list)


class CompletionRunnable(QRunnable):
    """Runs jedi's ``complete()`` in a thread-pool worker.

    Stateless beyond its inputs and the cancel flag. The controller handles
    filtering out stale emissions — it's fine to just let the runnable finish
    even after cancellation, because nobody is listening anymore.
    """

    def __init__(
        self,
        engine: JediEngine,
        request_id: int,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]] = None,
        path: Optional[str] = None,
        max_items: int = 50,
        mru: Optional[Mapping[str, int]] = None,
    ):
        super().__init__()
        self.signals = CompletionSignals()
        self._engine = engine
        self._request_id = request_id
        self._code = code
        self._line = line
        self._column = column
        # ``namespaces`` is kept as-is; we can't defensively copy exec_globals
        # without losing live introspection ability, and jedi reads lazily.
        self._namespaces = namespaces
        self._path = path
        self._max_items = max_items
        # Snapshot the MRU so the engine gets a stable view even if the
        # controller mutates it mid-flight (accept happening during a
        # racing completion request).
        self._mru: Optional[Mapping[str, int]] = dict(mru) if mru else None
        self._cancel = False

    def cancel(self):
        """Mark this request as superseded; its result will be ignored."""
        self._cancel = True

    def run(self):
        if self._cancel:
            return
        try:
            items: list[CompletionItem] = self._engine.complete(
                self._code,
                self._line,
                self._column,
                namespaces=self._namespaces,
                path=self._path,
                max_items=self._max_items,
                mru=self._mru,
            )
        except Exception as exc:
            # Engine already catches internal jedi errors; this is defence for
            # any surprise (e.g. namespaces containing objects that break
            # jedi's introspection). Log and emit an empty list so the
            # controller can still clear any stale popup.
            logger.debug(f"CompletionRunnable crashed: {exc}")
            items = []

        if self._cancel:
            return
        self.signals.completed.emit(self._request_id, items)


class DocstringSignals(QObject):
    """Signal carrier for :class:`DocstringRunnable`.

    Mirror of :class:`CompletionSignals` — ``QRunnable`` can't own signals
    directly, so we compose. The ``completed`` signal carries the request
    id so late emissions (user already moved on) can be dropped.
    """

    # (request_id, docstring_text). Empty text means jedi couldn't resolve
    # the identifier or the resolved object has no docstring.
    completed = Signal(int, str)


class DocstringRunnable(QRunnable):
    """Runs jedi's ``get_docstring()`` in a thread-pool worker.

    Same stateless-with-cancel-flag shape as :class:`CompletionRunnable`.
    Help popup triggers one per Ctrl+Shift+Space press (and per arrow-
    key selection change while the popup is visible). jedi inference on
    file-less in-house modules (network-mounted ``mCmds`` and the like)
    costs ~70 ms, hence the mandatory off-UI-thread dispatch.
    """

    def __init__(
        self,
        engine: JediEngine,
        request_id: int,
        code: str,
        line: int,
        column: int,
        namespaces: Optional[Sequence[dict]] = None,
        path: Optional[str] = None,
    ):
        super().__init__()
        self.signals = DocstringSignals()
        self._engine = engine
        self._request_id = request_id
        self._code = code
        self._line = line
        self._column = column
        self._namespaces = namespaces
        self._path = path
        self._cancel = False

    def cancel(self):
        """Mark this request as superseded; its result will be ignored."""
        self._cancel = True

    def run(self):
        if self._cancel:
            return
        try:
            text = self._engine.get_docstring(
                self._code,
                self._line,
                self._column,
                namespaces=self._namespaces,
                path=self._path,
            )
        except Exception as exc:
            logger.debug(f"DocstringRunnable crashed: {exc}")
            text = ""

        if self._cancel:
            return
        self.signals.completed.emit(self._request_id, text)


__all__ = [
    "CompletionRunnable",
    "CompletionSignals",
    "DocstringRunnable",
    "DocstringSignals",
]
