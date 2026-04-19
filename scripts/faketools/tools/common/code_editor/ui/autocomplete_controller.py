"""
Autocomplete controller for a single ``PythonEditor`` instance.

Responsibilities:

- Decide *when* to trigger a completion (dot, printable keystrokes, Ctrl+Space)
- Debounce word-triggered requests so fast typing doesn't thrash jedi
- Dispatch requests through ``QThreadPool`` via :class:`CompletionRunnable`
- Filter out stale responses once a newer request has superseded them
- Drive the ``QCompleter`` popup and insert the chosen text on accept

The controller holds no completion state beyond the latest request id and a
cached "last popup was shown here" flag, so a single instance per editor tab
is cheap. The ``JediEngine`` can be (and is) shared between controllers.
"""

from __future__ import annotations

from logging import getLogger
from typing import Callable, Optional

from .....lib_ui.qt_compat import (
    QAbstractItemView,
    QCompleter,
    QStringListModel,
    Qt,
    QTextCursor,
    QThreadPool,
    QTimer,
)
from ..command.autocomplete import JEDI_AVAILABLE, JediEngine
from .autocomplete_worker import CompletionRunnable

logger = getLogger(__name__)


# Characters that end an identifier — if the character immediately before the
# caret is one of these, there's no word to complete against.
_IDENT_TERMINATORS = set(" \t\n\r()[]{}:,;=+-*/%<>!&|^~")

# Default debounce window for word-triggered completions. Dot completions
# skip the debounce entirely so ``foo.`` feels instant.
_DEFAULT_DEBOUNCE_MS = 100


class AutocompleteController:
    """Orchestrates jedi + popup + editor events for one editor widget.

    Lifecycle:
        1. Constructed by ``PythonEditor.setup_autocomplete()``.
        2. Editor forwards text-change / key-press hooks.
        3. Controller schedules async jedi calls via QThreadPool.
        4. On completion the popup opens; accept/cancel edits the document.

    The controller is intentionally passive: it does nothing unless the editor
    calls into it, so toggling it off is just ``set_enabled(False)`` and
    forgetting about it.
    """

    def __init__(
        self,
        editor,
        engine: JediEngine,
        namespace_provider: Optional[Callable[[], list[dict]]] = None,
    ):
        self.editor = editor
        self.engine = engine
        # Lazy accessor so the controller doesn't capture exec_globals until
        # the user actually triggers a completion (avoids holding stale dicts
        # if the main window rebuilds its globals).
        self._namespace_provider = namespace_provider or (lambda: [])

        self._enabled = JEDI_AVAILABLE
        self._request_id = 0
        self._pending_runnable: Optional[CompletionRunnable] = None

        self._debounce_ms = _DEFAULT_DEBOUNCE_MS
        self._timer = QTimer(editor)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dispatch_completion)

        self._model = QStringListModel([], editor)
        self._completer = QCompleter(self._model, editor)
        self._completer.setWidget(editor)
        # UnfilteredPopupCompletion shows exactly what we put in the model and
        # uses the prefix only for highlighting. jedi has already filtered by
        # prefix, so we don't want QCompleter to re-filter — doing both would
        # reset the popup's current row any time we re-apply the prefix, which
        # made arrow-key navigation snap back to the first item.
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        popup = self._completer.popup()
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        popup.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Use the untyped overload; the slot detects whether it got a string
        # or a QModelIndex. Connecting via ``activated[str]`` broke in some
        # PySide builds where the signal emission raced with the popup hide.
        self._completer.activated.connect(self._on_activated)

        # Surface any popup current-row changes in the log so we can tell
        # whether the popup is being reset by our own code or by QCompleter.
        selection_model = popup.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_popup_current_changed)

        # Short-term cache of the items backing the current popup so we can
        # still know what was selected if the model gets cleared mid-accept.
        self._current_items: list = []

    # -------------------- enable / disable --------------------

    def set_enabled(self, enabled: bool):
        """Toggle completion. Immediately hides the popup on disable."""
        self._enabled = enabled and JEDI_AVAILABLE
        if not self._enabled:
            self._hide_popup()
            # Invalidate any in-flight request so a late response can't
            # reopen the popup after the user turned autocomplete off.
            self._request_id += 1

    def is_enabled(self) -> bool:
        return self._enabled

    def set_debounce_ms(self, ms: int):
        self._debounce_ms = max(0, int(ms))

    # -------------------- event hooks (called from editor) --------------------

    def on_text_changed(self):
        """Editor's content-change entry point.

        Popup-open policy:

        - ``.`` (dot): always schedules a fresh dispatch — this is the main
          on-ramp into completion.
        - word character: only refreshes an already-visible popup. We don't
          auto-open the popup on bare identifier typing, because that's
          intrusive when the user is just writing new code. ``Ctrl+Space``
          is the escape hatch for "complete this bare identifier".
        - anything else: hide the popup.
        """
        if not self._enabled:
            return

        trigger = self._classify_trigger()
        popup_visible = self._completer.popup().isVisible()
        logger.debug(f"autocomplete.on_text_changed trigger={trigger!r} popup_visible={popup_visible}")

        if trigger is None:
            self._hide_popup()
            return

        if trigger == "dot":
            self._timer.start(0)
            return

        # trigger == "word": only refresh an already-open popup. Typing a bare
        # identifier without a preceding dot should not auto-open — that's
        # what Ctrl+Space is for.
        if popup_visible:
            self._timer.start(self._debounce_ms)

    def handle_key_press(self, event) -> bool:
        """Called before the editor's default ``keyPressEvent``.

        Returns True to consume the key. Popup navigation and commit keys are
        claimed explicitly here rather than delegated to QCompleter's event
        filter — the filter is inconsistent across Qt versions / widget types
        for QPlainTextEdit, and this way the behaviour is testable and
        diagnosable through a single code path.
        """
        key = event.key()
        mods = event.modifiers()

        # Ctrl+Space always forces a completion, regardless of popup state.
        if key == Qt.Key_Space and mods == Qt.ControlModifier and self._enabled:
            logger.debug("autocomplete: Ctrl+Space — forcing dispatch")
            self._timer.stop()
            self._dispatch_completion()
            return True

        popup = self._completer.popup()
        visible = popup.isVisible()
        # ``mods`` is a Qt.KeyboardModifier enum on PySide6 — ``int()`` raises
        # there, so reach for ``.value`` when available and fall back otherwise.
        mods_repr = getattr(mods, "value", None)
        if mods_repr is None:
            mods_repr = repr(mods)
        logger.debug(f"autocomplete.handle_key_press key={key} mods={mods_repr} popup_visible={visible}")

        if not visible:
            return False

        row_count = popup.model().rowCount()
        current_row = popup.currentIndex().row()
        logger.debug(f"autocomplete: popup rows={row_count} current_row={current_row}")

        if key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
            completion = self._selected_completion()
            logger.debug(f"autocomplete: accept -> {completion!r}")
            # Hide before inserting: the insertion fires contentsChange, and
            # if the popup were still flagged as visible at that moment the
            # word-trigger branch in on_text_changed would re-open it with
            # the freshly inserted suffix as a sole candidate.
            popup.hide()
            # Cancel any pending debounced dispatch scheduled before the
            # accept, for the same reason.
            self._timer.stop()
            if completion:
                self._insert_completion(completion)
            return True

        if key == Qt.Key_Escape:
            logger.debug("autocomplete: escape — hide popup")
            popup.hide()
            return True

        # Explicitly drive popup navigation from our side. Relying on
        # QCompleter's built-in event filter for this turned out to be
        # unreliable with QPlainTextEdit (up/down appeared to move selection
        # briefly then snap back), so we manage currentIndex here ourselves.
        if key == Qt.Key_Down:
            new_row = 0 if current_row < 0 else min(current_row + 1, row_count - 1)
            self._set_popup_row(new_row)
            logger.debug(f"autocomplete: Down -> row {new_row}")
            return True
        if key == Qt.Key_Up:
            new_row = row_count - 1 if current_row < 0 else max(current_row - 1, 0)
            self._set_popup_row(new_row)
            logger.debug(f"autocomplete: Up -> row {new_row}")
            return True
        if key == Qt.Key_PageDown:
            step = max(1, popup.height() // max(1, popup.sizeHintForRow(0)))
            new_row = min((current_row if current_row >= 0 else 0) + step, row_count - 1)
            self._set_popup_row(new_row)
            logger.debug(f"autocomplete: PageDown -> row {new_row}")
            return True
        if key == Qt.Key_PageUp:
            step = max(1, popup.height() // max(1, popup.sizeHintForRow(0)))
            new_row = max((current_row if current_row >= 0 else 0) - step, 0)
            self._set_popup_row(new_row)
            logger.debug(f"autocomplete: PageUp -> row {new_row}")
            return True
        if key == Qt.Key_Home and not (mods & Qt.ControlModifier):
            self._set_popup_row(0)
            logger.debug("autocomplete: Home -> row 0")
            return True
        if key == Qt.Key_End and not (mods & Qt.ControlModifier):
            self._set_popup_row(row_count - 1)
            logger.debug(f"autocomplete: End -> row {row_count - 1}")
            return True

        # Any other key: let it go to the editor. If it changes text, on_text_changed
        # will refresh the completion; if it's a movement that takes the cursor out of
        # the completion context, the next refresh will hide the popup.
        return False

    def _set_popup_row(self, row: int):
        """Move the popup selection to ``row`` and scroll it into view."""
        popup = self._completer.popup()
        model = popup.model()
        if row < 0 or row >= model.rowCount():
            return
        index = model.index(row, 0)
        popup.setCurrentIndex(index)
        popup.scrollTo(index, QAbstractItemView.EnsureVisible)

    def _on_popup_current_changed(self, current, previous):
        """Diagnostic: log every popup currentIndex change with a short stack."""
        try:
            cur_row = current.row() if current.isValid() else -1
            prev_row = previous.row() if previous.isValid() else -1
        except RuntimeError:
            return
        logger.debug(f"autocomplete.popup currentChanged prev={prev_row} -> cur={cur_row}")

    def _selected_completion(self) -> str:
        """Return the text of the currently-highlighted popup row (empty if none)."""
        popup = self._completer.popup()
        idx = popup.currentIndex()
        if idx.isValid():
            value = popup.model().data(idx)
            if value:
                return str(value)
        # Fallback: first row of the source model. Reached when the popup is
        # visible but nothing is highlighted yet (unusual, but survivable).
        if self._model.rowCount() > 0:
            return str(self._model.data(self._model.index(0, 0)) or "")
        return ""

    def _on_activated(self, arg):
        """QCompleter.activated slot. PySide dispatches either ``str`` or ``QModelIndex``."""
        # Same popup-first / cancel-timer dance as the keyboard accept path —
        # QCompleter emits ``activated`` on mouse click, and if we insert
        # before hiding, the word trigger re-opens the popup immediately.
        popup = self._completer.popup()
        if popup.isVisible():
            popup.hide()
        self._timer.stop()
        if isinstance(arg, str):
            self._insert_completion(arg)
        else:
            # QModelIndex path — same resolution as Enter/Tab.
            completion = self._selected_completion()
            if completion:
                self._insert_completion(completion)

    # -------------------- internals --------------------

    def _classify_trigger(self) -> Optional[str]:
        """Inspect the char before the caret. Returns ``"dot"``, ``"word"``, or None."""
        cursor = self.editor.textCursor()
        position = cursor.position()
        if position == 0:
            return None

        doc = self.editor.document()
        char = doc.characterAt(position - 1)
        if char == ".":
            return "dot"
        if char.isalnum() or char == "_":
            return "word"
        if char in _IDENT_TERMINATORS:
            return None
        # Anything exotic (multibyte punctuation etc.) — safest to skip.
        return None

    def _dispatch_completion(self):
        """Take a snapshot of cursor state and submit a jedi request."""
        if not self._enabled:
            return

        editor = self.editor
        try:
            code = editor.toPlainText()
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1  # jedi is 1-indexed on lines
            column = cursor.columnNumber()  # 0-indexed within the line
            file_path = getattr(editor, "file_path", None)
        except RuntimeError:
            # Editor widget has been destroyed (workspace close / tool reload).
            self._enabled = False
            return

        namespaces = []
        try:
            namespaces = self._namespace_provider() or []
        except Exception as exc:
            logger.debug(f"namespace_provider raised: {exc}")

        # Invalidate any previous request: even if it's mid-flight, its
        # emission will be filtered out by the id check in the receiver.
        if self._pending_runnable is not None:
            self._pending_runnable.cancel()

        self._request_id += 1
        logger.debug(f"autocomplete.dispatch id={self._request_id} line={line} col={column} len={len(code)}")
        runnable = CompletionRunnable(
            engine=self.engine,
            request_id=self._request_id,
            code=code,
            line=line,
            column=column,
            namespaces=namespaces,
            path=file_path,
        )
        runnable.signals.completed.connect(self._on_completion)
        self._pending_runnable = runnable
        QThreadPool.globalInstance().start(runnable)

    def _on_completion(self, request_id: int, items: list):
        """Receive jedi results on the UI thread; show popup if still relevant."""
        if request_id != self._request_id:
            logger.debug(f"autocomplete._on_completion id={request_id} stale (current={self._request_id})")
            return

        if not self._enabled:
            logger.debug(f"autocomplete._on_completion id={request_id} disabled")
            return

        if not items:
            logger.debug(f"autocomplete._on_completion id={request_id} empty")
            self._hide_popup()
            return

        logger.debug(f"autocomplete._on_completion id={request_id} items={len(items)}")

        try:
            # The editor may have moved past the word that triggered this request.
            if self._classify_trigger() is None:
                self._hide_popup()
                return

            self._current_items = items
            names = [item.name for item in items]
            self._model.setStringList(names)

            # Position popup under the current cursor. Expand to fit the widest
            # visible item so long function names aren't clipped.
            rect = self.editor.cursorRect()
            width = self._completer.popup().sizeHintForColumn(0)
            width += self._completer.popup().verticalScrollBar().sizeHint().width()
            rect.setWidth(max(width, 180))
            self._completer.complete(rect)
        except RuntimeError:
            # Editor / completer got torn down between dispatch and delivery.
            self._enabled = False

    def _current_word_prefix(self) -> str:
        """Return the partial identifier the user has typed at the caret.

        We can't use ``QTextCursor.WordUnderCursor`` because that grabs the
        whole word including characters to the right; we want only what's
        left of the caret so QCompleter's prefix filter behaves.
        """
        cursor = self.editor.textCursor()
        pos = cursor.position()
        doc = self.editor.document()

        start = pos
        while start > 0:
            ch = doc.characterAt(start - 1)
            if ch.isalnum() or ch == "_":
                start -= 1
                continue
            break
        return doc.toPlainText()[start:pos] if start < pos else ""

    def _insert_completion(self, completion: str):
        """Replace the current partial word with ``completion``."""
        if not completion:
            return
        cursor = self.editor.textCursor()
        prefix_len = len(self._current_word_prefix())

        # Select the prefix range and overwrite it with the full completion.
        if prefix_len > 0:
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, prefix_len)
            cursor.removeSelectedText()
        cursor.insertText(completion)
        self.editor.setTextCursor(cursor)

    def _hide_popup(self):
        if self._completer.popup().isVisible():
            self._completer.popup().hide()


__all__ = ["AutocompleteController"]
