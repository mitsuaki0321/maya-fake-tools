"""QListView subclass with DnD indicator and hover tracking."""

from __future__ import annotations

from .....lib_ui.qt_compat import (
    QAbstractItemView,
    QColor,
    QListView,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    Qt,
    QtGui,
    Signal,
)
from .colors import DROP_INDICATOR
from .layer_delegate import ITEM_MARGIN_H, ITEM_RADIUS, LayerDelegate, hit_zone


class LayerView(QListView):
    """Drag-and-drop layer list with Photoshop-style insert indicator."""

    # Signals
    visibility_changed = Signal(int, bool)  # (stack_idx, visible)
    menu_requested = Signal(int)  # (row)
    order_changed = Signal()  # DnD finished

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delegate = LayerDelegate(self)
        self.setItemDelegate(self._delegate)

        # DnD
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

        # Stretch items to full viewport width
        self.setResizeMode(QListView.Adjust)

        # Hover tracking
        self.setMouseTracking(True)
        self._drop_row: int = -1
        self._drag_press_pos = None

    # ── Mouse press (record position for drag pixmap hotspot) ──

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._drag_press_pos = event.pos()

    # ── Hover tracking ──

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = self.indexAt(event.pos())
        if index.isValid():
            self._delegate.hovered_row = index.row()
            x = event.pos().x()
            w = self.viewport().width()
            self._delegate.hovered_zone = hit_zone(x, w)
        else:
            self._delegate.hovered_row = -1
            self._delegate.hovered_zone = ""
        self.viewport().update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._delegate.hovered_row = -1
        self._delegate.hovered_zone = ""
        self.viewport().update()

    # ── Mouse click: menu zone ──

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() != Qt.LeftButton:
            return
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        x = event.pos().x()
        w = self.viewport().width()
        if hit_zone(x, w) == "menu":
            self.menu_requested.emit(index.row())

    # ── DnD ──

    def startDrag(self, supportedActions):
        """Override to prevent Qt from removing source rows after drop.

        The default QAbstractItemView.startDrag calls clearOrRemove()
        when drag->exec() returns MoveAction.  We handle the row move
        entirely inside dropEvent, so the automatic removal must be
        suppressed.
        """
        indexes = self.selectedIndexes()
        if not indexes:
            return
        model = self.model()
        if model is None:
            return
        mime = model.mimeData(indexes)
        if mime is None:
            return

        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)

        # Render the dragged row clipped to the selection rounded rect
        rect = self.visualRect(indexes[0])
        raw = self.viewport().grab(rect)

        # inner rect matches the delegate's adjusted rect
        inner_x = ITEM_MARGIN_H
        inner_y = 1
        inner_w = rect.width() - ITEM_MARGIN_H * 2
        inner_h = rect.height() - 2

        pixmap = QPixmap(raw.size())
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(inner_x, inner_y, inner_w, inner_h, ITEM_RADIUS, ITEM_RADIUS)
        p.setClipPath(path)
        p.drawPixmap(0, 0, raw)
        p.end()

        drag.setPixmap(pixmap)
        if self._drag_press_pos is not None:
            drag.setHotSpot(self._drag_press_pos - rect.topLeft())
        else:
            drag.setHotSpot(rect.center() - rect.topLeft())

        drag.exec_(supportedActions, Qt.MoveAction)
        # Do NOT remove source rows — dropEvent handles the move.

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        pos = event.pos()
        index = self.indexAt(pos)
        if index.isValid():
            rect = self.visualRect(index)
            mid_y = rect.top() + rect.height() // 2
            self._drop_row = index.row() if pos.y() < mid_y else index.row() + 1
        else:
            self._drop_row = self.model().rowCount()
        self.viewport().update()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self._drop_row = -1
        self.viewport().update()

    def dropEvent(self, event):
        # Do NOT call super — handle the row reorder manually.
        model = self.model()
        source_indexes = self.selectedIndexes()
        if event.source() is not self or model is None or not source_indexes or self._drop_row < 0:
            event.ignore()
            self._drop_row = -1
            self.viewport().update()
            return

        source_row = source_indexes[0].row()
        dest_row = self._drop_row

        # Dropping on itself — no-op
        if source_row == dest_row or source_row == dest_row - 1:
            event.accept()
            self._drop_row = -1
            self.viewport().update()
            return

        items = model.takeRow(source_row)
        if dest_row > source_row:
            dest_row -= 1
        model.insertRow(dest_row, items)
        self.setCurrentIndex(model.index(dest_row, 0))

        event.accept()
        self._drop_row = -1
        self.viewport().update()
        self.order_changed.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_row < 0:
            return
        model = self.model()
        if model is None:
            return
        row_count = model.rowCount()
        if row_count == 0:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(DROP_INDICATOR), 2)
        painter.setPen(pen)

        if self._drop_row < row_count:
            rect = self.visualRect(model.index(self._drop_row, 0))
            y = rect.top()
        else:
            rect = self.visualRect(model.index(row_count - 1, 0))
            y = rect.bottom()

        m = ITEM_MARGIN_H
        r = 3
        painter.setBrush(QColor(DROP_INDICATOR))
        painter.drawEllipse(m, y - r, r * 2, r * 2)
        painter.drawLine(m + r * 2, y, self.viewport().width() - m - r * 2, y)
        painter.drawEllipse(self.viewport().width() - m - r * 2, y - r, r * 2, r * 2)
        painter.end()
