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
    QApplication,
    QBrush,
    QColor,
    QColorDialog,
    QDialog,
    QFont,
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
    LineAnnotation,
    NumberAnnotation,
    RectangleAnnotation,
)

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# Tool modes
TOOL_SELECT = "select"
TOOL_LINE = "line"
TOOL_ARROW = "arrow"
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"
TOOL_NUMBER = "number"

# Color presets (RGB, name)
COLOR_PRESETS = [
    ((255, 0, 0), "Red"),
    ((255, 255, 0), "Yellow"),
    ((0, 255, 0), "Green"),
]

# Line width presets (pixels, name)
LINE_WIDTH_PRESETS = [
    (2, "Thin"),
    (4, "Medium"),
    (6, "Thick"),
]

# Default number size (diameter)
DEFAULT_NUMBER_SIZE = 24


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
        self._current_color = (255, 0, 0)  # Default red
        self._line_width = 4  # Default medium
        self._next_number = 1  # Auto-increment for number tool

        # Tool buttons storage for state management
        self._tool_buttons: dict[str, QToolButton] = {}
        self._color_buttons: list[QPushButton] = []
        self._custom_color_btn: QPushButton | None = None
        self._width_buttons: list[QToolButton] = []

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
        tools = [
            ("Select", TOOL_SELECT),
            ("Line", TOOL_LINE),
            ("Arrow", TOOL_ARROW),
            ("Rect", TOOL_RECT),
            ("Ellipse", TOOL_ELLIPSE),
            ("Number", TOOL_NUMBER),
        ]

        for text, tool in tools:
            btn = self._create_tool_button(text, tool)
            self._tool_buttons[tool] = btn
            layout.addWidget(btn)

        # Set select tool as default
        self._tool_buttons[TOOL_SELECT].setChecked(True)

        # Separator
        layout.addWidget(self._create_separator())

        # Color preset buttons (circular)
        for color, name in COLOR_PRESETS:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setToolTip(name)
            self._update_color_button_style(btn, color, selected=(color == self._current_color))
            btn.clicked.connect(lambda checked=False, c=color: self._on_color_preset(c))
            self._color_buttons.append(btn)
            layout.addWidget(btn)

        # Custom color button (square)
        self._custom_color_btn = QPushButton()
        self._custom_color_btn.setFixedSize(20, 20)
        self._custom_color_btn.setToolTip("Custom Color")
        self._custom_color_btn.setStyleSheet("background-color: rgb(128, 128, 128); border: 1px solid #888;")
        self._custom_color_btn.clicked.connect(self._on_custom_color)
        layout.addWidget(self._custom_color_btn)

        # Separator
        layout.addWidget(self._create_separator())

        # Line width buttons
        for width, name in LINE_WIDTH_PRESETS:
            btn = QToolButton()
            btn.setText(name[0])  # T, M, T
            btn.setCheckable(True)
            btn.setFixedSize(24, 24)
            btn.setToolTip(f"{name} ({width}px)")
            btn.setChecked(width == self._line_width)
            btn.clicked.connect(lambda checked=False, w=width: self._on_line_width(w))
            self._width_buttons.append(btn)
            layout.addWidget(btn)

        # Separator
        layout.addWidget(self._create_separator())

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete Selected")
        delete_btn.clicked.connect(self._on_delete_selected)
        layout.addWidget(delete_btn)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Clear All Annotations")
        clear_btn.clicked.connect(self._on_clear_all)
        layout.addWidget(clear_btn)

        layout.addStretch()
        return toolbar

    def _create_separator(self) -> QWidget:
        """Create a vertical separator.

        Returns:
            Separator widget.
        """
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: palette(mid);")
        return sep

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

    def _update_color_button_style(self, btn: QPushButton, color: tuple[int, int, int], selected: bool = False):
        """Update color button style.

        Args:
            btn: Button to update.
            color: RGB color tuple.
            selected: Whether this color is selected.
        """
        r, g, b = color
        border = "3px solid #fff" if selected else "1px solid #888"
        btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: {border}; border-radius: 10px;")

    def _update_color_selection(self):
        """Update color button selection states."""
        # Update preset buttons
        for btn, (color, _) in zip(self._color_buttons, COLOR_PRESETS):
            self._update_color_button_style(btn, color, selected=(color == self._current_color))

        # Update custom button if current color is not a preset
        is_preset = any(color == self._current_color for color, _ in COLOR_PRESETS)
        if self._custom_color_btn:
            r, g, b = self._current_color
            if is_preset:
                self._custom_color_btn.setStyleSheet("background-color: rgb(128, 128, 128); border: 1px solid #888;")
            else:
                self._custom_color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 3px solid #fff;")

    def _on_tool_selected(self, tool: str):
        """Handle tool selection.

        Args:
            tool: Selected tool identifier.
        """
        self._current_tool = tool
        self._view.set_tool(tool)

        # Update button states
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)

    def _on_color_preset(self, color: tuple[int, int, int]):
        """Handle color preset selection.

        Args:
            color: Selected RGB color.
        """
        self._current_color = color
        self._update_color_selection()
        self._view.set_color(color)

    def _on_custom_color(self):
        """Handle custom color button click."""
        initial_color = QColor(*self._current_color)
        color = QColorDialog.getColor(initial_color, self, "Select Annotation Color")

        if color.isValid():
            self._current_color = (color.red(), color.green(), color.blue())
            self._update_color_selection()
            self._view.set_color(self._current_color)

    def _on_line_width(self, width: int):
        """Handle line width selection.

        Args:
            width: Selected line width.
        """
        self._line_width = width
        self._view.set_line_width(width)

        # Update button states
        for btn, (w, _) in zip(self._width_buttons, LINE_WIDTH_PRESETS):
            btn.setChecked(w == width)

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

        # Reset number counter
        self._next_number = 1
        self._view.set_next_number(1)

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

        # Update next number if this was a number annotation
        if isinstance(annotation, NumberAnnotation):
            self._next_number = annotation.number + 1
            self._view.set_next_number(self._next_number)

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
        self._line_width = 4
        self._next_number = 1

        self._drawing = False
        self._start_pos = None
        self._current_item = None
        self._shift_pressed = False

        # Custom signal
        self.annotation_created = self._Signal()

        # Set initial cursor
        self._update_cursor()

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
        self._update_cursor()

    def set_color(self, color: tuple[int, int, int]):
        """Set the current drawing color.

        Args:
            color: RGB tuple.
        """
        self._current_color = color

    def set_line_width(self, width: int):
        """Set the current line width.

        Args:
            width: Line width in pixels.
        """
        self._line_width = width

    def set_next_number(self, num: int):
        """Set the next number for number tool.

        Args:
            num: Next number to use.
        """
        self._next_number = num

    def _update_cursor(self):
        """Update cursor based on current tool."""
        if self._current_tool == TOOL_SELECT:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def keyPressEvent(self, event):
        """Handle key press events.

        Args:
            event: Key event.
        """
        if event.key() == Qt.Key.Key_Shift:
            self._shift_pressed = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events.

        Args:
            event: Key event.
        """
        if event.key() == Qt.Key.Key_Shift:
            self._shift_pressed = False
        super().keyReleaseEvent(event)

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

            # Number tool creates on click
            if self._current_tool == TOOL_NUMBER:
                self._create_number_annotation()
                self._drawing = False
            else:
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

    def _snap_to_angle(self, start_x: float, start_y: float, end_x: float, end_y: float) -> tuple[float, float]:
        """Snap line to 45-degree increments.

        Args:
            start_x: Start X position.
            start_y: Start Y position.
            end_x: End X position.
            end_y: End Y position.

        Returns:
            Snapped (end_x, end_y) tuple.
        """
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1:
            return end_x, end_y

        # Calculate angle and snap to nearest 45 degrees
        angle = math.atan2(dy, dx)
        snap_angle = round(angle / (math.pi / 4)) * (math.pi / 4)

        # Calculate new end point
        new_end_x = start_x + length * math.cos(snap_angle)
        new_end_y = start_y + length * math.sin(snap_angle)

        return new_end_x, new_end_y

    def _constrain_to_square(self, x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
        """Constrain rectangle to square.

        Args:
            x1, y1: Start position.
            x2, y2: Current end position.

        Returns:
            Constrained (x2, y2) tuple.
        """
        dx = x2 - x1
        dy = y2 - y1
        size = max(abs(dx), abs(dy))

        # Preserve direction
        new_x2 = x1 + size * (1 if dx >= 0 else -1)
        new_y2 = y1 + size * (1 if dy >= 0 else -1)

        return new_x2, new_y2

    def _create_preview_item(self):
        """Create a preview item for the current tool."""
        pen = QPen(QColor(*self._current_color))
        pen.setWidth(self._line_width)

        x, y = self._start_pos.x(), self._start_pos.y()

        if self._current_tool in (TOOL_LINE, TOOL_ARROW):
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

    def _update_preview_item(self, current_pos):
        """Update the preview item during drag.

        Args:
            current_pos: Current mouse position in scene coordinates.
        """
        if not self._current_item:
            return

        x1, y1 = self._start_pos.x(), self._start_pos.y()
        x2, y2 = current_pos.x(), current_pos.y()

        # Check for modifiers
        modifiers = QApplication.keyboardModifiers() if hasattr(self, "_shift_pressed") else None
        shift_pressed = bool(modifiers and modifiers & Qt.KeyboardModifier.ShiftModifier) or self._shift_pressed

        if self._current_tool in (TOOL_LINE, TOOL_ARROW):
            if shift_pressed:
                x2, y2 = self._snap_to_angle(x1, y1, x2, y2)
            self._current_item.setLine(x1, y1, x2, y2)

        elif self._current_tool == TOOL_RECT or self._current_tool == TOOL_ELLIPSE:
            if shift_pressed:
                x2, y2 = self._constrain_to_square(x1, y1, x2, y2)
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

        # Check for shift modifier
        modifiers = QApplication.keyboardModifiers() if hasattr(self, "_shift_pressed") else None
        shift_pressed = bool(modifiers and modifiers & Qt.KeyboardModifier.ShiftModifier) or self._shift_pressed

        # Apply constraints
        if self._current_tool in (TOOL_LINE, TOOL_ARROW) and shift_pressed:
            x2, y2 = self._snap_to_angle(x1, y1, x2, y2)
        elif self._current_tool in (TOOL_RECT, TOOL_ELLIPSE) and shift_pressed:
            x2, y2 = self._constrain_to_square(x1, y1, x2, y2)

        # Convert to ratios
        ratio_x1 = x1 / width
        ratio_y1 = y1 / height
        ratio_x2 = x2 / width
        ratio_y2 = y2 / height

        annotation = None

        if self._current_tool == TOOL_LINE:
            # Require minimum length
            if abs(x2 - x1) < 10 and abs(y2 - y1) < 10:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                return

            annotation = LineAnnotation(
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
                # Update line to final position
                self._current_item.setLine(x1, y1, x2, y2)

        elif self._current_tool == TOOL_ARROW:
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
                # Update rect to final position
                left_px = min(x1, x2)
                top_px = min(y1, y2)
                w_px = abs(x2 - x1)
                h_px = abs(y2 - y1)
                self._current_item.setRect(left_px, top_px, w_px, h_px)

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
                # Update ellipse to final position
                left_px = min(x1, x2)
                top_px = min(y1, y2)
                w_px = abs(x2 - x1)
                h_px = abs(y2 - y1)
                self._current_item.setRect(left_px, top_px, w_px, h_px)

        if annotation:
            self.annotation_created.emit(annotation)

        self._current_item = None

    def _create_number_annotation(self):
        """Create a number annotation at the current position."""
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        if width == 0 or height == 0:
            return

        x = self._start_pos.x()
        y = self._start_pos.y()

        # Convert to ratios
        ratio_x = x / width
        ratio_y = y / height

        annotation = NumberAnnotation(
            x=ratio_x,
            y=ratio_y,
            number=self._next_number,
            color=self._current_color,
            size=DEFAULT_NUMBER_SIZE,
        )

        # Create visual item (circle with number)
        size = DEFAULT_NUMBER_SIZE
        r = size / 2

        # Draw filled circle
        ellipse_item = QGraphicsEllipseItem(x - r, y - r, size, size)
        ellipse_item.setBrush(QBrush(QColor(*self._current_color)))
        ellipse_item.setPen(QPen(Qt.PenStyle.NoPen))
        ellipse_item.annotation_id = annotation.id
        ellipse_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.scene().addItem(ellipse_item)

        # Draw number text
        text_item = QGraphicsTextItem(str(self._next_number))
        text_item.setDefaultTextColor(QColor(255, 255, 255))
        font = QFont()
        font.setPixelSize(int(size * 0.65))
        font.setBold(True)
        text_item.setFont(font)

        # Center text in circle
        text_rect = text_item.boundingRect()
        text_item.setPos(x - text_rect.width() / 2, y - text_rect.height() / 2)
        text_item.setParentItem(ellipse_item)  # Make text follow circle

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
