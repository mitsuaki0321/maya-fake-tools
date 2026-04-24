"""Lifecycle controller for the help popup.

Triggered by Ctrl+Shift+Space: shows docs for the autocomplete
highlight when the list is open, otherwise for the identifier under
the caret. Dismissed by Esc, the shortcut again, autocomplete Show /
Hide, or owner-window state changes.
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


# Arrow-key debounce so scrolling past items doesn't fire a jedi call per row.
_SELECTION_DEBOUNCE_MS = 80

# Lines scrolled per Ctrl+Shift+Up/Down press inside the help popup.
_SCROLL_LINES_PER_PRESS = 3


class HelpPopupController(QObject):
    """Owns the :class:`HelpPopup` instance and wires its dependencies."""

    def __init__(self, main_window, engine: JediEngine):
        super().__init__(main_window)
        self._main_window = main_window
        self._engine = engine
        self._popup: Optional[HelpPopup] = None

        # Monotonic id to drop stale docstring results.
        self._request_id = 0
        self._active_runnable: Optional[DocstringRunnable] = None

        self._active_editor = None
        self._active_autocomplete = None
        self._active_autocomplete_popup = None

        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(_SELECTION_DEBOUNCE_MS)
        self._selection_timer.timeout.connect(self._refresh_from_autocomplete)

        self._owner_window_watcher: Optional[_OwnerWindowWatcher] = None

    # -------------------- public entry points --------------------

    def toggle(self) -> None:
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
        self._request_id += 1
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
        item = ac.selected_item()
        if item is None:
            return
        try:
            code, line, column = ac.synthesize_accepted_source(item)
        except Exception as exc:
            logger.debug(f"synthesize_accepted_source failed: {exc}")
            return

        self._ensure_popup()
        self._attach(editor, autocomplete=ac)
        anchor = ac.popup_global_rect() or self._cursor_global_rect(editor)
        assert self._popup is not None
        self._popup.set_loading(item.name)
        self._popup.show_at(anchor)
        self._start_fetch(editor, code, line, column)

    def _show_for_cursor(self, editor) -> None:
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
        if self._active_editor is not editor:
            if self._active_editor is not None:
                with contextlib.suppress(RuntimeError):
                    self._active_editor.removeEventFilter(self)
            editor.installEventFilter(self)
            self._active_editor = editor

        if self._active_autocomplete is not autocomplete:
            if self._active_autocomplete is not None:
                self._active_autocomplete.disconnect_popup_selection_changed(self._on_autocomplete_selection_changed)
                self._active_autocomplete.set_help_popup_widget(None)
            if autocomplete is not None:
                autocomplete.connect_popup_selection_changed(self._on_autocomplete_selection_changed)
            self._active_autocomplete = autocomplete

        if autocomplete is not None and self._popup is not None:
            autocomplete.set_help_popup_widget(self._popup)

        # Watch autocomplete popup for Show/Hide — either ends help's context.
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

        # Lambda getter so dock/undock popup swaps are picked up automatically.
        if self._popup is not None:
            if self._owner_window_watcher is None:
                self._owner_window_watcher = _OwnerWindowWatcher(lambda: self._popup, self)
            self._owner_window_watcher.attach(editor.window() or editor)

    def _ensure_popup(self) -> None:
        if self._popup is None:
            self._popup = HelpPopup()

    # -------------------- jedi worker --------------------

    def _start_fetch(self, editor, code: str, line: int, column: int) -> None:
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
        if request_id != self._request_id:
            return
        if self._popup is None or not self._popup.isVisible():
            return
        self._popup.set_text(text)

    def _collect_namespaces(self, editor) -> Optional[list[dict]]:
        """Reuse the autocomplete controller's namespaces so jedi resolves in-house runtime modules."""
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
        self._selection_timer.start()

    def _refresh_from_autocomplete(self) -> None:
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
        doc = editor.document()
        cursor = editor.textCursor()
        pos = cursor.position()

        start = pos
        while start > 0:
            ch = doc.characterAt(start - 1)
            if ch.isalnum() or ch == "_":
                start -= 1
                continue
            break

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
        # cursorRect() is in local coords; build from mapped top-left rather
        # than translate, which would double-add the local offset.
        cursor_rect = editor.cursorRect()
        global_top_left = editor.mapToGlobal(cursor_rect.topLeft())
        return QRect(global_top_left, cursor_rect.size())

    # -------------------- event filter --------------------

    def eventFilter(self, obj, event):
        et = event.type()
        popup_visible = self._popup is not None and self._popup.isVisible()
        if not popup_visible:
            return False

        if et == QEvent.KeyPress and event.key() == Qt.Key_Escape and obj is self._active_editor:
            # Don't consume — Esc should also dismiss the autocomplete list.
            self.hide()
            return False

        # Ctrl+Shift+Up/Down scrolls the help popup body. Handled on both the
        # editor and the autocomplete popup so it works whether the list is
        # open (keys go to the popup widget) or closed (keys go to the editor).
        if et == QEvent.KeyPress and obj in (self._active_editor, self._active_autocomplete_popup):
            mods = event.modifiers()
            if mods & Qt.ControlModifier and mods & Qt.ShiftModifier:
                key = event.key()
                if key == Qt.Key_Up:
                    self._popup.scroll_lines(-_SCROLL_LINES_PER_PRESS)
                    return True
                if key == Qt.Key_Down:
                    self._popup.scroll_lines(_SCROLL_LINES_PER_PRESS)
                    return True

        if obj is self._active_autocomplete_popup and et in (QEvent.Show, QEvent.Hide):
            self.hide()
            return False

        return False


__all__ = ["HelpPopupController"]
