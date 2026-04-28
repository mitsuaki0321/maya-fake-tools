"""
Autocomplete controller for a single ``PythonEditor`` instance.

Responsibilities:

- Decide *when* to trigger a completion (dot or a printable keystroke while the popup is open)
- Debounce word-triggered requests so fast typing doesn't thrash jedi
- Dispatch requests through ``QThreadPool`` via :class:`CompletionRunnable`
- Filter out stale responses once a newer request has superseded them
- Drive the ``QCompleter`` popup and insert the chosen text on accept

The controller holds no completion state beyond the latest request id and a
cached "last popup was shown here" flag, so a single instance per editor tab
is cheap. The ``JediEngine`` can be (and is) shared between controllers.
"""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import Callable, Optional

from ......lib_ui.qt_compat import (
    QAbstractItemView,
    QApplication,
    QCompleter,
    QEvent,
    QObject,
    QStringListModel,
    Qt,
    QTextCursor,
    QThreadPool,
    QTimer,
    QWidget,
)
from ...command.autocomplete import JEDI_AVAILABLE, JediEngine
from .._common import _OwnerWindowWatcher
from .worker import CompletionRunnable

logger = getLogger(__name__)


class _OutsideClickWatcher(QObject):
    """Closes the autocomplete popup on clicks outside of it.

    Replacement for ``Qt.Popup``'s built-in mouse-grab-and-auto-close
    behaviour. We drop ``Qt.Popup`` in favour of ``Qt.Tool`` so the
    help popup can receive its own mouse events (drag-select, scroll,
    right-click menu), which means the built-in auto-close no longer
    runs. This watcher reinstates it at the application level, with an
    optional ``exception`` widget carved out so clicks into the help
    popup don't dismiss the autocomplete list.

    ``popup_getter`` is re-invoked on every event for the same reason
    as :class:`_OwnerWindowWatcher`: QCompleter may internally swap the
    popup widget (observed after ``setWindowFlags``), so caching a
    reference at construction leaves us dangling.
    """

    def __init__(self, popup_getter: Callable[[], Optional[QWidget]], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._popup_getter = popup_getter
        self._exception: Optional[QWidget] = None
        self._alive = True
        self._installed = False  # idempotency flag — safe to re-install
        self._extra_targets: list[QWidget] = []

    def mark_dead(self) -> None:
        """External teardown signal. Auto-removes event filters via Qt."""
        self._alive = False
        self.uninstall()

    def set_exception(self, widget: Optional[QWidget]) -> None:
        """Mark ``widget`` as a "click-inside" region; ``None`` clears it."""
        self._exception = widget

    def install(self, extra_targets: Optional[list[QWidget]] = None) -> None:
        """Install on QApplication + optional ``extra_targets``. Idempotent."""
        if self._installed:
            return
        app = QApplication.instance()
        if app is None:
            logger.warning("_OutsideClickWatcher: QApplication.instance() is None — filter NOT installed")
            return
        app.installEventFilter(self)
        # Belt-and-suspenders: also register on explicit widgets (editor)
        # in case Maya intercepts application-level events before our
        # filter runs. Same filter object can be installed multiple
        # times; Qt deduplicates per (target, filter) pair.
        for target in extra_targets or ():
            if target is None:
                continue
            with contextlib.suppress(RuntimeError):
                target.installEventFilter(self)
                self._extra_targets.append(target)
        self._installed = True

    def _resolve_popup(self) -> Optional[QWidget]:
        try:
            return self._popup_getter()
        except Exception as exc:
            logger.debug(f"_OutsideClickWatcher popup_getter failed: {exc}")
            return None

    def uninstall(self) -> None:
        """Remove from everywhere we registered. Idempotent."""
        if not self._installed:
            return
        app = QApplication.instance()
        if app is not None:
            with contextlib.suppress(RuntimeError):
                app.removeEventFilter(self)
        for target in self._extra_targets:
            with contextlib.suppress(RuntimeError):
                target.removeEventFilter(self)
        self._extra_targets.clear()
        self._installed = False

    def eventFilter(self, obj, event):
        if not self._alive:
            return False
        # Fast reject: non-mouse-press events are ~all of the traffic here
        # (paint, move, key, etc.). This single comparison is the entire
        # overhead we add to Maya's event loop when nothing else is going
        # on — everything heavier runs only on real mouse presses.
        if event.type() != QEvent.MouseButtonPress:
            return False

        popup = self._resolve_popup()
        if popup is None:
            return False
        try:
            if not popup.isVisible():
                return False
            popup_rect = popup.geometry()
        except RuntimeError:
            # The popup instance we resolved just got torn down between
            # resolve and use — exceedingly rare but Qt/PySide can race
            # here during shutdown. Next event will re-resolve.
            return False

        # Qt5 exposes ``globalPos()``; Qt6 renamed it to ``globalPosition()``.
        # We support Maya 2023 (Qt5) through 2027 (Qt6) so probe both.
        if hasattr(event, "globalPosition"):
            global_pos = event.globalPosition().toPoint()
        else:
            global_pos = event.globalPos()

        if popup_rect.contains(global_pos):
            return False  # click inside autocomplete list — default handling

        exc_widget = self._exception
        if exc_widget is not None:
            try:
                if exc_widget.isVisible() and exc_widget.frameGeometry().contains(global_pos):
                    return False  # click on help popup — keep list open
            except RuntimeError:
                self._exception = None

        try:
            popup.hide()
            logger.debug(
                f"_OutsideClickWatcher hid popup on click at {global_pos.x()},{global_pos.y()} "
                f"(popup_rect={popup_rect.x()},{popup_rect.y()},{popup_rect.width()}x{popup_rect.height()})"
            )
        except RuntimeError:
            pass
        return False


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

        # True while _insert_completion is editing the document. The remove /
        # insertText pair fires textChanged on each half, and the "cursor lands
        # on a dot" moment in the middle would otherwise re-open the popup
        # right after the user just accepted something.
        self._inserting_completion = False

        # Per-session usage counter. Incremented each time the user accepts an
        # item; applied as a positive bias in _apply_mru_sort so recent picks
        # float to the top. Not persisted — resets when the controller is
        # rebuilt (tool reload / editor reopen).
        self._mru: dict[str, int] = {}

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
        # Drop ``Qt.Popup`` (QCompleter's default) in favour of ``Qt.Tool``.
        # Rationale:
        #   * Qt.Popup mouse-grabs globally → every click in the app
        #     (including on our help popup) gets delivered to the
        #     QListView first, and QCompleter then auto-closes its list
        #     because the click is "outside". That blocks help-popup
        #     interaction (text select, scroll, right-click menu).
        #   * Qt.Tool drops the grab → clicks go to the widget under the
        #     cursor. Auto-close-on-outside is re-implemented in
        #     :class:`_OutsideClickWatcher` which also whitelists the
        #     help popup as an exception.
        #
        # NO ``setParent`` call here: reparenting a QCompleter-owned
        # popup to Maya's main window has a history of crashing Maya on
        # workspace teardown (undock → close). ``setWindowFlags`` alone
        # is the safe path.
        #
        # No ``Qt.WindowStaysOnTopHint``: the popup is meant to sit
        # above Maya's windows, not above other applications.
        popup.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Use the untyped overload; the slot detects whether it got a string
        # or a QModelIndex. Connecting via ``activated[str]`` broke in some
        # PySide builds where the signal emission raced with the popup hide.
        self._completer.activated.connect(self._on_activated)

        # Both watchers use a getter that re-resolves the popup widget
        # on every event. QCompleter can replace its popup internally
        # (observed after the ``setWindowFlags`` call above: the original
        # QListView C++ object gets torn down and a new one takes its
        # place on the next ``popup()`` access). Caching the initial
        # reference would leave us holding a dangling pointer and
        # silently no-op'ing all subsequent mouse presses.
        def _get_popup() -> Optional[QWidget]:
            try:
                return self._completer.popup()
            except RuntimeError:
                return None
            except AttributeError:
                return None

        # Replacement for ``Qt.Popup``'s built-in auto-close. Holds an
        # optional exception (the help popup window) so clicks there keep
        # the list alive. We install on QApplication AND on the editor
        # directly — the latter is a safety net in case Maya intercepts
        # application-level mouse events before our filter sees them.
        self._outside_click_watcher = _OutsideClickWatcher(_get_popup, editor)
        self._outside_click_watcher.install(extra_targets=[editor])
        # Hide the popup when Maya's top-level window is minimised,
        # hidden, or deactivated — replaces the "follows parent" behaviour
        # we'd otherwise get from Qt parent ownership (which we avoid
        # because it crashes Maya).
        self._owner_window_watcher = _OwnerWindowWatcher(_get_popup, editor)

        # Short-term cache of the items backing the current popup so we can
        # still know what was selected if the model gets cleared mid-accept.
        self._current_items: list = []

    # -------------------- enable / disable --------------------

    def set_enabled(self, enabled: bool):
        """Toggle completion.

        Disable hides the popup, bumps the request id so a late jedi
        response can't reopen it, **and fully uninstalls the app-level
        mouse event filter** so Maya's event loop runs with zero
        overhead from this controller while autocomplete is off. Enable,
        when flipping from a previously-off state, re-installs the filter
        and checks whether the caret already sits at a natural dot
        trigger (``cmds.|`` and such) to fire a completion immediately —
        so the user doesn't have to delete and retype the ``.`` to see
        the popup after turning autocomplete back on via the toolbar /
        shortcut. Word triggers are intentionally not auto-fired here,
        matching :meth:`on_text_changed`'s policy of not popping on bare
        identifier typing. Guarded by ``editor.hasFocus()`` so background
        tabs don't spawn popups when the setting broadcasts to every tab
        at once.
        """
        was_enabled = self._enabled
        self._enabled = enabled and JEDI_AVAILABLE
        if not self._enabled:
            self._hide_popup()
            self._request_id += 1
            # Detach from all event streams so we cost nothing while off.
            self._outside_click_watcher.uninstall()
            self._owner_window_watcher.detach()
            return
        if was_enabled:
            return
        # Re-enabling: put the filters back. Idempotent — safe if we're
        # called while already installed (e.g. initial ``set_enabled(True)``
        # right after construction).
        self._outside_click_watcher.install(extra_targets=[self.editor])
        try:
            focused = self.editor.hasFocus()
        except RuntimeError:
            return
        if focused and self._classify_trigger() == "dot":
            self._timer.start(0)

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
          intrusive when the user is just writing new code. To complete a
          bare identifier, type a ``.`` (or toggle autocomplete off entirely
          via the toolbar if it's in the way).
        - anything else: hide the popup.
        """
        if not self._enabled:
            return
        if self._inserting_completion:
            # Document edits caused by accepting a completion are not the user
            # typing — suppressing the trigger here keeps the popup closed
            # after accept instead of re-opening on the intermediate dot.
            return

        trigger = self._classify_trigger()
        if trigger is None:
            self._hide_popup()
            return

        if trigger == "dot":
            # A small debounce even on dot — typing ``a.b.c`` would otherwise
            # fire three back-to-back jedi dispatches; coalescing them costs no
            # perceivable popup latency and avoids namespace snapshotting on
            # every character.
            self._timer.start(min(30, self._debounce_ms))
            return

        # trigger == "word": only refresh an already-open popup. Typing a bare
        # identifier without a preceding dot should not auto-open the popup.
        if self._completer.popup().isVisible():
            self._timer.start(self._debounce_ms)

    def handle_key_press(self, event) -> bool:
        """Called before the editor's default ``keyPressEvent``.

        Returns True to consume the key. Popup navigation and the explicit
        accept keys (Tab / Enter / Return) are claimed here rather than
        delegated to QCompleter's event filter — the filter is inconsistent
        across Qt versions / widget types for QPlainTextEdit, and this way
        the behaviour is testable and diagnosable through a single code
        path.

        **Accept is strictly Tab / Enter / Return.** Previously ``.``,
        ``(``, ``,``, and ``=`` would also commit the highlighted item and
        type through — a "commit character" shortcut borrowed from other
        editors — but that caused surprise inserts whenever the ranked top
        item wasn't what the user was typing (e.g. typing ``cmds.ls(``
        inserted ``cmds.ActivateGlobalScreenSlider(`` because the top row
        happened to match the ``ls`` substring). Removing commit chars
        means the user's typed text survives verbatim; they only get a
        completion when they explicitly ask for one with Tab / Enter.
        """
        key = event.key()
        mods = event.modifiers()

        popup = self._completer.popup()
        if not popup.isVisible():
            return False

        row_count = popup.model().rowCount()
        current_row = popup.currentIndex().row()

        if key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
            item = self._selected_item()
            # Hide before inserting: the insertion fires contentsChange, and
            # if the popup were still flagged as visible at that moment the
            # word-trigger branch in on_text_changed would re-open it with
            # the freshly inserted suffix as a sole candidate.
            popup.hide()
            # Cancel any pending debounced dispatch scheduled before the
            # accept, for the same reason.
            self._timer.stop()
            if item is not None:
                self._insert_completion(item)
            return True

        if key == Qt.Key_Escape:
            popup.hide()
            return True

        # Explicitly drive popup navigation from our side. Relying on
        # QCompleter's built-in event filter for this turned out to be
        # unreliable with QPlainTextEdit (up/down appeared to move selection
        # briefly then snap back), so we manage currentIndex here ourselves.
        if key == Qt.Key_Down:
            new_row = 0 if current_row < 0 else min(current_row + 1, row_count - 1)
            self._set_popup_row(new_row)
            return True
        if key == Qt.Key_Up:
            new_row = row_count - 1 if current_row < 0 else max(current_row - 1, 0)
            self._set_popup_row(new_row)
            return True
        if key == Qt.Key_PageDown:
            step = max(1, popup.height() // max(1, popup.sizeHintForRow(0)))
            new_row = min((current_row if current_row >= 0 else 0) + step, row_count - 1)
            self._set_popup_row(new_row)
            return True
        if key == Qt.Key_PageUp:
            step = max(1, popup.height() // max(1, popup.sizeHintForRow(0)))
            new_row = max((current_row if current_row >= 0 else 0) - step, 0)
            self._set_popup_row(new_row)
            return True
        if key == Qt.Key_Home and not (mods & Qt.ControlModifier):
            self._set_popup_row(0)
            return True
        if key == Qt.Key_End and not (mods & Qt.ControlModifier):
            self._set_popup_row(row_count - 1)
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

    def _selected_item(self):
        """Return the full ``CompletionItem`` for the highlighted popup row.

        The popup model only holds the display name; we need the jedi
        metadata (``type``, etc.) to decide whether to auto-insert ``()`` on
        accept, so we re-read it from ``_current_items`` using the popup row.
        Falls back to row 0 when nothing is highlighted.
        """
        popup = self._completer.popup()
        idx = popup.currentIndex()
        row = idx.row() if idx.isValid() else 0
        if 0 <= row < len(self._current_items):
            return self._current_items[row]
        return None

    # -------------------- public API for the help popup --------------------

    def is_popup_visible(self) -> bool:
        """True iff the autocomplete popup is currently shown."""
        return self._completer.popup().isVisible()

    def selected_item(self):
        """Public wrapper around :meth:`_selected_item`.

        The help popup needs the currently-highlighted :class:`CompletionItem`
        to decide what to fetch docstring for.
        """
        return self._selected_item()

    def popup_widget(self):
        """Return the autocomplete popup widget (QListView).

        Used by the help popup controller to install an event filter
        that ties help-popup lifetime to autocomplete-popup state
        changes (Show / Hide).
        """
        return self._completer.popup()

    def popup_global_rect(self):
        """Rectangle of the autocomplete popup in global screen coords.

        The help popup uses this to anchor itself beside the list without
        overlapping. Returns ``None`` when the list isn't visible.
        """
        popup = self._completer.popup()
        if not popup.isVisible():
            return None
        top_left = popup.mapToGlobal(popup.rect().topLeft())
        return popup.rect().translated(top_left)

    def set_help_popup_widget(self, widget) -> None:
        """Register a help popup window to exclude from outside-click-close.

        While the help popup is visible, clicks inside it are treated as
        "inside" by :class:`_OutsideClickWatcher` — the autocomplete list
        stays open when the user scrolls, selects text, or opens the
        context menu inside the help panel. Pass ``None`` to clear.
        """
        self._outside_click_watcher.set_exception(widget)

    def connect_popup_selection_changed(self, slot) -> bool:
        """Connect ``slot`` to the popup's selection-model ``currentChanged``.

        Returns ``True`` when the connection took, ``False`` if the popup
        hasn't been set up yet (slot simply won't fire). The slot receives
        the usual ``(QModelIndex, QModelIndex)`` pair from Qt — callers
        re-query :meth:`selected_item` for the actual data.
        """
        sel_model = self._completer.popup().selectionModel()
        if sel_model is None:
            return False
        sel_model.currentChanged.connect(slot)
        return True

    def disconnect_popup_selection_changed(self, slot) -> None:
        """Best-effort disconnect matching :meth:`connect_popup_selection_changed`."""
        with contextlib.suppress(Exception):
            sel_model = self._completer.popup().selectionModel()
            if sel_model is not None:
                sel_model.currentChanged.disconnect(slot)

    def synthesize_accepted_source(self, item) -> tuple[str, int, int]:
        """Return ``(code, line, column)`` as if ``item`` were just accepted.

        Used by the help popup so ``jedi.Script.help`` can resolve the
        currently-highlighted candidate — the partial word the user has
        typed isn't enough on its own, jedi needs to see the full name
        in the source. ``line`` is 1-indexed, ``column`` 0-indexed
        (jedi's convention).
        """
        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        caret = cursor.position()
        prefix_len = self._current_word_prefix_length()
        start = caret - prefix_len
        name = getattr(item, "name", "") or ""
        new_text = text[:start] + name + text[caret:]
        end_pos = start + len(name)
        before = new_text[:end_pos]
        line = before.count("\n") + 1
        last_nl = before.rfind("\n")
        column = end_pos - (last_nl + 1) if last_nl >= 0 else end_pos
        return new_text, line, column

    def _on_activated(self, arg):
        """QCompleter.activated slot. PySide dispatches either ``str`` or ``QModelIndex``."""
        # Same popup-first / cancel-timer dance as the keyboard accept path —
        # QCompleter emits ``activated`` on mouse click, and if we insert
        # before hiding, the word trigger re-opens the popup immediately.
        popup = self._completer.popup()
        if popup.isVisible():
            popup.hide()
        self._timer.stop()

        item = None
        if isinstance(arg, str):
            # Match the string back to the underlying item so accept-time
            # behaviour (auto-parens, MRU) can see the ``type`` field.
            for candidate in self._current_items:
                if candidate.name == arg:
                    item = candidate
                    break
        else:
            item = self._selected_item()

        if item is not None:
            self._insert_completion(item)

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
            # A dot preceded by a digit is a numeric literal (``0.``, ``1.5``),
            # not an attribute access — popping the completer here is noise.
            if position >= 2 and doc.characterAt(position - 2).isdigit():
                return None
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
        runnable = CompletionRunnable(
            engine=self.engine,
            request_id=self._request_id,
            code=code,
            line=line,
            column=column,
            namespaces=namespaces,
            path=file_path,
            mru=self._mru,
        )
        runnable.signals.completed.connect(self._on_completion)
        self._pending_runnable = runnable
        QThreadPool.globalInstance().start(runnable)

    def _on_completion(self, request_id: int, items: list):
        """Receive jedi results on the UI thread; show popup if still relevant."""
        # Stale / disabled / empty — all silent. A previous verbose log here
        # was useful while chasing feedback loops but fires several times per
        # keystroke in steady state.
        if request_id != self._request_id or not self._enabled:
            return
        if not items:
            self._hide_popup()
            return

        try:
            # The editor may have moved past the word that triggered this request.
            if self._classify_trigger() is None:
                self._hide_popup()
                return

            # Engine already applied the MRU boost (before its cap), so items
            # arrive here in final display order.
            self._current_items = items
            names = [item.name for item in items]
            self._model.setStringList(names)

            popup = self._completer.popup()
            # Mirror the editor's current font (family + zoomed size) before
            # measuring, so sizeHintForColumn reflects the font actually used
            # to render the list. This has to happen per-show because
            # Ctrl+Wheel / Ctrl+= can change the editor font at any time.
            popup.setFont(self.editor.font())

            # Position popup under the current cursor. Expand to fit the widest
            # visible item so long function names aren't clipped.
            rect = self.editor.cursorRect()
            width = popup.sizeHintForColumn(0)
            width += popup.verticalScrollBar().sizeHint().width()
            rect.setWidth(max(width, 180))
            # Re-anchor the Maya-main-window watcher right before the
            # popup becomes visible. ``editor.window()`` changes between
            # docked and floating states, so we look it up fresh each
            # time rather than caching at construction.
            self._owner_window_watcher.attach(self.editor.window() or self.editor)
            self._completer.complete(rect)
            # Highlight the first row so Enter/Tab accepts the obvious match
            # without the user having to press Down first.
            self._set_popup_row(0)
        except RuntimeError:
            # Editor / completer got torn down between dispatch and delivery.
            self._enabled = False

    def _current_word_prefix_length(self) -> int:
        """Return how many chars left of the caret belong to the current identifier.

        We only ever need the length (to know how much to delete before
        inserting the completion), so we walk back char-by-char and stop at
        the first non-identifier char. Avoids ``doc.toPlainText()``'s full-
        document string allocation on every accept.
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
        return pos - start

    def _insert_completion(self, item):
        """Replace the current partial word with ``item``'s name and record MRU."""
        name = getattr(item, "name", "")
        if not name:
            return

        cursor = self.editor.textCursor()
        prefix_len = self._current_word_prefix_length()

        # Flag the document mutation as "not user typing" so on_text_changed
        # doesn't re-dispatch on the intermediate state after removeSelectedText.
        self._inserting_completion = True
        try:
            if prefix_len > 0:
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, prefix_len)
                cursor.removeSelectedText()
            cursor.insertText(name)
            self.editor.setTextCursor(cursor)
        finally:
            self._inserting_completion = False

        # Record for MRU re-ranking on subsequent popups in this session.
        self._mru[name] = self._mru.get(name, 0) + 1

    def _hide_popup(self):
        if self._completer.popup().isVisible():
            self._completer.popup().hide()


__all__ = ["AutocompleteController"]
