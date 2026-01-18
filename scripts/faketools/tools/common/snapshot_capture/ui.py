"""Snapshot Capture UI - PySide-based window implementation."""

from __future__ import annotations

from io import BytesIO
import logging
import os

import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from ....lib_ui import ToolSettingsManager, get_maya_main_window
from ....lib_ui.maya_qt import qt_widget_from_maya_control
from ....lib_ui.qt_compat import (
    QApplication,
    QColor,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QIcon,
    QImage,
    QLabel,
    QMainWindow,
    QMenu,
    QPixmap,
    QPushButton,
    QSpinBox,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    shiboken,
)
from . import command
from .input_monitor import InputMonitor
from .input_overlay import draw_click_indicators, draw_cursor, draw_key_overlay
from .screen_capture import capture_screen_region, get_cursor_screen_position, get_widget_screen_bbox

logger = logging.getLogger(__name__)

_instance = None


class SnapshotCaptureWindow(QMainWindow):
    """Snapshot Capture window with embedded modelPanel."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Settings
        self.settings = ToolSettingsManager(tool_name="snapshot_capture", category="common")

        # Window configuration
        self.setObjectName(self._ui_name("MainWindow"))
        self.setWindowTitle("Snapshot Capture")

        # State variables
        self._current_mode: str = "png"
        self._bg_color: tuple[int, int, int] = (128, 128, 128)
        self._bg_transparent: bool = False
        self._is_recording: bool = False
        self._recorded_frames: list = []
        self._record_timer: QTimer | None = None
        self._countdown_timer: QTimer | None = None
        self._countdown_value: int = 0
        self._input_monitor: InputMonitor | None = None
        self._capture_bbox: tuple[int, int, int, int] | None = None
        self._show_cursor: bool = True
        self._show_clicks: bool = True
        self._show_keys: bool = False

        # Maya UI elements (will be created in _create_viewport)
        self.pane_layout_name: str | None = None
        self.panel_name: str | None = None

        # UI widgets (will be created in _setup_ui)
        self.mode_combo: QComboBox | None = None
        self.bg_button: QPushButton | None = None
        self.option_button: QToolButton | None = None
        self.option_menu: QMenu | None = None
        self.save_button: QPushButton | None = None
        self.copy_button: QPushButton | None = None
        self.record_button: QPushButton | None = None
        self.width_spinbox: QSpinBox | None = None
        self.height_spinbox: QSpinBox | None = None
        self.preset_button: QToolButton | None = None
        self.set_button: QPushButton | None = None

        # Load settings and setup UI
        self._load_settings()
        self._setup_ui()

    def _ui_name(self, name: str) -> str:
        """Generate unique name for Maya/Qt UI elements.

        Args:
            name: Base name.

        Returns:
            Unique name with prefix.
        """
        return f"snapshotCapture{name}"

    def _get_icon_path(self, icon_name: str) -> str | None:
        """Get icon path from module's icons folder.

        Args:
            icon_name: Icon filename.

        Returns:
            Full path to icon if exists, None otherwise.
        """
        module_dir = os.path.dirname(__file__)
        icon_path = os.path.join(module_dir, "icons", icon_name)
        return icon_path if os.path.exists(icon_path) else None

    def _load_settings(self):
        """Load saved settings from JSON."""
        data = self.settings.load_settings("default")

        self._current_mode = data.get("mode", "png")
        bg_color = data.get("bg_color")
        if bg_color and isinstance(bg_color, list) and len(bg_color) == 3:
            self._bg_color = tuple(bg_color)
        self._bg_transparent = data.get("bg_transparent", False)

    def _save_settings(self):
        """Save current settings to JSON."""
        # Get viewport size
        width = 640
        height = 360
        if self.width_spinbox:
            width = self.width_spinbox.value()
        if self.height_spinbox:
            height = self.height_spinbox.value()

        data = {
            "mode": self._current_mode,
            "width": width,
            "height": height,
            "bg_color": list(self._bg_color),
            "bg_transparent": self._bg_transparent,
            "fps": self._get_setting("fps", 24),
            "loop": self._get_setting("loop", True),
            "delay": self._get_setting("delay", 3),
            "trim": self._get_setting("trim", 0),
            "show_cursor": self._get_setting("show_cursor", True),
            "show_clicks": self._get_setting("show_clicks", True),
            "show_keys": self._get_setting("show_keys", False),
        }
        self.settings.save_settings(data, "default")

    def _get_setting(self, key: str, default):
        """Get a setting value.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            Setting value or default.
        """
        data = self.settings.load_settings("default")
        return data.get(key, default)

    def _set_setting(self, key: str, value):
        """Set a setting value.

        Args:
            key: Setting key.
            value: Value to set.
        """
        data = self.settings.load_settings("default")
        data[key] = value
        self.settings.save_settings(data, "default")

    def _setup_ui(self):
        """Setup the complete UI."""
        # Central widget and layout
        central_widget = QWidget()
        central_widget.setObjectName(self._ui_name("CentralWidget"))
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setObjectName(self._ui_name("MainLayout"))
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create viewport
        viewport_widget = self._create_viewport()
        main_layout.addWidget(viewport_widget)

        # Create toolbar
        toolbar_widget = self._create_toolbar()
        main_layout.addWidget(toolbar_widget)

        # Apply initial mode visibility
        self._update_toolbar_for_mode()

    def _create_viewport(self) -> QWidget:
        """Create the embedded viewport.

        Returns:
            Qt widget containing the Maya paneLayout.
        """
        # Create Maya native elements
        self.pane_layout_name = cmds.paneLayout(
            self._ui_name("PaneLayout#"),
            configuration="single",
        )
        self.panel_name = cmds.modelPanel(
            self._ui_name("ModelPanel#"),
            menuBarVisible=True,
            parent=self.pane_layout_name,
        )

        # Add Camera menu to panel's menu bar
        self._create_camera_menu()

        # Configure editor
        cmds.modelEditor(
            self.panel_name,
            edit=True,
            displayAppearance="smoothShaded",
            headsUpDisplay=False,
            grid=True,
        )

        # Convert to Qt widget
        pane_widget = qt_widget_from_maya_control(self.pane_layout_name)
        return pane_widget

    def _create_camera_menu(self):
        """Create Camera menu in panel's menu bar."""
        if not self.panel_name:
            return

        menu_name = self.panel_name + "CameraMenu"

        # Delete existing menu if present
        if cmds.menu(menu_name, exists=True):
            cmds.deleteUI(menu_name)

        # Create Camera menu in panel's menu bar
        cmds.menu(menu_name, label="Camera", parent=self.panel_name)

        # Add camera items
        cameras = cmds.ls(type="camera")
        for cam in cameras:
            parent = cmds.listRelatives(cam, parent=True)
            if parent:
                cam_name = parent[0]
                cmds.menuItem(
                    label=cam_name,
                    command=lambda x, c=cam_name: self._on_camera_changed(c),
                    parent=menu_name,
                )

    def _on_camera_changed(self, camera: str):
        """Handle camera selection change.

        Args:
            camera: Camera name.
        """
        if self.panel_name and cmds.modelPanel(self.panel_name, exists=True):
            cmds.modelPanel(self.panel_name, edit=True, camera=camera)
            logger.info(f"Changed camera to: {camera}")

    def _create_toolbar(self) -> QWidget:
        """Create the 2-row toolbar.

        Returns:
            Toolbar widget.
        """
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName(self._ui_name("ToolbarWidget"))

        toolbar_layout = QVBoxLayout(toolbar_widget)
        toolbar_layout.setObjectName(self._ui_name("ToolbarLayout"))
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(4)

        # Row 1: Mode + BG + Option + action buttons
        row1_layout = self._create_toolbar_row1()
        toolbar_layout.addLayout(row1_layout)

        # Row 2: Resolution fields
        row2_layout = self._create_toolbar_row2()
        toolbar_layout.addLayout(row2_layout)

        return toolbar_widget

    def _create_toolbar_row1(self) -> QHBoxLayout:
        """Create toolbar row 1 with mode selector and action buttons.

        Returns:
            Row 1 layout.
        """
        row1_layout = QHBoxLayout()
        row1_layout.setObjectName(self._ui_name("Row1Layout"))
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(4)

        # Mode selector
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName(self._ui_name("ModeCombo"))
        self.mode_combo.addItems(["PNG", "GIF", "Rec"])
        mode_label_map = {"png": "PNG", "gif": "GIF", "rec": "Rec"}
        self.mode_combo.setCurrentText(mode_label_map.get(self._current_mode, "PNG"))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.mode_combo.setFixedWidth(60)
        row1_layout.addWidget(self.mode_combo)

        # Stretch to push remaining items to right
        row1_layout.addStretch()

        # BG button (PNG/GIF only)
        self.bg_button = QPushButton()
        self.bg_button.setObjectName(self._ui_name("BGButton"))
        self.bg_button.setFixedSize(24, 24)
        self.bg_button.setToolTip("Background Color")
        self._update_bg_button_color()
        self.bg_button.clicked.connect(self._on_bg_color_button)
        row1_layout.addWidget(self.bg_button)

        # Option button
        self.option_button = QToolButton()
        self.option_button.setObjectName(self._ui_name("OptionButton"))
        self.option_button.setFixedSize(24, 24)
        self.option_button.setToolTip("Options")
        self.option_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        # Try to set icon
        option_icon_path = self._get_icon_path("advancedSettings.png")
        if option_icon_path:
            self.option_button.setIcon(QIcon(option_icon_path))
        else:
            # Use Maya's built-in icon
            self.option_button.setIcon(QIcon(":/advancedSettings.png"))

        # Create option menu
        self.option_menu = QMenu(self.option_button)
        self.option_menu.setObjectName(self._ui_name("OptionMenu"))
        self.option_menu.aboutToShow.connect(self._populate_option_menu)
        self.option_button.setMenu(self.option_menu)
        row1_layout.addWidget(self.option_button)

        # Save button (PNG/GIF only)
        self.save_button = QPushButton()
        self.save_button.setObjectName(self._ui_name("SaveButton"))
        self.save_button.setFixedSize(24, 24)
        self.save_button.setToolTip("Save")
        save_icon_path = self._get_icon_path("snapshot_save.png")
        if save_icon_path:
            self.save_button.setIcon(QIcon(save_icon_path))
        else:
            self.save_button.setText("S")
        self.save_button.clicked.connect(self._on_save_button)
        row1_layout.addWidget(self.save_button)

        # Copy button (PNG only)
        self.copy_button = QPushButton()
        self.copy_button.setObjectName(self._ui_name("CopyButton"))
        self.copy_button.setFixedSize(24, 24)
        self.copy_button.setToolTip("Copy to Clipboard")
        copy_icon_path = self._get_icon_path("snapshot_copy.png")
        if copy_icon_path:
            self.copy_button.setIcon(QIcon(copy_icon_path))
        else:
            self.copy_button.setText("C")
        self.copy_button.clicked.connect(self._on_copy_png_to_clipboard)
        row1_layout.addWidget(self.copy_button)

        # Record button (Rec only)
        self.record_button = QPushButton()
        self.record_button.setObjectName(self._ui_name("RecordButton"))
        self.record_button.setFixedSize(24, 24)
        self.record_button.setToolTip("Start Recording")
        self._update_record_button_icon("rec")
        self.record_button.clicked.connect(self._on_record_toggle)
        row1_layout.addWidget(self.record_button)

        return row1_layout

    def _create_toolbar_row2(self) -> QHBoxLayout:
        """Create toolbar row 2 with resolution controls.

        Returns:
            Row 2 layout.
        """
        row2_layout = QHBoxLayout()
        row2_layout.setObjectName(self._ui_name("Row2Layout"))
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(4)

        # Stretch to push items to right
        row2_layout.addStretch()

        # Width spinbox
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setObjectName(self._ui_name("WidthSpinBox"))
        self.width_spinbox.setRange(64, 4096)
        self.width_spinbox.setValue(self._get_setting("width", 640))
        self.width_spinbox.setFixedWidth(55)
        row2_layout.addWidget(self.width_spinbox)

        # "x" label
        x_label = QLabel("x")
        x_label.setObjectName(self._ui_name("XLabel"))
        row2_layout.addWidget(x_label)

        # Height spinbox
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setObjectName(self._ui_name("HeightSpinBox"))
        self.height_spinbox.setRange(64, 4096)
        self.height_spinbox.setValue(self._get_setting("height", 360))
        self.height_spinbox.setFixedWidth(55)
        row2_layout.addWidget(self.height_spinbox)

        # Preset button
        self.preset_button = QToolButton()
        self.preset_button.setObjectName(self._ui_name("PresetButton"))
        self.preset_button.setFixedSize(20, 20)
        self.preset_button.setToolTip("Resolution Presets")
        self.preset_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.preset_button.setIcon(QIcon(":/arrowDown.png"))

        # Create preset menu
        preset_menu = QMenu(self.preset_button)
        preset_menu.setObjectName(self._ui_name("PresetMenu"))
        for preset_label in command.RESOLUTION_PRESETS:
            preset_menu.addAction(preset_label, lambda checked=False, p=preset_label: self._on_preset_selected(p))
        self.preset_button.setMenu(preset_menu)
        row2_layout.addWidget(self.preset_button)

        # Set button
        self.set_button = QPushButton()
        self.set_button.setObjectName(self._ui_name("SetButton"))
        self.set_button.setFixedSize(24, 24)
        self.set_button.setToolTip("Apply Resolution")
        set_icon_path = self._get_icon_path("snapshot_set.png")
        if set_icon_path:
            self.set_button.setIcon(QIcon(set_icon_path))
        else:
            self.set_button.setText("Set")
        self.set_button.clicked.connect(self._on_set_custom_resolution)
        row2_layout.addWidget(self.set_button)

        return row2_layout

    def _update_bg_button_color(self):
        """Update BG button stylesheet to show current color."""
        if self.bg_button:
            r, g, b = self._bg_color
            self.bg_button.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")

    def _update_record_button_icon(self, state: str):
        """Update record button icon based on state.

        Args:
            state: "rec", "stop", or countdown number string.
        """
        if not self.record_button:
            return

        if state == "rec":
            icon_path = self._get_icon_path("snapshot_rec.png")
            self.record_button.setToolTip("Start Recording")
        elif state == "stop":
            icon_path = self._get_icon_path("snapshot_stop.png")
            self.record_button.setToolTip("Stop Recording")
        else:
            # Countdown state
            icon_path = self._get_icon_path(f"snapshot_countdown_{state}.png")
            self.record_button.setToolTip(f"Cancel ({state})")

        if icon_path:
            self.record_button.setIcon(QIcon(icon_path))
            self.record_button.setText("")
        else:
            self.record_button.setIcon(QIcon())
            self.record_button.setText(state.upper() if state in ["rec", "stop"] else state)

    def _update_toolbar_for_mode(self):
        """Update toolbar visibility based on current mode."""
        mode = self._current_mode

        # BG button: PNG/GIF only
        if self.bg_button:
            self.bg_button.setVisible(mode in ["png", "gif"])

        # Save button: PNG/GIF only
        if self.save_button:
            self.save_button.setVisible(mode in ["png", "gif"])

        # Copy button: PNG only
        if self.copy_button:
            self.copy_button.setVisible(mode == "png")

        # Record button: Rec only
        if self.record_button:
            self.record_button.setVisible(mode == "rec")

    def _populate_option_menu(self):
        """Populate option menu based on current mode."""
        if not self.option_menu:
            return

        self.option_menu.clear()

        # FPS options
        fps_options = [10, 12, 15, 24, 30, 50, 60]

        # PNG/GIF: Transparent option
        if self._current_mode in ["png", "gif"]:
            transparent_action = self.option_menu.addAction("Transparent")
            transparent_action.setCheckable(True)
            transparent_action.setChecked(self._bg_transparent)
            transparent_action.triggered.connect(self._on_transparent_changed)
            self.option_menu.addSeparator()

        # GIF: Loop, FPS submenu
        if self._current_mode == "gif":
            loop_action = self.option_menu.addAction("Loop")
            loop_action.setCheckable(True)
            loop_action.setChecked(self._get_setting("loop", True))
            loop_action.triggered.connect(lambda checked: self._set_setting("loop", checked))

            # FPS submenu
            current_fps = self._get_setting("fps", 24)
            fps_menu = self.option_menu.addMenu(f"FPS: {current_fps}")
            for fps in fps_options:
                fps_menu.addAction(str(fps), lambda checked=False, f=fps: self._on_fps_selected(f))

        # Rec: FPS, Delay, Trim, Show options
        elif self._current_mode == "rec":
            # FPS submenu
            current_fps = self._get_setting("fps", 24)
            fps_menu = self.option_menu.addMenu(f"FPS: {current_fps}")
            for fps in fps_options:
                fps_menu.addAction(str(fps), lambda checked=False, f=fps: self._on_fps_selected(f))

            # Delay submenu
            delay_val = self._get_setting("delay", 3)
            delay_menu = self.option_menu.addMenu(f"Delay: {delay_val}s")
            for d in [0, 1, 2, 3]:
                delay_menu.addAction(f"{d} sec", lambda checked=False, dv=d: self._set_setting("delay", dv))

            # Trim submenu
            trim_val = self._get_setting("trim", 0)
            trim_menu = self.option_menu.addMenu(f"Trim: {trim_val}s")
            for t in [0, 1, 2, 3]:
                trim_menu.addAction(f"{t} sec", lambda checked=False, tv=t: self._set_setting("trim", tv))

            self.option_menu.addSeparator()

            # Show options
            show_cursor_action = self.option_menu.addAction("Show Cursor")
            show_cursor_action.setCheckable(True)
            show_cursor_action.setChecked(self._get_setting("show_cursor", True))
            show_cursor_action.triggered.connect(lambda checked: self._set_setting("show_cursor", checked))

            show_clicks_action = self.option_menu.addAction("Show Clicks")
            show_clicks_action.setCheckable(True)
            show_clicks_action.setChecked(self._get_setting("show_clicks", True))
            show_clicks_action.triggered.connect(lambda checked: self._set_setting("show_clicks", checked))

            show_keys_action = self.option_menu.addAction("Show Keys")
            show_keys_action.setCheckable(True)
            show_keys_action.setChecked(self._get_setting("show_keys", False))
            show_keys_action.triggered.connect(lambda checked: self._set_setting("show_keys", checked))

    def _on_mode_changed(self, mode_label: str):
        """Handle mode selector change.

        Args:
            mode_label: Selected mode label ("PNG", "GIF", "Rec").
        """
        mode_map = {"PNG": "png", "GIF": "gif", "Rec": "rec"}
        self._current_mode = mode_map.get(mode_label, "png")
        self._set_setting("mode", self._current_mode)
        self._update_toolbar_for_mode()
        logger.debug(f"Mode changed to: {self._current_mode}")

    def _on_transparent_changed(self, checked: bool):
        """Handle transparent option change.

        Args:
            checked: Whether transparent is enabled.
        """
        self._bg_transparent = checked
        self._set_setting("bg_transparent", checked)
        logger.debug(f"Transparent set to: {checked}")

    def _on_fps_selected(self, fps: int):
        """Handle FPS selection.

        Args:
            fps: Selected FPS value.
        """
        self._set_setting("fps", fps)
        logger.debug(f"FPS set to: {fps}")

    def _on_bg_color_button(self):
        """Handle background color button click - open color picker."""
        initial_color = QColor(self._bg_color[0], self._bg_color[1], self._bg_color[2])
        color = QColorDialog.getColor(initial_color, self, "Select Background Color")

        if color.isValid():
            self._bg_color = (color.red(), color.green(), color.blue())
            self._update_bg_button_color()
            self._set_setting("bg_color", list(self._bg_color))
            logger.debug(f"Background color set to: {self._bg_color}")

    def _on_preset_selected(self, preset_label: str):
        """Handle resolution preset selection.

        Args:
            preset_label: Selected preset label.
        """
        if preset_label in command.RESOLUTION_PRESETS:
            width, height = command.RESOLUTION_PRESETS[preset_label]
            self._resize_viewport(width, height)
            logger.info(f"Selected preset: {preset_label}")

    def _on_set_custom_resolution(self):
        """Handle custom resolution set button."""
        if not self.width_spinbox or not self.height_spinbox:
            return

        width = self.width_spinbox.value()
        height = self.height_spinbox.value()
        self._resize_viewport(width, height)
        logger.info(f"Set custom resolution: {width}x{height}")

    def _set_viewport_size(self, width: int, height: int) -> bool:
        """Set viewport size only (without window adjustment).

        Args:
            width: Target viewport width.
            height: Target viewport height.

        Returns:
            True if successful, False otherwise.
        """
        if not self.panel_name:
            return False

        # Reset fixed size to allow resizing (same as sample_ui.py)
        self.setFixedSize(0, 0)

        # Get M3dView and wrap as QWidget
        try:
            view = omui.M3dView.getM3dViewFromModelPanel(self.panel_name)
            if not view:
                logger.warning("Failed to get M3dView from model panel.")
                return False

            viewport = shiboken.wrapInstance(int(view.widget()), QWidget)
            viewport.setFixedSize(width, height)
            logger.debug(f"Set viewport size to: {width}x{height}")
        except Exception as e:
            logger.warning(f"Failed to set viewport size: {e}")
            return False

        # Update spinboxes
        if self.width_spinbox:
            self.width_spinbox.setValue(width)
        if self.height_spinbox:
            self.height_spinbox.setValue(height)

        return True

    def _lock_window_size(self):
        """Lock window size to fit current content."""
        self.adjustSize()
        self.setFixedSize(self.size())
        logger.debug("Locked window size.")

    def _resize_viewport(self, width: int, height: int):
        """Resize the embedded viewport and lock window size.

        Args:
            width: Target viewport width.
            height: Target viewport height.
        """
        if not self._set_viewport_size(width, height):
            return

        # Fit window to content
        self._lock_window_size()

        # Save settings
        self._set_setting("width", width)
        self._set_setting("height", height)

    def _get_background_color(self) -> tuple[int, int, int] | None:
        """Get current background color.

        Returns:
            RGB tuple or None for transparent.
        """
        if self._bg_transparent:
            return None
        return self._bg_color

    def _on_save_button(self):
        """Handle Save button click - routes to PNG or GIF based on mode."""
        if self._current_mode == "png":
            self._on_capture_png()
        elif self._current_mode == "gif":
            self._on_capture_gif()

    def _on_copy_png_to_clipboard(self):
        """Handle PNG copy to clipboard button click."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for capture")
            return

        width = self.width_spinbox.value() if self.width_spinbox else 640
        height = self.height_spinbox.value() if self.height_spinbox else 360
        background_color = self._get_background_color()

        try:
            cmds.waitCursor(state=True)

            # Capture frame
            image = command.capture_frame(self.panel_name, width, height)
            image = command.composite_with_background(image, background_color)

            # Convert to QImage and copy to clipboard
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)

            qimage = QImage()
            qimage.loadFromData(buffer.read())

            clipboard = QApplication.clipboard()
            clipboard.setPixmap(QPixmap.fromImage(qimage))

            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Copied to clipboard!", pos="midCenter", fade=True)
            logger.info("PNG copied to clipboard")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.warning(f"Failed to copy to clipboard: {e}")
            logger.error(f"Failed to copy to clipboard: {e}")

    def _on_capture_png(self):
        """Handle PNG capture button click."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for capture")
            return

        width = self.width_spinbox.value() if self.width_spinbox else 640
        height = self.height_spinbox.value() if self.height_spinbox else 360
        background_color = self._get_background_color()

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="PNG Images (*.png)",
            dialogStyle=2,
            fileMode=0,
            caption="Save Snapshot",
        )

        if not file_path:
            return

        file_path = file_path[0]
        if not file_path.lower().endswith(".png"):
            file_path += ".png"

        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

            image = command.capture_frame(self.panel_name, width, height)
            command.save_png(image, file_path, background_color)

            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
            logger.info(f"Saved snapshot: {file_path}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(clear="midCenter")
            cmds.warning(f"Failed to save PNG: {e}")
            logger.error(f"Failed to save: {e}")

    def _on_capture_gif(self):
        """Handle GIF capture button click."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for capture")
            return

        width = self.width_spinbox.value() if self.width_spinbox else 640
        height = self.height_spinbox.value() if self.height_spinbox else 360

        # Get GIF settings - use Maya timeline for frame range
        start_frame = int(cmds.playbackOptions(query=True, minTime=True))
        end_frame = int(cmds.playbackOptions(query=True, maxTime=True))
        fps = self._get_setting("fps", 24)
        loop = self._get_setting("loop", True)
        background_color = self._get_background_color()

        # Validate frame range
        if start_frame > end_frame:
            cmds.warning("Start frame must be less than or equal to end frame")
            return

        frame_count = end_frame - start_frame + 1
        if frame_count > 500:
            cmds.warning("Frame range too large (max 500 frames)")
            return

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="GIF Images (*.gif)",
            dialogStyle=2,
            fileMode=0,
            caption="Save GIF",
        )

        if not file_path:
            return

        file_path = file_path[0]
        if not file_path.lower().endswith(".gif"):
            file_path += ".gif"

        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(message="Capturing...", pos="midCenter", fade=False)
            logger.info(f"Capturing {frame_count} frames...")

            images = command.capture_frame_range(self.panel_name, start_frame, end_frame, width, height)

            cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)
            command.save_gif(images, file_path, fps, background_color, loop=loop)

            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
            logger.info(f"Saved GIF: {file_path}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(clear="midCenter")
            cmds.warning(f"Failed to capture GIF: {e}")
            logger.error(f"Failed to capture GIF: {e}")

    def _on_record_toggle(self):
        """Toggle recording state."""
        # Check if we're in countdown phase
        if self._countdown_timer is not None:
            # Cancel countdown
            self._countdown_timer.stop()
            self._countdown_timer.deleteLater()
            self._countdown_timer = None
            self._countdown_value = 0
            self._update_record_button_icon("rec")
            cmds.inViewMessage(message="Cancelled", pos="midCenter", fade=True)
            logger.info("Recording countdown cancelled")
            return

        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording frames with optional countdown delay."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for recording")
            return

        delay_sec = self._get_setting("delay", 3)

        if delay_sec > 0:
            # Start countdown
            self._countdown_value = delay_sec
            self._update_record_button_icon(str(self._countdown_value))

            # Create countdown timer (1 second interval)
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
            self._countdown_timer.start(1000)

            logger.info(f"Recording countdown started: {delay_sec} seconds")
        else:
            # No delay, start recording immediately
            self._begin_recording()

    def _on_countdown_tick(self):
        """Handle countdown tick."""
        self._countdown_value -= 1

        if self._countdown_value > 0:
            self._update_record_button_icon(str(self._countdown_value))
        else:
            # Countdown finished
            if self._countdown_timer is not None:
                self._countdown_timer.stop()
                self._countdown_timer.deleteLater()
                self._countdown_timer = None

            self._begin_recording()

    def _begin_recording(self):
        """Begin actual recording (called after countdown or immediately)."""
        self._is_recording = True
        self._recorded_frames = []

        # Switch to stop icon
        self._update_record_button_icon("stop")

        # Get overlay settings
        self._show_cursor = self._get_setting("show_cursor", True)
        self._show_clicks = self._get_setting("show_clicks", True)
        self._show_keys = self._get_setting("show_keys", False)

        # Get the viewport widget using M3dView (same as _resize_viewport)
        # This gets the actual 3D viewport without the toolbar
        viewport_widget = None
        try:
            view = omui.M3dView.getM3dViewFromModelPanel(self.panel_name)
            if view:
                viewport_widget = shiboken.wrapInstance(int(view.widget()), QWidget)
        except Exception as e:
            logger.warning(f"Failed to get viewport widget: {e}")

        if viewport_widget:
            self._capture_bbox = get_widget_screen_bbox(viewport_widget)
            logger.debug(f"Capture bbox: {self._capture_bbox}")
        else:
            logger.warning("Could not get viewport widget for recording")
            self._capture_bbox = None

        # Start input monitor for cursor/keyboard tracking
        if viewport_widget and (self._show_cursor or self._show_keys):
            self._input_monitor = InputMonitor(viewport_widget)
            self._input_monitor.start()

        # Get FPS for timer interval
        fps = self._get_setting("fps", 24)
        interval_ms = int(1000 / fps)

        # Create and start timer
        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._on_timer_tick)
        self._record_timer.start(interval_ms)

        logger.info(f"Recording started at {fps} FPS (interval: {interval_ms}ms)")

    def _on_timer_tick(self):
        """Capture frame on timer tick using screen capture."""
        if not self._is_recording:
            return

        if self._capture_bbox is None:
            logger.error("No capture bbox available")
            return

        try:
            # Capture screen region
            image = capture_screen_region(self._capture_bbox)

            # Draw cursor overlay
            if self._show_cursor:
                cursor_pos = get_cursor_screen_position()
                image = draw_cursor(image, cursor_pos, self._capture_bbox)

                # Draw click indicators
                if self._show_clicks and self._input_monitor:
                    clicks = self._input_monitor.get_recent_clicks()
                    if clicks:
                        image = draw_click_indicators(image, clicks, self._capture_bbox)

            # Draw keyboard overlay
            if self._show_keys and self._input_monitor:
                pressed_keys = self._input_monitor.get_pressed_keys()
                if pressed_keys:
                    image = draw_key_overlay(image, pressed_keys)

            self._recorded_frames.append(image)
            logger.debug(f"Captured frame ({len(self._recorded_frames)} total)")
        except Exception as e:
            logger.error(f"Failed to capture frame: {e}")

    def _stop_recording(self):
        """Stop recording and save GIF."""
        self._is_recording = False

        # Stop timer
        if self._record_timer is not None:
            self._record_timer.stop()
            self._record_timer.deleteLater()
            self._record_timer = None

        # Stop input monitor
        if self._input_monitor is not None:
            self._input_monitor.stop()
            self._input_monitor = None

        # Clear capture state
        self._capture_bbox = None

        # Restore to rec icon
        self._update_record_button_icon("rec")

        # Check if we have frames
        if not self._recorded_frames:
            cmds.warning("No frames recorded")
            return

        original_count = len(self._recorded_frames)
        logger.info(f"Recording stopped - {original_count} frames captured")

        # Apply end trim
        trim_sec = self._get_setting("trim", 0)
        if trim_sec > 0:
            fps = self._get_setting("fps", 24)
            frames_to_trim = int(trim_sec * fps)
            if frames_to_trim > 0 and frames_to_trim < len(self._recorded_frames):
                self._recorded_frames = self._recorded_frames[:-frames_to_trim]
                logger.info(f"Trimmed {frames_to_trim} frames from end ({trim_sec} seconds)")

        frame_count = len(self._recorded_frames)
        if frame_count == 0:
            cmds.warning("All frames trimmed - nothing to save")
            self._recorded_frames = []
            return

        logger.info(f"Final frame count: {frame_count} (trimmed {original_count - frame_count})")

        # Get settings
        fps = self._get_setting("fps", 24)

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="GIF Images (*.gif)",
            dialogStyle=2,
            fileMode=0,
            caption="Save Recorded GIF",
        )

        if not file_path:
            self._recorded_frames = []
            return

        file_path = file_path[0]
        if not file_path.lower().endswith(".gif"):
            file_path += ".gif"

        # Save GIF
        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

            command.save_gif(self._recorded_frames, file_path, fps)

            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
            logger.info(f"Saved recorded GIF: {file_path}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(clear="midCenter")
            cmds.warning(f"Failed to save GIF: {e}")
            logger.error(f"Failed to save GIF: {e}")
        finally:
            self._recorded_frames = []

    def _stop_recording_cleanup_only(self):
        """Stop recording without saving (for closeEvent)."""
        self._is_recording = False

        if self._record_timer is not None:
            self._record_timer.stop()
            self._record_timer.deleteLater()
            self._record_timer = None

        if self._input_monitor is not None:
            self._input_monitor.stop()
            self._input_monitor = None

        self._capture_bbox = None
        self._recorded_frames = []

    def closeEvent(self, event):
        """Handle window close - cleanup Maya UI elements."""
        # Stop recording if active
        if self._is_recording:
            self._stop_recording_cleanup_only()

        # Stop countdown timer
        if self._countdown_timer is not None:
            self._countdown_timer.stop()
            self._countdown_timer.deleteLater()
            self._countdown_timer = None

        # Save current settings
        self._save_settings()

        # Delete Maya UI elements
        if self.pane_layout_name and cmds.paneLayout(self.pane_layout_name, exists=True):
            logger.debug(f"Deleting pane layout: {self.pane_layout_name}")
            cmds.deleteUI(self.pane_layout_name, layout=True)

        if self.panel_name and cmds.modelPanel(self.panel_name, exists=True):
            logger.debug(f"Deleting model panel: {self.panel_name}")
            cmds.deleteUI(self.panel_name, panel=True)

        super().closeEvent(event)


def show_ui():
    """Show the Snapshot Capture window.

    Returns:
        SnapshotCaptureWindow: The window instance.
    """
    global _instance

    # Close existing instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    _instance = SnapshotCaptureWindow(get_maya_main_window())
    _instance.show()

    # Restore viewport size with deferred execution
    data = _instance.settings.load_settings("default")
    width = data.get("width", 640)
    height = data.get("height", 360)

    # First deferred call: Set viewport size (with evaluateNext=True)
    def _apply_viewport_size():
        if _instance:
            _instance._set_viewport_size(width, height)
            logger.info(f"Restored viewport size to: {width}x{height}")

    cmds.evalDeferred(_apply_viewport_size, evaluateNext=True)

    # Second deferred call: Lock window size (without evaluateNext)
    def _lock_window():
        if _instance:
            _instance._lock_window_size()

    cmds.evalDeferred(_lock_window)

    return _instance


def get_panel_name() -> str | None:
    """Get the current panel name for capture.

    Returns:
        Panel name or None if no window is open.
    """
    global _instance
    if _instance:
        return _instance.panel_name
    return None


__all__ = ["show_ui", "get_panel_name"]
