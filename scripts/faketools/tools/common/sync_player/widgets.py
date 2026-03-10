"""Sync Player custom widgets."""

from __future__ import annotations

from pathlib import Path

from ....lib_ui import icons
from ....lib_ui.qt_compat import (
    QColor,
    QFont,
    QIcon,
    QLabel,
    QPainter,
    QPen,
    QRect,
    QSize,
    QSlider,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QVideoWidget,
    QWidget,
    Signal,
)
from ....lib_ui.ui_utils import scale_by_dpi

ICONS_DIR = str(Path(__file__).parent / "icons")


class LoopRangeBar(QWidget):
    """Dedicated A-B loop range bar with draggable markers."""

    loop_in_changed = Signal(int)
    loop_out_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop_in_ms: int | None = None
        self._loop_out_ms: int | None = None
        self._total_ms: int = 0
        self._dragging: str | None = None
        self.setMouseTracking(True)
        self.setFixedHeight(int(scale_by_dpi(16, self)))

    def set_loop_markers(self, loop_in: int | None, loop_out: int | None, total_ms: int) -> None:
        """Update A-B loop marker positions.

        Args:
            loop_in: A point in milliseconds, or None.
            loop_out: B point in milliseconds, or None.
            total_ms: Total duration in milliseconds.
        """
        self._loop_in_ms = loop_in
        self._loop_out_ms = loop_out
        self._total_ms = total_ms
        self.update()

    def set_total_ms(self, ms: int) -> None:
        """Update total duration.

        Args:
            ms: Total duration in milliseconds.
        """
        self._total_ms = ms
        self.update()

    def _value_to_pixel(self, ms: int) -> int:
        if self._total_ms <= 0:
            return 0
        return int(ms / self._total_ms * self.width())

    def _pixel_to_value(self, px: int) -> int:
        if self.width() <= 0 or self._total_ms <= 0:
            return 0
        ratio = max(0.0, min(1.0, px / self.width()))
        return int(ratio * self._total_ms)

    def _hit_test(self, x: int) -> str | None:
        if self._loop_in_ms is None or self._loop_out_ms is None:
            return None
        grab_px = int(scale_by_dpi(6, self))
        x_a = self._value_to_pixel(self._loop_in_ms)
        x_b = self._value_to_pixel(self._loop_out_ms)
        dist_a = abs(x - x_a)
        dist_b = abs(x - x_b)
        if dist_a <= grab_px and dist_b <= grab_px:
            return "in" if dist_a <= dist_b else "out"
        if dist_a <= grab_px:
            return "in"
        if dist_b <= grab_px:
            return "out"
        return None

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test(event.pos().x())
            if hit:
                self._dragging = hit
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            value = self._pixel_to_value(event.pos().x())
            value = max(0, min(self._total_ms, value))
            if self._dragging == "in" and self._loop_out_ms is not None:
                value = min(value, self._loop_out_ms - 1)
                self.loop_in_changed.emit(max(0, value))
            elif self._dragging == "out" and self._loop_in_ms is not None:
                value = max(value, self._loop_in_ms + 1)
                self.loop_out_changed.emit(min(self._total_ms, value))
            event.accept()
            return
        if self._loop_in_ms is not None and self._loop_out_ms is not None:
            if self._hit_test(event.pos().x()):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self.unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self._loop_in_ms is None or self._loop_out_ms is None:
            return
        w = self.width()
        h = self.height()
        x_a = self._value_to_pixel(self._loop_in_ms)
        x_b = self._value_to_pixel(self._loop_out_ms)
        disabled = not self.isEnabled()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors
        accent = QColor("#555555") if disabled else QColor("#4A9EFF")
        highlight = QColor(85, 85, 85, 60) if disabled else QColor(74, 158, 255, 90)

        # Rail line
        rail_h = max(1, int(scale_by_dpi(3, self)))
        rail_y = (h - rail_h) // 2
        painter.fillRect(QRect(0, rail_y, w, rail_h), QColor("#2A2A2A"))

        # A-B highlight
        painter.fillRect(QRect(x_a, rail_y, x_b - x_a, rail_h), highlight)

        # A line
        line_w = max(1, int(scale_by_dpi(2, self)))
        pen = QPen(accent)
        pen.setWidth(line_w)
        painter.setPen(pen)
        painter.drawLine(x_a, 0, x_a, h)

        # B line
        painter.drawLine(x_b, 0, x_b, h)

        # A/B labels
        font_size = max(1, int(scale_by_dpi(11, self)))
        font = QFont()
        font.setPixelSize(font_size)
        font.setBold(True)
        painter.setFont(font)

        label_offset = int(scale_by_dpi(2, self))
        fm = painter.fontMetrics()
        painter.drawText(x_a + label_offset, font_size, "A")
        painter.drawText(x_b - label_offset - fm.horizontalAdvance("B"), font_size, "B")

        painter.end()


class OffsetSpinBox(QSpinBox):
    """QSpinBox that returns focus to a target widget on Enter/Escape or focus loss."""

    def __init__(self, focus_widget: QWidget, parent=None):
        super().__init__(parent)
        self._focus_widget = focus_widget

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._focus_widget.setFocus()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if event.reason() != Qt.FocusReason.ActiveWindowFocusReason:
            self._focus_widget.setFocus()


class SeekSlider(QSlider):
    """Seek slider with click-to-jump behavior."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum() and self.width() > 0:
            ratio = max(0.0, min(1.0, event.pos().x() / self.width()))
            value = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
            self.setValue(value)
        super().mousePressEvent(event)


class PlaceholderWidget(QWidget):
    """Empty-state placeholder with icon and instruction text."""

    open_requested = Signal()

    def __init__(self, focus_widget: QWidget, parent=None):
        super().__init__(parent)
        self._focus_widget = focus_widget
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#0D0D0D"))
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Monitor icon
        icon_size = int(scale_by_dpi(64, self))
        icon_path = icons.get_path("monitor", base_dir=ICONS_DIR)
        pixmap = QIcon(icon_path).pixmap(QSize(icon_size, icon_size))
        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Instruction text
        font_size = max(11, int(scale_by_dpi(13, self)))
        text_label = QLabel("Double-click to open")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"color: rgba(255, 255, 255, 0.4); font-size: {font_size}px;")
        layout.addWidget(text_label)

    def mousePressEvent(self, event):
        self._focus_widget.setFocus()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.open_requested.emit()


class VideoWidget(QVideoWidget):
    """QVideoWidget with double-click to open and focus redirect."""

    open_requested = Signal()

    def __init__(self, focus_widget: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self._focus_widget = focus_widget
        self.setStyleSheet("background-color: #0D0D0D;")

    def mousePressEvent(self, event):
        self._focus_widget.setFocus()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.open_requested.emit()
