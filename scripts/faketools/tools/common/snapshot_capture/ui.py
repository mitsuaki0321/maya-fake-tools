"""Snapshot Capture UI - Maya native window implementation."""

from __future__ import annotations

import logging

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
_show_cursor = True
_show_clicks = True
_show_keys = False

# Background color state
_bg_color: tuple[int, int, int] = (128, 128, 128)  # Default gray
_bg_transparent: bool = False  # Whether to use transparent background


def _load_settings():
    """Load saved settings from optionVar."""
    global _bg_color, _bg_transparent

    # Load background color
    saved_bg = _settings.read("bg_color")
    if saved_bg is not None and isinstance(saved_bg, list) and len(saved_bg) == 3:
        _bg_color = tuple(saved_bg)

    # Load transparent setting
    _bg_transparent = _settings.read("bg_transparent", False)

    logger.debug(f"Loaded settings: bg_color={_bg_color}, bg_transparent={_bg_transparent}")


def _save_settings():
    """Save current settings to optionVar."""
    global _bg_color, _bg_transparent

    # Save background color
    _settings.write("bg_color", list(_bg_color))

    # Save transparent setting
    _settings.write("bg_transparent", _bg_transparent)

    logger.debug("Settings saved")


def show_ui():
    """Show the Snapshot Capture window."""
    global _panel_name, _pane_layout, _bg_color

    # Load saved settings
    _load_settings()

    # Close existing window
    if cmds.window(_window_name, exists=True):
        cmds.deleteUI(_window_name)

    # Create Maya window (non-resizable)
    cmds.window(_window_name, title="Snapshot Capture", sizeable=False)

    # Main layout
    main_layout = cmds.columnLayout(adjustableColumn=False)

    # === Viewport area ===
    # Get initial resolution from default preset
    init_width, init_height = command.RESOLUTION_PRESETS[command.DEFAULT_RESOLUTION]

    # Viewport container for centering (formLayout allows precise positioning)
    viewport_container = cmds.formLayout("snapshotCaptureViewportContainer")

    _pane_layout = cmds.paneLayout(configuration="single", width=init_width, height=init_height)
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
    _create_toolbar(main_layout, init_width, init_height)

    cmds.showWindow(_window_name)

    # Set initial window size to match viewport
    _set_viewport_size(init_width, init_height)

    logger.info(f"Created window with panel: {_panel_name}")

    return _panel_name


def _create_toolbar(parent_layout, init_width, init_height):
    """Create toolbar below viewport.

    Args:
        parent_layout: Parent layout to attach toolbar.
        init_width: Initial width value.
        init_height: Initial height value.
    """
    # Toolbar frame
    cmds.frameLayout(
        "snapshotCaptureToolbar",
        label="",
        labelVisible=False,
        borderVisible=False,
        marginWidth=2,
        marginHeight=2,
    )

    toolbar_column = cmds.columnLayout(adjustableColumn=True)

    # === Row 1: Resolution + Capture buttons ===
    cmds.rowLayout(
        numberOfColumns=11,
        adjustableColumn=1,
        columnAttach=[
            (1, "left", 0),
            (2, "left", 2),
            (3, "left", 2),
            (4, "left", 2),
            (5, "left", 2),
            (6, "left", 10),
            (7, "left", 2),
            (8, "left", 2),
            (9, "left", 2),
        ],
    )

    # Resolution preset
    resolution_menu = cmds.optionMenu(
        "snapshotCaptureResolutionMenu",
        changeCommand=_on_resolution_preset_changed,
    )
    for preset_label in command.RESOLUTION_PRESETS:
        cmds.menuItem(label=preset_label, parent=resolution_menu)
    # Set default preset
    cmds.optionMenu(resolution_menu, edit=True, value=command.DEFAULT_RESOLUTION)

    # Width x Height
    cmds.intField("snapshotCaptureWidthField", value=init_width, width=50)
    cmds.text(label="x")
    cmds.intField("snapshotCaptureHeightField", value=init_height, width=50)
    cmds.button(label="Set", width=35, command=_on_set_custom_resolution)

    # Separator
    cmds.separator(style="single", horizontal=False, width=10, height=20)

    # Capture buttons
    cmds.button(label="PNG", width=50, command=_on_capture_png)
    cmds.button(label="Copy", width=50, command=_on_copy_png_to_clipboard)
    cmds.button(label="GIF", width=50, command=_on_capture_gif)
    cmds.button("snapshotCaptureRecordButton", label="Rec", width=50, command=_on_record_toggle, backgroundColor=[0.5, 0.5, 0.5])

    cmds.setParent(toolbar_column)

    # === Row 2: GIF settings + Background ===
    # Get playback range for defaults
    start_frame = int(cmds.playbackOptions(query=True, minTime=True))
    end_frame = int(cmds.playbackOptions(query=True, maxTime=True))

    cmds.rowLayout(
        numberOfColumns=14,
        columnAttach=[
            (1, "left", 0),
            (2, "left", 2),
            (3, "left", 8),
            (4, "left", 2),
            (5, "left", 8),
            (6, "left", 2),
            (7, "left", 8),
            (8, "left", 15),
            (9, "left", 2),
            (10, "left", 2),
            (11, "left", 8),
            (12, "left", 2),
            (13, "left", 8),
            (14, "left", 2),
        ],
    )

    cmds.text(label="Start:")
    cmds.intField("snapshotCaptureStartFrame", value=start_frame, width=50)
    cmds.text(label="End:")
    cmds.intField("snapshotCaptureEndFrame", value=end_frame, width=50)
    cmds.text(label="FPS:")
    cmds.intField("snapshotCaptureFPS", value=24, width=40, minValue=1, maxValue=60)
    cmds.checkBox("snapshotCaptureLoop", label="Loop", value=True)

    # Background color selector (button with color preview)
    cmds.text(label="BG:")
    bg_button_color = _get_bg_button_color()
    cmds.button(
        "snapshotCaptureBGButton",
        label="",
        width=40,
        height=20,
        backgroundColor=bg_button_color,
        command=_on_bg_color_button,
    )
    cmds.checkBox("snapshotCaptureBGTransparent", label="Transp", value=_bg_transparent, changeCommand=_on_bg_transparent_changed)

    # Recording delay/trim settings
    cmds.text(label="Delay:")
    cmds.intField("snapshotCaptureDelay", value=3, width=30, minValue=0, maxValue=10, annotation="Countdown delay before recording starts (seconds)")
    cmds.text(label="Trim:")
    cmds.intField("snapshotCaptureTrim", value=0, width=30, minValue=0, maxValue=10, annotation="Remove frames from end of recording (seconds)")

    cmds.setParent(toolbar_column)

    # === Row 3: Recording overlay options ===
    cmds.rowLayout(
        numberOfColumns=5,
        columnAttach=[
            (1, "left", 0),
            (2, "left", 10),
            (3, "left", 10),
            (4, "left", 10),
            (5, "left", 10),
        ],
    )

    cmds.text(label="Rec Options:")
    cmds.checkBox("snapshotCaptureShowCursor", label="Show Cursor", value=True, annotation="Show mouse cursor in recording")
    cmds.checkBox("snapshotCaptureShowClicks", label="Show Clicks", value=True, annotation="Show click indicators in recording (requires Show Cursor)")
    cmds.checkBox("snapshotCaptureShowKeys", label="Show Keys", value=False, annotation="Show pressed keyboard keys in recording")

    cmds.setParent("..")
    cmds.setParent("..")
    cmds.setParent(parent_layout)


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


def _on_resolution_preset_changed(preset_label):
    """Handle resolution preset change."""
    if preset_label not in command.RESOLUTION_PRESETS:
        return

    width, height = command.RESOLUTION_PRESETS[preset_label]
    _set_viewport_size(width, height)
    logger.info(f"Changed resolution to preset: {preset_label}")


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

    # Get current sizes
    current_editor_width = editor_widget.width()
    current_editor_height = editor_widget.height()
    current_window_width = cmds.window(_window_name, query=True, width=True)
    current_window_height = cmds.window(_window_name, query=True, height=True)

    # Calculate the difference between window size and editor size (UI chrome)
    chrome_width = current_window_width - current_editor_width
    chrome_height = current_window_height - current_editor_height

    # Calculate new window size
    toolbar_min_width = 550  # Minimum width for toolbar UI
    new_window_width = max(width + chrome_width, toolbar_min_width)
    new_window_height = height + chrome_height

    # Resize window
    if cmds.window(_window_name, exists=True):
        cmds.window(_window_name, edit=True, widthHeight=(new_window_width, new_window_height))

    # Update pane layout to fill the space
    pane_width = new_window_width
    pane_height = new_window_height - 80  # Subtract toolbar height
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


def _on_bg_transparent_changed(value):
    """Handle transparent checkbox change."""
    global _bg_transparent

    _bg_transparent = value
    _settings.write("bg_transparent", _bg_transparent)
    logger.debug(f"Background transparent set to: {_bg_transparent}")


def _on_bg_color_button(*args):
    """Handle background color button click - open color picker."""
    global _bg_color

    # Get current color for dialog
    initial_color = QColor(_bg_color[0], _bg_color[1], _bg_color[2])

    # Open color dialog
    color = QColorDialog.getColor(initial_color, None, "Select Background Color")

    if color.isValid():
        _bg_color = (color.red(), color.green(), color.blue())

        # Update button color
        button_color = [c / 255.0 for c in _bg_color]
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

    # Get GIF settings
    start_frame = cmds.intField("snapshotCaptureStartFrame", query=True, value=True)
    end_frame = cmds.intField("snapshotCaptureEndFrame", query=True, value=True)
    fps = cmds.intField("snapshotCaptureFPS", query=True, value=True)
    loop = cmds.checkBox("snapshotCaptureLoop", query=True, value=True)

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
        cmds.button("snapshotCaptureRecordButton", edit=True, label="Rec", backgroundColor=[0.5, 0.5, 0.5])
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

    # Get delay setting
    delay_sec = cmds.intField("snapshotCaptureDelay", query=True, value=True)

    if delay_sec > 0:
        # Start countdown
        _countdown_value = delay_sec

        # Update button to show countdown (no inViewMessage to avoid overlay in recording)
        cmds.button("snapshotCaptureRecordButton", edit=True, label=str(_countdown_value), backgroundColor=[0.8, 0.6, 0.2])

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
        # Update countdown display (button label only)
        cmds.button("snapshotCaptureRecordButton", edit=True, label=str(_countdown_value))
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
    global _input_monitor, _capture_bbox, _show_cursor, _show_clicks, _show_keys

    _is_recording = True
    _recorded_frames = []

    # Update button appearance
    cmds.button("snapshotCaptureRecordButton", edit=True, label="Stop", backgroundColor=[0.8, 0.2, 0.2])

    # Get overlay settings from UI
    _show_cursor = cmds.checkBox("snapshotCaptureShowCursor", query=True, value=True)
    _show_clicks = cmds.checkBox("snapshotCaptureShowClicks", query=True, value=True)
    _show_keys = cmds.checkBox("snapshotCaptureShowKeys", query=True, value=True)

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

    # Get FPS for timer interval
    fps = cmds.intField("snapshotCaptureFPS", query=True, value=True)
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

    # Update button appearance
    cmds.button("snapshotCaptureRecordButton", edit=True, label="Rec", backgroundColor=[0.5, 0.5, 0.5])

    # Check if we have frames
    if not _recorded_frames:
        cmds.warning("No frames recorded")
        return

    original_count = len(_recorded_frames)
    logger.info(f"Recording stopped - {original_count} frames captured")

    # Apply end trim
    trim_sec = cmds.intField("snapshotCaptureTrim", query=True, value=True)
    if trim_sec > 0:
        fps = cmds.intField("snapshotCaptureFPS", query=True, value=True)
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

    # Get settings
    fps = cmds.intField("snapshotCaptureFPS", query=True, value=True)
    background_color = _get_background_color()

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

    # Save GIF
    try:
        cmds.waitCursor(state=True)
        cmds.inViewMessage(message="Saving...", pos="midCenter", fade=False)

        command.save_gif(_recorded_frames, file_path, fps, background_color)

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
