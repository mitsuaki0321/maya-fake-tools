"""Annotation editor UI for snapshot capture.

Provides a QGraphicsView-based canvas for adding and editing annotations
on captured images.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from ....lib_ui import get_maya_main_window
from ....lib_ui.qt_compat import (
    QBrush,
    QColor,
    QColorDialog,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QPainter,
    QPen,
    QPixmap,
    QPointF,
    QPolygonF,
    QPushButton,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from .annotation import (
    AnnotationLayer,
    ArrowAnnotation,
    EllipseAnnotation,
    RectangleAnnotation,
    TextAnnotation,
)

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# Tool modes
TOOL_SELECT = "select"
TOOL_TEXT = "text"
TOOL_ARROW = "arrow"
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"

# Default colors
DEFAULT_COLORS = {
    TOOL_TEXT: (255, 255, 255),
    TOOL_ARROW: (255, 0, 0),
    TOOL_RECT: (255, 255, 0),
    TOOL_ELLIPSE: (0, 255, 0),
}


class AnnotationEditorDialog(QDialog):
    """Dialog for editing annotations on an image."""

    def __init__(
        self,
        image: Image.Image,
        parent=None,
        background_color: tuple[int, int, int] | None = None,
    ):
        """Initialize annotation editor.

        Args:
            image: PIL Image to annotate.
            parent: Parent widget.
            background_color: RGB tuple for background compositing, or None for transparent.
        """
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle("Annotation Editor")
        self.setModal(True)

        self._image = image
        self._background_color = background_color
        self._annotation_layer = AnnotationLayer()
        self._current_tool = TOOL_SELECT
        self._current_color = (255, 0, 0)
        self._line_width = 3

        self._setup_ui()
        self._load_image()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Graphics view
        self._scene = QGraphicsScene(self)
        self._view = AnnotationGraphicsView(self._scene, self)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.annotation_created.connect(self._on_annotation_created)

        # Disable scroll bars for fixed size view
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(self._view)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

    def _create_toolbar(self) -> QWidget:
        """Create the toolbar widget.

        Returns:
            Toolbar widget.
        """
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tool buttons
        self._select_btn = self._create_tool_button("Select", TOOL_SELECT)
        self._select_btn.setChecked(True)
        layout.addWidget(self._select_btn)

        self._text_btn = self._create_tool_button("Text", TOOL_TEXT)
        layout.addWidget(self._text_btn)

        self._arrow_btn = self._create_tool_button("Arrow", TOOL_ARROW)
        layout.addWidget(self._arrow_btn)

        self._rect_btn = self._create_tool_button("Rect", TOOL_RECT)
        layout.addWidget(self._rect_btn)

        self._ellipse_btn = self._create_tool_button("Ellipse", TOOL_ELLIPSE)
        layout.addWidget(self._ellipse_btn)

        layout.addSpacing(16)

        # Color button
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(24, 24)
        self._color_btn.setToolTip("Annotation Color")
        self._update_color_button()
        self._color_btn.clicked.connect(self._on_color_button)
        layout.addWidget(self._color_btn)

        layout.addSpacing(16)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete Selected")
        delete_btn.clicked.connect(self._on_delete_selected)
        layout.addWidget(delete_btn)

        # Clear button
        clear_btn = QPushButton("Clear All")
        clear_btn.setToolTip("Clear All Annotations")
        clear_btn.clicked.connect(self._on_clear_all)
        layout.addWidget(clear_btn)

        layout.addStretch()
        return toolbar

    def _create_tool_button(self, text: str, tool: str) -> QToolButton:
        """Create a tool button.

        Args:
            text: Button text.
            tool: Tool identifier.

        Returns:
            Configured QToolButton.
        """
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setToolTip(f"{text} Tool")
        btn.clicked.connect(lambda: self._on_tool_selected(tool))
        return btn

    def _on_tool_selected(self, tool: str):
        """Handle tool selection.

        Args:
            tool: Selected tool identifier.
        """
        self._current_tool = tool
        self._view.set_tool(tool)

        # Update button states
        self._select_btn.setChecked(tool == TOOL_SELECT)
        self._text_btn.setChecked(tool == TOOL_TEXT)
        self._arrow_btn.setChecked(tool == TOOL_ARROW)
        self._rect_btn.setChecked(tool == TOOL_RECT)
        self._ellipse_btn.setChecked(tool == TOOL_ELLIPSE)

        # Update color to tool default
        if tool in DEFAULT_COLORS:
            self._current_color = DEFAULT_COLORS[tool]
            self._update_color_button()
            self._view.set_color(self._current_color)

    def _on_color_button(self):
        """Handle color button click."""
        initial_color = QColor(*self._current_color)
        color = QColorDialog.getColor(initial_color, self, "Select Annotation Color")

        if color.isValid():
            self._current_color = (color.red(), color.green(), color.blue())
            self._update_color_button()
            self._view.set_color(self._current_color)

    def _update_color_button(self):
        """Update color button appearance."""
        r, g, b = self._current_color
        self._color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #888;")

    def _on_delete_selected(self):
        """Delete selected annotation items."""
        selected = self._scene.selectedItems()
        for item in selected:
            if hasattr(item, "annotation_id"):
                self._annotation_layer.remove(item.annotation_id)
            # Also remove arrowhead if present
            if hasattr(item, "_arrowhead"):
                self._scene.removeItem(item._arrowhead)
            self._scene.removeItem(item)

    def _on_clear_all(self):
        """Clear all annotations."""
        # Remove annotation items but keep background
        for item in list(self._scene.items()):
            if hasattr(item, "annotation_id"):
                # Also remove arrowhead if present
                if hasattr(item, "_arrowhead"):
                    self._scene.removeItem(item._arrowhead)
                self._scene.removeItem(item)
        self._annotation_layer.clear()

    def _load_image(self):
        """Load the image into the scene."""
        from io import BytesIO

        from .image import composite_with_background

        # Composite with background color if provided
        display_image = composite_with_background(self._image, self._background_color)

        # Convert PIL image to QPixmap
        buffer = BytesIO()
        display_image.save(buffer, format="PNG")
        buffer.seek(0)

        pixmap = QPixmap()
        pixmap.loadFromData(buffer.read())

        # Add pixmap to scene
        self._scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        bg_item = self._scene.addPixmap(pixmap)
        bg_item.setZValue(-1)  # Keep behind annotations

        # Set view to fixed size matching the image
        self._view.setFixedSize(pixmap.width(), pixmap.height())

        # Resize dialog to fit the view
        self.adjustSize()

    def _on_annotation_created(self, annotation):
        """Handle annotation creation from view.

        Args:
            annotation: Created annotation object.
        """
        self._annotation_layer.add(annotation)

    def get_annotations(self) -> AnnotationLayer:
        """Get the annotation layer.

        Returns:
            AnnotationLayer with all annotations.
        """
        return self._annotation_layer


class AnnotationGraphicsView(QGraphicsView):
    """Custom graphics view for annotation drawing."""

    class _Signal:
        """Simple signal-like callback holder."""

        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args):
            for cb in self._callbacks:
                cb(*args)

    def __init__(self, scene: QGraphicsScene, parent=None):
        """Initialize the graphics view.

        Args:
            scene: QGraphicsScene to display.
            parent: Parent widget.
        """
        super().__init__(scene, parent)
        self._current_tool = TOOL_SELECT
        self._current_color = (255, 0, 0)
        self._line_width = 3

        self._drawing = False
        self._start_pos = None
        self._current_item = None

        # Custom signal
        self.annotation_created = self._Signal()

    def set_tool(self, tool: str):
        """Set the current drawing tool.

        Args:
            tool: Tool identifier.
        """
        self._current_tool = tool
        if tool == TOOL_SELECT:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_color(self, color: tuple[int, int, int]):
        """Set the current drawing color.

        Args:
            color: RGB tuple.
        """
        self._current_color = color

    def mousePressEvent(self, event):
        """Handle mouse press events.

        Args:
            event: Mouse event.
        """
        if self._current_tool == TOOL_SELECT:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start_pos = self.mapToScene(event.pos())
            self._create_preview_item()

    def mouseMoveEvent(self, event):
        """Handle mouse move events.

        Args:
            event: Mouse event.
        """
        if self._current_tool == TOOL_SELECT:
            super().mouseMoveEvent(event)
            return

        if self._drawing and self._current_item:
            current_pos = self.mapToScene(event.pos())
            self._update_preview_item(current_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events.

        Args:
            event: Mouse event.
        """
        if self._current_tool == TOOL_SELECT:
            super().mouseReleaseEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            end_pos = self.mapToScene(event.pos())
            self._finalize_item(end_pos)

    def _create_preview_item(self):
        """Create a preview item for the current tool."""
        pen = QPen(QColor(*self._current_color))
        pen.setWidth(self._line_width)

        x, y = self._start_pos.x(), self._start_pos.y()

        if self._current_tool == TOOL_ARROW:
            self._current_item = QGraphicsLineItem(x, y, x, y)
            self._current_item.setPen(pen)
            self.scene().addItem(self._current_item)

        elif self._current_tool == TOOL_RECT:
            self._current_item = QGraphicsRectItem(x, y, 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.scene().addItem(self._current_item)

        elif self._current_tool == TOOL_ELLIPSE:
            self._current_item = QGraphicsEllipseItem(x, y, 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.scene().addItem(self._current_item)

        elif self._current_tool == TOOL_TEXT:
            # For text, show input dialog on click
            self._current_item = None

    def _update_preview_item(self, current_pos):
        """Update the preview item during drag.

        Args:
            current_pos: Current mouse position in scene coordinates.
        """
        if not self._current_item:
            return

        x1, y1 = self._start_pos.x(), self._start_pos.y()
        x2, y2 = current_pos.x(), current_pos.y()

        if self._current_tool == TOOL_ARROW:
            self._current_item.setLine(x1, y1, x2, y2)

        elif self._current_tool == TOOL_RECT:
            # Calculate normalized rectangle
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            self._current_item.setRect(left, top, width, height)

        elif self._current_tool == TOOL_ELLIPSE:
            # Calculate normalized ellipse
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            self._current_item.setRect(left, top, width, height)

    def _finalize_item(self, end_pos):
        """Finalize the item and create annotation.

        Args:
            end_pos: End position in scene coordinates.
        """
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        if width == 0 or height == 0:
            return

        x1, y1 = self._start_pos.x(), self._start_pos.y()
        x2, y2 = end_pos.x(), end_pos.y()

        # Convert to ratios
        ratio_x1 = x1 / width
        ratio_y1 = y1 / height
        ratio_x2 = x2 / width
        ratio_y2 = y2 / height

        annotation = None

        if self._current_tool == TOOL_ARROW:
            # Require minimum length
            if abs(x2 - x1) < 10 and abs(y2 - y1) < 10:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                return

            annotation = ArrowAnnotation(
                start_x=ratio_x1,
                start_y=ratio_y1,
                end_x=ratio_x2,
                end_y=ratio_y2,
                color=self._current_color,
                line_width=self._line_width,
            )
            if self._current_item:
                self._current_item.annotation_id = annotation.id
                self._current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

                # Shorten line so it doesn't overlap with arrowhead
                arrow_length = self._line_width * 4
                angle = math.atan2(y2 - y1, x2 - x1)
                line_end_x = x2 - arrow_length * math.cos(angle)
                line_end_y = y2 - arrow_length * math.sin(angle)
                self._current_item.setLine(x1, y1, line_end_x, line_end_y)

                self._add_arrowhead(self._current_item, x1, y1, x2, y2)

        elif self._current_tool == TOOL_RECT:
            # Require minimum size
            if abs(x2 - x1) < 10 and abs(y2 - y1) < 10:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                return

            left = min(ratio_x1, ratio_x2)
            top = min(ratio_y1, ratio_y2)
            rect_width = abs(ratio_x2 - ratio_x1)
            rect_height = abs(ratio_y2 - ratio_y1)

            annotation = RectangleAnnotation(
                x=left,
                y=top,
                width=rect_width,
                height=rect_height,
                color=self._current_color,
                line_width=self._line_width,
            )
            if self._current_item:
                self._current_item.annotation_id = annotation.id
                self._current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        elif self._current_tool == TOOL_ELLIPSE:
            # Require minimum size
            if abs(x2 - x1) < 10 and abs(y2 - y1) < 10:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                return

            center_x = (ratio_x1 + ratio_x2) / 2
            center_y = (ratio_y1 + ratio_y2) / 2
            radius_x = abs(ratio_x2 - ratio_x1) / 2
            radius_y = abs(ratio_y2 - ratio_y1) / 2

            annotation = EllipseAnnotation(
                center_x=center_x,
                center_y=center_y,
                radius_x=radius_x,
                radius_y=radius_y,
                color=self._current_color,
                line_width=self._line_width,
            )
            if self._current_item:
                self._current_item.annotation_id = annotation.id
                self._current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        elif self._current_tool == TOOL_TEXT:
            # Create text at click position
            self._create_text_annotation(ratio_x1, ratio_y1)
            return

        if annotation:
            self.annotation_created.emit(annotation)

        self._current_item = None

    def _create_text_annotation(self, ratio_x: float, ratio_y: float):
        """Create a text annotation via input dialog.

        Args:
            ratio_x: X position ratio.
            ratio_y: Y position ratio.
        """
        from ....lib_ui.qt_compat import QInputDialog

        text, ok = QInputDialog.getText(self, "Add Text", "Enter annotation text:")
        if ok and text:
            annotation = TextAnnotation(
                text=text,
                x=ratio_x,
                y=ratio_y,
                color=self._current_color,
            )

            # Create visual item
            scene_rect = self.scene().sceneRect()
            x = ratio_x * scene_rect.width()
            y = ratio_y * scene_rect.height()

            text_item = QGraphicsTextItem(text)
            text_item.setPos(x, y)
            text_item.setDefaultTextColor(QColor(*self._current_color))
            text_item.annotation_id = annotation.id
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            self.scene().addItem(text_item)

            self.annotation_created.emit(annotation)

    def _add_arrowhead(self, line_item: QGraphicsLineItem, x1: float, y1: float, x2: float, y2: float):
        """Add an arrowhead polygon to the scene.

        Args:
            line_item: The line item (used to get color).
            x1, y1: Start point.
            x2, y2: End point (arrow tip).
        """
        # Calculate arrow angle
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = self._line_width * 4
        arrow_angle = math.pi / 6  # 30 degrees

        # Calculate arrowhead points
        left_x = x2 - arrow_length * math.cos(angle - arrow_angle)
        left_y = y2 - arrow_length * math.sin(angle - arrow_angle)
        right_x = x2 - arrow_length * math.cos(angle + arrow_angle)
        right_y = y2 - arrow_length * math.sin(angle + arrow_angle)

        # Create polygon for arrowhead
        polygon = QPolygonF(
            [
                QPointF(x2, y2),
                QPointF(left_x, left_y),
                QPointF(right_x, right_y),
            ]
        )

        # Create and add polygon item
        arrow_item = QGraphicsPolygonItem(polygon)
        arrow_item.setBrush(QBrush(QColor(*self._current_color)))
        arrow_item.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene().addItem(arrow_item)

        # Store reference to delete with line
        if not hasattr(line_item, "_arrowhead"):
            line_item._arrowhead = arrow_item


def show_annotation_editor(
    image: Image.Image,
    parent=None,
    background_color: tuple[int, int, int] | None = None,
) -> AnnotationLayer | None:
    """Show the annotation editor dialog.

    Args:
        image: PIL Image to annotate.
        parent: Parent widget.
        background_color: RGB tuple for background compositing, or None for transparent.

    Returns:
        AnnotationLayer if accepted, None if cancelled.
    """
    dialog = AnnotationEditorDialog(image, parent, background_color)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_annotations()
    return None
