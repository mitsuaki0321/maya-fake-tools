"""Skin weights copy and paste tool."""

from logging import getLogger
from pathlib import Path

from maya.api.OpenMaya import MGlobal
import maya.cmds as cmds

from ....lib_ui import BaseFramelessWindow, icons, maya_decorator
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QCursor, QEvent, QIcon, QPushButton, QSizePolicy, QSlider, Qt, Signal
from ....lib_ui.widgets import IconButton, IconToggleButton, extra_widgets
from .command import SkinWeightsCopyPaste

_IMAGES_DIR = Path(__file__).parent / "images"

logger = getLogger(__name__)
_instance = None


class MainWindow(BaseFramelessWindow):
    """Main Window for Skin Weights Copy Paste Tool."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(
            parent=parent,
            object_name="SkinWeightsCopyPasteMainWindow",
            window_title="Skin Weights Copy/Paste",
            central_layout="horizontal",
        )

        # Enable window resizing for frameless window
        self._enable_window_resize()

        self.skinWeights_copy_paste = SkinWeightsCopyPaste()
        self.is_value_changed = False
        self.is_use_select_pref = False  # Save the preference by user for trackSelectionOrder

        # Method button
        self.method_toggle_button = MethodButton(self.skinWeights_copy_paste)
        self.central_layout.addWidget(self.method_toggle_button)

        separator = extra_widgets.VerticalSeparator()
        self.central_layout.addWidget(separator)

        # Clipboard buttons
        self.src_clipboard_button = SourceClipboardButton(self.skinWeights_copy_paste)
        self.central_layout.addWidget(self.src_clipboard_button)

        self.dst_clipboard_button = DestinationClipboardButton(self.skinWeights_copy_paste)
        self.central_layout.addWidget(self.dst_clipboard_button)

        separator = extra_widgets.VerticalSeparator()
        self.central_layout.addWidget(separator)

        # Paste button
        self.paste_button = IconButton(icon_name="paste", icon_dir=_IMAGES_DIR)
        self.paste_button.setEnabled(False)
        self.central_layout.addWidget(self.paste_button)

        # Blend field, slider
        self.blend_spin_box = extra_widgets.ModifierSpinBox()
        self.blend_spin_box.setRange(0.0, 1.0)
        self.blend_spin_box.setSingleStep(0.01)
        self.blend_spin_box.setFixedWidth(self.blend_spin_box.sizeHint().width() * 1.2)
        self.blend_spin_box.setEnabled(False)
        blend_line_edit = self.blend_spin_box.lineEdit()
        blend_line_edit.setReadOnly(True)
        self.central_layout.addWidget(self.blend_spin_box)

        self.blend_slider = QSlider(Qt.Horizontal)
        self.blend_slider.setRange(0, 100)
        self.blend_slider.setEnabled(False)
        self.central_layout.addWidget(self.blend_slider, stretch=1)

        # Only unlock influences button
        self.only_unlock_infs_button = OnlyUnlockInfluencesButton(self.skinWeights_copy_paste)
        self.central_layout.addWidget(self.only_unlock_infs_button)

        # Rearrange the method button
        self.method_toggle_button.setMinimumHeight(self.blend_spin_box.sizeHint().height())

        # Signal & Slot
        self.src_clipboard_button.clear_clipboard_signal.connect(self.dst_clipboard_button.clear_clipboard)
        self.dst_clipboard_button.stock_clipboard_signal.connect(self._set_destination_clipboard)
        self.dst_clipboard_button.clear_clipboard_signal.connect(self._clear_destination_clipboard)

        self.blend_spin_box.valueChanged.connect(self._update_field_slider)
        self.blend_slider.valueChanged.connect(self._update_field_slider)

        self.blend_spin_box.valueChanged.connect(self._change_spin_box_value)

        self.blend_slider.valueChanged.connect(self._on_slider_value_changed)
        self.blend_slider.sliderReleased.connect(self._on_slider_released)

        self.paste_button.clicked.connect(self._paste_skinWeights)

        # Initialize the UI - use minimum height
        self.adjustSize()
        width = self.sizeHint().width()
        height = self.minimumSizeHint().height()
        self.resize(width, height)

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

    def _on_slider_value_changed(self):
        """Slot for the slider value changed."""
        if not self.is_value_changed:
            cmds.undoInfo(openChunk=True)
            self.is_value_changed = True

        try:
            self.__paste_skinWeights_blend()
        except Exception as e:
            MGlobal.displayError(str(e))

            self.is_value_changed = False

    def _on_slider_released(self):
        """Slot for the slider released."""
        if self.is_value_changed:
            cmds.undoInfo(closeChunk=True)
            self.is_value_changed = False

    @maya_decorator.undo_chunk("Skin Weights Copy Paste")
    @maya_decorator.error_handler
    def _change_spin_box_value(self, value):
        """Change the spin box value.

        Args:
            value (float): The new spin box value (not used, provided by valueChanged signal).
        """
        self.__paste_skinWeights_blend()

    def __paste_skinWeights_blend(self):
        """paste the skin weights."""
        self.skinWeights_copy_paste.set_blend_weights(self.blend_slider.value() / 100.0)
        self.skinWeights_copy_paste.paste_skinWeights()

    @maya_decorator.undo_chunk("Skin Weights Copy Paste")
    @maya_decorator.error_handler
    def _paste_skinWeights(self):
        """Paste the skin weights."""
        self.blend_spin_box.setValue(1.0)
        self.blend_slider.setValue(100)

    def _update_field_slider(self, value):
        """Update the field and slider.

        Args:
            value: The new value from the sender (0.0-1.0 from spin box, 0-100 from slider).
        """
        sender = self.sender()
        if sender == self.blend_spin_box:
            # Spin box sends 0.0-1.0, convert to 0-100 for slider
            self.blend_slider.blockSignals(True)
            self.blend_slider.setValue(int(value * 100))
            self.blend_slider.blockSignals(False)
        else:
            # Slider sends 0-100, convert to 0.0-1.0 for spin box
            self.blend_spin_box.blockSignals(True)
            self.blend_spin_box.setValue(value / 100.0)
            self.blend_spin_box.blockSignals(False)

    def _clear_destination_clipboard(self):
        """Clear the destination clipboard."""
        self.blend_spin_box.setEnabled(False)
        self.blend_slider.setEnabled(False)
        self.paste_button.setEnabled(False)

        self.blend_spin_box.blockSignals(True)
        self.blend_slider.blockSignals(True)

        self.blend_spin_box.setValue(0.0)
        self.blend_slider.setValue(0)

        self.blend_spin_box.blockSignals(False)
        self.blend_slider.blockSignals(False)

    def _set_destination_clipboard(self):
        """Set the destination clipboard."""
        self.blend_spin_box.setEnabled(True)
        self.blend_slider.setEnabled(True)
        self.paste_button.setEnabled(True)

        self.blend_spin_box.blockSignals(True)
        self.blend_slider.blockSignals(True)

        self.blend_spin_box.setValue(0.0)
        self.blend_slider.setValue(0)

        self.blend_spin_box.blockSignals(False)
        self.blend_slider.blockSignals(False)

    def showEvent(self, event):
        """Show event."""
        # Settings for trackSelectionOrder
        self.is_use_select_pref = cmds.selectPref(q=True, trackSelectionOrder=True)
        if not self.is_use_select_pref:
            cmds.selectPref(trackSelectionOrder=True)

        super().showEvent(event)

    def closeEvent(self, event):
        """Close event."""
        # Restore the settings for trackSelectionOrder
        if not self.is_use_select_pref:
            cmds.selectPref(trackSelectionOrder=False)

        super().closeEvent(event)


class MethodButton(QPushButton):
    """This button is used to toggle the method for SkinWeightsCopyPaste."""

    def __init__(self, skinWeights_copy_paste: SkinWeightsCopyPaste, parent=None):
        """Initializer.

        Args:
            skinWeights_copy_paste (SkinWeightsCopyPaste): SkinWeightsCopyPaste instance.
        """
        super().__init__(parent=parent)

        if not isinstance(skinWeights_copy_paste, SkinWeightsCopyPaste):
            raise ValueError("Invalid skinWeights_copy_paste.")
        self._skinWeights_copy_paste = skinWeights_copy_paste

        self.method_label_map = {"oneToAll": "1:N", "oneToOne": "1:1"}

        self.setText(self.method_label_map[self._skinWeights_copy_paste.method])

        minimum_size_hint = self.minimumSizeHint()
        self.setMinimumWidth(minimum_size_hint.width() * 1.2)

        self.clicked.connect(self.toggle_method)

    @maya_decorator.error_handler
    def toggle_method(self):
        """Toggle the method."""
        if self._skinWeights_copy_paste.method == "oneToAll":
            self._skinWeights_copy_paste.set_method("oneToOne")
        elif self._skinWeights_copy_paste.method == "oneToOne":
            self._skinWeights_copy_paste.set_method("oneToAll")

        self.setText(self.method_label_map[self._skinWeights_copy_paste.method])


class SourceClipboardButton(IconButton):
    """This button is used to stock the source components for SkinWeightsCopyPaste."""

    clear_clipboard_signal = Signal()

    def __init__(self, skinWeights_copy_paste: SkinWeightsCopyPaste, parent=None):
        """Initializer.

        Args:
            skinWeights_copy_paste (SkinWeightsCopyPaste): SkinWeightsCopyPaste instance.
        """
        super().__init__(icon_name="source", icon_dir=_IMAGES_DIR, parent=parent)

        if not isinstance(skinWeights_copy_paste, SkinWeightsCopyPaste):
            raise ValueError("Invalid skinWeights_copy_paste.")

        self._skinWeights_copy_paste = skinWeights_copy_paste
        self._select_icon = QIcon(icons.get_path("source", base_dir=_IMAGES_DIR))
        self._selected_icon = QIcon(icons.get_path("source-checked", base_dir=_IMAGES_DIR))

        self.setText("0")
        self.setIcon(self._select_icon)

        minimum_size_hint = self.minimumSizeHint()
        self.setMinimumWidth(minimum_size_hint.width() * 1.2)

        self.clicked.connect(self.stock_clipborad)

    @maya_decorator.error_handler
    def stock_clipborad(self):
        """Stock the clipboard."""
        sel_objs = cmds.ls(sl=True)
        if not sel_objs:
            self.setText("0")
            self.setIcon(self._select_icon)

            self._skinWeights_copy_paste.clear_src_components()
            self.clear_clipboard_signal.emit()

            cmds.warning("Clear the source components.")
            return

        sel_components = cmds.ls(orderedSelection=True, flatten=True)
        filter_components = cmds.filterExpand(sel_components, ex=True, sm=[28, 31, 46])
        if len(sel_components) != len(filter_components):
            cmds.error("Invalid components or objects selected.")

        try:
            self._skinWeights_copy_paste.set_src_components(sel_components)
            self.setText(str(len(sel_components)))
            self.setIcon(self._selected_icon)

            self.clear_clipboard_signal.emit()
        except Exception as e:
            cmds.error(str(e))


class DestinationClipboardButton(IconButton):
    """This button is used to stock the destination components for SkinWeightsCopyPaste."""

    stock_clipboard_signal = Signal()
    clear_clipboard_signal = Signal()

    def __init__(self, skinWeights_copy_paste: SkinWeightsCopyPaste, parent=None):
        """Initializer.

        Args:
            skinWeights_copy_paste (SkinWeightsCopyPaste): SkinWeightsCopyPaste instance.
        """
        super().__init__(icon_name="destination", icon_dir=_IMAGES_DIR, parent=parent)

        if not isinstance(skinWeights_copy_paste, SkinWeightsCopyPaste):
            raise ValueError("Invalid skinWeights_copy_paste.")

        self._skinWeights_copy_paste = skinWeights_copy_paste
        self._select_icon = QIcon(icons.get_path("destination", base_dir=_IMAGES_DIR))
        self._selected_icon = QIcon(icons.get_path("destination-checked", base_dir=_IMAGES_DIR))

        self.setText("0")
        self.setIcon(self._select_icon)

        minimum_size_hint = self.minimumSizeHint()
        self.setMinimumWidth(minimum_size_hint.width() * 1.2)

        self.clicked.connect(self.stock_clipborad)

    @maya_decorator.error_handler
    def stock_clipborad(self):
        """Stock the clipboard."""
        sel_objs = cmds.ls(sl=True)
        if not sel_objs:
            self.setText("0")
            self.setIcon(self._select_icon)

            self._skinWeights_copy_paste.clear_dst_components()
            self.clear_clipboard_signal.emit()

            cmds.warning("Clear the destination components.")
            return

        sel_components = cmds.ls(orderedSelection=True, flatten=True)
        filter_components = cmds.filterExpand(sel_components, ex=True, sm=[28, 31, 46])
        if len(sel_components) != len(filter_components):
            cmds.error("Invalid components or objects selected.")

        try:
            self._skinWeights_copy_paste.set_dst_components(sel_components)
            self.setText(str(len(sel_components)))
            self.setIcon(self._selected_icon)
        except Exception as e:
            cmds.error(str(e))

        self.stock_clipboard_signal.emit()

    def clear_clipboard(self):
        """Clear the clipboard."""
        self.setText("0")
        self.setIcon(self._select_icon)

        self.clear_clipboard_signal.emit()

        logger.debug("Clear the destination components.")


class OnlyUnlockInfluencesButton(IconToggleButton):
    """This button is used to toggle only_unlock_influences mode for SkinWeightsCopyPaste."""

    def __init__(self, skinWeights_copy_paste: SkinWeightsCopyPaste, parent=None):
        """Initializer.

        Args:
            skinWeights_copy_paste (SkinWeightsCopyPaste): SkinWeightsCopyPaste instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(icon_on="lock", icon_off="lock-open", icon_dir=_IMAGES_DIR, parent=parent)

        if not isinstance(skinWeights_copy_paste, SkinWeightsCopyPaste):
            raise ValueError("Invalid skinWeights_copy_paste.")

        self._skinWeights_copy_paste = skinWeights_copy_paste

        self.clicked.connect(self._toggle_mode)

    @maya_decorator.error_handler
    def _toggle_mode(self):
        """Toggle the only_unlock_influences mode."""
        is_only_unlock = self.isChecked()
        self._skinWeights_copy_paste.set_only_unlock_influences(is_only_unlock)
        logger.debug("Only unlock influences mode: %s", "ON" if is_only_unlock else "OFF")


def show_ui():
    """
    Show the skin weights copy and paste tool UI.

    Creates or raises the main window.

    Returns:
        MainWindow: The main window instance.
    """
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent=parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
