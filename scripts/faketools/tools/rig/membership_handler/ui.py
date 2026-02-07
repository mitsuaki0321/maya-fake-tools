"""
Membership Handler for deformer tags tool.
"""

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds

from ....lib import lib_memberShip, lib_selection
from ....lib_ui import BaseFramelessWindow, get_maya_main_window, maya_decorator
from ....lib_ui.qt_compat import QCursor, QEvent, QLineEdit, QSizePolicy, Qt
from ....lib_ui.widgets import IconButton

_IMAGES_DIR = Path(__file__).parent / "images"

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseFramelessWindow):
    """
    Membership Handler Main Window.

    Provides UI for managing deformer membership using component tags.
    """

    def __init__(self, parent=None):
        """
        Initialize the Membership Handler window.

        Args:
            parent (QWidget | None): Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="MembershipHandlerMainWindow",
            window_title="Membership Handler",
            central_layout="horizontal",
        )

        self.deformer = None

        # Enable window resizing for frameless window
        self._enable_window_resize()

        set_deformer_button = IconButton(icon_name="pin", icon_dir=_IMAGES_DIR)
        self.central_layout.addWidget(set_deformer_button)

        self.deformer_field = QLineEdit()
        self.deformer_field.setReadOnly(True)
        self.deformer_field.setPlaceholderText("Deformer")
        self.central_layout.addWidget(self.deformer_field, stretch=1)

        update_button = IconButton(icon_name="refresh", icon_dir=_IMAGES_DIR)
        self.central_layout.addWidget(update_button)

        select_button = IconButton(icon_name="select", icon_dir=_IMAGES_DIR)
        self.central_layout.addWidget(select_button)

        # Signal & Slot
        set_deformer_button.clicked.connect(self.set_deformer)
        update_button.clicked.connect(self.update_memberships)
        select_button.clicked.connect(self.select_memberships)

        # Adjust size to content
        self.adjustSize()

        # Variables for resize handling
        self._resize_margin = 6  # Pixels from edge to trigger resize
        self._resize_direction = None
        self._resize_start_pos = None
        self._resize_start_geometry = None

        # Enable mouse tracking for all widgets to detect cursor position
        self._enable_mouse_tracking_for_children()

    def _enable_window_resize(self):
        """Enable window resizing for frameless window."""
        # Set size policy to allow resizing
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMouseTracking(True)

    def _enable_mouse_tracking_for_children(self):
        """Enable mouse tracking for all child widgets."""
        # Enable for main window
        self.setMouseTracking(True)

        # Enable for all child widgets recursively and install event filter
        for widget in self.findChildren(object):
            if hasattr(widget, "setMouseTracking"):
                widget.setMouseTracking(True)
                widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events from child widgets to update cursor on window edges.

        Args:
            obj: The object that generated the event
            event: The event

        Returns:
            bool: True if event was handled, False otherwise
        """
        # Get move event type constant (compatible with PySide2/6)
        try:
            # PySide6
            mouse_move = QEvent.Type.MouseMove
        except AttributeError:
            # PySide2
            mouse_move = QEvent.MouseMove

        if event.type() == mouse_move:
            # Convert child widget position to window coordinates
            window_pos = self.mapFromGlobal(obj.mapToGlobal(event.pos()))

            # Check if near window edge
            resize_dir = self._get_resize_direction(window_pos)
            if resize_dir:
                cursor_shape = self._get_cursor_shape(resize_dir)
                self.setCursor(QCursor(cursor_shape))
            else:
                self.unsetCursor()

        return super().eventFilter(obj, event)

    def _get_resize_direction(self, pos):
        """Get resize direction based on mouse position.

        Args:
            pos: Mouse position

        Returns:
            str or None: Resize direction ('left', 'right', 'top', 'bottom', 'topleft', 'topright', 'bottomleft', 'bottomright')
        """
        rect = self.rect()
        margin = self._resize_margin

        on_left = pos.x() <= margin
        on_right = pos.x() >= rect.width() - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= rect.height() - margin

        # Corners have priority
        if on_top and on_left:
            return "topleft"
        if on_top and on_right:
            return "topright"
        if on_bottom and on_left:
            return "bottomleft"
        if on_bottom and on_right:
            return "bottomright"

        # Edges
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"

        return None

    def mousePressEvent(self, event):
        """Handle mouse press for dragging and resizing."""
        # Get global position (compatible with PySide2/6)
        try:
            # PySide6
            global_pos = event.globalPosition().toPoint()
        except AttributeError:
            # PySide2
            global_pos = event.globalPos()

        # Get left button constant (compatible with PySide2/6)
        left_button = getattr(Qt, "LeftButton", None) or Qt.MouseButton.LeftButton

        if event.button() == left_button:
            # Check for resize
            resize_dir = self._get_resize_direction(event.pos())
            if resize_dir:
                self._resize_direction = resize_dir
                self._resize_start_pos = global_pos
                self._resize_start_geometry = self.geometry()
                event.accept()
                return

        # Call parent implementation for window dragging
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging, resizing, and cursor changes."""
        # Get global position (compatible with PySide2/6)
        try:
            # PySide6
            global_pos = event.globalPosition().toPoint()
        except AttributeError:
            # PySide2
            global_pos = event.globalPos()

        # Get left button constant (compatible with PySide2/6)
        left_button = getattr(Qt, "LeftButton", None) or Qt.MouseButton.LeftButton

        # Handle active resize
        if event.buttons() == left_button and self._resize_direction and self._resize_start_pos:
            delta = global_pos - self._resize_start_pos
            new_geometry = self._resize_start_geometry

            # Calculate new geometry based on resize direction
            if "left" in self._resize_direction:
                new_x = new_geometry.x() + delta.x()
                new_width = new_geometry.width() - delta.x()
                if new_width >= self.minimumWidth():
                    self.setGeometry(new_x, new_geometry.y(), new_width, new_geometry.height())
                    if "top" not in self._resize_direction and "bottom" not in self._resize_direction:
                        return

            if "right" in self._resize_direction:
                new_width = new_geometry.width() + delta.x()
                self.resize(new_width, self.height())
                if "top" not in self._resize_direction and "bottom" not in self._resize_direction:
                    return

            if "top" in self._resize_direction:
                new_y = new_geometry.y() + delta.y()
                new_height = new_geometry.height() - delta.y()
                if new_height >= self.minimumHeight():
                    self.setGeometry(self.x(), new_y, self.width(), new_height)
                    return

            if "bottom" in self._resize_direction:
                new_height = new_geometry.height() + delta.y()
                self.resize(self.width(), new_height)
                return

            event.accept()
            return

        # Update cursor based on position (when not dragging)
        if not event.buttons():
            resize_dir = self._get_resize_direction(event.pos())
            if resize_dir:
                # Set appropriate cursor
                cursor_shape = self._get_cursor_shape(resize_dir)
                self.setCursor(QCursor(cursor_shape))
                event.accept()
                return
            else:
                self.unsetCursor()

        # Call parent implementation for window dragging
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging or resizing."""
        self._resize_direction = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        super().mouseReleaseEvent(event)

    def _get_cursor_shape(self, direction):
        """Get cursor shape for resize direction.

        Args:
            direction (str): Resize direction

        Returns:
            Qt.CursorShape: Cursor shape
        """
        # Handle both PySide2 and PySide6 cursor constants
        if direction == "left" or direction == "right":
            return getattr(Qt, "SizeHorCursor", None) or Qt.CursorShape.SizeHorCursor
        elif direction == "top" or direction == "bottom":
            return getattr(Qt, "SizeVerCursor", None) or Qt.CursorShape.SizeVerCursor
        elif direction == "topleft" or direction == "bottomright":
            return getattr(Qt, "SizeFDiagCursor", None) or Qt.CursorShape.SizeFDiagCursor
        elif direction == "topright" or direction == "bottomleft":
            return getattr(Qt, "SizeBDiagCursor", None) or Qt.CursorShape.SizeBDiagCursor
        else:
            return getattr(Qt, "ArrowCursor", None) or Qt.CursorShape.ArrowCursor

    @maya_decorator.error_handler
    def set_deformer(self):
        """Set the deformer to the selected deformer."""
        # Get the selected deformer.
        sel_deformers = cmds.ls(sl=True, type="weightGeometryFilter")
        if not sel_deformers:
            cmds.error("Select any weightGeometryFilter.")

        self.deformer_field.setText(sel_deformers[0])
        self.deformer = lib_memberShip.DeformerMembership(sel_deformers[0])

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Update Memberships")
    def update_memberships(self):
        """Update the memberships."""
        if not self.deformer:
            cmds.error("Set any deformer to field.")

        components = cmds.filterExpand(expand=True, sm=(28, 31, 46))
        if not components:
            cmds.error("Select any components (vertex, cv, latticePoint).")

        lib_memberShip.remove_deformer_blank_indices(self.deformer.deformer_name)
        self.deformer.update_components(components)

    @maya_decorator.error_handler
    def select_memberships(self):
        """Select the memberships."""
        if not self.deformer:
            cmds.error("Set any deformer to field.")

        components = self.deformer.get_components()
        cmds.select(components, r=True)

        # Change the component mode.
        selection_mode = lib_selection.SelectionMode()
        selection_mode.to_component()

        for component_type in ["vertex", "controlVertex", "latticePoint"]:
            selection_mode.set_component_mode(component_type, True)

        objs = cmds.ls(sl=True, objectsOnly=True)
        hilite_selection = lib_selection.HiliteSelection()
        hilite_selection.hilite(objs, replace=True)


def show_ui():
    """
    Show the Membership Handler UI.

    Creates or raises the main window.

    Returns:
        MainWindow | None: The main window instance, or None if component tags are disabled
    """
    # Check if component tags are enabled
    if not lib_memberShip.is_use_component_tag():
        cmds.warning("Please enable component tags from preferences of rigging before launching the tool.")
        return None

    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
