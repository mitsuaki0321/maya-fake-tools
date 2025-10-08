"""Node stock view widget."""

from ....lib_ui.qt_compat import (
    QBrush,
    QColor,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QObject,
    QPen,
    QPoint,
    QRectF,
    QRubberBand,
    Qt,
    QTransform,
    Signal,
)


class NodeStockTextItem(QGraphicsTextItem):
    pass


class NodeStockButton(QGraphicsRectItem, QObject):
    """Node stock button item."""

    left_button_clicked = Signal(object)
    middle_button_clicked = Signal(object)
    right_button_clicked = Signal(object)
    hovered = Signal(object)
    unhovered = Signal()

    def __init__(self, key: str, x: int, y: int, size: int, **kwargs):
        """Initialize the short button.

        Args:
            key (str): The stock key.
            x (int): The x position.
            y (int): The y position.
            size (int): The size of the button.

        Keyword Args:
            base_color (str): The base color of the button.
            label (str): The label text.
        """
        base_color = kwargs.get("base_color", "gray")
        label = kwargs.get("label")

        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, size, size)
        self._key = key
        self.size = size

        base_color = QColor(base_color)
        self.hover_color_brush = QBrush(self._get_lightness_color(base_color, 1.5))
        self.pressed_color_brush = QBrush(self._get_lightness_color(base_color, 0.8))
        self.transparent_brush = QBrush(Qt.transparent)
        self.stoked_color_brush = QBrush(base_color)

        self.default_border_pen = QPen(QColor("lightgray"), 1, Qt.SolidLine)
        self.default_border_pen.setJoinStyle(Qt.MiterJoin)

        self.hover_border_pen = QPen(QColor("white"), 1, Qt.SolidLine)
        self.hover_border_pen.setJoinStyle(Qt.MiterJoin)

        self.pressed_border_pen = QPen(QColor("darkgray"), 1, Qt.SolidLine)
        self.pressed_border_pen.setJoinStyle(Qt.MiterJoin)

        self.setBrush(Qt.NoBrush)
        self.setPos(x, y)

        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.MiddleButton | Qt.RightButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)

        self.is_stoked = False
        self.is_hovered = False
        self.is_pressed = False

        if label:
            self.label = NodeStockTextItem(label, self)
            font = self.label.font()
            font.setPointSize(self.size // 3)
            font.setBold(True)
            self.label.setFont(font)

            self.label.setPos(size / 2 - self.label.boundingRect().width() / 2, size / 2 - self.label.boundingRect().height() / 2)
            self.label.setDefaultTextColor(QColor("lightgray"))

    @property
    def key(self):
        """str: The stock key."""
        return self._key

    def _get_lightness_color(self, color, factor) -> QColor:
        """Adjust the brightness of a color for hover and pressed states.

        Args:
            color (QColor): The color to adjust.
            factor (float): The brightness factor.

        Returns:
            QColor: The adjusted color.
        """
        h, s, v, a = color.getHsv()
        v = max(0, min(v * factor, 255))
        return QColor.fromHsv(h, s, v, a)

    def hoverEnterEvent(self, event) -> None:
        """Change color and border when mouse hovers over the button."""
        self.is_hovered = True
        self.update()
        self.hovered.emit(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """Reset color and border when mouse leaves the button."""
        self.is_hovered = False
        self.update()
        self.unhovered.emit()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        """Change color when the button is pressed."""
        self.is_pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Emit the clicked signal when the button is released."""
        if event.button() == Qt.LeftButton and self.is_pressed:
            self.left_button_clicked.emit(self)
        elif event.button() == Qt.MiddleButton and self.is_pressed:
            self.middle_button_clicked.emit(self)
        elif event.button() == Qt.RightButton and self.is_pressed:
            self.right_button_clicked.emit(self)
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def reset_color(self) -> None:
        """Reset button color to default."""
        self.is_hovered = False
        self.is_pressed = False
        self.update()

    def apply_hover_color(self) -> None:
        """Apply hover color to the button."""
        self.is_hovered = True
        self.update()

    def apply_stoked_color(self) -> None:
        """Apply stoked color to the button."""
        self.is_stoked = True
        self.update()

    def reset_stoked_color(self) -> None:
        """Reset stoked color to default."""
        self.is_stoked = False
        self.update()

    def paint(self, painter, option, widget=None) -> None:
        """Custom paint to draw the button with hover and pressed state."""
        rect = self.rect().adjusted(0, 0, -1, -1)
        inner_rect = rect.adjusted(3, 3, -3, -3)

        painter.setBrush(Qt.NoBrush)

        scale = painter.transform().m11()
        pen_width = 3 / scale

        if self.is_pressed:
            brush = self.pressed_color_brush
            pen = self.pressed_border_pen
        elif self.is_hovered:
            brush = self.hover_color_brush
            pen = self.hover_border_pen
        elif self.is_stoked:
            brush = self.stoked_color_brush
            pen = self.default_border_pen
        else:
            brush = self.transparent_brush
            pen = self.default_border_pen

        pen.setWidthF(pen_width)
        painter.setPen(pen)
        painter.drawRect(inner_rect)

        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawRect(inner_rect.adjusted(pen_width / 2, pen_width / 2, -pen_width / 2, -pen_width / 2))


class NodeStockGraphicsScene(QGraphicsScene):
    def list_buttons(self) -> list[NodeStockButton]:
        """List NodeStockButton items in the scene.

        Returns:
            list[NodeStockButton]: The list of buttons.
        """
        return [item for item in self.items() if isinstance(item, NodeStockButton)]

    def mouseReleaseEvent(self, event):
        """Without this handling, the event would be consumed first,
        and right-click and middle-click would not be passed to NodeStockButton.
        """
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, NodeStockButton):
            item.mouseReleaseEvent(event)
        if isinstance(item, NodeStockTextItem):
            item.parentItem().mouseReleaseEvent(event)

        super().mouseReleaseEvent(event)


class NodeStockGraphicsView(QGraphicsView):
    """Customized QGraphicsView."""

    rubber_band_selection = Signal([object])

    def __init__(self, scene: QGraphicsScene, parent=None):
        """Initialize the custom graphics view.

        Args:
            scene (QGraphicsScene): The graphics scene.
            parent (QWidget): The parent widget.
        """
        super().__init__(scene, parent)

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        self.is_rubber_band_active = False
        self.hovered_items = []

    def mousePressEvent(self, event) -> None:
        """Handle mouse press to start rubber band selection."""
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRectF(self.origin, self.origin).toRect())
            self.rubber_band.show()
            self.is_rubber_band_active = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move to update rubber band selection."""
        if self.is_rubber_band_active:
            self.rubber_band.setGeometry(QRectF(self.origin, event.pos()).normalized().toRect())
            self._update_hovered_items()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release to finalize selection."""
        if self.is_rubber_band_active:
            self._select_items_in_rubber_band()
            self.rubber_band.hide()
            self.origin = QPoint()
            self.is_rubber_band_active = False
            self._reset_hovered_items()
        super().mouseReleaseEvent(event)

    def _update_hovered_items(self) -> None:
        """Update items currently hovered by the rubber band."""
        rect = self.rubber_band.geometry()
        mapped_rect = self.mapToScene(rect).boundingRect()

        for item in self.hovered_items:
            if isinstance(item, NodeStockButton):
                item.reset_color()

        self.hovered_items = []
        for item in self.scene().items(mapped_rect):
            if isinstance(item, NodeStockButton):
                item.apply_hover_color()
                self.hovered_items.append(item)

    def _reset_hovered_items(self) -> None:
        """Reset colors for all items hovered by the rubber band."""
        for item in self.hovered_items:
            if isinstance(item, NodeStockButton):
                item.reset_color()
        self.hovered_items = []

    def _select_items_in_rubber_band(self) -> None:
        """Select items within the rubber band area."""
        rect = self.rubber_band.geometry()
        mapped_rect = self.mapToScene(rect).boundingRect()
        items = []
        for item in self.scene().items(mapped_rect):
            if isinstance(item, NodeStockButton):
                items.append(item)

        if not items:
            return

        self.rubber_band_selection.emit(items)

    def resizeEvent(self, event) -> None:
        """Handle resize event to adjust the scene rectangle."""
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
