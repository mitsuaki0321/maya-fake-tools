"""Shared UI helpers used by more than one feature package.

Lives at the top of ``ui/`` so feature sub-packages can reach it without
crossing each other (the historical reason this module exists is to break a
cycle between ``autocomplete/`` and ``help/``: both need
:class:`_OwnerWindowWatcher`).
"""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import Callable, Optional

from .....lib_ui.qt_compat import QEvent, QObject, Qt, QWidget

logger = getLogger(__name__)


class _OwnerWindowWatcher(QObject):
    """Hides a popup when its owner top-level window changes state.

    We don't parent QCompleter-managed popups onto Maya's main window
    — reparenting a top-level widget that QCompleter manages crashes
    Maya when the workspace is torn down (observed on dock → undock →
    close). Instead we install an event filter on the current top-level
    window and hide the popup ourselves whenever Maya's window goes
    away (``Hide``), is minimised (``WindowStateChange`` with the
    ``WindowMinimized`` flag set), or loses focus to another app
    (``WindowDeactivate``).

    ``popup_getter`` is re-invoked on every event. This matters because
    QCompleter can replace its popup widget internally (observed after
    ``setWindowFlags``: the original QListView C++ object is destroyed
    and a new one appears on the next access to ``QCompleter.popup()``).
    Caching the reference would leave us holding a dangling pointer;
    the getter pattern keeps us on the current popup.

    Callers should ``attach`` right before the popup becomes visible —
    ``editor.window()`` can change between docked and floating states.
    """

    def __init__(self, popup_getter: Callable[[], Optional[QWidget]], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._popup_getter = popup_getter
        self._watched_window: Optional[QWidget] = None
        self._alive = True

    def mark_dead(self) -> None:
        """External teardown signal (e.g. AutocompleteController shutdown)."""
        self._alive = False
        self.detach()

    def attach(self, window: Optional[QWidget]) -> None:
        """Begin watching ``window``. No-op if already watching it or dead."""
        if not self._alive or window is None:
            return
        if self._watched_window is window:
            return
        self.detach()
        window.installEventFilter(self)
        self._watched_window = window

    def detach(self) -> None:
        """Stop watching whatever window we're on. Safe to call repeatedly."""
        if self._watched_window is not None:
            with contextlib.suppress(RuntimeError):
                self._watched_window.removeEventFilter(self)
            self._watched_window = None

    def _resolve_popup(self) -> Optional[QWidget]:
        try:
            return self._popup_getter()
        except Exception as exc:
            logger.debug(f"_OwnerWindowWatcher popup_getter failed: {exc}")
            return None

    def eventFilter(self, obj, event):
        if not self._alive or obj is not self._watched_window:
            return False
        et = event.type()
        if et not in (QEvent.Hide, QEvent.WindowStateChange, QEvent.WindowDeactivate):
            return False
        popup = self._resolve_popup()
        if popup is None:
            return False
        try:
            visible = popup.isVisible()
        except RuntimeError:
            return False
        if not visible:
            return False
        try:
            if et == QEvent.WindowStateChange:
                # WindowStateChange fires on every state transition.
                # Only hide when the window ended up minimised — we don't
                # want to nuke the popup on e.g. maximise/restore.
                ws = getattr(self._watched_window, "windowState", None)
                if ws is None or not bool(ws() & Qt.WindowMinimized):
                    return False
            popup.hide()
            logger.debug(f"_OwnerWindowWatcher hid popup (event_type={et})")
        except RuntimeError:
            pass
        return False
