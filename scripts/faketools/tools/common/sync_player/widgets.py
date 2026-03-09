"""Sync Player custom widgets."""

from __future__ import annotations

from pathlib import Path

from ....lib_ui import icons
from ....lib_ui.qt_compat import (
    QColor,
    QFont,
    QFrame,
    QGraphicsScene,
    QGraphicsVideoItem,
    QGraphicsView,
    QIcon,
    QLabel,
    QPainter,
    QPen,
    QPointF,
    QRect,
    QSize,
    QSlider,
    QSpinBox,
    Qt,
    QTransform,
    QVBoxLayout,
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


_ZOOM_FACTOR = 1.15
_ZOOM_MAX = 20.0


class VideoGraphicsView(QGraphicsView):
    """QGraphicsView hosting a QGraphicsVideoItem with flip, pan, and zoom support."""

    open_requested = Signal()

    def __init__(self, focus_widget: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self._focus_widget = focus_widget
        self._flip_h = False
        self._flip_v = False
        self._zoom_level = 1.0

        # Alt+Middle-drag pan state
        self._pan_last_pos: QPointF | None = None
        # Alt+Right-drag zoom state
        self._drag_zoom_start_pos: QPointF | None = None
        self._drag_zoom_start_level: float = 1.0
        self._drag_zoom_anchor_view: QPointF | None = None

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._video_item = QGraphicsVideoItem()
        self._scene.addItem(self._video_item)
        self._video_item.nativeSizeChanged.connect(self._fit_video)

        # Appearance
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #0D0D0D;")
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

    @property
    def video_item(self) -> QGraphicsVideoItem:
        """The underlying QGraphicsVideoItem (pass to VideoPlayerCore)."""
        return self._video_item

    @property
    def flip_h(self) -> bool:
        """Current horizontal flip state."""
        return self._flip_h

    @property
    def flip_v(self) -> bool:
        """Current vertical flip state."""
        return self._flip_v

    def set_flip(self, horizontal: bool, vertical: bool) -> None:
        """Apply horizontal / vertical flip via QTransform on the video item.

        Args:
            horizontal: True to mirror left-right.
            vertical: True to mirror top-bottom.
        """
        self._flip_h = horizontal
        self._flip_v = vertical
        sx = -1.0 if horizontal else 1.0
        sy = -1.0 if vertical else 1.0
        center = self._video_item.boundingRect().center()
        t = QTransform()
        t.translate(center.x(), center.y())
        t.scale(sx, sy)
        t.translate(-center.x(), -center.y())
        self._video_item.setTransform(t)

    def reset_view(self) -> None:
        """Reset zoom and pan to fit the video in the view."""
        self._zoom_level = 1.0
        self._fit_video()

    def _fit_video(self, _size=None) -> None:
        """Fit the video item into the view keeping aspect ratio."""
        if self._zoom_level > 1.001:
            return
        rect = self._video_item.boundingRect()
        if rect.width() > 0 and rect.height() > 0:
            self._scene.setSceneRect(rect)
            self.fitInView(self._video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _apply_zoom(self, factor: float, anchor_view: QPointF) -> None:
        """Apply zoom factor, keeping the anchor point stable in the view.

        Args:
            factor: Multiplicative zoom factor.
            anchor_view: View-local coordinate that should remain stationary.
        """
        new_level = self._zoom_level * factor
        if new_level < 1.0:
            self._zoom_level = 1.0
            self._fit_video()
            return
        if new_level > _ZOOM_MAX:
            factor = _ZOOM_MAX / self._zoom_level
            new_level = _ZOOM_MAX

        scene_before = self.mapToScene(anchor_view.toPoint())
        self.scale(factor, factor)
        scene_after = self.mapToScene(anchor_view.toPoint())
        delta = scene_after - scene_before
        self.translate(delta.x(), delta.y())

        self._zoom_level = new_level

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_video()

    def wheelEvent(self, event):
        if event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        factor = _ZOOM_FACTOR if event.angleDelta().y() > 0 else 1.0 / _ZOOM_FACTOR
        self._apply_zoom(factor, event.position())
        event.accept()

    def mousePressEvent(self, event):
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)

        if alt and event.button() == Qt.MouseButton.MiddleButton and self._zoom_level > 1.001:
            self._pan_last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if alt and event.button() == Qt.MouseButton.RightButton:
            self._drag_zoom_start_pos = event.position()
            self._drag_zoom_start_level = self._zoom_level
            self._drag_zoom_anchor_view = event.position()
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            event.accept()
            return

        self._focus_widget.setFocus()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_last_pos is not None:
            delta = event.position() - self._pan_last_pos
            self._pan_last_pos = event.position()
            t = self.transform()
            self.setTransform(QTransform(t).translate(delta.x() / t.m11(), delta.y() / t.m22()))
            event.accept()
            return

        if self._drag_zoom_start_pos is not None and self._drag_zoom_anchor_view is not None:
            dx = event.position().x() - self._drag_zoom_start_pos.x()
            dy = event.position().y() - self._drag_zoom_start_pos.y()
            target_level = self._drag_zoom_start_level * (2.0 ** ((dx + dy) / 200.0))
            target_level = max(1.0, min(_ZOOM_MAX, target_level))
            factor = target_level / self._zoom_level
            if abs(factor - 1.0) > 1e-6:
                self._apply_zoom(factor, self._drag_zoom_anchor_view)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_last_pos is not None and event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last_pos = None
            self.unsetCursor()
            event.accept()
            return
        if self._drag_zoom_start_pos is not None and event.button() == Qt.MouseButton.RightButton:
            self._drag_zoom_start_pos = None
            self._drag_zoom_anchor_view = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.open_requested.emit()
