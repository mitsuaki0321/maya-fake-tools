"""
Line number area widget for the code editor.
Displays line numbers and fold indicators alongside the code editor.
"""

from .....lib_ui.qt_compat import Qt, QTimer, QWidget

# Fade animation settings
_FADE_DURATION_MS = 150  # Total animation duration
_FADE_INTERVAL_MS = 16  # ~60 FPS update interval
_FADE_STEPS = _FADE_DURATION_MS // _FADE_INTERVAL_MS


class LineNumberArea(QWidget):
    """Widget that displays line numbers and fold indicators for the code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
        self.setMouseTracking(True)
        self._hover_fold_block = -1  # Block number under mouse hover (-1 = none)
        self._hover_gutter = False  # True when mouse is over the fold gutter column

        # Fade animation state (0.0 = hidden, 1.0 = fully visible)
        self._indicator_opacity = 0.0
        self._fade_target = 0.0  # Target opacity
        self._fade_step = 0.0  # Opacity change per tick
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(_FADE_INTERVAL_MS)
        self._fade_timer.timeout.connect(self._fade_tick)

    def sizeHint(self):
        """Return the size hint for the line number area."""
        return self.code_editor.lineNumberAreaWidth()

    def paintEvent(self, event):
        """Paint the line numbers and fold indicators."""
        self.code_editor.lineNumberAreaPaintEvent(event)

    def _fold_gutter_x(self):
        """Return the X coordinate where the fold gutter column starts."""
        spacing = self.code_editor.fontMetrics().horizontalAdvance("  ")
        return self.width() - spacing - self.code_editor._fold_gutter_width()

    def _start_fade(self, target):
        """Start fade animation towards target opacity.

        Args:
            target (float): Target opacity (0.0 or 1.0).
        """
        if target == self._fade_target:
            return
        self._fade_target = target
        steps = max(1, _FADE_STEPS)
        self._fade_step = (target - self._indicator_opacity) / steps
        if not self._fade_timer.isActive():
            self._fade_timer.start()

    def _fade_tick(self):
        """Advance one step of the fade animation."""
        self._indicator_opacity += self._fade_step
        # Clamp and check if done
        if (
            self._fade_step > 0
            and self._indicator_opacity >= self._fade_target
            or self._fade_step < 0
            and self._indicator_opacity <= self._fade_target
        ):
            self._indicator_opacity = self._fade_target
            self._fade_timer.stop()
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse click on fold indicators."""
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        # Check if the click is in the fold gutter area (right of line numbers)
        if event.pos().x() < self._fold_gutter_x():
            super().mousePressEvent(event)
            return

        # Determine which block was clicked
        block_number = self._block_number_at_y(event.pos().y())
        if block_number >= 0 and hasattr(self.code_editor, "fold_manager") and self.code_editor.fold_manager.is_fold_header(block_number):
            self.code_editor.fold_manager.toggle_fold(block_number)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse hover to highlight fold indicators."""
        in_gutter = event.pos().x() >= self._fold_gutter_x()
        old_hover = self._hover_fold_block
        old_gutter = self._hover_gutter

        self._hover_gutter = in_gutter

        if in_gutter:
            block_number = self._block_number_at_y(event.pos().y())
            if block_number >= 0 and hasattr(self.code_editor, "fold_manager") and self.code_editor.fold_manager.is_fold_header(block_number):
                self._hover_fold_block = block_number
                self.setCursor(Qt.PointingHandCursor)
            else:
                self._hover_fold_block = -1
                self.setCursor(Qt.PointingHandCursor)
        else:
            self._hover_fold_block = -1
            self.unsetCursor()

        # Trigger fade animation on gutter hover state change
        if old_gutter != self._hover_gutter:
            self._start_fade(1.0 if in_gutter else 0.0)

        if old_hover != self._hover_fold_block:
            self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear hover state when mouse leaves the widget."""
        if self._hover_fold_block != -1 or self._hover_gutter:
            self._hover_fold_block = -1
            self._hover_gutter = False
            self._start_fade(0.0)
        super().leaveEvent(event)

    def _block_number_at_y(self, y):
        """Determine the block number at a given Y coordinate.

        Args:
            y (int): Y coordinate in widget space.

        Returns:
            int: Block number, or -1 if not found.
        """
        block = self.code_editor.firstVisibleBlock()
        top = self.code_editor.blockBoundingGeometry(block).translated(self.code_editor.contentOffset()).top()

        while block.isValid():
            if not block.isVisible():
                block = block.next()
                continue
            block_height = self.code_editor.blockBoundingRect(block).height()
            bottom = top + block_height
            if top <= y < bottom:
                return block.blockNumber()
            top = bottom
            block = block.next()

        return -1
