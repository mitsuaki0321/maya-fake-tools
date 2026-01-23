"""Annotation editor UI for snapshot capture.

Provides a QGraphicsView-based canvas for adding and editing annotations
on captured images.
"""

from __future__ import annotations

import logging
import math
import os
from typing import TYPE_CHECKING

from ....lib_ui import ToolSettingsManager, get_maya_main_window
from ....lib_ui.qt_compat import (
    QApplication,
    QBrush,
    QByteArray,
    QColor,
    QColorDialog,
    QDialog,
    QFont,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QIcon,
    QImage,
    QMimeData,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPointF,
    QPolygonF,
    QPushButton,
    QSize,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from .annotation import (
    AnnotationLayer,
    ArrowAnnotation,
    EllipseAnnotation,
    FreehandAnnotation,
    LineAnnotation,
    NumberAnnotation,
    RectangleAnnotation,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from PIL import Image

logger = logging.getLogger(__name__)

# Tool modes
TOOL_SELECT = "select"
TOOL_LINE = "line"
TOOL_ARROW = "arrow"
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"
TOOL_NUMBER = "number"
TOOL_FREEHAND = "freehand"

# Icon directory path
_ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")

# Tool icons (SVG filenames)
TOOL_ICONS = {
    TOOL_SELECT: "tool_select.svg",
    TOOL_LINE: "tool_line.svg",
    TOOL_ARROW: "tool_arrow.svg",
    TOOL_RECT: "tool_rect.svg",
    TOOL_ELLIPSE: "tool_ellipse.svg",
    TOOL_NUMBER: "tool_number.svg",
    TOOL_FREEHAND: "tool_freehand.svg",
}

# Stroke width icons (SVG filenames)
STROKE_ICONS = {
    2: "stroke_thin.svg",
    4: "stroke_medium.svg",
    6: "stroke_thick.svg",
}

# Action icons (SVG filenames)
ACTION_ICONS = {
    "undo": "action_undo.svg",
    "delete": "action_delete.svg",
    "clear": "action_clear.svg",
    "save": "action_apply.svg",
    "copy": "snapshot_copy.svg",
    "cancel": "action_cancel.svg",
}

# Color presets (RGB hex, RGB tuple, name)
COLOR_PRESETS = [
    ("#e53935", (229, 57, 53), "Red"),
    ("#fdd835", (253, 216, 53), "Yellow"),
    ("#43a047", (67, 160, 71), "Green"),
    ("#ffffff", (255, 255, 255), "White"),
    ("#212121", (33, 33, 33), "Black"),
]

# Line width presets (pixels, visual height, name)
LINE_WIDTH_PRESETS = [
    (2, 1, "Thin"),
    (4, 3, "Medium"),
    (6, 5, "Thick"),
]

# Tooltip style (Maya's default)
TOOLTIP_STYLE = "QToolTip { background-color: #FFFFDC; color: #000000; border: 1px solid #767676; border-radius: 0px; }"


class AnnotationEditorDialog(QDialog):
    """Dialog for editing annotations on an image."""

    def __init__(
        self,
        image: Image.Image,
        parent=None,
        background_color: tuple[int, int, int] | None = None,
        save_callback: Callable[[Image.Image, AnnotationLayer, QWidget], bool] | None = None,
    ):
        """Initialize annotation editor.

        Args:
            image: PIL Image to annotate.
            parent: Parent widget.
            background_color: RGB tuple for background compositing, or None for transparent.
            save_callback: Optional callback for save action. Should return True if save succeeded.
                          If provided, the dialog only closes when save succeeds.
                          Signature: (image, annotations, parent_widget) -> bool
        """
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle("Annotation Editor")
        self.setModal(True)

        self._image = image
        self._background_color = background_color
        self._save_callback = save_callback
        self._annotation_layer = AnnotationLayer()
        self._current_tool = TOOL_SELECT
        self._next_number = 1  # Auto-increment for number tool

        # Settings manager for persisting user preferences
        self._settings = ToolSettingsManager(tool_name="snapshot_capture", category="common")
        self._load_settings()  # Load saved color and line width

        # Undo stack for annotation history
        self._undo_stack: list[tuple] = []

        # Tool buttons storage for state management (initialized before _setup_ui)
        self._tool_buttons: dict[str, QToolButton] = {}
        self._color_buttons: list[QPushButton] = []
        self._custom_color_btn: QPushButton | None = None
        self._width_buttons: list[QToolButton] = []

        self._setup_ui()
        self._load_image()

        # Apply loaded settings to the view
        self._view.set_color(self._current_color)
        self._view.set_line_width(self._line_width)

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Graphics view
        self._scene = QGraphicsScene(self)
        self._view = AnnotationGraphicsView(self._scene, self)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.annotation_created.connect(self._on_annotation_created)
        self._view.setStyleSheet("border: 1px solid #444444;")

        # Disable scroll bars for fixed size view
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Center the view horizontally
        view_container = QHBoxLayout()
        view_container.setContentsMargins(0, 0, 0, 0)
        view_container.addStretch()
        view_container.addWidget(self._view)
        view_container.addStretch()
        layout.addLayout(view_container)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.addStretch()

        # Action button group with background
        footer_action_group = QWidget()
        footer_action_group.setStyleSheet("background: #2e2e2e; border-radius: 5px;")
        footer_action_layout = QHBoxLayout(footer_action_group)
        footer_action_layout.setContentsMargins(4, 1, 4, 1)
        footer_action_layout.setSpacing(1)

        # Save button (accept and close)
        save_btn = QToolButton()
        save_btn.setFixedSize(26, 26)
        save_btn.setToolTip("Save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_icon_path = self._get_icon_path(ACTION_ICONS["save"])
        if save_icon_path:
            save_btn.setIcon(QIcon(save_icon_path))
            save_btn.setIconSize(QSize(20, 20))
        else:
            save_btn.setText("S")
        save_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        save_btn.clicked.connect(self._on_save_clicked)
        footer_action_layout.addWidget(save_btn)

        # Copy to clipboard button
        copy_btn = QToolButton()
        copy_btn.setFixedSize(26, 26)
        copy_btn.setToolTip("Copy to Clipboard")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_icon_path = self._get_icon_path(ACTION_ICONS["copy"])
        if copy_icon_path:
            copy_btn.setIcon(QIcon(copy_icon_path))
            copy_btn.setIconSize(QSize(20, 20))
        else:
            copy_btn.setText("C")
        copy_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        copy_btn.clicked.connect(self._on_copy_to_clipboard)
        footer_action_layout.addWidget(copy_btn)

        # Cancel button
        cancel_btn = QToolButton()
        cancel_btn.setFixedSize(26, 26)
        cancel_btn.setToolTip("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_icon_path = self._get_icon_path(ACTION_ICONS["cancel"])
        if cancel_icon_path:
            cancel_btn.setIcon(QIcon(cancel_icon_path))
            cancel_btn.setIconSize(QSize(20, 20))
        else:
            cancel_btn.setText("X")
        cancel_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        cancel_btn.clicked.connect(self.reject)
        footer_action_layout.addWidget(cancel_btn)

        button_layout.addWidget(footer_action_group)
        layout.addLayout(button_layout)

    def _create_toolbar(self) -> QWidget:
        """Create the toolbar widget.

        Returns:
            Toolbar widget.
        """
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)

        # Tool group container with background
        tool_group = QWidget()
        tool_group.setStyleSheet("background: #2e2e2e; border-radius: 5px;")
        tool_group_layout = QHBoxLayout(tool_group)
        tool_group_layout.setContentsMargins(2, 1, 2, 1)
        tool_group_layout.setSpacing(1)

        # Tool buttons with icons
        tools = [
            (TOOL_SELECT, "Select"),
            (TOOL_FREEHAND, "Freehand"),
            (TOOL_LINE, "Line"),
            (TOOL_ARROW, "Arrow"),
            (TOOL_RECT, "Rectangle"),
            (TOOL_ELLIPSE, "Ellipse"),
            (TOOL_NUMBER, "Number"),
        ]

        for tool, tooltip in tools:
            btn = self._create_tool_button(TOOL_ICONS[tool], tool, tooltip)
            self._tool_buttons[tool] = btn
            tool_group_layout.addWidget(btn)

        layout.addWidget(tool_group)

        # Set select tool as default
        self._tool_buttons[TOOL_SELECT].setChecked(True)
        self._update_tool_button_styles()

        # Divider
        layout.addWidget(self._create_divider())

        # Color group
        color_group = QWidget()
        color_group_layout = QHBoxLayout(color_group)
        color_group_layout.setContentsMargins(4, 0, 4, 0)
        color_group_layout.setSpacing(5)

        # Color preset buttons (circular)
        for _hex_color, rgb_color, name in COLOR_PRESETS:
            btn = QPushButton()
            btn.setFixedSize(16, 16)
            btn.setToolTip(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Don't select preset if custom color is selected
            is_selected = (rgb_color == self._current_color) and not self._is_custom_selected
            self._update_color_button_style(btn, rgb_color, selected=is_selected)
            btn.clicked.connect(lambda checked=False, c=rgb_color: self._on_color_preset(c))
            self._color_buttons.append(btn)
            color_group_layout.addWidget(btn)

        # Custom color button (square)
        self._custom_color_btn = QPushButton()
        self._custom_color_btn.setFixedSize(16, 16)
        self._custom_color_btn.setToolTip("Custom Color (Right-click to change)")
        self._custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_custom_color_button()
        self._custom_color_btn.clicked.connect(self._on_custom_color_click)
        self._custom_color_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._custom_color_btn.customContextMenuRequested.connect(self._on_custom_color_picker)
        color_group_layout.addWidget(self._custom_color_btn)

        layout.addWidget(color_group)

        # Divider
        layout.addWidget(self._create_divider())

        # Stroke width group container with background
        stroke_group = QWidget()
        stroke_group.setStyleSheet("background: #2e2e2e; border-radius: 4px;")
        stroke_group_layout = QHBoxLayout(stroke_group)
        stroke_group_layout.setContentsMargins(2, 1, 2, 1)
        stroke_group_layout.setSpacing(1)

        # Line width buttons with visual stroke
        for width, visual_height, name in LINE_WIDTH_PRESETS:
            btn = self._create_stroke_button(width, visual_height, name)
            self._width_buttons.append(btn)
            stroke_group_layout.addWidget(btn)

        layout.addWidget(stroke_group)

        # Spacer to push action buttons to the right
        layout.addStretch()

        # Action group container with background
        action_group = QWidget()
        action_group.setStyleSheet("background: #2e2e2e; border-radius: 5px;")
        action_group_layout = QHBoxLayout(action_group)
        action_group_layout.setContentsMargins(4, 1, 4, 1)
        action_group_layout.setSpacing(1)

        # Undo button
        undo_btn = QToolButton()
        undo_btn.setFixedSize(26, 26)
        undo_btn.setToolTip("Undo Last Action")
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_icon_path = self._get_icon_path(ACTION_ICONS["undo"])
        if undo_icon_path:
            undo_btn.setIcon(QIcon(undo_icon_path))
            undo_btn.setIconSize(QSize(20, 20))
        else:
            undo_btn.setText("U")
        undo_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        undo_btn.clicked.connect(self._on_undo)
        action_group_layout.addWidget(undo_btn)

        # Delete selected button
        delete_btn = QToolButton()
        delete_btn.setFixedSize(26, 26)
        delete_btn.setToolTip("Delete Selected (Del)")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_icon_path = self._get_icon_path(ACTION_ICONS["delete"])
        if delete_icon_path:
            delete_btn.setIcon(QIcon(delete_icon_path))
            delete_btn.setIconSize(QSize(20, 20))
        else:
            delete_btn.setText("D")
        delete_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        delete_btn.clicked.connect(self._on_delete_selected)
        action_group_layout.addWidget(delete_btn)

        # Clear button
        clear_btn = QToolButton()
        clear_btn.setFixedSize(26, 26)
        clear_btn.setToolTip("Clear All Annotations")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_icon_path = self._get_icon_path(ACTION_ICONS["clear"])
        if clear_icon_path:
            clear_btn.setIcon(QIcon(clear_icon_path))
            clear_btn.setIconSize(QSize(20, 20))
        else:
            clear_btn.setText("C")
        clear_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
        )
        clear_btn.clicked.connect(self._on_clear_all)
        action_group_layout.addWidget(clear_btn)

        layout.addWidget(action_group)

        return toolbar

    def _create_divider(self) -> QWidget:
        """Create a vertical divider between tool groups.

        Returns:
            Divider widget.
        """
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        divider.setFixedHeight(20)
        divider.setStyleSheet("background-color: #555;")
        divider.setContentsMargins(6, 0, 6, 0)
        return divider

    def _get_icon_path(self, filename: str) -> str | None:
        """Get full path to an icon file.

        Args:
            filename: Icon filename.

        Returns:
            Full path if exists, None otherwise.
        """
        path = os.path.join(_ICON_DIR, filename)
        return path if os.path.exists(path) else None

    def _create_tool_button(self, icon_file: str, tool: str, tooltip: str) -> QToolButton:
        """Create a tool button with icon.

        Args:
            icon_file: SVG icon filename.
            tool: Tool identifier.
            tooltip: Tooltip text.

        Returns:
            Configured QToolButton.
        """
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setFixedSize(26, 26)
        btn.setToolTip(f"{tooltip} Tool")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        icon_path = self._get_icon_path(icon_file)
        if icon_path:
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(20, 20))
        else:
            # Fallback to first letter
            btn.setText(tooltip[0])

        btn.clicked.connect(lambda: self._on_tool_selected(tool))
        return btn

    def _update_tool_button_styles(self):
        """Update tool button styles based on selection state."""
        for _tool, btn in self._tool_buttons.items():
            if btn.isChecked():
                btn.setStyleSheet(f"QToolButton {{ background: #505050; border: none; border-radius: 4px; }}{TOOLTIP_STYLE}")
            else:
                btn.setStyleSheet(
                    f"QToolButton {{ background: transparent; border: none; border-radius: 4px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
                )

    def _create_stroke_button(self, width: int, visual_height: int, name: str) -> QToolButton:
        """Create a stroke width button with visual line representation.

        Args:
            width: Actual line width in pixels.
            visual_height: Visual height of the stroke indicator.
            name: Name for tooltip.

        Returns:
            Configured QToolButton.
        """
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setFixedSize(26, 26)
        btn.setToolTip(f"{name} ({width}px)")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setChecked(width == self._line_width)

        # Store line width for styling
        btn.setProperty("line_width", width)

        # Set icon
        icon_file = STROKE_ICONS.get(width)
        if icon_file:
            icon_path = self._get_icon_path(icon_file)
            if icon_path:
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(20, 20))

        self._update_stroke_button_style(btn)
        btn.clicked.connect(lambda checked=False, w=width: self._on_line_width(w))
        return btn

    def _update_stroke_button_style(self, btn: QToolButton):
        """Update stroke button style based on state.

        Args:
            btn: Button to update.
        """
        is_selected = btn.isChecked()

        if is_selected:
            btn.setStyleSheet(f"QToolButton {{ background: #4a4a4a; border: none; border-radius: 3px; }}{TOOLTIP_STYLE}")
        else:
            btn.setStyleSheet(
                f"QToolButton {{ background: transparent; border: none; border-radius: 3px; }}QToolButton:hover {{ background: #404040; }}{TOOLTIP_STYLE}"
            )

    def _update_color_button_style(self, btn: QPushButton, color: tuple[int, int, int], selected: bool = False):
        """Update color button style.

        Args:
            btn: Button to update.
            color: RGB color tuple.
            selected: Whether this color is selected.
        """
        r, g, b = color
        if selected:
            btn.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 2px solid #fff; border-radius: 8px; box-shadow: 0 0 0 1px #333;{TOOLTIP_STYLE}"
            )
        else:
            btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 2px solid transparent; border-radius: 8px;{TOOLTIP_STYLE}")

    def _update_custom_color_button(self):
        """Update custom color button to show custom color and selection state."""
        if not self._custom_color_btn:
            return

        # Determine display color
        if self._custom_color:
            r, g, b = self._custom_color
        else:
            # Default gray when no custom color set
            r, g, b = 128, 128, 128

        # Show selection border if custom color is selected
        if self._is_custom_selected:
            self._custom_color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 2px solid #fff; border-radius: 3px;{TOOLTIP_STYLE}")
        else:
            self._custom_color_btn.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 2px solid transparent; border-radius: 3px;{TOOLTIP_STYLE}"
            )

    def _update_color_selection(self):
        """Update color button selection states."""
        # Update preset buttons (don't select if custom color is active)
        for btn, (_, rgb_color, _) in zip(self._color_buttons, COLOR_PRESETS):
            is_selected = (rgb_color == self._current_color) and not self._is_custom_selected
            self._update_color_button_style(btn, rgb_color, selected=is_selected)

        # Update custom color button
        self._update_custom_color_button()

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

        # Update button styles
        self._update_tool_button_styles()

    def _on_color_preset(self, color: tuple[int, int, int]):
        """Handle color preset selection.

        Args:
            color: Selected RGB color.
        """
        self._current_color = color
        self._is_custom_selected = False
        self._update_color_selection()
        self._view.set_color(color)

    def _on_custom_color_click(self):
        """Handle custom color button click - select custom color or open picker if not set."""
        if self._custom_color:
            # Select the existing custom color
            self._current_color = self._custom_color
            self._is_custom_selected = True
            self._update_color_selection()
            self._view.set_color(self._current_color)
        else:
            # No custom color set yet, open picker
            self._on_custom_color_picker()

    def _on_custom_color_picker(self):
        """Open color picker to set custom color."""
        initial_color = QColor(*(self._custom_color or self._current_color))
        color = QColorDialog.getColor(initial_color, self, "Select Annotation Color")

        if color.isValid():
            self._custom_color = (color.red(), color.green(), color.blue())
            self._current_color = self._custom_color
            self._is_custom_selected = True
            self._update_color_selection()
            self._view.set_color(self._current_color)

    def _on_line_width(self, width: int):
        """Handle line width selection.

        Args:
            width: Selected line width.
        """
        self._line_width = width
        self._view.set_line_width(width)

        # Update button states and styles
        for btn, (w, _, _) in zip(self._width_buttons, LINE_WIDTH_PRESETS):
            btn.setChecked(w == width)
            self._update_stroke_button_style(btn)

    def _on_undo(self):
        """Undo the last annotation creation."""
        if not self._undo_stack:
            return

        # Get last created annotation info
        annotation_id, item = self._undo_stack.pop()

        # Remove from annotation layer
        self._annotation_layer.remove(annotation_id)

        # Remove from scene
        if item and item.scene():
            # Also remove arrowhead if present
            if hasattr(item, "_arrowhead") and item._arrowhead.scene():
                self._scene.removeItem(item._arrowhead)
            self._scene.removeItem(item)

        # Recalculate next number to reuse deleted numbers
        self._recalculate_next_number()

    def _on_delete_selected(self):
        """Delete selected annotation items."""
        selected = self._scene.selectedItems()
        for item in selected:
            if hasattr(item, "annotation_id"):
                self._annotation_layer.remove(item.annotation_id)
                # Remove from undo stack if present
                self._undo_stack = [(aid, itm) for aid, itm in self._undo_stack if aid != item.annotation_id]
            # Also remove arrowhead if present
            if hasattr(item, "_arrowhead"):
                self._scene.removeItem(item._arrowhead)
            self._scene.removeItem(item)

        # Recalculate next number to reuse deleted numbers
        self._recalculate_next_number()

    def _recalculate_next_number(self):
        """Recalculate the next number to use by finding the smallest available number."""
        # Collect all numbers currently in use
        used_numbers = set()
        for ann in self._annotation_layer.annotations:
            if isinstance(ann, NumberAnnotation):
                used_numbers.add(ann.number)

        # Find the smallest available number starting from 1
        next_num = 1
        while next_num in used_numbers:
            next_num += 1

        self._next_number = next_num
        self._view.set_next_number(self._next_number)

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

        # Clear undo stack
        self._undo_stack.clear()

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

        # Find the graphics item for this annotation (for undo support)
        item = None
        for scene_item in self._scene.items():
            if hasattr(scene_item, "annotation_id") and scene_item.annotation_id == annotation.id:
                item = scene_item
                break

        # Add to undo stack
        self._undo_stack.append((annotation.id, item))

        # Update next number if this was a number annotation
        if isinstance(annotation, NumberAnnotation):
            self._recalculate_next_number()

    def get_annotations(self) -> AnnotationLayer:
        """Get the annotation layer.

        Returns:
            AnnotationLayer with all annotations.
        """
        return self._annotation_layer

    def _on_copy_to_clipboard(self):
        """Copy annotated image to clipboard."""
        from io import BytesIO

        from .annotation_renderer import render_annotations
        from .image import composite_with_background

        # Composite image with background
        composited = composite_with_background(self._image, self._background_color)

        # Render annotations onto the image
        annotated = render_annotations(composited, self._annotation_layer)

        # Convert to PNG bytes
        buffer = BytesIO()
        annotated.save(buffer, format="PNG")
        buffer.seek(0)
        png_data = buffer.read()

        # Convert to QImage
        qimage = QImage()
        qimage.loadFromData(png_data)

        # Set clipboard with multiple formats
        mime_data = QMimeData()
        mime_data.setImageData(qimage)
        mime_data.setData("image/png", QByteArray(png_data))

        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime_data)

        logger.info("Annotated image copied to clipboard")

    def _load_settings(self):
        """Load saved annotation editor settings."""
        data = self._settings.load_settings("annotation")

        # Load color settings
        saved_color = data.get("color")
        if saved_color and isinstance(saved_color, list) and len(saved_color) == 3:
            self._current_color = tuple(saved_color)
        else:
            self._current_color = (229, 57, 53)  # Default red (#e53935)

        # Load custom color
        saved_custom = data.get("custom_color")
        if saved_custom and isinstance(saved_custom, list) and len(saved_custom) == 3:
            self._custom_color = tuple(saved_custom)
        else:
            self._custom_color = None

        # Load whether custom color is selected
        self._is_custom_selected = data.get("is_custom_selected", False)

        # Load line width
        saved_width = data.get("line_width")
        if saved_width in [2, 4, 6]:
            self._line_width = saved_width
        else:
            self._line_width = 4  # Default medium

    def _save_settings(self):
        """Save current annotation editor settings."""
        data = {
            "color": list(self._current_color),
            "custom_color": list(self._custom_color) if self._custom_color else None,
            "is_custom_selected": self._is_custom_selected,
            "line_width": self._line_width,
        }
        self._settings.save_settings(data, "annotation")

    def _on_save_clicked(self):
        """Handle save button click.

        If save_callback is provided, call it and only close dialog on success.
        Otherwise, just accept the dialog.
        """
        if self._save_callback is not None:
            # Call the save callback with image, annotations, and self as parent for file dialog
            success = self._save_callback(self._image, self._annotation_layer, self)
            if success:
                self.accept()
            # If not successful, keep the dialog open
        else:
            # No callback, just accept
            self.accept()

    def accept(self):
        """Accept dialog and save settings."""
        self._save_settings()
        super().accept()

    def reject(self):
        """Reject dialog and save settings."""
        self._save_settings()
        super().reject()


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
        self._current_color = (229, 57, 53)  # Default red (#e53935)
        self._line_width = 4
        self._next_number = 1

        self._drawing = False
        self._start_pos = None
        self._current_item = None
        self._shift_pressed = False

        # Freehand drawing state
        self._freehand_path: QPainterPath | None = None
        self._freehand_points: list[tuple[float, float]] = []
        self._freehand_last_point: tuple[float, float] | None = None
        self._freehand_last_midpoint: tuple[float, float] | None = None
        self._freehand_min_distance_sq = 0.0

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
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Delete selected items
            self._delete_selected_items()
        super().keyPressEvent(event)

    def _delete_selected_items(self):
        """Delete currently selected annotation items."""
        selected = self.scene().selectedItems()
        for item in selected:
            if hasattr(item, "annotation_id"):
                # Notify parent dialog to handle deletion
                parent = self.parent()
                if parent and hasattr(parent, "_on_delete_selected"):
                    parent._on_delete_selected()
                    return

    def keyReleaseEvent(self, event):
        """Handle key release events.

        Args:
            event: Key event.
        """
        if event.key() == Qt.Key.Key_Shift:
            self._shift_pressed = False
        super().keyReleaseEvent(event)

    def wheelEvent(self, event):
        """Disable wheel scrolling to prevent unwanted view movement.

        Args:
            event: Wheel event.
        """
        event.accept()

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

        elif self._current_tool in (TOOL_ELLIPSE, TOOL_NUMBER):
            # Both ellipse and number use circle preview (number is always circle)
            self._current_item = QGraphicsEllipseItem(x, y, 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.scene().addItem(self._current_item)

        elif self._current_tool == TOOL_FREEHAND:
            # Create path for freehand drawing
            self._freehand_path = QPainterPath()
            self._freehand_path.moveTo(x, y)
            self._freehand_points = [(x, y)]
            self._freehand_last_point = (x, y)
            self._freehand_last_midpoint = None
            min_distance = max(1.5, self._line_width * 0.35)
            self._freehand_min_distance_sq = min_distance * min_distance

            # Use round caps and joins for smooth freehand appearance
            freehand_pen = QPen(QColor(*self._current_color))
            freehand_pen.setWidth(self._line_width)
            freehand_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            freehand_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

            self._current_item = QGraphicsPathItem(self._freehand_path)
            self._current_item.setPen(freehand_pen)
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

        elif self._current_tool == TOOL_NUMBER:
            # Number: center at start, radius = distance to cursor (always circle)
            radius = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            self._current_item.setRect(x1 - radius, y1 - radius, radius * 2, radius * 2)

        elif self._current_tool == TOOL_FREEHAND:
            # Add point to path
            if self._freehand_path is not None and self._append_freehand_point(x2, y2):
                self._current_item.setPath(self._freehand_path)

    def _append_freehand_point(self, x: float, y: float) -> bool:
        """Append a filtered point to the freehand path with light smoothing."""
        if self._freehand_points:
            last_x, last_y = self._freehand_points[-1]
            dx = x - last_x
            dy = y - last_y
            if dx * dx + dy * dy < self._freehand_min_distance_sq:
                return False

        self._freehand_points.append((x, y))

        if self._freehand_path is None:
            return True

        if self._freehand_last_point is None:
            self._freehand_last_point = (x, y)
            return True

        mid_x = (self._freehand_last_point[0] + x) / 2.0
        mid_y = (self._freehand_last_point[1] + y) / 2.0

        if self._freehand_last_midpoint is None:
            self._freehand_path.lineTo(mid_x, mid_y)
        else:
            self._freehand_path.quadTo(self._freehand_last_point[0], self._freehand_last_point[1], mid_x, mid_y)

        self._freehand_last_midpoint = (mid_x, mid_y)
        self._freehand_last_point = (x, y)
        return True

    def _finish_freehand_path(self):
        """Finish the smoothed freehand path at the last point."""
        if self._freehand_path is None or self._freehand_last_point is None:
            return
        if self._freehand_last_midpoint is not None:
            self._freehand_path.lineTo(self._freehand_last_point[0], self._freehand_last_point[1])

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

        elif self._current_tool == TOOL_NUMBER:
            # Number: center at start, radius = distance to cursor
            radius_px = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

            # Require minimum size
            if radius_px < 10:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                return

            # Radius as ratio of width
            radius_ratio = radius_px / width

            annotation = NumberAnnotation(
                x=ratio_x1,
                y=ratio_y1,
                radius=radius_ratio,
                number=self._next_number,
                color=self._current_color,
                line_width=self._line_width,
            )

            if self._current_item:
                self._current_item.annotation_id = annotation.id
                self._current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
                # Update circle to final position (centered at start)
                self._current_item.setRect(x1 - radius_px, y1 - radius_px, radius_px * 2, radius_px * 2)

                # Add number text
                self._add_number_text(self._current_item, x1, y1, radius_px)

        elif self._current_tool == TOOL_FREEHAND:
            if self._freehand_path is not None:
                self._append_freehand_point(x2, y2)
                self._finish_freehand_path()
                if self._current_item:
                    self._current_item.setPath(self._freehand_path)

            # Require minimum points (at least 2 distinct points)
            if len(self._freehand_points) < 2:
                if self._current_item:
                    self.scene().removeItem(self._current_item)
                self._current_item = None
                self._freehand_path = None
                self._freehand_points = []
                self._freehand_last_point = None
                self._freehand_last_midpoint = None
                self._freehand_min_distance_sq = 0.0
                return

            # Simplify path using Douglas-Peucker algorithm
            simplified_points = self._simplify_path(self._freehand_points, epsilon=2.0)

            # Convert pixel coordinates to ratio coordinates
            ratio_points = [(px / width, py / height) for px, py in simplified_points]

            annotation = FreehandAnnotation(
                points=ratio_points,
                color=self._current_color,
                line_width=self._line_width,
            )

            if self._current_item:
                self._current_item.annotation_id = annotation.id
                self._current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

            # Reset freehand state
            self._freehand_path = None
            self._freehand_points = []
            self._freehand_last_point = None
            self._freehand_last_midpoint = None
            self._freehand_min_distance_sq = 0.0

        if annotation:
            self.annotation_created.emit(annotation)

        self._current_item = None

    def _add_number_text(self, ellipse_item: QGraphicsEllipseItem, cx: float, cy: float, radius: float):
        """Add number text to a number annotation circle.

        Args:
            ellipse_item: The circle item.
            cx, cy: Center position.
            radius: Circle radius in pixels.
        """
        text_item = QGraphicsTextItem(str(self._next_number))
        text_item.setDefaultTextColor(QColor(*self._current_color))
        font = QFont()
        font.setPixelSize(max(10, int(radius * 1.2)))
        font.setBold(True)
        text_item.setFont(font)

        # Center text in circle
        text_rect = text_item.boundingRect()
        text_item.setPos(cx - text_rect.width() / 2, cy - text_rect.height() / 2)
        text_item.setParentItem(ellipse_item)

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

    def _simplify_path(self, points: list[tuple[float, float]], epsilon: float = 2.0) -> list[tuple[float, float]]:
        """Simplify path using the Douglas-Peucker algorithm.

        Reduces the number of points in a path while preserving its shape.

        Args:
            points: List of (x, y) tuples.
            epsilon: Maximum distance threshold for simplification.

        Returns:
            Simplified list of points.
        """
        if len(points) < 3:
            return points

        # Find the point with maximum distance from the line between first and last
        first = points[0]
        last = points[-1]

        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(points) - 1):
            dist = self._perpendicular_distance(points[i], first, last)
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # If max distance is greater than epsilon, recursively simplify
        if max_dist > epsilon:
            # Recursive call
            left = self._simplify_path(points[: max_idx + 1], epsilon)
            right = self._simplify_path(points[max_idx:], epsilon)

            # Concatenate results (avoid duplicate point at junction)
            return left[:-1] + right
        else:
            # Return just endpoints
            return [first, last]

    def _perpendicular_distance(self, point: tuple[float, float], line_start: tuple[float, float], line_end: tuple[float, float]) -> float:
        """Calculate perpendicular distance from point to line.

        Args:
            point: Point (x, y).
            line_start: Line start (x, y).
            line_end: Line end (x, y).

        Returns:
            Perpendicular distance.
        """
        x, y = point
        x1, y1 = line_start
        x2, y2 = line_end

        # Handle degenerate case where line is a point
        dx = x2 - x1
        dy = y2 - y1
        line_len_sq = dx * dx + dy * dy

        if line_len_sq == 0:
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)

        # Calculate perpendicular distance using cross product formula
        numerator = abs(dy * x - dx * y + x2 * y1 - y2 * x1)
        denominator = math.sqrt(line_len_sq)

        return numerator / denominator


def show_annotation_editor(
    image: Image.Image,
    parent=None,
    background_color: tuple[int, int, int] | None = None,
    save_callback: Callable[[Image.Image, AnnotationLayer, QWidget], bool] | None = None,
) -> AnnotationLayer | None:
    """Show the annotation editor dialog.

    Args:
        image: PIL Image to annotate.
        parent: Parent widget.
        background_color: RGB tuple for background compositing, or None for transparent.
        save_callback: Optional callback for save action. Should return True if save succeeded.
                      If provided, the dialog only closes when save succeeds.
                      Signature: (image, annotations, parent_widget) -> bool

    Returns:
        AnnotationLayer if accepted, None if cancelled.
    """
    dialog = AnnotationEditorDialog(image, parent, background_color, save_callback)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_annotations()
    return None
