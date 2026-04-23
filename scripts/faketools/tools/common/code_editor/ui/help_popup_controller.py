"""
Orchestrates the help popup's lifecycle alongside the autocomplete list.

Single ``HelpPopupController`` per main window. On ``Ctrl+Shift+Space``
it decides *what* to document:

- Autocomplete list open: the currently-highlighted candidate. Arrow
  keys thereafter refresh the help content (debounced) so the user can
  preview docs without repeatedly re-triggering the shortcut.
- Autocomplete list closed: the identifier under the caret.

Dismissal paths:

- ``Esc`` in the editor.
- ``Ctrl+Shift+Space`` again (toggle).
- Autocomplete popup state change (``Show`` or ``Hide``): unifying both
  the popup-tied case (list closes → help should go with it) and the
  cursor-tied case (list opens because the user typed ``.`` → help's
  context is now stale, close it).
- Maya main window minimise / hide / deactivate via
  :class:`_OwnerWindowWatcher` (lives in :mod:`autocomplete_controller`
  and is reused here).

Docstring fetches run on the shared ``QThreadPool`` via
:class:`DocstringRunnable` — jedi inference on file-less in-house
modules (network-mounted ``mCmds`` et al.) can cost ~70 ms, hence the
mandatory off-UI-thread dispatch.

No Qt parent-child tricks: the help popup is a parent-less top-level
(``parent=None``, ``Qt.Tool``) to match the autocomplete popup, so
neither show() re-raises Maya's main window and sinks the other.
Following Maya's state is done explicitly via ``_OwnerWindowWatcher``.
"""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import Optional

from .....lib_ui.qt_compat import QEvent, QObject, QRect, Qt, QTextCursor, QThreadPool, QTimer
from ..command.autocomplete import JEDI_AVAILABLE, JediEngine
from .autocomplete_controller import _OwnerWindowWatcher
from .autocomplete_worker import DocstringRunnable
from .help_popup import HelpPopup

logger = getLogger(__name__)


# Delay (ms) between an arrow-key-driven selection change in the
# autocomplete popup and the docstring fetch it triggers. Small enough
# not to feel laggy, large enough that scrolling past a dozen items
# doesn't fire a dozen jedi calls.
_SELECTION_DEBOUNCE_MS = 80


class HelpPopupController(QObject):
    """Owns the :class:`HelpPopup` instance and wires its dependencies.

    ``QObject`` subclass so we can install event filters (for ``Esc``
    on the editor, ``Show`` / ``Hide`` on the autocomplete popup) without
    leaking that responsibility into the editor or autocomplete.
    """

    def __init__(self, main_window, engine: JediEngine):
        super().__init__(main_window)
        self._main_window = main_window
        self._engine = engine
        self._popup: Optional[HelpPopup] = None

        # Monotonic request id so stale docstring results (user moved
        # past the symbol) are dropped.
        self._request_id = 0
        self._active_runnable: Optional[DocstringRunnable] = None

        # Editor we're showing "against", plus the autocomplete
        # controller and its popup widget when in popup-tied mode. We
        # track these so we can cleanly detach all filters on hide().
        self._active_editor = None
        self._active_autocomplete = None
        self._active_autocomplete_popup = None

        # Debounce timer for selection-change-driven refreshes. Reused;
        # started fresh on every change.
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(_SELECTION_DEBOUNCE_MS)
        self._selection_timer.timeout.connect(self._refresh_from_autocomplete)

        # Maya-state watcher for the help popup itself. The autocomplete
        # controller has its own watcher for its own popup; these don't
        # interfere because each hides only the popup it was constructed
        # with.
        self._owner_window_watcher: Optional[_OwnerWindowWatcher] = None

    # -------------------- public entry points --------------------

    def toggle(self) -> None:
        """Bound to ``Ctrl+Shift+Space``.

        Closes the popup when it's visible. Otherwise picks the display
        target (autocomplete selection vs cursor identifier) based on
        whether the list is currently shown.
        """
        if self._popup is not None and self._popup.isVisible():
            self.hide()
            return
        if not JEDI_AVAILABLE:
            return

        editor = self._main_window.get_current_editor()
        if editor is None:
            return

        ac = getattr(editor, "autocomplete", None)
        if ac is not None and ac.is_popup_visible():
            self._show_for_autocomplete(editor, ac)
        else:
            self._show_for_cursor(editor)

    def hide(self) -> None:
        """Hide the popup and detach all per-session wiring."""
        self._request_id += 1  # invalidate any in-flight fetch
        if self._active_runnable is not None:
            self._active_runnable.cancel()
            self._active_runnable = None
        self._selection_timer.stop()
        if self._active_autocomplete is not None:
            self._active_autocomplete.disconnect_popup_selection_changed(self._on_autocomplete_selection_changed)
            self._active_autocomplete.set_help_popup_widget(None)
            self._active_autocomplete = None
        if self._active_autocomplete_popup is not None:
            with contextlib.suppress(RuntimeError):
                self._active_autocomplete_popup.removeEventFilter(self)
            self._active_autocomplete_popup = None
        if self._active_editor is not None:
            with contextlib.suppress(RuntimeError):
                self._active_editor.removeEventFilter(self)
            self._active_editor = None
        if self._owner_window_watcher is not None:
            self._owner_window_watcher.detach()
        if self._popup is not None:
            self._popup.hide()

    # -------------------- show paths --------------------

    def _show_for_autocomplete(self, editor, ac) -> None:
        """Fetch + show help for the currently-highlighted candidate."""
        item = ac.selected_item()
        if item is None:
            return
        try:
            code, line, column = ac.synthesize_accepted_source(item)
        except Exception as exc:
            logger.debug(f"synthesize_accepted_source failed: {exc}")
            return

        # Ensure popup exists before ``_attach`` — the attachment
        # registers the popup reference with the autocomplete
        # controller's outside-click exception list.
        self._ensure_popup()
        self._attach(editor, autocomplete=ac)
        anchor = ac.popup_global_rect() or self._cursor_global_rect(editor)
        assert self._popup is not None
        self._popup.set_loading(item.name)
        self._popup.show_at(anchor)
        self._start_fetch(editor, code, line, column)

    def _show_for_cursor(self, editor) -> None:
        """Fetch + show help for the identifier at the caret, if any."""
        identifier = self._identifier_under_cursor(editor)
        if not identifier:
            return

        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1  # jedi is 1-indexed
        column = cursor.positionInBlock()
        code = editor.toPlainText()

        self._ensure_popup()
        self._attach(editor, autocomplete=None)
        anchor = self._cursor_global_rect(editor)
        assert self._popup is not None
        self._popup.set_loading(identifier)
        self._popup.show_at(anchor)
        self._start_fetch(editor, code, line, column)

    def _attach(self, editor, autocomplete) -> None:
        """Wire event filters and selection listeners for a fresh show.

        Always watches the editor (for ``Esc``) and the autocomplete
        popup widget (for ``Show`` / ``Hide``, unified across both
        modes). In popup-tied mode we additionally register for
        selection-change and mark the help popup as a click-exception
        on the autocomplete controller.
        """
        if self._active_editor is not editor:
            if self._active_editor is not None:
                with contextlib.suppress(RuntimeError):
                    self._active_editor.removeEventFilter(self)
            editor.installEventFilter(self)
            self._active_editor = editor

        # Selection-change wiring + click-exception registration apply
        # only when we're pinned to an autocomplete list.
        if self._active_autocomplete is not autocomplete:
            if self._active_autocomplete is not None:
                self._active_autocomplete.disconnect_popup_selection_changed(self._on_autocomplete_selection_changed)
                self._active_autocomplete.set_help_popup_widget(None)
            if autocomplete is not None:
                autocomplete.connect_popup_selection_changed(self._on_autocomplete_selection_changed)
            self._active_autocomplete = autocomplete

        if autocomplete is not None and self._popup is not None:
            autocomplete.set_help_popup_widget(self._popup)

        # Watch the autocomplete popup widget regardless of mode:
        #  - popup-tied: Hide → list closed, help should follow.
        #  - cursor-tied: Show → user triggered completion, context
        #    changed, help becomes stale.
        # Either signal closes the help popup.
        new_popup_widget = None
        ac_for_popup = autocomplete
        if ac_for_popup is None:
            ac_for_popup = getattr(editor, "autocomplete", None)
        if ac_for_popup is not None:
            try:
                new_popup_widget = ac_for_popup.popup_widget()
            except Exception as exc:
                logger.debug(f"popup_widget lookup failed: {exc}")
        if self._active_autocomplete_popup is not new_popup_widget:
            if self._active_autocomplete_popup is not None:
                with contextlib.suppress(RuntimeError):
                    self._active_autocomplete_popup.removeEventFilter(self)
            if new_popup_widget is not None:
                new_popup_widget.installEventFilter(self)
            self._active_autocomplete_popup = new_popup_widget

        # Maya-state watcher: hide help when the editor's top-level
        # window gets minimised / hidden / deactivated. ``editor.window()``
        # is re-read on every show so dock/undock transitions pick up
        # the new owner.
        #
        # The watcher API takes a popup *getter* (callable), not the
        # popup instance itself. We use a lambda so the getter always
        # returns the current ``self._popup`` — if the popup is
        # recreated for any reason the watcher automatically picks up
        # the new instance.
        if self._popup is not None:
            if self._owner_window_watcher is None:
                self._owner_window_watcher = _OwnerWindowWatcher(lambda: self._popup, self)
            self._owner_window_watcher.attach(editor.window() or editor)

    def _ensure_popup(self) -> None:
        """Lazy-construct the popup the first time it's needed."""
        if self._popup is None:
            self._popup = HelpPopup()

    # -------------------- jedi worker --------------------

    def _start_fetch(self, editor, code: str, line: int, column: int) -> None:
        """Cancel any in-flight fetch, start a fresh one."""
        if self._active_runnable is not None:
            self._active_runnable.cancel()

        self._request_id += 1
        runnable = DocstringRunnable(
            engine=self._engine,
            request_id=self._request_id,
            code=code,
            line=line,
            column=column,
            namespaces=self._collect_namespaces(editor),
            path=getattr(editor, "file_path", None),
        )
        runnable.setAutoDelete(True)
        runnable.signals.completed.connect(self._on_docstring)
        self._active_runnable = runnable
        QThreadPool.globalInstance().start(runnable)

    def _on_docstring(self, request_id: int, text: str) -> None:
        """Worker callback: ignore stale ids, update the popup otherwise."""
        if request_id != self._request_id:
            return
        if self._popup is None or not self._popup.isVisible():
            return
        self._popup.set_text(text)

    def _collect_namespaces(self, editor) -> Optional[list[dict]]:
        """Reuse the autocomplete controller's namespaces for consistency.

        Lets jedi resolve in-house runtime modules (``eST3``, ``mCmds``
        etc.) by reading the same ``exec_globals`` the completions
        already use. Non-fatal on failure — jedi falls back to
        Script-only resolution.
        """
        ac = getattr(editor, "autocomplete", None)
        if ac is None:
            return None
        try:
            return list(ac._namespace_provider())  # noqa: SLF001
        except Exception as exc:
            logger.debug(f"namespace provider failed: {exc}")
            return None

    # -------------------- selection follow-through --------------------

    def _on_autocomplete_selection_changed(self, *_args) -> None:
        """Selection changed in the autocomplete popup — restart the debounce."""
        self._selection_timer.start()

    def _refresh_from_autocomplete(self) -> None:
        """Debounce fired: re-fetch for the new selection."""
        if self._popup is None or not self._popup.isVisible():
            return
        editor = self._active_editor
        ac = self._active_autocomplete
        if editor is None or ac is None or not ac.is_popup_visible():
            return
        item = ac.selected_item()
        if item is None:
            return
        try:
            code, line, column = ac.synthesize_accepted_source(item)
        except Exception as exc:
            logger.debug(f"synthesize_accepted_source failed during refresh: {exc}")
            return
        self._popup.set_loading(item.name)
        self._start_fetch(editor, code, line, column)

    # -------------------- identifier extraction --------------------

    @staticmethod
    def _identifier_under_cursor(editor) -> str:
        """Return the identifier at the caret, or empty string if none."""
        doc = editor.document()
        cursor = editor.textCursor()
        pos = cursor.position()

        # Walk left while still inside an identifier.
        start = pos
        while start > 0:
            ch = doc.characterAt(start - 1)
            if ch.isalnum() or ch == "_":
                start -= 1
                continue
            break

        # Walk right too so the caret can sit anywhere inside the word.
        end = pos
        length = doc.characterCount()
        while end < length - 1:
            ch = doc.characterAt(end)
            if ch.isalnum() or ch == "_":
                end += 1
                continue
            break

        if end <= start:
            return ""
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        return cursor.selectedText().strip()

    @staticmethod
    def _cursor_global_rect(editor) -> QRect:
        """Caret rect in global screen coords — anchor for cursor-tied show.

        ``cursorRect()`` is in the editor's local coordinates (with a
        non-zero origin at the caret position), so we build a fresh
        rect at the mapped-to-global top-left rather than translating,
        which would double-add the local offset.
        """
        cursor_rect = editor.cursorRect()
        global_top_left = editor.mapToGlobal(cursor_rect.topLeft())
        return QRect(global_top_left, cursor_rect.size())

    # -------------------- event filter --------------------

    def eventFilter(self, obj, event):
        """Bridge the two lifetime-ending signals we care about:

        - ``Esc`` on the editor → close help.
        - ``Show`` / ``Hide`` on the autocomplete popup → close help.
          Unifying both events covers popup-tied mode (Hide = list
          closed) and cursor-tied mode (Show = list re-opened, context
          stale).
        """
        et = event.type()
        popup_visible = self._popup is not None and self._popup.isVisible()
        if not popup_visible:
            return False

        if et == QEvent.KeyPress and event.key() == Qt.Key_Escape and obj is self._active_editor:
            # Don't consume — let Esc also dismiss the autocomplete list
            # if it happens to be open.
            self.hide()
            return False

        if obj is self._active_autocomplete_popup and et in (QEvent.Show, QEvent.Hide):
            self.hide()
            return False

        return False


__all__ = ["HelpPopupController"]
