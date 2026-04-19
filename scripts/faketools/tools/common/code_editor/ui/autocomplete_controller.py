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
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        popup = self._completer.popup()
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        popup.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._completer.activated[str].connect(self._insert_completion)

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
        """Editor's ``textChanged`` entry point.

        Decides whether to schedule a request based on the character right
        before the caret. The popup is only driven from this side — key press
        handling deals with accept/navigate, not with opening.
        """
        if not self._enabled:
            return

        trigger = self._classify_trigger()
        if trigger is None:
            self._hide_popup()
            return
        if trigger == "dot":
            self._timer.start(0)
        else:
            self._timer.start(self._debounce_ms)

    def handle_key_press(self, event) -> bool:
        """Called before the editor's default ``keyPressEvent``.

        Returns True to consume the key. Popup navigation keys (Enter / Tab /
        Escape / arrows when popup visible) are claimed; Ctrl+Space is
        claimed to force a request.
        """
        # Ctrl+Space always forces a completion, regardless of popup state.
        if event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier and self._enabled:
            # Skip debounce on manual trigger; user is waiting.
            self._timer.stop()
            self._dispatch_completion()
            return True

        popup = self._completer.popup()
        if not popup.isVisible():
            return False

        key = event.key()
        if key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
            idx = popup.currentIndex()
            if not idx.isValid():
                idx = self._model.index(0, 0)
            if idx.isValid():
                completion = self._model.data(idx)
                self._insert_completion(completion)
            popup.hide()
            return True
        if key == Qt.Key_Escape:
            popup.hide()
            return True
        # Let arrow keys pass through to QCompleter's popup so it can navigate.
        return False

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
        code = editor.toPlainText()
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1  # jedi is 1-indexed on lines
        column = cursor.columnNumber()  # 0-indexed within the line

        namespaces = []
        try:
            namespaces = self._namespace_provider() or []
        except Exception as exc:
            logger.debug(f"namespace_provider raised: {exc}")

        file_path = getattr(editor, "file_path", None)

        # Invalidate any previous request: even if it's mid-flight, its
        # emission will be filtered out by the id check in the receiver.
        if self._pending_runnable is not None:
            self._pending_runnable.cancel()

        self._request_id += 1
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
            # A newer request has superseded this one; ignore the stale result.
            return

        if not self._enabled:
            return

        if not items:
            self._hide_popup()
            return

        # The editor may have moved beyond the word that triggered this
        # request. If so, don't pop open a list that no longer matches.
        prefix = self._current_word_prefix()
        if self._classify_trigger() is None:
            self._hide_popup()
            return

        self._current_items = items
        names = [item.name for item in items]
        self._model.setStringList(names)
        self._completer.setCompletionPrefix(prefix)

        # Position popup under the current cursor. Expand to fit the widest
        # visible item so long function names aren't clipped.
        rect = self.editor.cursorRect()
        width = self._completer.popup().sizeHintForColumn(0)
        width += self._completer.popup().verticalScrollBar().sizeHint().width()
        rect.setWidth(max(width, 180))
        self._completer.complete(rect)

        # Pre-select the first row so Enter/Tab accepts without needing arrow.
        popup = self._completer.popup()
        if popup.model().rowCount() > 0:
            popup.setCurrentIndex(popup.model().index(0, 0))

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
