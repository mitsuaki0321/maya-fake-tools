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

from collections.abc import Sequence
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


__all__ = ["CompletionRunnable", "CompletionSignals"]
