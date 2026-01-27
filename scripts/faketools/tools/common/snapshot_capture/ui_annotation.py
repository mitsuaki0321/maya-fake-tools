"""Annotation editor UI for snapshot capture.

Provides a QGraphicsView-based canvas for adding and editing annotations
on captured images.
"""

from __future__ import annotations

import logging
import math
import os
from typing import TYPE_CHECKING

from ....lib_ui import ToolSettingsManager, center_on_screen, get_maya_main_window
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
    QGraphicsProxyWidget,
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
    QPlainTextEdit,
    QPointF,
    QPolygonF,
    QPushButton,
    QSize,
    Qt,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Signal,
)
from .annotation import (
    AnnotationLayer,
    ArrowAnnotation,
    EllipseAnnotation,
    FreehandAnnotation,
    LineAnnotation,
    NumberAnnotation,
    RectangleAnnotation,
    TextAnnotation,
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
TOOL_TEXT = "text"

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
    TOOL_TEXT: "tool_text.svg",
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


class MovableLineItem(QGraphicsLineItem):
    """Line item that tracks movement for undo support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self._original_pos: QPointF | None = None
        self.annotation_id: str | None = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._original_pos is None:
            self._original_pos = self.pos()
        return super().itemChange(change, value)


class MovableRectItem(QGraphicsRectItem):
    """Rectangle item that tracks movement for undo support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self._original_pos: QPointF | None = None
        self.annotation_id: str | None = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._original_pos is None:
            self._original_pos = self.pos()
        return super().itemChange(change, value)


class MovableEllipseItem(QGraphicsEllipseItem):
    """Ellipse item that tracks movement for undo support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self._original_pos: QPointF | None = None
        self.annotation_id: str | None = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._original_pos is None:
            self._original_pos = self.pos()
        return super().itemChange(change, value)


class MovablePathItem(QGraphicsPathItem):
    """Path item that tracks movement for undo support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self._original_pos: QPointF | None = None
        self.annotation_id: str | None = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._original_pos is None:
            self._original_pos = self.pos()
        return super().itemChange(change, value)


class MovableTextItem(QGraphicsRectItem):
    """Text item container that tracks movement for undo support.

    Uses QGraphicsRectItem as a container for QGraphicsTextItem to enable
    proper selection and movement handling.
    """

    def __init__(self, text_item: QGraphicsTextItem, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self._original_pos: QPointF | None = None
        self.annotation_id: str | None = None

        # Make container invisible
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        # Set text item as child
        self._text_item = text_item
        self._text_item.setParentItem(self)

    @property
    def text_item(self) -> QGraphicsTextItem:
        """Get the child text item."""
        return self._text_item

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._original_pos is None:
            self._original_pos = self.pos()
        return super().itemChange(change, value)


class TextInputWidget(QWidget):
    """Widget for inline multiline text input on canvas."""

    text_accepted = Signal(str)
    text_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the input widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlaceholderText("Enter text... (Ctrl+Enter to confirm)")
        self._text_edit.setMinimumWidth(150)
        self._text_edit.setStyleSheet(
            "QPlainTextEdit { background: rgba(42, 42, 42, 120); color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 3px; padding: 4px 8px; font-size: 14px; }"
        )
        # Set initial fixed height (will grow with content)
        self._min_height = 60
        self._max_height = 200
        self._text_edit.setFixedHeight(self._min_height)
        self._text_edit.textChanged.connect(self._adjust_size)
        layout.addWidget(self._text_edit)

    def _adjust_size(self):
        """Adjust widget height based on content."""
        # Calculate height based on line count and font metrics
        font_metrics = self._text_edit.fontMetrics()
        line_height = font_metrics.lineSpacing()
        line_count = max(1, self._text_edit.document().blockCount())
        # Add padding for margins (top/bottom padding + border)
        content_height = line_count * line_height + 24
        # Clamp between min and max, only grow (never shrink below min)
        new_height = max(self._min_height, min(self._max_height, content_height))
        self._text_edit.setFixedHeight(new_height)

    def _on_accept(self):
        """Handle text acceptance."""
        text = self._text_edit.toPlainText().strip()
        if text:
            self.text_accepted.emit(text)
        else:
            self.text_cancelled.emit()

    def keyPressEvent(self, event):
        """Handle key press events.

        - Ctrl+Enter: Confirm text
        - Escape: Cancel input
        - Enter: Insert newline (default behavior)
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._on_accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            self.text_cancelled.emit()
            return
        super().keyPressEvent(event)

    def set_focus(self):
        """Set focus to the text edit."""
        self._text_edit.setFocus()
        self._text_edit.selectAll()

    def has_text(self) -> bool:
        """Check if the text edit has non-empty content."""
        return bool(self._text_edit.toPlainText().strip())

    def accept_text(self):
        """Accept the current text (for external calls like outside click)."""
        self._on_accept()

    def get_text_offset(self) -> tuple[float, float]:
        """Get the offset from widget origin to where text actually starts.

        Returns:
            Tuple of (x_offset, y_offset) in pixels.
        """
        # Get the cursor rect at position 0 to find where text starts
        cursor = self._text_edit.textCursor()
        cursor.setPosition(0)
        cursor_rect = self._text_edit.cursorRect(cursor)

        # Add the viewport offset within the QPlainTextEdit
        viewport_pos = self._text_edit.viewport().pos()

        return (
            viewport_pos.x() + cursor_rect.x(),
            viewport_pos.y() + cursor_rect.y(),
        )


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

        # Centering flag
        self._first_show = True

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
            (TOOL_TEXT, "Text"),
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

    def _update_tool_buttons(self, tool: str):
        """Update tool button visual states without triggering set_tool.

        Used by AnnotationGraphicsView for spacebar temporary tool switch.

        Args:
            tool: Tool identifier to show as selected.
        """
        self._current_tool = tool
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)
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
        """Undo the last annotation action (create or move)."""
        if not self._undo_stack:
            return

        # Get last action info
        entry = self._undo_stack.pop()

        # Handle new format: (action_type, annotation_id, item, extra_data)
        if len(entry) == 4:
            action_type, annotation_id, item, extra_data = entry
        else:
            # Legacy format: (annotation_id, item) - treat as create
            action_type = "create"
            annotation_id, item = entry
            extra_data = None

        if action_type == "create":
            # Remove from annotation layer
            self._annotation_layer.remove(annotation_id)

            # Remove from scene
            if item and item.scene():
                # Child items (arrowhead, text) are removed automatically
                self._scene.removeItem(item)

            # Recalculate next number to reuse deleted numbers
            self._recalculate_next_number()

        elif action_type == "move":
            # Restore original coordinates
            annotation = self._annotation_layer.get(annotation_id)
            if annotation and extra_data:
                for key, value in extra_data.items():
                    setattr(annotation, key, value)

                # Reset item position to origin (coords are stored in annotation)
                if item and item.scene():
                    item.setPos(0, 0)
                    item._original_pos = None

        elif action_type == "scale":
            # Restore original size/coordinates
            annotation = self._annotation_layer.get(annotation_id)
            if annotation and extra_data:
                for key, value in extra_data.items():
                    setattr(annotation, key, value)

                # Update visual item to reflect restored values
                if item and item.scene():
                    self._view._refresh_item_from_annotation(item, annotation)

    def _on_delete_selected(self):
        """Delete selected annotation items."""
        selected = self._scene.selectedItems()
        for item in selected:
            if hasattr(item, "annotation_id"):
                annotation_id = item.annotation_id
                self._annotation_layer.remove(annotation_id)
                # Remove from undo stack if present (handle both old and new formats)
                new_stack = []
                for entry in self._undo_stack:
                    if len(entry) == 4:
                        _, aid, _, _ = entry
                    else:
                        aid, _ = entry
                    if aid != annotation_id:
                        new_stack.append(entry)
                self._undo_stack = new_stack
            # Child items (arrowhead, text) are removed automatically
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
        # Child items (arrowheads, text) are removed automatically with parents
        for item in list(self._scene.items()):
            if hasattr(item, "annotation_id"):
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

        # Add to undo stack with new format: (action_type, annotation_id, item, extra_data)
        self._undo_stack.append(("create", annotation.id, item, None))

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

    def showEvent(self, event):
        """Handle show event to center dialog on first display."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Defer centering to ensure dialog size is finalized
            QTimer.singleShot(0, lambda: center_on_screen(self, target="maya"))

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

        # Spacebar temporary tool switch state
        self._spacebar_pressed = False
        self._tool_before_spacebar: str | None = None

        # Freehand drawing state
        self._freehand_path: QPainterPath | None = None
        self._freehand_points: list[tuple[float, float]] = []
        self._freehand_last_point: tuple[float, float] | None = None
        self._freehand_last_midpoint: tuple[float, float] | None = None
        self._freehand_min_distance_sq = 0.0

        # Text input state
        self._text_input_proxy: QGraphicsProxyWidget | None = None
        self._text_input_widget: TextInputWidget | None = None
        self._text_input_pos: QPointF | None = None

        # Custom signal
        self.annotation_created = self._Signal()

        # Set initial cursor
        self._update_cursor()

    def set_tool(self, tool: str):
        """Set the current drawing tool.

        Args:
            tool: Tool identifier.
        """
        # Clear spacebar state if tool is changed manually (e.g., via toolbar button)
        if self._spacebar_pressed:
            self._spacebar_pressed = False
            self._tool_before_spacebar = None

        # Cancel any pending text input when switching tools
        if self._current_tool == TOOL_TEXT and tool != TOOL_TEXT:
            self._cancel_text_input()

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
        elif self._current_tool == TOOL_TEXT:
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def keyPressEvent(self, event):
        """Handle key press events.

        Args:
            event: Key event.
        """
        # Handle spacebar for temporary tool switch
        if event.key() == Qt.Key.Key_Space:
            # Ignore auto-repeat events (key held down)
            if event.isAutoRepeat():
                return
            # Ignore if text input is active (allow space character input)
            if self._text_input_widget is not None:
                super().keyPressEvent(event)
                return
            # Ignore if drawing in progress
            if self._drawing:
                return
            # Ignore if already in spacebar mode or already using select tool
            if self._spacebar_pressed or self._current_tool == TOOL_SELECT:
                return
            # Save current tool and switch to select tool
            self._spacebar_pressed = True
            self._tool_before_spacebar = self._current_tool
            self._current_tool = TOOL_SELECT
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self._update_cursor()
            # Notify parent to update toolbar button state
            parent = self.parent()
            if parent and hasattr(parent, "_update_tool_buttons"):
                parent._update_tool_buttons(TOOL_SELECT)
            return

        if event.key() == Qt.Key.Key_Shift:
            self._shift_pressed = True
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Delete selected items
            self._delete_selected_items()
        elif event.key() == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Undo last action
            parent = self.parent()
            if parent and hasattr(parent, "_on_undo"):
                parent._on_undo()
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
        # Handle spacebar release to restore original tool
        if event.key() == Qt.Key.Key_Space:
            # Ignore auto-repeat events (key held down)
            if event.isAutoRepeat():
                return
            if self._spacebar_pressed and self._tool_before_spacebar is not None:
                original_tool = self._tool_before_spacebar
                self._spacebar_pressed = False
                self._tool_before_spacebar = None
                self._current_tool = original_tool
                if original_tool == TOOL_SELECT:
                    self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                else:
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self._update_cursor()
                # Notify parent to update toolbar button state
                parent = self.parent()
                if parent and hasattr(parent, "_update_tool_buttons"):
                    parent._update_tool_buttons(original_tool)
            return

        if event.key() == Qt.Key.Key_Shift:
            self._shift_pressed = False
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        """Handle focus out events.

        Restores the original tool if spacebar was pressed when focus is lost.

        Args:
            event: Focus event.
        """
        # Restore original tool if spacebar mode is active
        if self._spacebar_pressed and self._tool_before_spacebar is not None:
            original_tool = self._tool_before_spacebar
            self._spacebar_pressed = False
            self._tool_before_spacebar = None
            self._current_tool = original_tool
            if original_tool == TOOL_SELECT:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._update_cursor()
            # Notify parent to update toolbar button state
            parent = self.parent()
            if parent and hasattr(parent, "_update_tool_buttons"):
                parent._update_tool_buttons(original_tool)
        super().focusOutEvent(event)

    def wheelEvent(self, event):
        """Handle wheel events for scaling selected items.

        Ctrl+wheel scales selected annotation items.
        Without Ctrl, wheel is disabled to prevent unwanted scrolling.

        Args:
            event: Wheel event.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            selected_items = self.scene().selectedItems()
            if selected_items:
                # Determine scale factor from wheel direction
                delta = event.angleDelta().y()
                scale_factor = 1.1 if delta > 0 else 0.9

                for item in selected_items:
                    self._scale_item(item, scale_factor)

                event.accept()
                return

        event.accept()

    def mousePressEvent(self, event):
        """Handle mouse press events.

        Args:
            event: Mouse event.
        """
        # Handle click outside text input widget
        if self._text_input_widget and self._text_input_proxy:
            click_pos = self.mapToScene(event.pos())
            proxy_rect = self._text_input_proxy.sceneBoundingRect()
            if not proxy_rect.contains(click_pos):
                # Click outside text input - confirm if has text, cancel otherwise
                if self._text_input_widget.has_text():
                    self._text_input_widget.accept_text()
                else:
                    self._cancel_text_input()
                # Don't return - allow starting new text input or other tool action

        if self._current_tool == TOOL_SELECT:
            super().mousePressEvent(event)
            return

        if self._current_tool == TOOL_TEXT:
            if event.button() == Qt.MouseButton.LeftButton:
                self._start_text_input(event)
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
            # Finalize any item moves before calling super
            self._finalize_item_moves()
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

    def _snap_radius(self, radius: float, increment: float = 10.0) -> float:
        """Snap radius to increments.

        Args:
            radius: Current radius in pixels.
            increment: Snap increment in pixels.

        Returns:
            Snapped radius.
        """
        return max(increment, round(radius / increment) * increment)

    def _create_preview_item(self):
        """Create a preview item for the current tool."""
        pen = QPen(QColor(*self._current_color))
        pen.setWidth(self._line_width)

        x, y = self._start_pos.x(), self._start_pos.y()

        if self._current_tool in (TOOL_LINE, TOOL_ARROW):
            self._current_item = MovableLineItem(x, y, x, y)
            self._current_item.setPen(pen)
            self.scene().addItem(self._current_item)

        elif self._current_tool == TOOL_RECT:
            self._current_item = MovableRectItem(x, y, 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.scene().addItem(self._current_item)

        elif self._current_tool in (TOOL_ELLIPSE, TOOL_NUMBER):
            # Both ellipse and number use circle preview (number is always circle)
            self._current_item = MovableEllipseItem(x, y, 0, 0)
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

            self._current_item = MovablePathItem(self._freehand_path)
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
            if shift_pressed:
                radius = self._snap_radius(radius)
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
                # Update ellipse to final position
                left_px = min(x1, x2)
                top_px = min(y1, y2)
                w_px = abs(x2 - x1)
                h_px = abs(y2 - y1)
                self._current_item.setRect(left_px, top_px, w_px, h_px)

        elif self._current_tool == TOOL_NUMBER:
            # Number: center at start, radius = distance to cursor
            radius_px = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if shift_pressed:
                radius_px = self._snap_radius(radius_px)

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

            # Reset freehand state
            self._freehand_path = None
            self._freehand_points = []
            self._freehand_last_point = None
            self._freehand_last_midpoint = None
            self._freehand_min_distance_sq = 0.0

        if annotation:
            self.annotation_created.emit(annotation)

        self._current_item = None

    def _finalize_item_moves(self):
        """Finalize item movements and update annotation data."""
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        if width == 0 or height == 0:
            return

        parent = self.parent()
        if not parent:
            return

        # Check all items for movement
        for item in self.scene().items():
            if not hasattr(item, "_original_pos") or not hasattr(item, "annotation_id"):
                continue

            original_pos = item._original_pos
            if original_pos is None:
                continue

            # Calculate movement delta
            current_pos = item.pos()
            dx = current_pos.x() - original_pos.x()
            dy = current_pos.y() - original_pos.y()

            # Skip if no significant movement
            if abs(dx) < 1 and abs(dy) < 1:
                item._original_pos = None
                continue

            # Convert to ratio delta
            ratio_dx = dx / width
            ratio_dy = dy / height

            # Get the annotation from parent
            annotation_id = item.annotation_id
            if hasattr(parent, "_annotation_layer"):
                annotation = parent._annotation_layer.get(annotation_id)
                if annotation:
                    # Store original values for undo
                    original_coords = self._get_annotation_coords(annotation)

                    # Update annotation coordinates based on type
                    self._update_annotation_coords(annotation, ratio_dx, ratio_dy)

                    # Add to undo stack
                    if hasattr(parent, "_undo_stack"):
                        parent._undo_stack.append(("move", annotation_id, item, original_coords))

            # Reset original position
            item._original_pos = None

    def _get_annotation_coords(self, annotation) -> dict:
        """Get current coordinates from an annotation for undo.

        Args:
            annotation: Annotation object.

        Returns:
            Dictionary of coordinate values.
        """
        ann_type = annotation.annotation_type

        if ann_type in ("line", "arrow"):
            return {
                "start_x": annotation.start_x,
                "start_y": annotation.start_y,
                "end_x": annotation.end_x,
                "end_y": annotation.end_y,
            }
        elif ann_type == "rectangle":
            return {
                "x": annotation.x,
                "y": annotation.y,
            }
        elif ann_type == "ellipse":
            return {
                "center_x": annotation.center_x,
                "center_y": annotation.center_y,
            }
        elif ann_type == "number":
            return {
                "x": annotation.x,
                "y": annotation.y,
            }
        elif ann_type == "freehand":
            return {
                "points": list(annotation.points),
            }
        elif ann_type == "text":
            return {
                "x": annotation.x,
                "y": annotation.y,
                "font_size": annotation.font_size,
            }
        return {}

    def _update_annotation_coords(self, annotation, dx: float, dy: float):
        """Update annotation coordinates by delta.

        Args:
            annotation: Annotation object.
            dx: X delta in ratio coordinates.
            dy: Y delta in ratio coordinates.
        """
        ann_type = annotation.annotation_type

        if ann_type in ("line", "arrow"):
            annotation.start_x += dx
            annotation.start_y += dy
            annotation.end_x += dx
            annotation.end_y += dy
        elif ann_type == "rectangle":
            annotation.x += dx
            annotation.y += dy
        elif ann_type == "ellipse":
            annotation.center_x += dx
            annotation.center_y += dy
        elif ann_type == "number":
            annotation.x += dx
            annotation.y += dy
        elif ann_type == "freehand":
            annotation.points = [(px + dx, py + dy) for px, py in annotation.points]
        elif ann_type == "text":
            annotation.x += dx
            annotation.y += dy

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
        """Add an arrowhead polygon as a child of the line item.

        Args:
            line_item: The parent line item.
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

        # Create polygon item as child of line item so it moves together
        arrow_item = QGraphicsPolygonItem(polygon, line_item)
        arrow_item.setBrush(QBrush(QColor(*self._current_color)))
        arrow_item.setPen(QPen(Qt.PenStyle.NoPen))

        # Store reference for cleanup
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

    # ==================== Text Input Methods ====================

    def _start_text_input(self, event):
        """Start inline text input at click position.

        Args:
            event: Mouse event.
        """
        # Remove any existing text input immediately (synchronous)
        self._cleanup_text_input_sync()

        # Get scene position
        self._text_input_pos = self.mapToScene(event.pos())

        # Create text input widget
        self._text_input_widget = TextInputWidget()
        self._text_input_widget.text_accepted.connect(self._finalize_text_input)
        self._text_input_widget.text_cancelled.connect(self._cancel_text_input)

        # Add to scene via proxy widget
        self._text_input_proxy = QGraphicsProxyWidget()
        self._text_input_proxy.setWidget(self._text_input_widget)
        self._text_input_proxy.setZValue(1000)  # Above other items
        self.scene().addItem(self._text_input_proxy)

        # Position widget so text starts at click position
        # Need to defer positioning until widget is laid out
        self._text_input_proxy.setPos(self._text_input_pos)
        QTimer.singleShot(0, self._adjust_text_input_position)

        # Set focus to input
        self._text_input_widget.set_focus()

    def _adjust_text_input_position(self):
        """Adjust text input widget position after layout is complete."""
        if not self._text_input_widget or not self._text_input_proxy or not self._text_input_pos:
            return

        # Get the offset from widget origin to where text actually starts
        offset_x, offset_y = self._text_input_widget.get_text_offset()

        # Save the y offset for use when creating final text item
        self._text_input_offset = (offset_x, offset_y)

        # Adjust position so text starts at click position
        adjusted_pos = QPointF(
            self._text_input_pos.x() - offset_x,
            self._text_input_pos.y() - offset_y,
        )
        self._text_input_proxy.setPos(adjusted_pos)

    def _finalize_text_input(self, text: str):
        """Finalize text input and create annotation.

        Args:
            text: The text content.
        """
        if not self._text_input_pos:
            # Defer cleanup to avoid deleting widget during signal processing
            QTimer.singleShot(0, self._cleanup_text_input)
            return

        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        if width == 0 or height == 0:
            QTimer.singleShot(0, self._cleanup_text_input)
            return

        # Store values before cleanup
        pos_x = self._text_input_pos.x()
        pos_y = self._text_input_pos.y()

        # Get input offset for vertical alignment adjustment
        input_offset_y = 0.0
        if hasattr(self, "_text_input_offset") and self._text_input_offset:
            _, input_offset_y = self._text_input_offset

        # Calculate adjusted position (same adjustment as _create_text_item)
        adjusted_y = pos_y - input_offset_y

        # Convert to ratio coordinates using adjusted position
        ratio_x = pos_x / width
        ratio_y = adjusted_y / height

        # Create text annotation (bold if line width >= 4)
        use_bold = self._line_width >= 4
        annotation = TextAnnotation(
            text=text,
            x=ratio_x,
            y=ratio_y,
            font_size=16,
            color=self._current_color,
            background_color=None,  # No background for simple text
            bold=use_bold,
        )

        # Create visual text item (uses annotation.x/y which now have adjusted coords)
        self._create_text_item(annotation, pos_x, adjusted_y)

        # Emit signal
        self.annotation_created.emit(annotation)

        # Defer cleanup to avoid deleting widget during signal processing
        QTimer.singleShot(0, self._cleanup_text_input)

    def _cancel_text_input(self):
        """Cancel text input without creating annotation."""
        # Defer cleanup to avoid deleting widget during signal processing
        QTimer.singleShot(0, self._cleanup_text_input)

    def _cleanup_text_input_sync(self):
        """Clean up text input widget synchronously (for starting new input)."""
        # Disconnect signals first to prevent further callbacks
        if self._text_input_widget:
            try:
                self._text_input_widget.text_accepted.disconnect(self._finalize_text_input)
                self._text_input_widget.text_cancelled.disconnect(self._cancel_text_input)
            except (RuntimeError, TypeError):
                pass  # Already disconnected or widget deleted

        if self._text_input_proxy:
            if self._text_input_proxy.scene():
                self.scene().removeItem(self._text_input_proxy)
            self._text_input_proxy = None

        self._text_input_widget = None
        self._text_input_pos = None

    def _cleanup_text_input(self):
        """Clean up text input widget with deferred deletion."""
        # Disconnect signals first to prevent further callbacks
        if self._text_input_widget:
            try:
                self._text_input_widget.text_accepted.disconnect(self._finalize_text_input)
                self._text_input_widget.text_cancelled.disconnect(self._cancel_text_input)
            except (RuntimeError, TypeError):
                pass  # Already disconnected or widget deleted

        if self._text_input_proxy:
            if self._text_input_proxy.scene():
                self.scene().removeItem(self._text_input_proxy)
            # Schedule for deletion to ensure clean removal
            self._text_input_proxy.deleteLater()
            self._text_input_proxy = None

        if self._text_input_widget:
            self._text_input_widget.deleteLater()
            self._text_input_widget = None

        self._text_input_pos = None
        self._text_input_offset = None

    def _create_text_item(self, annotation: TextAnnotation, x: float, y: float):
        """Create a visual text item for a text annotation.

        Args:
            annotation: TextAnnotation object.
            x: X position in pixels.
            y: Y position in pixels.
        """
        # Create text item
        text_item = QGraphicsTextItem(annotation.text)
        text_item.setDefaultTextColor(QColor(*annotation.color))

        font = QFont()
        font.setPixelSize(annotation.font_size)
        font.setBold(getattr(annotation, "bold", False))
        text_item.setFont(font)

        # Remove internal document margin so text starts exactly at position
        text_item.document().setDocumentMargin(0)

        # Create container for selection/movement
        # Position is already adjusted by caller (x, y are the final display coordinates)
        text_rect = text_item.boundingRect()
        container = MovableTextItem(text_item, 0, 0, text_rect.width(), text_rect.height())
        container.annotation_id = annotation.id
        container.setPos(x, y)
        # Clear _original_pos to prevent _finalize_item_moves from adding duplicate offset
        container._original_pos = None

        self.scene().addItem(container)

    # ==================== Scale Methods ====================

    def _scale_item(self, item, scale_factor: float):
        """Scale an annotation item.

        Args:
            item: QGraphicsItem to scale.
            scale_factor: Scale multiplier (>1 to enlarge, <1 to shrink).
        """
        annotation_id = getattr(item, "annotation_id", None)
        if not annotation_id:
            return

        parent = self.parent()
        if not parent or not hasattr(parent, "_annotation_layer"):
            return

        annotation = parent._annotation_layer.get(annotation_id)
        if not annotation:
            return

        # Store original values for undo
        original_coords = self._get_annotation_coords(annotation)

        # Scale based on annotation type
        self._scale_annotation(item, annotation, scale_factor)

        # Add to undo stack
        if hasattr(parent, "_undo_stack"):
            parent._undo_stack.append(("scale", annotation_id, item, original_coords))

    def _scale_annotation(self, item, annotation, scale_factor: float):
        """Scale annotation based on its type.

        Args:
            item: QGraphicsItem.
            annotation: Annotation object.
            scale_factor: Scale multiplier.
        """
        ann_type = annotation.annotation_type

        if ann_type in ("line", "arrow"):
            self._scale_line_annotation(item, annotation, scale_factor)
        elif ann_type == "rectangle":
            self._scale_rect_annotation(item, annotation, scale_factor)
        elif ann_type == "ellipse":
            self._scale_ellipse_annotation(item, annotation, scale_factor)
        elif ann_type == "number":
            self._scale_number_annotation(item, annotation, scale_factor)
        elif ann_type == "freehand":
            self._scale_freehand_annotation(item, annotation, scale_factor)
        elif ann_type == "text":
            self._scale_text_annotation(item, annotation, scale_factor)

    def _scale_line_annotation(self, item, annotation, scale_factor: float):
        """Scale line/arrow annotation from center.

        Args:
            item: QGraphicsLineItem.
            annotation: LineAnnotation or ArrowAnnotation.
            scale_factor: Scale multiplier.
        """
        # Calculate center point
        cx = (annotation.start_x + annotation.end_x) / 2
        cy = (annotation.start_y + annotation.end_y) / 2

        # Scale endpoints from center
        annotation.start_x = cx + (annotation.start_x - cx) * scale_factor
        annotation.start_y = cy + (annotation.start_y - cy) * scale_factor
        annotation.end_x = cx + (annotation.end_x - cx) * scale_factor
        annotation.end_y = cy + (annotation.end_y - cy) * scale_factor

        # Update visual item
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        x1 = annotation.start_x * width
        y1 = annotation.start_y * height
        x2 = annotation.end_x * width
        y2 = annotation.end_y * height

        if isinstance(item, MovableLineItem):
            # Reset item position to use absolute coordinates
            item.setPos(0, 0)
            item._original_pos = None  # Clear to avoid affecting next move calculation

            # For arrows, shorten line and update arrowhead
            if annotation.annotation_type == "arrow":
                arrow_length = annotation.line_width * 4
                angle = math.atan2(y2 - y1, x2 - x1)
                line_end_x = x2 - arrow_length * math.cos(angle)
                line_end_y = y2 - arrow_length * math.sin(angle)
                item.setLine(x1, y1, line_end_x, line_end_y)

                # Update arrowhead
                if hasattr(item, "_arrowhead") and item._arrowhead:
                    self._update_arrowhead(item, x1, y1, x2, y2)
            else:
                item.setLine(x1, y1, x2, y2)

    def _update_arrowhead(self, line_item, x1: float, y1: float, x2: float, y2: float):
        """Update arrowhead polygon position.

        Args:
            line_item: Parent line item.
            x1, y1: Start point.
            x2, y2: End point (arrow tip).
        """
        if not hasattr(line_item, "_arrowhead") or not line_item._arrowhead:
            return

        # Get line width from annotation
        parent = self.parent()
        if parent and hasattr(parent, "_annotation_layer"):
            annotation_id = getattr(line_item, "annotation_id", None)
            if annotation_id:
                annotation = parent._annotation_layer.get(annotation_id)
                if annotation:
                    line_width = annotation.line_width
                else:
                    line_width = self._line_width
            else:
                line_width = self._line_width
        else:
            line_width = self._line_width

        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = line_width * 4
        arrow_angle = math.pi / 6

        left_x = x2 - arrow_length * math.cos(angle - arrow_angle)
        left_y = y2 - arrow_length * math.sin(angle - arrow_angle)
        right_x = x2 - arrow_length * math.cos(angle + arrow_angle)
        right_y = y2 - arrow_length * math.sin(angle + arrow_angle)

        polygon = QPolygonF(
            [
                QPointF(x2, y2),
                QPointF(left_x, left_y),
                QPointF(right_x, right_y),
            ]
        )
        line_item._arrowhead.setPolygon(polygon)

    def _scale_rect_annotation(self, item, annotation, scale_factor: float):
        """Scale rectangle annotation from center.

        Args:
            item: MovableRectItem.
            annotation: RectangleAnnotation.
            scale_factor: Scale multiplier.
        """
        # Calculate center
        cx = annotation.x + annotation.width / 2
        cy = annotation.y + annotation.height / 2

        # Scale dimensions
        new_width = annotation.width * scale_factor
        new_height = annotation.height * scale_factor

        # Update annotation (maintain center)
        annotation.width = new_width
        annotation.height = new_height
        annotation.x = cx - new_width / 2
        annotation.y = cy - new_height / 2

        # Update visual item
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        left_px = annotation.x * width
        top_px = annotation.y * height
        w_px = annotation.width * width
        h_px = annotation.height * height

        if isinstance(item, MovableRectItem):
            # Reset item position to use absolute coordinates
            item.setPos(0, 0)
            item._original_pos = None  # Clear to avoid affecting next move calculation
            item.setRect(left_px, top_px, w_px, h_px)

    def _scale_ellipse_annotation(self, item, annotation, scale_factor: float):
        """Scale ellipse annotation.

        Args:
            item: MovableEllipseItem.
            annotation: EllipseAnnotation.
            scale_factor: Scale multiplier.
        """
        # Scale radii
        annotation.radius_x *= scale_factor
        annotation.radius_y *= scale_factor

        # Update visual item
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        cx = annotation.center_x * width
        cy = annotation.center_y * height
        rx = annotation.radius_x * width
        ry = annotation.radius_y * height

        if isinstance(item, MovableEllipseItem):
            # Reset item position to use absolute coordinates
            item.setPos(0, 0)
            item._original_pos = None  # Clear to avoid affecting next move calculation
            item.setRect(cx - rx, cy - ry, rx * 2, ry * 2)

    def _scale_number_annotation(self, item, annotation, scale_factor: float):
        """Scale number annotation.

        Args:
            item: MovableEllipseItem.
            annotation: NumberAnnotation.
            scale_factor: Scale multiplier.
        """
        # Scale radius
        annotation.radius *= scale_factor

        # Update visual item
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()

        cx = annotation.x * width
        cy = annotation.y * scene_rect.height()
        r = annotation.radius * width

        if isinstance(item, MovableEllipseItem):
            # Reset item position to use absolute coordinates
            item.setPos(0, 0)
            item._original_pos = None  # Clear to avoid affecting next move calculation
            item.setRect(cx - r, cy - r, r * 2, r * 2)

            # Update text size
            for child in item.childItems():
                if isinstance(child, QGraphicsTextItem):
                    font = child.font()
                    font.setPixelSize(max(10, int(r * 1.2)))
                    child.setFont(font)
                    # Re-center text in circle (position relative to parent's local coords)
                    text_rect = child.boundingRect()
                    child.setPos(cx - text_rect.width() / 2, cy - text_rect.height() / 2)

    def _scale_freehand_annotation(self, item, annotation, scale_factor: float):
        """Scale freehand annotation from centroid.

        Args:
            item: MovablePathItem.
            annotation: FreehandAnnotation.
            scale_factor: Scale multiplier.
        """
        points = annotation.points
        if not points:
            return

        # Calculate centroid
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)

        # Scale points from centroid
        annotation.points = [(cx + (x - cx) * scale_factor, cy + (y - cy) * scale_factor) for x, y in points]

        # Rebuild path
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        pixel_points = [(x * width, y * height) for x, y in annotation.points]

        path = QPainterPath()
        if pixel_points:
            path.moveTo(pixel_points[0][0], pixel_points[0][1])
            for px, py in pixel_points[1:]:
                path.lineTo(px, py)

        if isinstance(item, MovablePathItem):
            # Reset item position to use absolute coordinates
            item.setPos(0, 0)
            item._original_pos = None  # Clear to avoid affecting next move calculation
            item.setPath(path)

    def _scale_text_annotation(self, item, annotation, scale_factor: float):
        """Scale text annotation by changing font size.

        Args:
            item: MovableTextItem.
            annotation: TextAnnotation.
            scale_factor: Scale multiplier.
        """
        # Scale font size with limits
        new_size = int(annotation.font_size * scale_factor)
        annotation.font_size = max(8, min(72, new_size))

        # Update visual item
        if isinstance(item, MovableTextItem):
            text_item = item.text_item
            font = text_item.font()
            font.setPixelSize(annotation.font_size)
            text_item.setFont(font)

            # Reset item position to annotation coordinates
            scene_rect = self.scene().sceneRect()
            x = annotation.x * scene_rect.width()
            y = annotation.y * scene_rect.height()
            item.setPos(x, y)
            item._original_pos = None  # Clear to avoid affecting next move calculation

            # Update container rect
            text_rect = text_item.boundingRect()
            item.setRect(0, 0, text_rect.width(), text_rect.height())

    def _refresh_item_from_annotation(self, item, annotation):
        """Refresh visual item from annotation data (for undo).

        Args:
            item: QGraphicsItem to update.
            annotation: Annotation object with current data.
        """
        scene_rect = self.scene().sceneRect()
        width = scene_rect.width()
        height = scene_rect.height()

        ann_type = annotation.annotation_type

        if ann_type in ("line", "arrow"):
            x1 = annotation.start_x * width
            y1 = annotation.start_y * height
            x2 = annotation.end_x * width
            y2 = annotation.end_y * height

            if isinstance(item, MovableLineItem):
                if ann_type == "arrow":
                    arrow_length = annotation.line_width * 4
                    angle = math.atan2(y2 - y1, x2 - x1)
                    line_end_x = x2 - arrow_length * math.cos(angle)
                    line_end_y = y2 - arrow_length * math.sin(angle)
                    item.setLine(x1, y1, line_end_x, line_end_y)
                    if hasattr(item, "_arrowhead") and item._arrowhead:
                        self._update_arrowhead(item, x1, y1, x2, y2)
                else:
                    item.setLine(x1, y1, x2, y2)

        elif ann_type == "rectangle":
            left_px = annotation.x * width
            top_px = annotation.y * height
            w_px = annotation.width * width
            h_px = annotation.height * height
            if isinstance(item, MovableRectItem):
                item.setRect(left_px, top_px, w_px, h_px)

        elif ann_type == "ellipse":
            cx = annotation.center_x * width
            cy = annotation.center_y * height
            rx = annotation.radius_x * width
            ry = annotation.radius_y * height
            if isinstance(item, MovableEllipseItem):
                item.setRect(cx - rx, cy - ry, rx * 2, ry * 2)

        elif ann_type == "number":
            cx = annotation.x * width
            cy = annotation.y * height
            r = annotation.radius * width
            if isinstance(item, MovableEllipseItem):
                item.setRect(cx - r, cy - r, r * 2, r * 2)
                for child in item.childItems():
                    if isinstance(child, QGraphicsTextItem):
                        font = child.font()
                        font.setPixelSize(max(10, int(r * 1.2)))
                        child.setFont(font)
                        text_rect = child.boundingRect()
                        child.setPos(-text_rect.width() / 2, -text_rect.height() / 2)

        elif ann_type == "freehand":
            pixel_points = [(x * width, y * height) for x, y in annotation.points]
            path = QPainterPath()
            if pixel_points:
                path.moveTo(pixel_points[0][0], pixel_points[0][1])
                for px, py in pixel_points[1:]:
                    path.lineTo(px, py)
            if isinstance(item, MovablePathItem):
                item.setPath(path)

        elif ann_type == "text":
            if isinstance(item, MovableTextItem):
                text_item = item.text_item
                font = text_item.font()
                font.setPixelSize(annotation.font_size)
                font.setBold(getattr(annotation, "bold", False))
                text_item.setFont(font)
                text_rect = text_item.boundingRect()
                item.setRect(0, 0, text_rect.width(), text_rect.height())


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
