"""
Line number area widget for the code editor.
Displays line numbers and fold indicators alongside the code editor.
"""

from ......lib_ui.qt_compat import (
    QColor,
    QPainter,
    QPen,
    QPointF,
    QPolygonF,
    Qt,
    QTimer,
    QWidget,
)
from ...themes import AppTheme

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
        return self.calculate_width()

    def calculate_width(self):
        """Calculate the width needed for line numbers and fold gutter.

        Layout: ``[ line_numbers | fold_gutter | spacing(1char) | code ]``
        """
        editor = self.code_editor
        digits = 1
        max_num = max(1, editor.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        char_width = editor.fontMetrics().horizontalAdvance("9")
        extra_spacing = editor.fontMetrics().horizontalAdvance(" ")
        return 3 + char_width * digits + extra_spacing + self._fold_gutter_width()

    def _fold_gutter_width(self):
        """Return the width of the fold indicator gutter area."""
        return self.code_editor.fontMetrics().horizontalAdvance("9") + 4

    def _fold_gutter_x(self):
        """Return the X coordinate where the fold gutter column starts."""
        spacing = self.code_editor.fontMetrics().horizontalAdvance(" ")
        return self.width() - spacing - self._fold_gutter_width()

    def paintEvent(self, event):
        """Paint line numbers and fold indicators."""
        editor = self.code_editor
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(AppTheme.LINE_NUMBER_BACKGROUND))
        painter.setFont(editor.font())

        block = editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        bottom = top + editor.blockBoundingRect(block).height()
        current_block_number = editor.textCursor().blockNumber()

        single_line_height = painter.fontMetrics().height()

        # Layout: [ line_numbers | fold_gutter | spacing(1char) | code ]
        fold_gutter_w = self._fold_gutter_width()
        spacing = editor.fontMetrics().horizontalAdvance(" ")
        line_number_draw_width = self.width() - spacing - fold_gutter_w
        fold_gutter_x = line_number_draw_width

        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                if block_number == current_block_number:
                    painter.setPen(QColor(AppTheme.LINE_NUMBER_ACTIVE))
                else:
                    painter.setPen(QColor(AppTheme.LINE_NUMBER_INACTIVE))
                painter.drawText(0, int(top), line_number_draw_width, single_line_height, Qt.AlignRight, number)

                self._draw_fold_indicator(painter, block_number, fold_gutter_x, int(top), fold_gutter_w + spacing, single_line_height)

            block = block.next()
            top = bottom
            bottom = top + editor.blockBoundingRect(block).height()
            block_number += 1

    def _draw_fold_indicator(self, painter, block_number, x, y, width, height):
        """Draw a VSCode-style chevron fold indicator for a block.

        Args:
            painter (QPainter): Active painter on this widget.
            block_number (int): Current block number.
            x (int): Left edge of the fold gutter area.
            y (int): Top of the block.
            width (int): Width of the fold gutter area.
            height (int): Single line height.
        """
        fold_manager = self.code_editor.fold_manager
        if not fold_manager.is_fold_header(block_number):
            return

        is_folded = fold_manager.is_folded(block_number)

        # Folded indicators are always fully visible; unfolded ones fade with hover.
        if not is_folded and self._indicator_opacity <= 0.0:
            return

        if block_number == self._hover_fold_block:
            color = QColor(AppTheme.FOLD_INDICATOR_HOVER)
        else:
            color = QColor(AppTheme.FOLD_INDICATOR_COLOR)

        if not is_folded:
            color.setAlphaF(self._indicator_opacity)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Stroke-based chevron (VSCode style) — no fill.
        pen = QPen(color, 1.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        padding = 2
        half_w = max(3, (width - padding * 2) // 2)
        cx = x + width // 2
        cy = y + height // 2
        s = half_w * 0.5

        if is_folded:
            # Right-pointing chevron ›
            painter.drawPolyline(
                QPolygonF(
                    [
                        QPointF(cx - s * 0.35, cy - s),
                        QPointF(cx + s * 0.55, cy),
                        QPointF(cx - s * 0.35, cy + s),
                    ]
                )
            )
        else:
            # Down-pointing chevron ˅
            painter.drawPolyline(
                QPolygonF(
                    [
                        QPointF(cx - s, cy - s * 0.35),
                        QPointF(cx, cy + s * 0.55),
                        QPointF(cx + s, cy - s * 0.35),
                    ]
                )
            )

        painter.restore()

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
            # Shift+Click: recursive fold/unfold
            if event.modifiers() & Qt.ShiftModifier:
                self.code_editor.fold_manager.toggle_fold_recursive(block_number)
            else:
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
