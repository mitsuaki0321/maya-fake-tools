"""
Multi-cursor mixin for ``CodeEditor``.

Thin facade: this module keeps the public API (``init_multi_cursor``,
``handle_multi_cursor_keys``, etc.) that external callers already rely on,
while delegating the actual work to three composition partners:

- ``MultiCursorController`` — state transitions and rectangle selection
- ``MultiCursorPainter``    — on-screen drawing
- ``MultiCursorInputHandler`` — mouse / key dispatch across cursors

Keeping a mixin here (rather than breaking the API) avoids a sweeping change to
every call site. The three helpers each own their own module so they can be
read, modified, and in future tested independently.
"""

from __future__ import annotations

from .......lib_ui.qt_compat import QColor, QKeySequence, QShortcut, Signal
from ....themes import AppTheme
from .controller import MultiCursorController
from .input import MultiCursorInputHandler
from .painter import MultiCursorPainter


class MultiCursorMixin:
    """
    Adds VSCode-style multi-cursor editing to ``QPlainTextEdit`` subclasses.

    Features: Ctrl+Click, Ctrl+D, Ctrl+Shift+L, Alt+Shift+I, and synchronized
    editing across all cursors. State (``all_cursors``, ``search_text``, ...)
    is stored on the editor itself so that external callers like the search
    dialog can inspect it directly.
    """

    multi_cursor_status = Signal(str)

    def init_multi_cursor(self):
        """Initialise multi-cursor state and attach the helper objects."""
        # Cursor collection and meta
        self.all_cursors = []
        self.search_text = ""
        self.initial_selection_done = False
        self.last_cursor_position = None

        # Ctrl+drag tracking
        self.ctrl_drag_start = None
        self.is_ctrl_dragging = False
        self.ctrl_drag_cursor = None

        # Middle-click rectangle selection tracking
        self.rect_selection_start = None
        self.rect_selection_end = None
        self.is_rect_selecting = False
        self.rect_selection_left_to_right = True
        self.rect_start_col = 0
        self.rect_end_col = 0

        # Visual palette
        self.multi_cursor_color = QColor(*AppTheme.MULTI_CURSOR_COLOR)
        self.multi_selection_color = QColor(*AppTheme.MULTI_SELECTION_COLOR)
        self.rect_selection_color = QColor(*AppTheme.RECT_SELECTION_COLOR)

        # Remember the standard cursor width so we can restore it on exit
        self.original_cursor_width = self.cursorWidth()

        # Composition: logic / paint / input
        self._mc_controller = MultiCursorController(self)
        self._mc_painter = MultiCursorPainter(self)
        self._mc_input = MultiCursorInputHandler(self, self._mc_controller)

        self.setup_multi_cursor_shortcuts()

    def setup_multi_cursor_shortcuts(self):
        """Wire keyboard shortcuts that don't need to go through the input handler."""
        # Ctrl+D is handled in the editor's key pressed flow; shortcuts here are
        # one-shot helpers that never interfere with per-cursor editing.
        shortcut_all = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        shortcut_all.activated.connect(self.select_all_occurrences)

        shortcut_line_ends = QShortcut(QKeySequence("Alt+Shift+I"), self)
        shortcut_line_ends.activated.connect(self.add_cursors_to_line_ends)

    # -------------------- Public API (delegated) --------------------

    def clear_multi_cursors(self):
        self._mc_controller.clear()

    def add_next_occurrence(self):
        self._mc_controller.add_next_occurrence()

    def select_all_occurrences(self):
        self._mc_controller.select_all_occurrences()

    def add_cursors_to_line_ends(self):
        self._mc_controller.add_cursors_to_line_ends()

    def handle_multi_cursor_mouse_press(self, event) -> bool:
        return self._mc_input.handle_mouse_press(event)

    def handle_multi_cursor_mouse_move(self, event) -> bool:
        return self._mc_input.handle_mouse_move(event)

    def handle_multi_cursor_mouse_release(self, event) -> bool:
        return self._mc_input.handle_mouse_release(event)

    def handle_multi_cursor_keys(self, event) -> bool:
        return self._mc_input.handle_keys(event)

    def paint_multi_cursors(self, painter):
        self._mc_painter.paint(painter)

    def start_rectangle_selection(self, event):
        self._mc_controller.start_rectangle_selection(event)

    def update_rectangle_selection(self, event):
        self._mc_controller.update_rectangle_selection(event)

    def finalize_rectangle_selection(self, event):
        self._mc_controller.finalize_rectangle_selection(event)

    def _merge_overlapping_cursors(self):
        """Kept for any legacy internal caller; prefer the controller directly."""
        self._mc_controller.merge_overlapping()
