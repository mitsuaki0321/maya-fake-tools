"""Snapshot Capture UI - PySide-based window implementation."""

from __future__ import annotations

from io import BytesIO
import logging
import os

import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

# Check PIL availability
try:
    from PIL import Image  # noqa: F401

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ....lib_ui import ToolDataManager, ToolSettingsManager, get_maya_main_window
from ....lib_ui.maya_qt import qt_widget_from_maya_control, qt_widget_from_maya_layout
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
    QSize,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    shiboken,
)
from ....lib_ui.widgets import IconButton, IconButtonStyle, IconToolButton
from . import command
from .export_handlers import Mp4ExportHandler
from .external_handlers import get_available_handlers
from .ui_annotation import show_annotation_editor
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
QUALITY_OPTIONS = ["high", "medium", "low"]
QUALITY_LABELS = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

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
        self._viewport_width: int = command.DEFAULT_WIDTH  # Cached viewport size
        self._viewport_height: int = command.DEFAULT_HEIGHT

        # Recording controller
        self._recording_controller = RecordingController(self)
        self._recording_controller.recording_started.connect(self._on_recording_started)
        self._recording_controller.recording_stopped.connect(self._on_recording_stopped)
        self._recording_controller.countdown_tick.connect(self._on_countdown_tick)
        self._recording_controller.countdown_cancelled.connect(self._on_countdown_cancelled)

        # Maya UI elements (will be created in _create_viewport)
        self.pane_layout_name: str | None = None
        self.panel_name: str | None = None
        self.pane_widget: QWidget | None = None

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
        self.toolbar_widget: QWidget | None = None

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
            "width": command.DEFAULT_WIDTH,
            "height": command.DEFAULT_HEIGHT,
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
        self._viewport_width = self._settings_cache.get("width", command.DEFAULT_WIDTH)
        self._viewport_height = self._settings_cache.get("height", command.DEFAULT_HEIGHT)
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
        default_width, default_height = command.DEFAULT_WIDTH, command.DEFAULT_HEIGHT

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
        self.toolbar_widget = toolbar_widget
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

        # Add custom menus to panel's menu bar
        self._create_camera_menu()
        self._create_isolate_menu()

        # Configure editor
        cmds.modelEditor(
            self.panel_name,
            edit=True,
            displayAppearance="smoothShaded",
            headsUpDisplay=False,
            grid=True,
        )

        # Convert to Qt widget
        self.pane_widget = qt_widget_from_maya_control(self.pane_layout_name)
        return self.pane_widget

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

    def _create_isolate_menu(self):
        """Create Isolate menu in panel's menu bar."""
        if not self.panel_name:
            return

        menu_name = self.panel_name + "IsolateMenu"

        # Delete existing menu if present
        if cmds.menu(menu_name, exists=True):
            cmds.deleteUI(menu_name)

        # Create Isolate menu in panel's menu bar
        cmds.menu(menu_name, label="Isolate", parent=self.panel_name)

        # Store menu item name for later access
        self._isolate_menu_item = cmds.menuItem(
            label="View Selected",
            checkBox=False,
            command=lambda x: self._on_isolate_toggled(x),
            parent=menu_name,
        )

        # Add Selected menu item
        cmds.menuItem(
            label="Add Selected",
            command=lambda x: self._on_isolate_add_selected(),
            parent=menu_name,
        )

        # Remove Selected menu item
        cmds.menuItem(
            label="Remove Selected",
            command=lambda x: self._on_isolate_remove_selected(),
            parent=menu_name,
        )

    def _on_isolate_toggled(self, checked: bool):
        """Handle isolate select toggle.

        Args:
            checked: Isolate state.
        """
        if not self.panel_name:
            return

        if checked:
            # Isolate selected objects
            cmds.isolateSelect(self.panel_name, state=True)
            cmds.isolateSelect(self.panel_name, addSelectedObjects=True)
        else:
            # Disable isolate
            cmds.isolateSelect(self.panel_name, state=False)

        logger.debug(f"Isolate select: {checked}")

    def _on_isolate_add_selected(self):
        """Add selected objects to isolate set."""
        if not self.panel_name:
            return

        cmds.isolateSelect(self.panel_name, addSelectedObjects=True)
        logger.debug("Added selected objects to isolate set")

    def _on_isolate_remove_selected(self):
        """Remove selected objects from isolate set."""
        if not self.panel_name:
            return

        cmds.isolateSelect(self.panel_name, removeSelected=True)
        logger.debug("Removed selected objects from isolate set")

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
        copy_icon_path = self._get_icon_path("snapshot_copy.svg")
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

        option_icon_path = self._get_icon_path("snapshot_options.svg")
        if option_icon_path:
            self.option_button.setIcon(QIcon(option_icon_path))

        self.option_menu = QMenu(self.option_button)
        self.option_menu.setObjectName(self._ui_name("OptionMenu"))
        self.option_menu.aboutToShow.connect(self._populate_option_menu)
        self.option_button.setMenu(self.option_menu)
        self.option_button.setStyleSheet("QToolButton::menu-indicator { image: none; }")
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
        save_icon_path = self._get_icon_path("snapshot_save.svg")
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
        self.width_edit.setValidator(QIntValidator(command.MIN_RESOLUTION, command.MAX_RESOLUTION))
        self.width_edit.setText(str(self._get_setting("width", command.DEFAULT_WIDTH)))
        self.width_edit.setFixedWidth(RESOLUTION_INPUT_WIDTH)
        row2_layout.addWidget(self.width_edit)

        # "x" label
        x_label = QLabel("x")
        x_label.setObjectName(self._ui_name("XLabel"))
        row2_layout.addWidget(x_label)

        # Height input
        self.height_edit = QLineEdit()
        self.height_edit.setObjectName(self._ui_name("HeightEdit"))
        self.height_edit.setValidator(QIntValidator(command.MIN_RESOLUTION, command.MAX_RESOLUTION))
        self.height_edit.setText(str(self._get_setting("height", command.DEFAULT_HEIGHT)))
        self.height_edit.setFixedWidth(RESOLUTION_INPUT_WIDTH)
        row2_layout.addWidget(self.height_edit)

        # Preset button
        self.preset_button = IconToolButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.preset_button.setObjectName(self._ui_name("PresetButton"))
        self.preset_button.setFixedSize(BUTTON_SIZE_SMALL, BUTTON_SIZE_SMALL)
        self.preset_button.setToolTip("Resolution Presets")
        self.preset_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        preset_icon_path = self._get_icon_path("snapshot_dropdown.svg")
        if preset_icon_path:
            self.preset_button.setIcon(QIcon(preset_icon_path))

        # Create preset menu
        preset_menu = QMenu(self.preset_button)
        preset_menu.setObjectName(self._ui_name("PresetMenu"))
        for preset_label in command.RESOLUTION_PRESETS:
            preset_menu.addAction(preset_label, lambda checked=False, p=preset_label: self._on_preset_selected(p))
        self.preset_button.setMenu(preset_menu)
        self.preset_button.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        row2_layout.addWidget(self.preset_button)

        # Set button
        self.set_button = IconButton(style_mode=IconButtonStyle.TRANSPARENT, auto_size=False)
        self.set_button.setObjectName(self._ui_name("SetButton"))
        self.set_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.set_button.setToolTip("Apply Resolution")
        set_icon_path = self._get_icon_path("snapshot_set.svg")
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
            icon_path = self._get_icon_path("snapshot_rec.svg")
            self.record_button.setToolTip("Start Recording")
        elif state == "stop":
            icon_path = self._get_icon_path("snapshot_stop.svg")
            self.record_button.setToolTip("Stop Recording")
        else:
            # Countdown state
            icon_path = self._get_icon_path(f"snapshot_countdown_{state}.svg")
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

        # PNG only: Edit annotations before save
        if self._current_mode == "png":
            edit_annotations_action = self.option_menu.addAction("Edit Annotations")
            edit_annotations_action.setCheckable(True)
            edit_annotations_action.setChecked(self._get_setting("edit_annotations", False))
            edit_annotations_action.triggered.connect(lambda checked: self._set_setting("edit_annotations", checked))

            self.option_menu.addSeparator()

        # GIF: Loop, FPS submenu, MP4 quality
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

            # MP4 quality submenu (only if FFmpeg available)
            if Mp4ExportHandler.is_available():
                current_quality = self._get_setting("mp4_quality", "medium")
                quality_label = QUALITY_LABELS.get(current_quality, "Medium")
                quality_menu = self.option_menu.addMenu(f"MP4 Quality: {quality_label}")
                for q in QUALITY_OPTIONS:
                    quality_menu.addAction(
                        QUALITY_LABELS[q],
                        lambda checked=False, qv=q: self._set_setting("mp4_quality", qv),
                    )

        # Rec: Loop, FPS, Delay, Trim, Show options, MP4 quality
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

            # MP4 quality submenu (only if FFmpeg available)
            if Mp4ExportHandler.is_available():
                current_quality = self._get_setting("mp4_quality", "medium")
                quality_label = QUALITY_LABELS.get(current_quality, "Medium")
                quality_menu = self.option_menu.addMenu(f"MP4 Quality: {quality_label}")
                for q in QUALITY_OPTIONS:
                    quality_menu.addAction(
                        QUALITY_LABELS[q],
                        lambda checked=False, qv=q: self._set_setting("mp4_quality", qv),
                    )

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

        # Use cached pane_widget if valid, otherwise try to re-wrap
        pane_widget = None
        cached_pane = self.pane_widget
        if cached_pane is not None:
            if hasattr(shiboken, "isValid") and shiboken.isValid(cached_pane):
                pane_widget = cached_pane
            else:
                self.pane_widget = None  # Clear invalid reference

        if not pane_widget and self.pane_layout_name:
            try:
                # Use findLayout instead of findControl for paneLayout
                pane_widget = qt_widget_from_maya_layout(self.pane_layout_name)
                if pane_widget and hasattr(shiboken, "isValid") and not shiboken.isValid(pane_widget):
                    pane_widget = None
                else:
                    self.pane_widget = pane_widget  # Update cache
            except Exception:
                pane_widget = None

        if pane_widget is None:
            logger.warning("pane_widget is None - using fallback overhead values for window sizing")

        # Reset fixed size to allow resizing
        self.setMinimumSize(QSize(0, 0))
        self.setMaximumSize(QSize(16777215, 16777215))

        # Get M3dView and wrap as QWidget
        viewport = None
        try:
            view = omui.M3dView.getM3dViewFromModelPanel(self.panel_name)
            if not view:
                logger.warning("Failed to get M3dView from model panel.")
                return

            raw_widget = shiboken.wrapInstance(int(view.widget()), QWidget)
            if hasattr(shiboken, "isValid") and not shiboken.isValid(raw_widget):
                logger.warning("Viewport widget invalidated before resize.")
            else:
                viewport = raw_widget
                prev_size = viewport.size()
                viewport.setFixedSize(width, height)
        except Exception as e:
            logger.warning(f"Failed to set viewport size: {e}")
            return

        # Size the paneLayout wrapper (includes menuBar overhead)
        # Base overhead values (at 100% DPI): width=4 (border), height=26 (menuBar)
        dpi_scale = viewport.devicePixelRatioF() if viewport and hasattr(viewport, "devicePixelRatioF") else 1.0
        overhead_width = int(4 * dpi_scale)
        overhead_height = int(26 * dpi_scale)

        if pane_widget and viewport:
            try:
                prev_pane_size = pane_widget.size()
                # Calculate overhead from actual pane size if available
                calculated_w = max(0, prev_pane_size.width() - prev_size.width())
                calculated_h = max(0, prev_pane_size.height() - prev_size.height())
                if calculated_w > 0 or calculated_h > 0:
                    overhead_width = calculated_w
                    overhead_height = calculated_h
                pane_widget.setFixedSize(width + overhead_width, height + overhead_height)
                pane_widget.updateGeometry()
            except Exception as e:
                logger.warning(f"Failed to size pane widget: {e}")

        # Update input fields
        if self.width_edit:
            self.width_edit.setText(str(width))
        if self.height_edit:
            self.height_edit.setText(str(height))

        # Fit window to content after Qt processes the deferred viewport resize
        def _lock_window_size():
            try:
                # Drop invalidated widgets before querying sizes
                nonlocal pane_widget
                if pane_widget and hasattr(shiboken, "isValid") and not shiboken.isValid(pane_widget):
                    pane_widget = None

                QApplication.processEvents()
                # Compute desired window size explicitly
                # Use pane_widget size if available, otherwise use viewport size + overhead
                if pane_widget:
                    pane_w = pane_widget.size().width() or (width + overhead_width)
                    pane_h = pane_widget.size().height() or (height + overhead_height)
                else:
                    pane_w = width + overhead_width
                    pane_h = height + overhead_height

                toolbar_w = self.toolbar_widget.sizeHint().width() if self.toolbar_widget else 0
                toolbar_h = self.toolbar_widget.sizeHint().height() if self.toolbar_widget else 0
                desired_w = max(pane_w, toolbar_w)
                desired_h = pane_h + toolbar_h

                if desired_w > 0 and desired_h > 0:
                    self.resize(desired_w, desired_h)
                    self.setFixedSize(desired_w, desired_h)
                else:
                    if self.layout():
                        self.layout().invalidate()
                        self.layout().activate()
                    self.adjustSize()
                    self.resize(self.sizeHint())
                    self.setFixedSize(self.size())
            except Exception as e:
                logger.warning(f"Failed during window lock: {e}")

        QTimer.singleShot(0, _lock_window_size)

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
            cmds.inViewMessage(amg="Copied to clipboard!", pos="midCenter", fade=True)
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
        edit_annotations = self._get_setting("edit_annotations", False)

        try:
            cmds.waitCursor(state=True)

            # Capture image first
            image = command.capture_frame(self.panel_name, width, height)
            cmds.waitCursor(state=False)

            # Show annotation editor if enabled
            annotations = None
            if edit_annotations:
                annotations = show_annotation_editor(image, self, background_color)
                if annotations is None:
                    # User cancelled annotation editor
                    return

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

            cmds.waitCursor(state=True)
            cmds.inViewMessage(amg="Saving...", pos="midCenter", fade=False)

            command.save_png(image, file_path, background_color, annotations=annotations)

            self._update_last_save_dir(file_path)
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="Saved!", pos="midCenter", fade=True)
            logger.info(f"Saved snapshot: {file_path}")
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="", pos="midCenter", fade=True, fadeOutTime=0.0)
            cmds.warning(f"Failed to save PNG: {e}")
            logger.error(f"Failed to save: {e}")

    def _get_animation_file_filter(self) -> str:
        """Build file filter for animation export.

        Returns:
            File filter string with available formats.
        """
        filters = ["GIF Images (*.gif)"]
        if Mp4ExportHandler.is_available():
            filters.append("MP4 Video (*.mp4)")
        return ";;".join(filters)

    def _on_capture_gif(self):
        """Handle GIF/MP4 capture button click."""
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
        quality = self._get_setting("mp4_quality", "medium")

        # Validate frame range
        if start_frame > end_frame:
            cmds.warning("Start frame must be less than or equal to end frame")
            return

        frame_count = end_frame - start_frame + 1
        if frame_count > MAX_GIF_FRAMES:
            cmds.warning(f"Frame range too large (max {MAX_GIF_FRAMES} frames)")
            return

        # Get save path from user (with format selection)
        file_filter = self._get_animation_file_filter()
        file_path = cmds.fileDialog2(
            fileFilter=file_filter,
            dialogStyle=2,
            fileMode=0,
            caption="Save Animation",
            startingDirectory=self._get_save_directory(),
        )

        if not file_path:
            return

        file_path = file_path[0]

        # Determine format from extension
        is_mp4 = file_path.lower().endswith(".mp4")
        is_gif = file_path.lower().endswith(".gif")

        if not is_mp4 and not is_gif:
            # Default to GIF if no recognized extension
            file_path += ".gif"
            is_gif = True

        try:
            cmds.waitCursor(state=True)
            logger.debug(f"Capturing {frame_count} frames...")

            images = command.capture_frame_range(self.panel_name, start_frame, end_frame, width, height)

            cmds.inViewMessage(amg="Saving...", pos="midCenter", fade=False)

            if is_mp4:
                command.save_mp4(images, file_path, fps, background_color, loop=loop, quality=quality)
                logger.info(f"Saved MP4: {file_path}")
            else:
                command.save_gif(images, file_path, fps, background_color, loop=loop)
                logger.info(f"Saved GIF: {file_path}")

            self._update_last_save_dir(file_path)
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="Saved!", pos="midCenter", fade=True)
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="", pos="midCenter", fade=True, fadeOutTime=0.0)
            cmds.warning(f"Failed to save: {e}")
            logger.error(f"Failed to save: {e}")

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
        cmds.inViewMessage(amg="Cancelled", pos="midCenter", fade=True)

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
        quality = self._get_setting("mp4_quality", "medium")
        background_color = self._get_background_color()

        # Get save path from user (with format selection)
        file_filter = self._get_animation_file_filter()
        file_path = cmds.fileDialog2(
            fileFilter=file_filter,
            dialogStyle=2,
            fileMode=0,
            caption="Save Recording",
            startingDirectory=self._get_save_directory(),
        )

        if not file_path:
            return

        file_path = file_path[0]

        # Determine format from extension
        is_mp4 = file_path.lower().endswith(".mp4")
        is_gif = file_path.lower().endswith(".gif")

        if not is_mp4 and not is_gif:
            # Default to GIF if no recognized extension
            file_path += ".gif"
            is_gif = True

        # Save animation
        try:
            cmds.waitCursor(state=True)
            cmds.inViewMessage(amg="Saving...", pos="midCenter", fade=False)

            if is_mp4:
                command.save_mp4(frames, file_path, fps, background_color, loop=loop, quality=quality)
                logger.info(f"Saved recorded MP4: {file_path}")
            else:
                command.save_gif(frames, file_path, fps, background_color, loop=loop)
                logger.info(f"Saved recorded GIF: {file_path}")

            self._update_last_save_dir(file_path)
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="Saved!", pos="midCenter", fade=True)
        except Exception as e:
            cmds.waitCursor(state=False)
            cmds.inViewMessage(amg="", pos="midCenter", fade=True, fadeOutTime=0.0)
            cmds.warning(f"Failed to save: {e}")
            logger.error(f"Failed to save: {e}")

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
        SnapshotCaptureWindow: The window instance, or None if PIL is not available.
    """
    global _instance

    # Check PIL availability
    if not PIL_AVAILABLE:
        cmds.error("Snapshot Capture requires PIL (Pillow) library. Please install it or use Maya 2022+.")
        return None

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
    width = _instance._settings_cache.get("width", command.DEFAULT_WIDTH)
    height = _instance._settings_cache.get("height", command.DEFAULT_HEIGHT)

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
