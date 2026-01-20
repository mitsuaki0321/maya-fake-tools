"""Snapshot Capture UI - PySide-based window implementation."""

from __future__ import annotations

from io import BytesIO
import logging
import os

import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from ....lib_ui import ToolDataManager, ToolSettingsManager, get_maya_main_window
from ....lib_ui.maya_qt import qt_widget_from_maya_control
from ....lib_ui.qt_compat import (
    QApplication,
    QByteArray,
    QColor,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QIcon,
    QImage,
    QIntValidator,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMimeData,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
    shiboken,
)
from ....lib_ui.widgets import IconButton, IconButtonStyle, IconToolButton
from . import command
from .external_handlers import get_available_handlers
from .ui_recording import RecordingController

logger = logging.getLogger(__name__)

# UI Constants
BUTTON_SIZE = 24
BUTTON_SIZE_SMALL = 20
TOOLBAR_SPACING = 4
TOOLBAR_MARGINS = (4, 4, 4, 4)
MODE_COMBO_WIDTH = 60
RESOLUTION_INPUT_WIDTH = 45

# Recording Constants
MAX_GIF_FRAMES = 500

# Options
FPS_OPTIONS = [10, 12, 15, 24, 30, 50, 60]
DELAY_OPTIONS = [0, 1, 2, 3]
TRIM_OPTIONS = [0, 1, 2, 3]

_instance = None


class SnapshotCaptureWindow(QMainWindow):
    """Snapshot Capture window with embedded modelPanel."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Settings
        self.settings = ToolSettingsManager(tool_name="snapshot_capture", category="common")
        self._settings_cache: dict = {}  # In-memory cache to avoid frequent file I/O

        # Default save directory (using ToolDataManager)
        tool_data_manager = ToolDataManager("snapshot_capture", "common")
        tool_data_manager.ensure_data_dir()
        self._default_save_dir = str(tool_data_manager.get_data_dir())
        self._last_save_dir: str | None = None  # Tracks last used directory during session

        # Window configuration
        self.setObjectName(self._ui_name("MainWindow"))
        self.setWindowTitle("Snapshot Capture")

        # State variables
        self._current_mode: str = "png"
        self._bg_color: tuple[int, int, int] = (128, 128, 128)
        self._bg_transparent: bool = False
        self._viewport_width: int = 640  # Cached viewport size
        self._viewport_height: int = 360

        # Recording controller
        self._recording_controller = RecordingController(self)
        self._recording_controller.recording_started.connect(self._on_recording_started)
        self._recording_controller.recording_stopped.connect(self._on_recording_stopped)
        self._recording_controller.countdown_tick.connect(self._on_countdown_tick)
        self._recording_controller.countdown_cancelled.connect(self._on_countdown_cancelled)

        # Maya UI elements (will be created in _create_viewport)
        self.pane_layout_name: str | None = None
        self.panel_name: str | None = None

        # UI widgets (will be created in _setup_ui)
        self.mode_combo: QComboBox | None = None
        self.bg_button: QPushButton | None = None  # Shared BG button (PNG/GIF only)
        self.bg_separator: QWidget | None = None  # Separator after BG button (PNG/GIF only)
        self.option_button: IconToolButton | None = None
        self.option_menu: QMenu | None = None
        self.action_stack: QStackedWidget | None = None  # Mode-specific action buttons
        # PNG mode action buttons
        self.png_save_button: IconButton | None = None
        self.png_copy_button: IconButton | None = None
        # GIF mode action buttons
        self.gif_save_button: IconButton | None = None
        # Rec mode action buttons
        self.record_button: IconButton | None = None
        # Resolution controls
        self.width_edit: QLineEdit | None = None
        self.height_edit: QLineEdit | None = None
        self.preset_button: IconToolButton | None = None
        self.set_button: IconButton | None = None

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

    def _get_maya_background_color(self) -> tuple[int, int, int]:
        """Get Maya's global background color.

        Returns:
            RGB tuple (0-255).
        """
        try:
            rgb = cmds.displayRGBColor("background", query=True)
            if rgb and len(rgb) == 3:
                return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        except Exception as e:
            logger.warning(f"Failed to get Maya background color: {e}")
        return (128, 128, 128)  # Fallback gray

    def _load_settings(self):
        """Load saved settings from JSON into cache."""
        data = self.settings.load_settings("default")

        # Populate cache with defaults, then override with saved values
        self._settings_cache = {
            "mode": "png",
            "width": 640,
            "height": 360,
            "bg_color": None,  # Will be set below
            "bg_transparent": False,
            "fps": 24,
            "loop": True,
            "delay": 3,
            "trim": 0,
            "show_cursor": True,
            "show_clicks": True,
            "show_keys": False,
        }
        self._settings_cache.update(data)

        # Set instance variables from cache
        self._current_mode = self._settings_cache.get("mode", "png")
        self._viewport_width = self._settings_cache.get("width", 640)
        self._viewport_height = self._settings_cache.get("height", 360)
        bg_color = self._settings_cache.get("bg_color")
        if bg_color and isinstance(bg_color, list) and len(bg_color) == 3:
            # Use saved color
            self._bg_color = tuple(bg_color)
        else:
            # First launch: use Maya's global background color
            self._bg_color = self._get_maya_background_color()
            self._settings_cache["bg_color"] = list(self._bg_color)
        self._bg_transparent = self._settings_cache.get("bg_transparent", False)

    def _get_resolution(self) -> tuple[int, int]:
        """Get current resolution from input fields.

        Returns:
            Tuple of (width, height).
        """
        default_width, default_height = 640, 360

        width_text = self.width_edit.text() if self.width_edit else ""
        height_text = self.height_edit.text() if self.height_edit else ""

        width = int(width_text) if width_text.isdigit() else default_width
        height = int(height_text) if height_text.isdigit() else default_height

        return width, height

    def _get_save_directory(self) -> str:
        """Get the directory to use for save dialogs.

        Returns:
            Last used directory if available, otherwise default directory.
        """
        if self._last_save_dir and os.path.isdir(self._last_save_dir):
            return self._last_save_dir
        return self._default_save_dir

    def _update_last_save_dir(self, file_path: str):
        """Update the last save directory from a file path.

        Args:
            file_path: Full path to the saved file.
        """
        self._last_save_dir = os.path.dirname(file_path)

    def _save_settings(self):
        """Save cached settings to JSON file."""
        # Sync instance variables to cache before saving
        width, height = self._get_resolution()
        self._settings_cache["mode"] = self._current_mode
        self._settings_cache["width"] = width
        self._settings_cache["height"] = height
        self._settings_cache["bg_color"] = list(self._bg_color)
        self._settings_cache["bg_transparent"] = self._bg_transparent

        # Save cache to file
        self.settings.save_settings(self._settings_cache, "default")

    def _get_setting(self, key: str, default):
        """Get a setting value from cache.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            Setting value or default.
        """
        return self._settings_cache.get(key, default)

    def _set_setting(self, key: str, value):
        """Set a setting value in cache (no file I/O).

        Args:
            key: Setting key.
            value: Value to set.
        """
        self._settings_cache[key] = value

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

        # Hide the icon bar (toolbar) - native toolbar buttons don't work in embedded Qt windows
        bar_layout = cmds.modelPanel(self.panel_name, query=True, barLayout=True)
        if bar_layout:
            cmds.layout(bar_layout, edit=True, visible=False)

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
            logger.debug(f"Changed camera to: {camera}")

    def _create_toolbar(self) -> QWidget:
        """Create the 2-row toolbar.

        Returns:
            Toolbar widget.
        """
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName(self._ui_name("ToolbarWidget"))

        toolbar_layout = QVBoxLayout(toolbar_widget)
        toolbar_layout.setObjectName(self._ui_name("ToolbarLayout"))
        toolbar_layout.setContentsMargins(*TOOLBAR_MARGINS)
        toolbar_layout.setSpacing(TOOLBAR_SPACING)

        # Row 1: Mode + BG + Option + action buttons
        row1_layout = self._create_toolbar_row1()
        toolbar_layout.addLayout(row1_layout)

        # Row 2: Resolution fields
        row2_layout = self._create_toolbar_row2()
        toolbar_layout.addLayout(row2_layout)

        return toolbar_widget

    def _create_toolbar_row1(self) -> QHBoxLayout:
        """Create toolbar row 1 with mode selector and action buttons.

        Layout: [Mode] [stretch] [BG] [ActionStack] [Option]
        - BG button: shown for PNG/GIF, hidden for Rec
        - ActionStack: mode-specific action buttons (Save+Copy / Save / Record)
        - Option button: always visible at rightmost position

        Returns:
            Row 1 layout.
        """
        row1_layout = QHBoxLayout()
        row1_layout.setObjectName(self._ui_name("Row1Layout"))
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(TOOLBAR_SPACING)

        # Mode selector
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName(self._ui_name("ModeCombo"))
        self.mode_combo.addItems(["PNG", "GIF", "Rec"])
        mode_label_map = {"png": "PNG", "gif": "GIF", "rec": "Rec"}
        self.mode_combo.setCurrentText(mode_label_map.get(self._current_mode, "PNG"))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.mode_combo.setFixedWidth(MODE_COMBO_WIDTH)
        row1_layout.addWidget(self.mode_combo)

        # Stretch to push remaining items to right
        row1_layout.addStretch()

        # BG button (PNG/GIF only)
        self.bg_button = QPushButton()
        self.bg_button.setObjectName(self._ui_name("BGButton"))
        self.bg_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.bg_button.setToolTip("Background Color")
        self._update_bg_button_color()
        self.bg_button.clicked.connect(self._on_bg_color_button)
        self.bg_button.setVisible(self._current_mode in ["png", "gif"])
        row1_layout.addWidget(self.bg_button)

        # Separator after BG button (PNG/GIF only)
        self.bg_separator = self._create_separator("BGSeparator")
        self.bg_separator.setVisible(self._current_mode in ["png", "gif"])
        row1_layout.addWidget(self.bg_separator)

        # Action buttons stack (mode-specific)
        self.action_stack = QStackedWidget()
        self.action_stack.setObjectName(self._ui_name("ActionStack"))
        self.action_stack.setContentsMargins(0, 0, 0, 0)  # Remove default margins
        # Set size policy to only take minimum required width
        self.action_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        # PNG mode widget (index 0): Save + Copy
        png_widget = QWidget()
        png_layout = QHBoxLayout(png_widget)
        png_layout.setContentsMargins(0, 0, 0, 0)
        png_layout.setSpacing(TOOLBAR_SPACING)

        self.png_save_button = self._create_save_button("PNGSaveButton")
        png_layout.addWidget(self.png_save_button)

        self.png_copy_button = IconButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.png_copy_button.setObjectName(self._ui_name("PNGCopyButton"))
        self.png_copy_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.png_copy_button.setToolTip("Copy to Clipboard (Right-click for more options)")
        copy_icon_path = self._get_icon_path("snapshot_copy.png")
        if copy_icon_path:
            self.png_copy_button.setIcon(QIcon(copy_icon_path))
        else:
            self.png_copy_button.setText("C")
        self.png_copy_button.clicked.connect(self._on_copy_png_to_clipboard)
        self.png_copy_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.png_copy_button.customContextMenuRequested.connect(self._show_copy_context_menu)
        png_layout.addWidget(self.png_copy_button)

        self.action_stack.addWidget(png_widget)  # index 0

        # GIF mode widget (index 1): Save
        gif_widget = QWidget()
        gif_layout = QHBoxLayout(gif_widget)
        gif_layout.setContentsMargins(0, 0, 0, 0)
        gif_layout.setSpacing(TOOLBAR_SPACING)

        gif_layout.addStretch()  # Push button to right edge
        self.gif_save_button = self._create_save_button("GIFSaveButton")
        gif_layout.addWidget(self.gif_save_button)

        self.action_stack.addWidget(gif_widget)  # index 1

        # Rec mode widget (index 2): Record
        rec_widget = QWidget()
        rec_layout = QHBoxLayout(rec_widget)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        rec_layout.setSpacing(TOOLBAR_SPACING)

        rec_layout.addStretch()  # Push button to right edge
        self.record_button = IconButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.record_button.setObjectName(self._ui_name("RecordButton"))
        self.record_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.record_button.setToolTip("Start Recording")
        self._update_record_button_icon("rec")
        self.record_button.clicked.connect(self._on_record_toggle)
        rec_layout.addWidget(self.record_button)

        self.action_stack.addWidget(rec_widget)  # index 2

        # Set initial stack index based on mode
        mode_index_map = {"png": 0, "gif": 1, "rec": 2}
        self.action_stack.setCurrentIndex(mode_index_map.get(self._current_mode, 0))

        row1_layout.addWidget(self.action_stack)

        # Separator before Option button
        option_separator = self._create_separator("OptionSeparator")
        row1_layout.addWidget(option_separator)

        # Option button (always visible at rightmost position)
        self.option_button = IconToolButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.option_button.setObjectName(self._ui_name("OptionButton"))
        self.option_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.option_button.setToolTip("Options")
        self.option_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        option_icon_path = self._get_icon_path("snapshot_options.png")
        if option_icon_path:
            self.option_button.setIcon(QIcon(option_icon_path))

        self.option_menu = QMenu(self.option_button)
        self.option_menu.setObjectName(self._ui_name("OptionMenu"))
        self.option_menu.aboutToShow.connect(self._populate_option_menu)
        self.option_button.setMenu(self.option_menu)
        row1_layout.addWidget(self.option_button)

        return row1_layout

    def _create_save_button(self, name: str) -> IconButton:
        """Create a save button.

        Args:
            name: Object name for the button.

        Returns:
            Configured IconButton.
        """
        button = IconButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        button.setObjectName(self._ui_name(name))
        button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        button.setToolTip("Save")
        save_icon_path = self._get_icon_path("snapshot_save.png")
        if save_icon_path:
            button.setIcon(QIcon(save_icon_path))
        else:
            button.setText("S")
        button.clicked.connect(self._on_save_button)
        return button

    def _create_separator(self, name: str) -> QWidget:
        """Create a vertical separator line.

        Args:
            name: Object name for the separator.

        Returns:
            Configured QWidget as separator.
        """
        separator = QWidget()
        separator.setObjectName(self._ui_name(name))
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: palette(mid);")
        return separator

    def _create_toolbar_row2(self) -> QHBoxLayout:
        """Create toolbar row 2 with resolution controls.

        Returns:
            Row 2 layout.
        """
        row2_layout = QHBoxLayout()
        row2_layout.setObjectName(self._ui_name("Row2Layout"))
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(TOOLBAR_SPACING)

        # Stretch to push items to right
        row2_layout.addStretch()

        # Width input
        self.width_edit = QLineEdit()
        self.width_edit.setObjectName(self._ui_name("WidthEdit"))
        self.width_edit.setValidator(QIntValidator(64, 4096))
        self.width_edit.setText(str(self._get_setting("width", 640)))
        self.width_edit.setFixedWidth(RESOLUTION_INPUT_WIDTH)
        row2_layout.addWidget(self.width_edit)

        # "x" label
        x_label = QLabel("x")
        x_label.setObjectName(self._ui_name("XLabel"))
        row2_layout.addWidget(x_label)

        # Height input
        self.height_edit = QLineEdit()
        self.height_edit.setObjectName(self._ui_name("HeightEdit"))
        self.height_edit.setValidator(QIntValidator(64, 4096))
        self.height_edit.setText(str(self._get_setting("height", 360)))
        self.height_edit.setFixedWidth(RESOLUTION_INPUT_WIDTH)
        row2_layout.addWidget(self.height_edit)

        # Preset button
        self.preset_button = IconToolButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.preset_button.setObjectName(self._ui_name("PresetButton"))
        self.preset_button.setFixedSize(BUTTON_SIZE_SMALL, BUTTON_SIZE_SMALL)
        self.preset_button.setToolTip("Resolution Presets")
        self.preset_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        preset_icon_path = self._get_icon_path("snapshot_dropdown.png")
        if preset_icon_path:
            self.preset_button.setIcon(QIcon(preset_icon_path))

        # Create preset menu
        preset_menu = QMenu(self.preset_button)
        preset_menu.setObjectName(self._ui_name("PresetMenu"))
        for preset_label in command.RESOLUTION_PRESETS:
            preset_menu.addAction(preset_label, lambda checked=False, p=preset_label: self._on_preset_selected(p))
        self.preset_button.setMenu(preset_menu)
        row2_layout.addWidget(self.preset_button)

        # Set button
        self.set_button = IconButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.set_button.setObjectName(self._ui_name("SetButton"))
        self.set_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
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
            self.bg_button.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 2px solid #888888;")

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

    def _populate_option_menu(self):
        """Populate option menu based on current mode."""
        if not self.option_menu:
            return

        self.option_menu.clear()

        # PNG/GIF: Transparent option and Maya background color
        if self._current_mode in ["png", "gif"]:
            transparent_action = self.option_menu.addAction("Transparent")
            transparent_action.setCheckable(True)
            transparent_action.setChecked(self._bg_transparent)
            transparent_action.triggered.connect(self._on_transparent_changed)

            # Use Maya background color option
            maya_bg_action = self.option_menu.addAction("Use Maya Background")
            maya_bg_action.triggered.connect(self._on_use_maya_background)

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
            for fps in FPS_OPTIONS:
                fps_menu.addAction(str(fps), lambda checked=False, f=fps: self._on_fps_selected(f))

        # Rec: Loop, FPS, Delay, Trim, Show options
        elif self._current_mode == "rec":
            # Loop option
            loop_action = self.option_menu.addAction("Loop")
            loop_action.setCheckable(True)
            loop_action.setChecked(self._get_setting("loop", True))
            loop_action.triggered.connect(lambda checked: self._set_setting("loop", checked))

            # FPS submenu
            current_fps = self._get_setting("fps", 24)
            fps_menu = self.option_menu.addMenu(f"FPS: {current_fps}")
            for fps in FPS_OPTIONS:
                fps_menu.addAction(str(fps), lambda checked=False, f=fps: self._on_fps_selected(f))

            # Delay submenu
            delay_val = self._get_setting("delay", 3)
            delay_menu = self.option_menu.addMenu(f"Delay: {delay_val}s")
            for d in DELAY_OPTIONS:
                delay_menu.addAction(f"{d} sec", lambda checked=False, dv=d: self._set_setting("delay", dv))

            # Trim submenu
            trim_val = self._get_setting("trim", 0)
            trim_menu = self.option_menu.addMenu(f"Trim: {trim_val}s")
            for t in TRIM_OPTIONS:
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

        # Update BG button and separator visibility (PNG/GIF only)
        bg_visible = self._current_mode in ["png", "gif"]
        if self.bg_button:
            self.bg_button.setVisible(bg_visible)
        if self.bg_separator:
            self.bg_separator.setVisible(bg_visible)

        # Switch action stack to show mode-specific buttons
        if self.action_stack:
            mode_index_map = {"png": 0, "gif": 1, "rec": 2}
            self.action_stack.setCurrentIndex(mode_index_map.get(self._current_mode, 0))

        logger.debug(f"Mode changed to: {self._current_mode}")

    def _on_transparent_changed(self, checked: bool):
        """Handle transparent option change.

        Args:
            checked: Whether transparent is enabled.
        """
        self._bg_transparent = checked
        self._set_setting("bg_transparent", checked)
        logger.debug(f"Transparent set to: {checked}")

    def _on_use_maya_background(self):
        """Handle 'Use Maya Background' option - set BG color from Maya's global setting."""
        self._bg_color = self._get_maya_background_color()
        self._update_bg_button_color()
        self._set_setting("bg_color", list(self._bg_color))
        logger.debug(f"Background color set to Maya's global: {self._bg_color}")

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
            if width == self._viewport_width and height == self._viewport_height:
                return
            self._resize_viewport(width, height)
            logger.debug(f"Selected preset: {preset_label}")

    def _on_set_custom_resolution(self):
        """Handle custom resolution set button."""
        if not self.width_edit or not self.height_edit:
            return

        width, height = self._get_resolution()
        if width == self._viewport_width and height == self._viewport_height:
            return
        self._resize_viewport(width, height)

    def _resize_viewport(self, width: int, height: int):
        """Resize the embedded viewport and lock window size.

        Args:
            width: Target viewport width.
            height: Target viewport height.
        """
        if not self.panel_name:
            return

        # Reset fixed size to allow resizing
        self.setFixedSize(0, 0)

        # Get M3dView and wrap as QWidget
        try:
            view = omui.M3dView.getM3dViewFromModelPanel(self.panel_name)
            if not view:
                logger.warning("Failed to get M3dView from model panel.")
                return

            viewport = shiboken.wrapInstance(int(view.widget()), QWidget)
            viewport.setFixedSize(width, height)
            logger.debug(f"Set viewport size to: {width}x{height}")
        except Exception as e:
            logger.warning(f"Failed to set viewport size: {e}")
            return

        # Update input fields
        if self.width_edit:
            self.width_edit.setText(str(width))
        if self.height_edit:
            self.height_edit.setText(str(height))

        # Fit window to content
        self.adjustSize()
        self.setFixedSize(self.size())

        # Update cached viewport size
        self._viewport_width = width
        self._viewport_height = height

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

        width, height = self._get_resolution()
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
            png_data = buffer.read()

            qimage = QImage()
            qimage.loadFromData(png_data)

            # Set clipboard with multiple formats for compatibility
            # DIB format for Windows apps (Snipping Tool, etc.)
            # PNG format for web apps (Gmail, etc.)
            mime_data = QMimeData()
            mime_data.setImageData(qimage)
            mime_data.setData("image/png", QByteArray(png_data))

            clipboard = QApplication.clipboard()
            clipboard.setMimeData(mime_data)

            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Copied to clipboard!", pos="midCenter", fade=True)
            logger.info("PNG copied to clipboard")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.warning(f"Failed to copy to clipboard: {e}")
            logger.error(f"Failed to copy to clipboard: {e}")

    def _show_copy_context_menu(self, pos):
        """Show context menu for copy button with external app options.

        Args:
            pos: Position where context menu was requested.
        """
        handlers = get_available_handlers()
        if not handlers:
            return

        menu = QMenu(self)
        for handler in handlers:
            action = menu.addAction(handler.menu_name)
            action.triggered.connect(lambda checked=False, h=handler: self._open_in_external_app(h))
        menu.exec_(self.png_copy_button.mapToGlobal(pos))

    def _open_in_external_app(self, handler):
        """Capture image and open in external application.

        Args:
            handler: ExternalAppHandler instance to use.
        """
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for capture")
            return

        width, height = self._get_resolution()
        background_color = self._get_background_color()

        try:
            cmds.waitCursor(state=True)

            # Capture frame
            image = command.capture_frame(self.panel_name, width, height)
            image = command.composite_with_background(image, background_color)

            # Save to temp file
            import tempfile
            import time

            timestamp = int(time.time() * 1000)
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"snapshot_capture_{timestamp}.png")
            image.save(temp_path, format="PNG")

            # Verify file was saved successfully
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                raise OSError(f"Failed to save temp file: {temp_path}")

            cmds.waitCursor(state=False)
            logger.debug(f"Saved temp file: {temp_path} ({os.path.getsize(temp_path)} bytes)")

            # Open in external app
            if handler.open_image(temp_path):
                logger.info(f"Opened in external app: {temp_path}")
            else:
                cmds.warning("Failed to open external application")
                logger.error("Failed to open external application")
        except FileNotFoundError:
            cmds.waitCursor(state=False)
            cmds.warning(f"Application not found: {handler.menu_name}")
            logger.error(f"Application not found for handler: {handler.menu_name}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.warning(f"Failed to open in external app: {e}")
            logger.error(f"Failed to open in external app: {e}")

    def _on_capture_png(self):
        """Handle PNG capture button click."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for capture")
            return

        width, height = self._get_resolution()
        background_color = self._get_background_color()

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="PNG Images (*.png)",
            dialogStyle=2,
            fileMode=0,
            caption="Save Snapshot",
            startingDirectory=self._get_save_directory(),
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

            self._update_last_save_dir(file_path)
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

        width, height = self._get_resolution()

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
        if frame_count > MAX_GIF_FRAMES:
            cmds.warning(f"Frame range too large (max {MAX_GIF_FRAMES} frames)")
            return

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="GIF Images (*.gif)",
            dialogStyle=2,
            fileMode=0,
            caption="Save GIF",
            startingDirectory=self._get_save_directory(),
        )

        if not file_path:
            return

        file_path = file_path[0]
        if not file_path.lower().endswith(".gif"):
            file_path += ".gif"

        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(message="Capturing...", pos="midCenter", fade=False)
            logger.debug(f"Capturing {frame_count} frames...")

            images = command.capture_frame_range(self.panel_name, start_frame, end_frame, width, height)

            cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)
            command.save_gif(images, file_path, fps, background_color, loop=loop)

            self._update_last_save_dir(file_path)
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
        if self._recording_controller.is_counting_down:
            self._recording_controller.cancel_countdown()
            return

        if self._recording_controller.is_recording:
            self._recording_controller.stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording frames with optional countdown delay."""
        if not self.panel_name or not cmds.modelPanel(self.panel_name, exists=True):
            cmds.warning("No panel available for recording")
            return

        # Get the viewport widget using M3dView
        viewport_widget = None
        try:
            view = omui.M3dView.getM3dViewFromModelPanel(self.panel_name)
            if view:
                viewport_widget = shiboken.wrapInstance(int(view.widget()), QWidget)
        except Exception as e:
            logger.warning(f"Failed to get viewport widget: {e}")
            return

        if not viewport_widget:
            cmds.warning("Could not get viewport widget for recording")
            return

        # Get settings
        fps = self._get_setting("fps", 24)
        delay = self._get_setting("delay", 3)
        show_cursor = self._get_setting("show_cursor", True)
        show_clicks = self._get_setting("show_clicks", True)
        show_keys = self._get_setting("show_keys", False)

        # Update button to show countdown (if delay > 0)
        if delay > 0:
            self._update_record_button_icon(str(delay))

        # Start recording via controller
        self._recording_controller.start_recording(
            viewport_widget=viewport_widget,
            fps=fps,
            delay=delay,
            show_cursor=show_cursor,
            show_clicks=show_clicks,
            show_keys=show_keys,
        )

    def _on_countdown_tick(self, remaining: int):
        """Handle countdown tick from controller.

        Args:
            remaining: Remaining seconds.
        """
        self._update_record_button_icon(str(remaining))

    def _on_countdown_cancelled(self):
        """Handle countdown cancellation from controller."""
        self._update_record_button_icon("rec")
        cmds.inViewMessage(message="Cancelled", pos="midCenter", fade=True)

    def _on_recording_started(self):
        """Handle recording start signal from controller."""
        self._update_record_button_icon("stop")

    def _on_recording_stopped(self, frames: list):
        """Handle recording stop signal from controller.

        Args:
            frames: List of captured PIL Image frames.
        """
        # Restore to rec icon
        self._update_record_button_icon("rec")

        # Check if we have frames
        if not frames:
            cmds.warning("No frames recorded")
            return

        original_count = len(frames)

        # Apply end trim
        trim_sec = self._get_setting("trim", 0)
        if trim_sec > 0:
            fps = self._get_setting("fps", 24)
            frames_to_trim = int(trim_sec * fps)
            if frames_to_trim > 0 and frames_to_trim < len(frames):
                frames = frames[:-frames_to_trim]
                logger.debug(f"Trimmed {frames_to_trim} frames from end ({trim_sec} seconds)")

        frame_count = len(frames)
        if frame_count == 0:
            cmds.warning("All frames trimmed - nothing to save")
            return

        logger.debug(f"Final frame count: {frame_count} (trimmed {original_count - frame_count})")

        # Get settings
        fps = self._get_setting("fps", 24)
        loop = self._get_setting("loop", True)

        # Get save path from user
        file_path = cmds.fileDialog2(
            fileFilter="GIF Images (*.gif)",
            dialogStyle=2,
            fileMode=0,
            caption="Save Recorded GIF",
            startingDirectory=self._get_save_directory(),
        )

        if not file_path:
            return

        file_path = file_path[0]
        if not file_path.lower().endswith(".gif"):
            file_path += ".gif"

        # Save GIF
        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

            command.save_gif(frames, file_path, fps, loop=loop)

            self._update_last_save_dir(file_path)
            cmds.waitCursor(state=False)
            cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
            logger.info(f"Saved recorded GIF: {file_path}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(clear="midCenter")
            cmds.warning(f"Failed to save GIF: {e}")
            logger.error(f"Failed to save GIF: {e}")

    def closeEvent(self, event):
        """Handle window close - cleanup Maya UI elements."""
        # Clean up recording controller
        self._recording_controller.cleanup()

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

    # Restore viewport size with deferred execution (using cached settings)
    width = _instance._settings_cache.get("width", 640)
    height = _instance._settings_cache.get("height", 360)

    # Deferred call: Resize viewport (includes window size adjustment)
    def _apply_viewport_size():
        if _instance:
            _instance._resize_viewport(width, height)
            logger.debug(f"Restored viewport size to: {width}x{height}")

    cmds.evalDeferred(_apply_viewport_size, evaluateNext=True)

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
