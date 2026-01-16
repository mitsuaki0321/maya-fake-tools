"""Snapshot Capture UI - Maya native window implementation."""

from __future__ import annotations

import logging
import os

import maya.cmds as cmds

from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QApplication, QColor, QColorDialog, QTimer
from . import command
from .input_monitor import InputMonitor
from .input_overlay import draw_click_indicators, draw_cursor, draw_key_overlay
from .screen_capture import capture_screen_region, get_cursor_screen_position, get_widget_screen_bbox

logger = logging.getLogger(__name__)

# Settings for persistence
_settings = ToolOptionSettings("snapshot_capture")

_window_name = "snapshotCaptureWindow"
_panel_name = None
_pane_layout = None

# Recording state
_is_recording = False
_recorded_frames = []
_record_timer = None
_countdown_timer = None
_countdown_value = 0

# Screen capture state
_input_monitor: InputMonitor | None = None
_capture_bbox: tuple[int, int, int, int] | None = None
_show_cursor: bool = True
_show_clicks: bool = True
_show_keys: bool = False

# Current mode: "png", "gif", "rec"
_current_mode: str = "png"

# Background color state
_bg_color: tuple[int, int, int] = (128, 128, 128)  # Default gray
_bg_transparent: bool = False  # Whether to use transparent background


def _get_icon_path(icon_name: str) -> str | None:
    """Get icon path from module's icons folder.

    Args:
        icon_name: Icon filename (e.g., "snapshot_save.png").

    Returns:
        Full path to icon if exists, None otherwise.
    """
    module_dir = os.path.dirname(__file__)
    icon_path = os.path.join(module_dir, "icons", icon_name)
    return icon_path if os.path.exists(icon_path) else None


def _create_icon_button(
    name: str,
    icon_name: str,
    fallback_label: str,
    width: int = 24,
    command=None,
    annotation: str | None = None,
    bg_color: list | None = None,
) -> str:
    """Create icon button with text fallback.

    Args:
        name: Button name for Maya.
        icon_name: Icon filename.
        fallback_label: Text label if icon not found.
        width: Button width.
        command: Button command callback.
        annotation: Tooltip text.
        bg_color: Background color [r, g, b] (0-1 range).

    Returns:
        Created button name.
    """
    icon_path = _get_icon_path(icon_name)
    tooltip = annotation or fallback_label

    if icon_path:
        btn = cmds.iconTextButton(
            name,
            style="iconOnly",
            image=icon_path,
            width=width,
            height=20,
            command=command,
            annotation=tooltip,
        )
        if bg_color:
            cmds.iconTextButton(btn, edit=True, backgroundColor=bg_color)
        return btn
    else:
        # Fallback to text button
        btn = cmds.button(
            name,
            label=fallback_label,
            width=max(width, 30),
            height=20,
            command=command,
            annotation=tooltip,
        )
        if bg_color:
            cmds.button(btn, edit=True, backgroundColor=bg_color)
        return btn


def _load_settings() -> dict:
    """Load saved settings from optionVar.

    Returns:
        Dictionary of settings for UI initialization.
    """
    global _bg_color, _bg_transparent, _current_mode

    # Load mode
    _current_mode = _settings.read("mode", "png")

    # Load background color
    saved_bg = _settings.read("bg_color")
    if saved_bg is not None and isinstance(saved_bg, list) and len(saved_bg) == 3:
        _bg_color = tuple(saved_bg)

    # Load transparent setting
    _bg_transparent = _settings.read("bg_transparent", False)

    # Return all settings for UI initialization
    return {
        "mode": _current_mode,
        "width": _settings.read("width", 640),
        "height": _settings.read("height", 360),
        "fps": _settings.read("fps", 24),
        "loop": _settings.read("loop", True),
        "delay": _settings.read("delay", 3),
        "trim": _settings.read("trim", 0),
        "show_cursor": _settings.read("show_cursor", True),
        "show_clicks": _settings.read("show_clicks", True),
        "show_keys": _settings.read("show_keys", False),
    }


def show_ui():
    """Show the Snapshot Capture window."""
    global _panel_name, _pane_layout

    # Load saved settings
    saved = _load_settings()

    # Close existing window
    if cmds.window(_window_name, exists=True):
        cmds.deleteUI(_window_name)

    # Get initial resolution from saved settings
    init_width = saved["width"]
    init_height = saved["height"]

    # Create Maya window (non-resizable)
    # Initial size will be set after showing
    cmds.window(
        _window_name,
        title="Snapshot Capture",
        sizeable=False,
    )

    # Main layout (adjustableColumn=True to allow toolbar to stretch)
    main_layout = cmds.columnLayout(adjustableColumn=True)

    # === Viewport area ===
    # Panel menu bar height: ~45px
    panel_menubar_height = 45

    # Viewport container for centering (formLayout allows precise positioning)
    viewport_container = cmds.formLayout("snapshotCaptureViewportContainer")

    # paneLayout needs extra height for panel menu bar
    _pane_layout = cmds.paneLayout(configuration="single", width=init_width, height=init_height + panel_menubar_height)
    _panel_name = cmds.modelPanel(menuBarVisible=True)

    # Add Camera menu to panel's menu bar
    _create_camera_menu(_panel_name)

    # Configure editor
    cmds.modelEditor(
        _panel_name,
        edit=True,
        displayAppearance="smoothShaded",
        headsUpDisplay=False,
        grid=True,
    )

    cmds.setParent(viewport_container)

    # Attach paneLayout to top, leave sides free for centering
    cmds.formLayout(
        viewport_container,
        edit=True,
        attachForm=[(_pane_layout, "top", 0)],
    )

    cmds.setParent(main_layout)

    # === Toolbar ===
    _create_toolbar(main_layout, saved)

    cmds.showWindow(_window_name)

    # Force window to target size after showing
    # First, measure actual chrome by comparing window and editor sizes
    from ....lib_ui.maya_qt import qt_widget_from_maya_control

    model_editor = cmds.modelPanel(_panel_name, query=True, modelEditor=True)
    editor_widget = qt_widget_from_maya_control(model_editor)

    if editor_widget:
        current_editor_width = editor_widget.width()
        current_editor_height = editor_widget.height()
        current_window_width = cmds.window(_window_name, query=True, width=True)
        current_window_height = cmds.window(_window_name, query=True, height=True)

        chrome_width = current_window_width - current_editor_width
        chrome_height = current_window_height - current_editor_height

        # Resize window to target editor size + chrome
        window_width = init_width + chrome_width
        window_height = init_height + chrome_height
        cmds.window(
            _window_name,
            edit=True,
            widthHeight=(window_width, window_height),
        )

    # Apply initial mode visibility
    _update_toolbar_for_mode(_current_mode)

    logger.info(f"Created window with panel: {_panel_name}")

    return _panel_name


def _create_toolbar(parent_layout, saved: dict):
    """Create 2-row toolbar below viewport.

    Row 1: Mode selector + [BG]* + Option + action buttons (right-aligned)
           * BG is only visible for PNG/GIF modes
    Row 2: Resolution fields (right-aligned)

    Uses visibility toggling for mode switching (no tabLayout).

    Args:
        parent_layout: Parent layout to attach toolbar.
        saved: Dictionary of saved settings.
    """
    # Main toolbar container (2 rows)
    toolbar_form = cmds.formLayout("snapshotCaptureToolbar")

    # ========== Row 1: Mode + BG + Option + actions ==========
    row1_form = cmds.formLayout("snapshotCaptureRow1", height=24)

    # Mode selector (left-most)
    mode_menu = cmds.optionMenu(
        "snapshotCaptureModeMenu",
        changeCommand=_on_mode_changed,
        width=55,
    )
    cmds.menuItem(label="PNG", parent=mode_menu)
    cmds.menuItem(label="GIF", parent=mode_menu)
    cmds.menuItem(label="Rec", parent=mode_menu)
    mode_label_map = {"png": "PNG", "gif": "GIF", "rec": "Rec"}
    cmds.optionMenu(mode_menu, edit=True, value=mode_label_map.get(saved["mode"], "PNG"))

    bg_button_color = _get_bg_button_color()

    # BG button (PNG/GIF only - visibility controlled by mode)
    bg_btn = cmds.button(
        "snapshotCaptureBGButton",
        label="",
        width=24,
        height=20,
        backgroundColor=bg_button_color,
        command=_on_bg_color_button,
        annotation="Background Color",
    )

    # Option button (always visible)
    option_btn = cmds.iconTextButton(
        "snapshotCaptureOptionButton",
        style="iconOnly",
        image="advancedSettings.png",
        width=20,
        height=20,
        annotation="Options",
    )
    cmds.popupMenu(parent=option_btn, button=1, postMenuCommand=_populate_option_menu)

    # Save button (PNG/GIF only)
    save_btn = _create_icon_button(
        "snapshotCaptureSaveButton",
        "snapshot_save.png",
        "Save",
        width=24,
        command=_on_save_button,
        annotation="Save",
    )

    # Copy button (PNG only)
    copy_btn = _create_icon_button(
        "snapshotCaptureCopyButton",
        "snapshot_copy.png",
        "Copy",
        width=24,
        command=_on_copy_png_to_clipboard,
        annotation="Copy to Clipboard",
    )

    # Record button (Rec only) - icon only, state indicated by icon change
    rec_icon = _get_icon_path("snapshot_rec.png")
    rec_btn = cmds.iconTextButton(
        "snapshotCaptureRecordButton",
        style="iconOnly" if rec_icon else "textOnly",
        image=rec_icon if rec_icon else "",
        label="Rec",
        width=20,
        height=20,
        command=_on_record_toggle,
        annotation="Start Recording",
    )

    # Attach elements to right edge with formLayout
    # Layout: [Mode] ... [BG] [Option] [action buttons]
    # Action buttons: PNG=[Save][Copy], GIF=[Save], Rec=[Rec]
    cmds.formLayout(
        row1_form,
        edit=True,
        attachForm=[
            (mode_menu, "left", 2),
            (mode_menu, "top", 2),
            (mode_menu, "bottom", 2),
            (copy_btn, "right", 2),
            (copy_btn, "top", 2),
            (save_btn, "top", 2),
            (rec_btn, "right", 2),
            (rec_btn, "top", 2),
            (option_btn, "top", 2),
            (bg_btn, "top", 2),
        ],
        attachControl=[
            (save_btn, "right", 4, copy_btn),
            (option_btn, "right", 4, save_btn),
            (bg_btn, "right", 4, option_btn),
        ],
        attachNone=[
            (copy_btn, "left"),
            (save_btn, "left"),
            (rec_btn, "left"),
            (option_btn, "left"),
            (bg_btn, "left"),
        ],
    )
    cmds.setParent(toolbar_form)

    # ========== Row 2: Resolution (right-aligned) ==========
    row2_form = cmds.formLayout("snapshotCaptureRow2", height=24)

    res_row = cmds.rowLayout(
        "snapshotCaptureResRow",
        numberOfColumns=5,
        columnAttach=[
            (1, "left", 0),
            (2, "left", 2),
            (3, "left", 0),
            (4, "left", 2),
            (5, "left", 2),
        ],
    )
    cmds.intField(
        "snapshotCaptureWidthField",
        value=saved["width"],
        width=45,
        changeCommand=lambda v: _settings.write("width", v),
    )
    cmds.text(label="x")
    cmds.intField(
        "snapshotCaptureHeightField",
        value=saved["height"],
        width=45,
        changeCommand=lambda v: _settings.write("height", v),
    )
    cmds.iconTextButton(
        "snapshotCapturePresetButton",
        style="iconOnly",
        image="arrowDown.png",
        width=16,
        height=16,
        annotation="Resolution Presets",
    )
    cmds.popupMenu(parent="snapshotCapturePresetButton", button=1)
    for preset_label in command.RESOLUTION_PRESETS:
        cmds.menuItem(label=preset_label, command=lambda x, p=preset_label: _on_preset_selected(p))

    _create_icon_button(
        "snapshotCaptureSetButton",
        "snapshot_set.png",
        "Set",
        width=24,
        command=_on_set_custom_resolution,
        annotation="Apply Resolution",
    )
    cmds.setParent(row2_form)

    # Attach res_row to right
    cmds.formLayout(
        row2_form,
        edit=True,
        attachForm=[
            (res_row, "right", 2),
            (res_row, "top", 0),
            (res_row, "bottom", 0),
        ],
        attachNone=[(res_row, "left")],
    )
    cmds.setParent(toolbar_form)

    # ========== Attach rows to toolbar ==========
    cmds.formLayout(
        toolbar_form,
        edit=True,
        attachForm=[
            (row1_form, "left", 0),
            (row1_form, "right", 0),
            (row1_form, "top", 0),
            (row2_form, "left", 0),
            (row2_form, "right", 0),
            (row2_form, "bottom", 0),
        ],
        attachControl=[
            (row2_form, "top", 2, row1_form),
        ],
    )

    cmds.setParent(parent_layout)


def _update_toolbar_for_mode(mode: str):
    """Update toolbar visibility based on mode.

    Args:
        mode: Current mode ("png", "gif", "rec").
    """
    # BG button: PNG/GIF only
    bg_visible = mode in ["png", "gif"]
    if cmds.button("snapshotCaptureBGButton", exists=True):
        cmds.button("snapshotCaptureBGButton", edit=True, visible=bg_visible)

    # Save button: PNG/GIF only
    save_visible = mode in ["png", "gif"]
    if cmds.iconTextButton("snapshotCaptureSaveButton", exists=True):
        cmds.iconTextButton("snapshotCaptureSaveButton", edit=True, visible=save_visible)
    elif cmds.button("snapshotCaptureSaveButton", exists=True):
        cmds.button("snapshotCaptureSaveButton", edit=True, visible=save_visible)

    # Copy button: PNG only
    copy_visible = mode == "png"
    if cmds.iconTextButton("snapshotCaptureCopyButton", exists=True):
        cmds.iconTextButton("snapshotCaptureCopyButton", edit=True, visible=copy_visible)
    elif cmds.button("snapshotCaptureCopyButton", exists=True):
        cmds.button("snapshotCaptureCopyButton", edit=True, visible=copy_visible)

    # Record button: Rec only
    rec_visible = mode == "rec"
    if cmds.iconTextButton("snapshotCaptureRecordButton", exists=True):
        cmds.iconTextButton("snapshotCaptureRecordButton", edit=True, visible=rec_visible)

    # Update option button attachment based on mode
    # For PNG/GIF: attach to right of save_btn
    # For Rec: attach to right of rec_btn
    row1_form = "snapshotCaptureRow1"
    option_btn = "snapshotCaptureOptionButton"
    save_btn = "snapshotCaptureSaveButton"
    rec_btn = "snapshotCaptureRecordButton"

    if cmds.formLayout(row1_form, exists=True) and cmds.iconTextButton(option_btn, exists=True):
        if mode == "rec":
            # Attach option to the left of rec button
            cmds.formLayout(
                row1_form,
                edit=True,
                attachControl=[(option_btn, "right", 4, rec_btn)],
            )
        else:
            # Attach option to the left of save button
            cmds.formLayout(
                row1_form,
                edit=True,
                attachControl=[(option_btn, "right", 4, save_btn)],
            )


def _populate_option_menu(popup, *args):
    """Populate option menu based on current mode.

    Args:
        popup: Popup menu to populate.
    """
    global _current_mode, _bg_transparent

    # Clear existing items
    cmds.popupMenu(popup, edit=True, deleteAllItems=True)

    # FPS options available
    fps_options = [10, 12, 15, 24, 30, 50, 60]

    # PNG/GIF: Transparent option
    if _current_mode in ["png", "gif"]:
        cmds.menuItem(
            label="Transparent",
            checkBox=_bg_transparent,
            command=_on_transparent_menu_changed,
            parent=popup,
        )
        cmds.menuItem(divider=True, parent=popup)

    # GIF: Loop, FPS submenu
    if _current_mode == "gif":
        loop_val = _settings.read("loop", True)
        cmds.menuItem(
            label="Loop",
            checkBox=loop_val,
            command=_on_loop_menu_changed,
            parent=popup,
        )

        # FPS submenu for GIF
        current_fps = _settings.read("fps", 24)
        fps_menu = cmds.menuItem(
            label=f"FPS: {current_fps}",
            subMenu=True,
            parent=popup,
        )
        for fps in fps_options:
            cmds.menuItem(
                label=str(fps),
                command=lambda x, f=fps: _on_fps_selected(f),
                parent=fps_menu,
            )
        cmds.setParent(popup, menu=True)

    # Rec: FPS, Delay, Trim, Show options
    elif _current_mode == "rec":
        # FPS submenu
        current_fps = _settings.read("fps", 24)
        fps_menu = cmds.menuItem(
            label=f"FPS: {current_fps}",
            subMenu=True,
            parent=popup,
        )
        for fps in fps_options:
            cmds.menuItem(
                label=str(fps),
                command=lambda x, f=fps: _on_fps_selected(f),
                parent=fps_menu,
            )
        cmds.setParent(popup, menu=True)

        # Delay submenu
        delay_val = _settings.read("delay", 3)
        delay_menu = cmds.menuItem(
            label=f"Delay: {delay_val}s",
            subMenu=True,
            parent=popup,
        )
        for d in [0, 1, 2, 3]:
            cmds.menuItem(
                label=f"{d} sec",
                command=lambda x, dv=d: _on_delay_selected(dv),
                parent=delay_menu,
            )
        cmds.setParent(popup, menu=True)

        # Trim submenu
        trim_val = _settings.read("trim", 0)
        trim_menu = cmds.menuItem(
            label=f"Trim: {trim_val}s",
            subMenu=True,
            parent=popup,
        )
        for t in [0, 1, 2, 3]:
            cmds.menuItem(
                label=f"{t} sec",
                command=lambda x, tv=t: _on_trim_selected(tv),
                parent=trim_menu,
            )
        cmds.setParent(popup, menu=True)

        cmds.menuItem(divider=True, parent=popup)

        # Show options
        show_cursor = _settings.read("show_cursor", True)
        show_clicks = _settings.read("show_clicks", True)
        show_keys = _settings.read("show_keys", False)

        cmds.menuItem(
            label="Show Cursor",
            checkBox=show_cursor,
            command=lambda v: _settings.write("show_cursor", v),
            parent=popup,
        )
        cmds.menuItem(
            label="Show Clicks",
            checkBox=show_clicks,
            command=lambda v: _settings.write("show_clicks", v),
            parent=popup,
        )
        cmds.menuItem(
            label="Show Keys",
            checkBox=show_keys,
            command=lambda v: _settings.write("show_keys", v),
            parent=popup,
        )


def _on_fps_selected(fps_value):
    """Handle FPS value selection from menu."""
    _settings.write("fps", fps_value)
    logger.debug(f"FPS set to: {fps_value}")


def _on_delay_selected(delay_value):
    """Handle delay value selection from menu."""
    _settings.write("delay", delay_value)
    logger.debug(f"Delay set to: {delay_value}")


def _on_mode_changed(mode_label):
    """Handle mode selector change.

    Args:
        mode_label: Selected mode label ("PNG", "GIF", "Rec").
    """
    global _current_mode

    mode_map = {"PNG": "png", "GIF": "gif", "Rec": "rec"}
    _current_mode = mode_map.get(mode_label, "png")

    # Save mode
    _settings.write("mode", _current_mode)

    # Update toolbar visibility
    _update_toolbar_for_mode(_current_mode)

    logger.debug(f"Mode changed to: {_current_mode}")


def _on_preset_selected(preset_label):
    """Handle resolution preset selection.

    Args:
        preset_label: Selected preset label.
    """
    if preset_label in command.RESOLUTION_PRESETS:
        width, height = command.RESOLUTION_PRESETS[preset_label]
        _set_viewport_size(width, height)
        # Save to settings
        _settings.write("width", width)
        _settings.write("height", height)
        logger.info(f"Selected preset: {preset_label}")


def _on_transparent_menu_changed(value):
    """Handle transparent menu item change."""
    global _bg_transparent
    _bg_transparent = value
    _settings.write("bg_transparent", _bg_transparent)
    logger.debug(f"Transparent set to: {_bg_transparent}")


def _on_loop_menu_changed(value):
    """Handle loop menu item change."""
    _settings.write("loop", value)
    logger.debug(f"Loop set to: {value}")


def _on_trim_selected(trim_value):
    """Handle trim value selection."""
    _settings.write("trim", trim_value)
    logger.debug(f"Trim set to: {trim_value}")


def _on_save_button(*args):
    """Handle Save button click - routes to PNG or GIF based on mode."""
    global _current_mode

    if _current_mode == "png":
        _on_capture_png()
    elif _current_mode == "gif":
        _on_capture_gif()


def _create_camera_menu(panel_name):
    """Create Camera menu in panel's menu bar.

    Args:
        panel_name: Model panel name.
    """
    menu_name = panel_name + "CameraMenu"

    # Delete existing menu if present
    if cmds.menu(menu_name, exists=True):
        cmds.deleteUI(menu_name)

    # Create Camera menu in panel's menu bar
    cmds.menu(menu_name, label="Camera", parent=panel_name)

    # Add camera items
    cameras = cmds.ls(type="camera")
    for cam in cameras:
        parent = cmds.listRelatives(cam, parent=True)
        if parent:
            cam_name = parent[0]
            cmds.menuItem(
                label=cam_name,
                command=lambda x, c=cam_name: _on_camera_changed(c),
                parent=menu_name,
            )


def _on_camera_changed(camera):
    """Handle camera selection change."""
    global _panel_name
    if _panel_name and cmds.modelPanel(_panel_name, exists=True):
        cmds.modelPanel(_panel_name, edit=True, camera=camera)
        logger.info(f"Changed camera to: {camera}")


def _on_set_custom_resolution(*args):
    """Handle custom resolution set button."""
    width = cmds.intField("snapshotCaptureWidthField", query=True, value=True)
    height = cmds.intField("snapshotCaptureHeightField", query=True, value=True)

    # Validate
    if width < 64 or height < 64:
        cmds.warning("Minimum resolution is 64x64")
        return
    if width > 4096 or height > 4096:
        cmds.warning("Maximum resolution is 4096x4096")
        return

    _set_viewport_size(width, height)

    # Save to settings
    _settings.write("width", width)
    _settings.write("height", height)

    logger.info(f"Set custom resolution: {width}x{height}")


def _set_viewport_size(width: int, height: int):
    """Set viewport size.

    Args:
        width: Target viewport content width (modelEditor area).
        height: Target viewport content height (modelEditor area).
    """
    global _pane_layout, _panel_name

    if not _pane_layout or not cmds.paneLayout(_pane_layout, exists=True):
        return

    if not _panel_name or not cmds.modelPanel(_panel_name, exists=True):
        return

    # Get Qt widget for accurate size measurement
    from ....lib_ui.maya_qt import qt_widget_from_maya_control

    model_editor = cmds.modelPanel(_panel_name, query=True, modelEditor=True)
    editor_widget = qt_widget_from_maya_control(model_editor)

    if not editor_widget:
        logger.warning("Could not get Qt widget for viewport size adjustment")
        return

    # Get current sizes for chrome calculation
    current_editor_width = editor_widget.width()
    current_editor_height = editor_widget.height()
    current_window_width = cmds.window(_window_name, query=True, width=True)
    current_window_height = cmds.window(_window_name, query=True, height=True)

    # Calculate the difference between window size and editor size (UI chrome)
    chrome_width = current_window_width - current_editor_width
    chrome_height = current_window_height - current_editor_height

    # Calculate new window size
    # Row 2 minimum: Width(45) + x + Height(45) + Preset(16) + Set(24) + margins
    toolbar_min_width = 200
    new_window_width = max(width + chrome_width, toolbar_min_width)
    new_window_height = height + chrome_height

    # paneLayout height needs panel menu bar space (~45px)
    panel_menubar_height = 45
    pane_width = new_window_width
    pane_height = height + panel_menubar_height

    # Resize window
    if cmds.window(_window_name, exists=True):
        cmds.window(_window_name, edit=True, widthHeight=(new_window_width, new_window_height))

    # Update pane layout
    cmds.paneLayout(_pane_layout, edit=True, width=pane_width, height=pane_height)

    # Update viewport container
    viewport_container = "snapshotCaptureViewportContainer"
    if cmds.formLayout(viewport_container, exists=True):
        cmds.formLayout(viewport_container, edit=True, width=pane_width, height=pane_height)
        cmds.formLayout(
            viewport_container,
            edit=True,
            attachForm=[(_pane_layout, "top", 0), (_pane_layout, "left", 0), (_pane_layout, "right", 0), (_pane_layout, "bottom", 0)],
        )

    # Update size fields to show target size
    cmds.intField("snapshotCaptureWidthField", edit=True, value=width)
    cmds.intField("snapshotCaptureHeightField", edit=True, value=height)


def _get_background_color():
    """Get current background color.

    Returns:
        RGB tuple or None for transparent.
    """
    global _bg_color, _bg_transparent

    if _bg_transparent:
        return None

    return _bg_color


def _get_bg_button_color():
    """Get background color for the BG button display.

    Returns:
        List of RGB values normalized to 0-1 for Maya button.
    """
    global _bg_color
    return [c / 255.0 for c in _bg_color]


def _on_bg_color_button(*args):
    """Handle background color button click - open color picker."""
    global _bg_color

    # Get current color for dialog
    initial_color = QColor(_bg_color[0], _bg_color[1], _bg_color[2])

    # Open color dialog
    color = QColorDialog.getColor(initial_color, None, "Select Background Color")

    if color.isValid():
        _bg_color = (color.red(), color.green(), color.blue())

        # Update BG button
        button_color = [c / 255.0 for c in _bg_color]
        if cmds.button("snapshotCaptureBGButton", exists=True):
            cmds.button("snapshotCaptureBGButton", edit=True, backgroundColor=button_color)

        # Save to settings
        _settings.write("bg_color", list(_bg_color))
        logger.debug(f"Background color set to: {_bg_color}")


def _on_copy_png_to_clipboard(*args):
    """Handle PNG copy to clipboard button click."""
    global _panel_name
    if not _panel_name or not cmds.modelPanel(_panel_name, exists=True):
        cmds.warning("No panel available for capture")
        return

    # Get resolution from size fields
    width = cmds.intField("snapshotCaptureWidthField", query=True, value=True)
    height = cmds.intField("snapshotCaptureHeightField", query=True, value=True)

    # Get background color
    background_color = _get_background_color()

    try:
        cmds.waitCursor(state=True)

        # Capture frame
        image = command.capture_frame(_panel_name, width, height)
        image = command.composite_with_background(image, background_color)

        # Convert to QImage and copy to clipboard
        from io import BytesIO

        from ....lib_ui.qt_compat import QImage, QPixmap

        # Save to bytes buffer
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        # Load as QImage
        qimage = QImage()
        qimage.loadFromData(buffer.read())

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(QPixmap.fromImage(qimage))

        cmds.waitCursor(state=False)
        cmds.inViewMessage(message="Copied to clipboard!", pos="midCenter", fade=True)
        logger.info("PNG copied to clipboard")
    except Exception as e:
        cmds.waitCursor(state=False)
        cmds.warning(f"Failed to copy to clipboard: {e}")
        logger.error(f"Failed to copy to clipboard: {e}")


def _on_capture_png(*args):
    """Handle PNG capture button click."""
    global _panel_name
    if not _panel_name or not cmds.modelPanel(_panel_name, exists=True):
        cmds.warning("No panel available for capture")
        return

    # Get resolution from size fields
    width = cmds.intField("snapshotCaptureWidthField", query=True, value=True)
    height = cmds.intField("snapshotCaptureHeightField", query=True, value=True)

    # Get background color
    background_color = _get_background_color()

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

    # Capture and save
    try:
        cmds.waitCursor(state=True)
        cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

        image = command.capture_frame(_panel_name, width, height)
        command.save_png(image, file_path, background_color)

        cmds.waitCursor(state=False)
        cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
        logger.info(f"Saved snapshot: {file_path}")
    except Exception as e:
        cmds.waitCursor(state=False)
        cmds.inViewMessage(clear="midCenter")
        cmds.warning(f"Failed to save PNG: {e}")
        logger.error(f"Failed to save: {e}")


def _on_capture_gif(*args):
    """Handle GIF capture button click."""
    global _panel_name
    if not _panel_name or not cmds.modelPanel(_panel_name, exists=True):
        cmds.warning("No panel available for capture")
        return

    # Get resolution from size fields
    width = cmds.intField("snapshotCaptureWidthField", query=True, value=True)
    height = cmds.intField("snapshotCaptureHeightField", query=True, value=True)

    # Get GIF settings - use Maya timeline for frame range
    start_frame = int(cmds.playbackOptions(query=True, minTime=True))
    end_frame = int(cmds.playbackOptions(query=True, maxTime=True))
    fps = _settings.read("fps", 24)  # Read from settings (Option menu)
    loop = _settings.read("loop", True)  # Read from settings (Option menu)

    # Get background color
    background_color = _get_background_color()

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

    # Capture and save
    try:
        cmds.waitCursor(state=True)
        cmds.inViewMessage(message="Capturing...", pos="midCenter", fade=False)
        logger.info(f"Capturing {frame_count} frames...")

        images = command.capture_frame_range(_panel_name, start_frame, end_frame, width, height)

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


def _on_record_toggle(*args):
    """Toggle recording state."""
    global _is_recording, _countdown_timer, _countdown_value

    # Check if we're in countdown phase
    if _countdown_timer is not None:
        # Cancel countdown
        _countdown_timer.stop()
        _countdown_timer.deleteLater()
        _countdown_timer = None
        _countdown_value = 0
        # Restore to rec icon
        rec_icon = _get_icon_path("snapshot_rec.png")
        cmds.iconTextButton(
            "snapshotCaptureRecordButton",
            edit=True,
            style="iconOnly" if rec_icon else "textOnly",
            image=rec_icon if rec_icon else "",
            label="Rec",
        )
        cmds.inViewMessage(message="Cancelled", pos="midCenter", fade=True)
        logger.info("Recording countdown cancelled")
        return

    if _is_recording:
        _stop_recording()
    else:
        _start_recording()


def _start_recording():
    """Start recording frames using QTimer (with optional countdown delay)."""
    global _panel_name, _countdown_timer, _countdown_value

    if not _panel_name or not cmds.modelPanel(_panel_name, exists=True):
        cmds.warning("No panel available for recording")
        return

    # Get delay setting from settings (Option menu)
    delay_sec = _settings.read("delay", 3)

    if delay_sec > 0:
        # Start countdown
        _countdown_value = delay_sec

        # Use countdown icon
        countdown_icon = _get_icon_path(f"snapshot_countdown_{_countdown_value}.png")
        cmds.iconTextButton(
            "snapshotCaptureRecordButton",
            edit=True,
            style="iconOnly" if countdown_icon else "textOnly",
            image=countdown_icon if countdown_icon else "",
            label=str(_countdown_value),
        )

        # Create countdown timer (1 second interval)
        _countdown_timer = QTimer()
        _countdown_timer.timeout.connect(_on_countdown_tick)
        _countdown_timer.start(1000)

        logger.info(f"Recording countdown started: {delay_sec} seconds")
    else:
        # No delay, start recording immediately
        _begin_recording()


def _on_countdown_tick():
    """Handle countdown tick."""
    global _countdown_timer, _countdown_value

    _countdown_value -= 1

    if _countdown_value > 0:
        # Update countdown icon
        countdown_icon = _get_icon_path(f"snapshot_countdown_{_countdown_value}.png")
        cmds.iconTextButton(
            "snapshotCaptureRecordButton",
            edit=True,
            style="iconOnly" if countdown_icon else "textOnly",
            image=countdown_icon if countdown_icon else "",
            label=str(_countdown_value),
        )
    else:
        # Countdown finished, stop countdown timer and start recording
        if _countdown_timer is not None:
            _countdown_timer.stop()
            _countdown_timer.deleteLater()
            _countdown_timer = None

        _begin_recording()


def _begin_recording():
    """Begin actual recording (called after countdown or immediately)."""
    global _is_recording, _recorded_frames, _record_timer, _panel_name
    global _input_monitor, _capture_bbox

    _is_recording = True
    _recorded_frames = []

    # Switch to stop icon
    stop_icon = _get_icon_path("snapshot_stop.png")
    cmds.iconTextButton(
        "snapshotCaptureRecordButton",
        edit=True,
        style="iconOnly" if stop_icon else "textOnly",
        image=stop_icon if stop_icon else "",
        label="Stop",
    )

    # Get overlay settings from settings (Option menu)
    show_cursor = _settings.read("show_cursor", True)
    show_clicks = _settings.read("show_clicks", True)
    show_keys = _settings.read("show_keys", False)

    # Store in module-level for _on_timer_tick
    global _show_cursor, _show_clicks, _show_keys
    _show_cursor = show_cursor
    _show_clicks = show_clicks
    _show_keys = show_keys

    # Get the Qt widget for the modelEditor (viewport only, not menu/toolbar)
    from ....lib_ui.maya_qt import qt_widget_from_maya_control

    # Get the modelEditor name from the panel
    model_editor = cmds.modelPanel(_panel_name, query=True, modelEditor=True)
    editor_widget = qt_widget_from_maya_control(model_editor)

    if editor_widget:
        _capture_bbox = get_widget_screen_bbox(editor_widget)
        logger.debug(f"Capture bbox: {_capture_bbox}")
    else:
        logger.warning("Could not get Qt widget for model editor")
        _capture_bbox = None

    # Start input monitor for cursor/keyboard tracking
    if editor_widget and (_show_cursor or _show_keys):
        _input_monitor = InputMonitor(editor_widget)
        _input_monitor.start()

    # Get FPS for timer interval from settings (Option menu)
    fps = _settings.read("fps", 24)
    interval_ms = int(1000 / fps)

    # Create and start timer
    _record_timer = QTimer()
    _record_timer.timeout.connect(_on_timer_tick)
    _record_timer.start(interval_ms)

    logger.info(f"Recording started at {fps} FPS (interval: {interval_ms}ms)")


def _on_timer_tick():
    """Capture frame on timer tick using screen capture."""
    global _recorded_frames, _capture_bbox, _input_monitor, _show_cursor, _show_clicks, _show_keys

    if not _is_recording:
        return

    if _capture_bbox is None:
        logger.error("No capture bbox available")
        return

    try:
        # Capture screen region
        image = capture_screen_region(_capture_bbox)

        # Draw cursor overlay (required for click indicators)
        if _show_cursor:
            cursor_pos = get_cursor_screen_position()
            image = draw_cursor(image, cursor_pos, _capture_bbox)

            # Draw click indicators (only if both cursor and clicks are enabled)
            if _show_clicks and _input_monitor:
                clicks = _input_monitor.get_recent_clicks()
                if clicks:
                    image = draw_click_indicators(image, clicks, _capture_bbox)

        # Draw keyboard overlay
        if _show_keys and _input_monitor:
            pressed_keys = _input_monitor.get_pressed_keys()
            if pressed_keys:
                image = draw_key_overlay(image, pressed_keys)

        _recorded_frames.append(image)
        logger.debug(f"Captured frame ({len(_recorded_frames)} total)")
    except Exception as e:
        logger.error(f"Failed to capture frame: {e}")


def _stop_recording():
    """Stop recording and save GIF."""
    global _is_recording, _recorded_frames, _record_timer, _input_monitor, _capture_bbox

    _is_recording = False

    # Stop timer
    if _record_timer is not None:
        _record_timer.stop()
        _record_timer.deleteLater()
        _record_timer = None

    # Stop input monitor
    if _input_monitor is not None:
        _input_monitor.stop()
        _input_monitor = None

    # Clear capture state
    _capture_bbox = None

    # Restore to rec icon
    rec_icon = _get_icon_path("snapshot_rec.png")
    cmds.iconTextButton(
        "snapshotCaptureRecordButton",
        edit=True,
        style="iconOnly" if rec_icon else "textOnly",
        image=rec_icon if rec_icon else "",
        label="Rec",
    )

    # Check if we have frames
    if not _recorded_frames:
        cmds.warning("No frames recorded")
        return

    original_count = len(_recorded_frames)
    logger.info(f"Recording stopped - {original_count} frames captured")

    # Apply end trim (read from settings - Option menu)
    trim_sec = _settings.read("trim", 0)
    if trim_sec > 0:
        fps = _settings.read("fps", 24)
        frames_to_trim = int(trim_sec * fps)
        if frames_to_trim > 0 and frames_to_trim < len(_recorded_frames):
            _recorded_frames = _recorded_frames[:-frames_to_trim]
            logger.info(f"Trimmed {frames_to_trim} frames from end ({trim_sec} seconds)")

    frame_count = len(_recorded_frames)
    if frame_count == 0:
        cmds.warning("All frames trimmed - nothing to save")
        _recorded_frames = []
        return

    logger.info(f"Final frame count: {frame_count} (trimmed {original_count - frame_count})")

    # Get settings (read from settings - Option menu)
    fps = _settings.read("fps", 24)
    # Note: No background_color for Rec mode - screen captures are already RGB

    # Get save path from user
    file_path = cmds.fileDialog2(
        fileFilter="GIF Images (*.gif)",
        dialogStyle=2,
        fileMode=0,
        caption="Save Recorded GIF",
    )

    if not file_path:
        _recorded_frames = []
        return

    file_path = file_path[0]
    if not file_path.lower().endswith(".gif"):
        file_path += ".gif"

    # Save GIF (no background color - screen captures are RGB)
    try:
        cmds.waitCursor(state=True)
        cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

        command.save_gif(_recorded_frames, file_path, fps)

        cmds.waitCursor(state=False)
        cmds.inViewMessage(message="Saved!", pos="midCenter", fade=True)
        logger.info(f"Saved recorded GIF: {file_path}")
    except Exception as e:
        cmds.waitCursor(state=False)
        cmds.inViewMessage(clear="midCenter")
        cmds.warning(f"Failed to save GIF: {e}")
        logger.error(f"Failed to save GIF: {e}")
    finally:
        _recorded_frames = []


def get_panel_name():
    """Get the current panel name for capture."""
    return _panel_name


__all__ = ["show_ui", "get_panel_name"]
