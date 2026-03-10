"""Sync Player UI layer.

Full-featured playback window with seek slider, transport controls,
volume, speed, loop toggle, Maya sync toggle, and image sequence mode.
"""

from __future__ import annotations

from logging import getLogger
import os
import shutil

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ....lib_ui import (
    BaseMainWindow,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
)
from ....lib_ui.base_window import get_spacing
from ....lib_ui.qt_compat import (
    QColor,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSize,
    QSizePolicy,
    QSlider,
    Qt,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
    get_open_file_name,
)
from ....lib_ui.ui_utils import get_relative_size, scale_by_dpi
from ....lib_ui.widgets.icon_button import IconButton, IconButtonStyle, IconToggleButton, IconToolButton
from . import command
from .sequence import FfmpegExtractor, ImageDisplayWidget, SequencePlayerCore
from .widgets import ICONS_DIR, LoopRangeBar, OffsetSpinBox, PlaceholderWidget, SeekSlider, VideoWidget

logger = getLogger(__name__)

_instance = None

_SPEED_OPTIONS = ["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]
_SPEED_VALUES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
_DEFAULT_SPEED_INDEX = 3  # 1.0x

_VIDEO_EXTENSIONS = {".mov", ".avi", ".mp4", ".wmv"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_SEQUENCE_FILE_FILTER = (
    "Video and Image Files (*.mov *.avi *.mp4 *.wmv *.jpg *.jpeg *.png);;"
    "Video Files (*.mov *.avi *.mp4 *.wmv);;"
    "Image Files (*.jpg *.jpeg *.png);;"
    "All Files (*)"
)


class MainWindow(BaseMainWindow):
    """Sync Player main window."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="SyncPlayerMainWindow",
            window_title="Sync Player",
            central_layout="vertical",
        )
        self._player_core: command.VideoPlayerCore | None = None
        self._sync_controller: command.MayaSyncController | None = None
        self._seeking = False
        self._was_playing_before_seek = False
        self._was_muted_before_seek = False
        self._pending_scrub_pos: int | None = None
        self._scrub_timer = QTimer(self)
        self._scrub_timer.setInterval(30)
        self._scrub_timer.timeout.connect(self._apply_scrub_seek)
        self._current_speed_index = _DEFAULT_SPEED_INDEX
        self._opacity_value = 50
        self._settings = ToolSettingsManager(tool_name="sync_player", category="common")

        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._on_load_timeout)

        # Sequence mode state
        self._sequence_mode: bool = False
        self._image_display: ImageDisplayWidget | None = None
        self._sequence_core: SequencePlayerCore | None = None
        self._active_core: command.VideoPlayerCore | SequencePlayerCore | None = None
        self._extractor: FfmpegExtractor | None = None
        self._temp_dirs: list[str] = []

        self._setup_ui()

        width = get_relative_size(self, width_ratio=3.0)[0]
        self.resize(width, int(width * 9 / 16))
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the full UI."""
        self.central_layout.setSpacing(0)
        left, _top, _right, _bottom = self.central_layout.getContentsMargins()
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        self._setup_video_area()

        # -- bottom_widget: scrub + controls container --
        border_w = max(1, int(scale_by_dpi(1, self)))
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet(f"QWidget#SyncPlayerBottom {{ background-color: #1A1A1A; border-top: {border_w}px solid #333333; }}")
        bottom_widget.setObjectName("SyncPlayerBottom")
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, int(scale_by_dpi(4, self)))
        bottom_layout.setSpacing(0)

        self._setup_scrub_section(bottom_layout, left)

        # -- controls row --
        controls = QWidget()
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(left, 0, left, 0)
        h_spacing = int(get_spacing(self, direction="horizontal") * 0.3)
        ctrl_layout.setSpacing(0)

        # Icon / button sizes
        icon_size = int(scale_by_dpi(18, self))
        play_icon_size = int(scale_by_dpi(30, self))
        btn_icon_size = QSize(icon_size, icon_size)
        play_btn_icon_size = QSize(play_icon_size, play_icon_size)
        btn_size = int(scale_by_dpi(30, self))
        play_btn_size = int(scale_by_dpi(36, self))
        sep_margin = int(scale_by_dpi(12, self))

        ctrl_layout.addWidget(self._setup_controls_left(h_spacing, btn_icon_size, btn_size, border_w, sep_margin), stretch=1)
        ctrl_layout.addWidget(self._setup_controls_center(h_spacing, btn_icon_size, play_btn_icon_size, btn_size, play_btn_size), stretch=0)
        ctrl_layout.addWidget(self._setup_controls_right(h_spacing, btn_icon_size, btn_size, border_w, sep_margin), stretch=1)

        # Focus policy: all controls NoFocus so keyPressEvent handles shortcuts
        for widget in (
            self._seek_slider,
            self._loop_bar,
            self._btn_ab,
            self._btn_loop,
            self._btn_sync,
            self._btn_opacity,
            self._btn_prev,
            self._btn_play_pause,
            self._btn_next,
            self._btn_mute,
            self._volume_slider,
            self._options_btn,
        ):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        bottom_layout.addWidget(controls)
        self.central_layout.addWidget(bottom_widget)

    def _setup_video_area(self):
        """Set up the video container, placeholder, player core, sequence core, and sync controller."""
        self._video_container = QWidget()
        container_layout = QVBoxLayout(self._video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._placeholder = PlaceholderWidget(focus_widget=self)
        self._placeholder.open_requested.connect(self._on_open)
        container_layout.addWidget(self._placeholder)

        self._video_widget = VideoWidget(focus_widget=self, parent=self)
        self._video_widget.open_requested.connect(self._on_video_open_requested)
        self._video_widget.hide()
        container_layout.addWidget(self._video_widget)

        # Image display widget for sequence mode
        self._image_display = ImageDisplayWidget(focus_widget=self, parent=self)
        self._image_display.open_requested.connect(self._on_video_open_requested)
        self._image_display.hide()
        container_layout.addWidget(self._image_display)

        # Progress overlay for ffmpeg extraction (hidden by default)
        self._progress_overlay = QWidget(self._video_container)
        self._progress_overlay.setAutoFillBackground(True)
        palette = self._progress_overlay.palette()
        palette.setColor(self._progress_overlay.backgroundRole(), QColor("#0D0D0D"))
        self._progress_overlay.setPalette(palette)
        self._progress_overlay.hide()
        overlay_layout = QVBoxLayout(self._progress_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label = QLabel("Extracting frames...")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        overlay_layout.addWidget(self._progress_label)

        bar_w = int(scale_by_dpi(200, self))
        bar_h = int(scale_by_dpi(4, self))
        bar_r = bar_h // 2
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedSize(bar_w, bar_h)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #2D2D2D;
                border: none;
                border-radius: {bar_r}px;
            }}
            QProgressBar::chunk {{
                background: #555555;
                border-radius: {bar_r}px;
            }}
        """)
        overlay_layout.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        overlay_layout.addSpacing(int(scale_by_dpi(8, self)))

        border_w = max(1, int(scale_by_dpi(1, self)))
        btn_r = int(scale_by_dpi(2, self))
        btn_pad_v = int(scale_by_dpi(4, self))
        btn_pad_h = int(scale_by_dpi(12, self))
        self._progress_cancel_btn = QPushButton("Cancel")
        self._progress_cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: {border_w}px solid #444444;
                border-radius: {btn_r}px;
                color: #CCCCCC;
                padding: {btn_pad_v}px {btn_pad_h}px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-color: #555555;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.05);
            }}
        """)
        self._progress_cancel_btn.clicked.connect(self._on_extraction_cancel)
        overlay_layout.addWidget(self._progress_cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.central_layout.addWidget(self._video_container, stretch=1)

        # Player core (video mode)
        self._player_core = command.VideoPlayerCore(self._video_widget, parent=self)
        self._connect_core_signals(self._player_core)
        self._active_core = self._player_core

        # Sequence core (image sequence mode)
        self._sequence_core = SequencePlayerCore(self._image_display, parent=self)

        # Sync controller
        self._sync_controller = command.MayaSyncController(self._player_core)

    def _connect_core_signals(self, core) -> None:
        """Connect a player core's signals to the UI handlers.

        Args:
            core: VideoPlayerCore or SequencePlayerCore.
        """
        core.position_changed.connect(self._on_position_changed)
        core.duration_changed.connect(self._on_duration_changed)
        core.state_changed.connect(self._on_state_changed)
        core.video_fps_detected.connect(self._on_video_fps_detected)
        core.video_ready.connect(self._on_video_ready)
        core.load_failed.connect(self._on_load_failed)
        core.ab_loop_changed.connect(self._on_ab_loop_changed)

    def _disconnect_core_signals(self, core) -> None:
        """Disconnect a player core's signals from the UI handlers.

        Args:
            core: VideoPlayerCore or SequencePlayerCore.
        """
        core.position_changed.disconnect(self._on_position_changed)
        core.duration_changed.disconnect(self._on_duration_changed)
        core.state_changed.disconnect(self._on_state_changed)
        core.video_fps_detected.disconnect(self._on_video_fps_detected)
        core.video_ready.disconnect(self._on_video_ready)
        core.load_failed.disconnect(self._on_load_failed)
        core.ab_loop_changed.disconnect(self._on_ab_loop_changed)

    def _setup_scrub_section(self, parent_layout, pad_h):
        """Set up the time label, seek slider, and loop range bar.

        Args:
            parent_layout: Layout to add the scrub widgets to.
            pad_h: Horizontal padding in pixels.
        """
        # scrub header row: time_label (left) + fps_label (right)
        scrub_header = QWidget()
        scrub_header_layout = QHBoxLayout(scrub_header)
        pad_v = int(scale_by_dpi(6, self))
        scrub_header_layout.setContentsMargins(pad_h, pad_v, pad_h, 0)
        scrub_header_layout.setSpacing(0)
        self._time_label = QLabel("00:00 / 00:00    [ 0 / 0 ]")
        scrub_header_layout.addWidget(self._time_label)
        scrub_header_layout.addStretch()
        self._fps_label = QLabel(f"{command.DEFAULT_FPS:.0f}fps")
        scrub_header_layout.addWidget(self._fps_label)
        parent_layout.addWidget(scrub_header)

        # seek slider
        self._seek_slider = SeekSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.sliderMoved.connect(self._on_seek_moved)

        groove_h = int(scale_by_dpi(4, self))
        handle_w = int(scale_by_dpi(10, self))
        handle_m = int(scale_by_dpi(3, self))
        handle_r = handle_w // 2
        self._seek_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: {groove_h}px;
                background: #2D2D2D;
                border-radius: {groove_h // 2}px;
            }}
            QSlider::sub-page:horizontal {{
                background: #555555;
                border-radius: {groove_h // 2}px;
            }}
            QSlider::handle:horizontal {{
                background: #CCCCCC;
                width: {handle_w}px;
                height: {handle_w}px;
                margin: -{handle_m}px 0;
                border-radius: {handle_r}px;
            }}
            QSlider::groove:horizontal:disabled {{
                background: #252525;
            }}
            QSlider::sub-page:horizontal:disabled {{
                background: #3A3A3A;
            }}
            QSlider::handle:horizontal:disabled {{
                background: #666666;
            }}
        """)

        self._loop_bar = LoopRangeBar(self)
        self._loop_bar.loop_in_changed.connect(self._on_slider_loop_in)
        self._loop_bar.loop_out_changed.connect(self._on_slider_loop_out)

        slider_wrap = QWidget()
        slider_wrap_layout = QVBoxLayout(slider_wrap)
        pad_slider_top = int(scale_by_dpi(2, self))
        pad_slider_bottom = int(scale_by_dpi(4, self))
        slider_wrap_layout.setContentsMargins(pad_h, pad_slider_top, pad_h, pad_slider_bottom)
        slider_wrap_layout.setSpacing(int(scale_by_dpi(4, self)))
        slider_wrap_layout.addWidget(self._seek_slider)
        slider_wrap_layout.addWidget(self._loop_bar)
        parent_layout.addWidget(slider_wrap)

    def _setup_controls_left(self, h_spacing, btn_icon_size, btn_size, border_w, sep_margin):
        """Set up the left control group: AB loop, loop, sync, opacity, and offset.

        Args:
            h_spacing: Horizontal spacing between buttons.
            btn_icon_size: Icon size for standard buttons.
            btn_size: Fixed size for standard buttons.
            border_w: Border width in pixels.
            sep_margin: Margin around separator lines.

        Returns:
            QWidget: The left control group widget.
        """
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(h_spacing)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._btn_ab = IconToggleButton(icon_on="ab_on", icon_off="ab_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_ab.setToolTip("A-B Loop")
        self._btn_ab.setIconSize(btn_icon_size)
        self._btn_ab.setFixedSize(btn_size, btn_size)
        self._btn_ab.setEnabled(False)
        self._btn_ab.toggled.connect(self._on_ab_toggled)
        left_layout.addWidget(self._btn_ab)

        self._btn_loop = IconToggleButton(icon_on="loop_on", icon_off="loop_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_loop.setToolTip("Loop")
        self._btn_loop.setIconSize(btn_icon_size)
        self._btn_loop.setFixedSize(btn_size, btn_size)
        self._btn_loop.setEnabled(False)
        self._btn_loop.toggled.connect(self._on_loop_toggled)
        left_layout.addWidget(self._btn_loop)

        self._btn_sync = IconToggleButton(icon_on="sync_on", icon_off="sync_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_sync.setToolTip("Maya Sync")
        self._btn_sync.setIconSize(btn_icon_size)
        self._btn_sync.setFixedSize(btn_size, btn_size)
        self._btn_sync.setEnabled(False)
        self._btn_sync.toggled.connect(self._on_sync_toggled)
        left_layout.addWidget(self._btn_sync)

        self._btn_opacity = IconToggleButton(icon_on="opacity_on", icon_off="opacity_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_opacity.setToolTip("Opacity (Ctrl+T)")
        self._btn_opacity.setIconSize(btn_icon_size)
        self._btn_opacity.setFixedSize(btn_size, btn_size)
        self._btn_opacity.toggled.connect(self._on_opacity_toggled)
        left_layout.addWidget(self._btn_opacity)

        left_layout.addSpacing(sep_margin)
        left_layout.addWidget(self._create_separator_line())
        left_layout.addSpacing(sep_margin)

        offset_label = QLabel("Offset")
        offset_label.setStyleSheet("color: #999999;")
        left_layout.addWidget(offset_label)

        left_layout.addSpacing(int(scale_by_dpi(4, self)))

        self._offset_spin = OffsetSpinBox(focus_widget=self)
        self._offset_spin.setRange(-999999, 999999)
        self._offset_spin.setValue(0)
        self._offset_spin.setFixedHeight(int(scale_by_dpi(24, self)))
        spin_pad_h = int(scale_by_dpi(4, self))
        spin_pad_v = int(scale_by_dpi(2, self))
        self._offset_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: transparent;
                border: {border_w}px solid #444444;
                border-radius: {int(scale_by_dpi(2, self))}px;
                color: #CCCCCC;
                padding: {spin_pad_v}px {spin_pad_h}px;
            }}
            QSpinBox:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-color: #555555;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0px;
                border: none;
            }}
            QSpinBox:disabled {{
                color: rgba(204, 204, 204, 0.3);
                border-color: rgba(68, 68, 68, 0.5);
            }}
        """)
        self._offset_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._offset_spin.setToolTip("Frame offset for Maya sync")
        self._offset_spin.valueChanged.connect(self._on_offset_changed)
        left_layout.addWidget(self._offset_spin)

        return left_widget

    def _setup_controls_center(self, h_spacing, btn_icon_size, play_btn_icon_size, btn_size, play_btn_size):
        """Set up the center control group: previous, play/pause, and next buttons.

        Args:
            h_spacing: Horizontal spacing between buttons.
            btn_icon_size: Icon size for standard buttons.
            play_btn_icon_size: Icon size for the play/pause button.
            btn_size: Fixed size for standard buttons.
            play_btn_size: Fixed size for the play/pause button.

        Returns:
            QWidget: The center control group widget.
        """
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(h_spacing)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._btn_prev = IconButton(icon_name="frame_prev", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_prev.setToolTip("Previous frame")
        self._btn_prev.setIconSize(btn_icon_size)
        self._btn_prev.setFixedSize(btn_size, btn_size)
        self._btn_prev.clicked.connect(self._on_step_backward)
        center_layout.addWidget(self._btn_prev)

        self._btn_play_pause = IconToggleButton(icon_on="pause", icon_off="play", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_play_pause.setToolTip("Play / Pause")
        self._btn_play_pause.setIconSize(play_btn_icon_size)
        self._btn_play_pause.setFixedSize(play_btn_size, play_btn_size)
        self._btn_play_pause.toggled.connect(self._on_play_pause_toggled)
        center_layout.addWidget(self._btn_play_pause)

        self._btn_next = IconButton(icon_name="frame_next", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_next.setToolTip("Next frame")
        self._btn_next.setIconSize(btn_icon_size)
        self._btn_next.setFixedSize(btn_size, btn_size)
        self._btn_next.clicked.connect(self._on_step_forward)
        center_layout.addWidget(self._btn_next)

        return center_widget

    def _setup_controls_right(self, h_spacing, btn_icon_size, btn_size, border_w, sep_margin):
        """Set up the right control group: mute, volume, and options menu.

        Args:
            h_spacing: Horizontal spacing between buttons.
            btn_icon_size: Icon size for standard buttons.
            btn_size: Fixed size for standard buttons.
            border_w: Border width in pixels.
            sep_margin: Margin around separator lines.

        Returns:
            QWidget: The right control group widget.
        """
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(h_spacing)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        right_layout.addStretch(1)

        self._btn_mute = IconToggleButton(icon_on="volume_off", icon_off="volume_on", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=ICONS_DIR)
        self._btn_mute.setToolTip("Mute")
        self._btn_mute.setIconSize(btn_icon_size)
        self._btn_mute.setFixedSize(btn_size, btn_size)
        self._btn_mute.toggled.connect(self._on_mute_toggled)
        right_layout.addWidget(self._btn_mute)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setFixedWidth(int(get_relative_size(self, width_ratio=0.3)[0]))
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        right_layout.addWidget(self._volume_slider)

        right_layout.addSpacing(sep_margin)
        right_layout.addWidget(self._create_separator_line())
        right_layout.addSpacing(sep_margin)

        self._options_btn = IconToolButton(
            icon_name="options",
            style_mode=IconButtonStyle.TRANSPARENT,
            auto_size=False,
            icon_dir=ICONS_DIR,
        )
        self._options_btn.setToolTip("Options")
        self._options_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._options_btn.setFixedSize(btn_size, btn_size)
        self._options_btn.setIconSize(btn_icon_size)
        self._options_btn.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        menu_pad_v = int(scale_by_dpi(4, self))
        menu_pad_h = int(scale_by_dpi(12, self))
        arrow_size = int(scale_by_dpi(8, self))
        arrow_reserve = arrow_size + menu_pad_h * 2
        menu_style = f"""
            QMenu {{
                background-color: #1A1A1A;
                border: {border_w}px solid #333333;
                color: #CCCCCC;
                padding: {menu_pad_v}px 0px;
            }}
            QMenu::item {{
                padding: {menu_pad_v}px {arrow_reserve}px {menu_pad_v}px {menu_pad_h}px;
            }}
            QMenu::item:selected {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QMenu::separator {{
                height: {border_w}px;
                background: #333333;
                margin: {menu_pad_v}px 0px;
            }}
            QMenu::right-arrow {{
                width: {arrow_size}px;
                height: {arrow_size}px;
                right: {menu_pad_h}px;
            }}
        """
        self._options_menu = QMenu(self)
        self._options_menu.setWindowFlags(self._options_menu.windowFlags() | Qt.WindowType.NoDropShadowWindowHint)
        self._options_menu.setStyleSheet(menu_style)
        self._options_menu.aboutToShow.connect(self._populate_options_menu)
        self._options_btn.setMenu(self._options_menu)
        right_layout.addWidget(self._options_btn)

        return right_widget

    def _create_separator_line(self) -> QFrame:
        """Create a vertical separator line for the controls row."""
        sep_h = int(scale_by_dpi(18, self))
        sep_border = max(1, int(scale_by_dpi(1, self)))
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedHeight(sep_h)
        line.setStyleSheet(f"QFrame {{ color: #333333; border: none; border-left: {sep_border}px solid #333333; }}")
        return line

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_video(self, path: str) -> None:
        """Load a video file (in video mode).

        Args:
            path: Absolute file path.
        """
        if self._active_core:
            self._active_core.clear_ab_loop()
            self.setCursor(Qt.CursorShape.WaitCursor)
            self._load_timer.start(10000)
            self._placeholder.hide()
            self._video_widget.show()
            self._image_display.hide()
            self._player_core.load(path)
            self.setWindowTitle(f"Sync Player - {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Time display helper
    # ------------------------------------------------------------------

    def _update_time_display(self, position_ms: int, duration_ms: int) -> None:
        """Update the time label with time and frame numbers."""
        fps = self._active_core.fps if self._active_core else command.DEFAULT_FPS
        current_frame = command.ms_to_frame(position_ms, fps)
        total_frames = command.ms_to_frame(duration_ms, fps)
        time_text = f"{command.format_time(position_ms)} / {command.format_time(duration_ms)}"
        frame_text = f"[ {current_frame} / {total_frames} ]"
        display = f"{time_text}    {frame_text}"
        if self._active_core and self._active_core.has_ab_loop:
            a_text = command.format_time(self._active_core.loop_in)
            b_text = command.format_time(self._active_core.loop_out)
            a_frame = command.ms_to_frame(self._active_core.loop_in, fps)
            b_frame = command.ms_to_frame(self._active_core.loop_out, fps)
            display += f"      A-B: {a_text} - {b_text} [ {a_frame} - {b_frame} ]"
        self._time_label.setText(display)

    # ------------------------------------------------------------------
    # Signal handlers — transport
    # ------------------------------------------------------------------

    def _is_playing(self) -> bool:
        """Return True if a video is currently playing."""
        return self._btn_play_pause.isChecked()

    @error_handler
    def _on_open(self):
        if self._sequence_mode:
            self._on_open_sequence()
        else:
            self._on_open_video()

    def _on_open_video(self):
        """Open a video file (video mode)."""
        path, _ = get_open_file_name(
            self,
            caption="Open Video",
            filter=command.VIDEO_FILTER,
        )
        if path:
            self.load_video(path)

    @error_handler
    def _on_open_sequence(self):
        """Open a file in sequence mode — auto-detect video vs image."""
        path, _ = get_open_file_name(
            self,
            caption="Open Video or Image",
            filter=_SEQUENCE_FILE_FILTER,
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in _VIDEO_EXTENSIONS:
            self._start_ffmpeg_extraction(path)
        elif ext in _IMAGE_EXTENSIONS:
            self._load_image_sequence(os.path.dirname(path))
        else:
            cmds.warning(f"Sync Player: Unsupported file type: {ext}")

    @error_handler
    def _on_open_folder(self):
        """Open a folder as image sequence."""
        folder = QFileDialog.getExistingDirectory(self, "Open Image Sequence Folder")
        if folder:
            self._load_image_sequence(folder)

    def _on_video_open_requested(self):
        """Handle open request from video view (with sync/playing guards)."""
        if self._sync_controller and self._sync_controller.is_enabled:
            return
        if self._is_playing():
            cmds.warning("Sync Player: Cannot open a new video while playing")
            return
        self._on_open()

    @error_handler
    def _on_play_pause_toggled(self, checked: bool):
        if self._active_core:
            if checked:
                self._active_core.play()
            else:
                self._active_core.pause()

    @error_handler
    def _on_step_forward(self):
        if self._active_core:
            self._active_core.step_forward()

    @error_handler
    def _on_step_backward(self):
        if self._active_core:
            self._active_core.step_backward()

    # ------------------------------------------------------------------
    # Signal handlers — seek
    # ------------------------------------------------------------------

    def _on_seek_pressed(self):
        self._seeking = True
        self._was_playing_before_seek = False
        self._was_muted_before_seek = False
        if self._active_core:
            self._was_playing_before_seek = self._active_core.get_playback_state() == "playing"
            self._was_muted_before_seek = self._btn_mute.isChecked()
            if not self._was_muted_before_seek:
                self._active_core.set_muted(True)
            self._active_core.set_ab_enforcement(False)
            self._active_core.pause()
            pos = self._seek_slider.value()
            self._active_core.seek(pos)
            self._pending_scrub_pos = None
            self._scrub_timer.start()
            self._update_time_display(pos, self._seek_slider.maximum())

    def _on_seek_released(self):
        self._scrub_timer.stop()
        if self._active_core:
            self._active_core.seek(self._seek_slider.value())
            if self._was_playing_before_seek:
                self._active_core.play()
            if not self._was_muted_before_seek:
                self._active_core.set_muted(False)
            self._active_core.set_ab_enforcement(True)
            self._update_time_display(self._seek_slider.value(), self._seek_slider.maximum())
        self._pending_scrub_pos = None
        # Unblock _on_state_changed only after all state is restored.
        self._seeking = False

    def _on_seek_moved(self, position: int):
        self._pending_scrub_pos = position
        self._update_time_display(position, self._seek_slider.maximum())

    def _apply_scrub_seek(self):
        if self._pending_scrub_pos is not None and self._active_core:
            self._active_core.seek(self._pending_scrub_pos)
            self._pending_scrub_pos = None

    # ------------------------------------------------------------------
    # Signal handlers — player feedback
    # ------------------------------------------------------------------

    def _on_position_changed(self, position: int):
        if not self._seeking:
            self._seek_slider.setValue(position)
            self._update_time_display(position, self._seek_slider.maximum())

    def _on_duration_changed(self, duration: int):
        self._seek_slider.setRange(0, duration)
        self._loop_bar.set_total_ms(duration)
        self._update_time_display(0, duration)

    def _on_state_changed(self, state: str):
        if self._seeking:
            return
        is_playing = state == "playing"
        self._btn_play_pause.blockSignals(True)
        self._btn_play_pause.setChecked(is_playing)
        self._btn_play_pause.blockSignals(False)

    def _on_video_fps_detected(self, fps: float):
        self._fps_label.setText(f"{fps:.4g}fps")

    def _on_video_ready(self):
        self._load_timer.stop()
        self.unsetCursor()
        self._btn_ab.setEnabled(True)
        self._btn_loop.setEnabled(True)
        self._btn_sync.setEnabled(True)

    def _on_load_failed(self, message: str):
        self._load_timer.stop()
        self.unsetCursor()
        self._btn_ab.setEnabled(False)
        self._btn_loop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._video_widget.hide()
        self._image_display.hide()
        self._placeholder.show()

    def _on_load_timeout(self):
        self.unsetCursor()
        self._btn_ab.setEnabled(False)
        self._btn_loop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._video_widget.hide()
        self._image_display.hide()
        self._placeholder.show()
        om2.MGlobal.displayError("Sync Player: Video load timed out")

    # ------------------------------------------------------------------
    # Signal handlers — loop / speed / volume / mute
    # ------------------------------------------------------------------

    @error_handler
    def _on_ab_toggled(self, checked: bool):
        if not self._active_core:
            return
        if checked:
            if not self._active_core.has_media():
                self._btn_ab.blockSignals(True)
                self._btn_ab.setChecked(False)
                self._btn_ab.blockSignals(False)
                return
            self._active_core.set_loop_in(0)
            self._active_core.set_loop_out(self._active_core.duration)
        else:
            self._active_core.clear_ab_loop()

    @error_handler
    def _on_loop_toggled(self, checked: bool):
        if self._active_core:
            self._active_core.set_loop(checked)

    @error_handler
    def _on_speed_selected(self, index: int):
        if 0 <= index < len(_SPEED_VALUES):
            self._current_speed_index = index
            if self._active_core:
                self._active_core.set_playback_rate(_SPEED_VALUES[index])

    @error_handler
    def _on_volume_changed(self, value: int):
        if self._active_core:
            self._active_core.set_volume(value)

    @error_handler
    def _on_mute_toggled(self, checked: bool):
        if self._active_core:
            self._active_core.set_muted(checked)

    @error_handler
    def _on_offset_changed(self, value: int):
        if self._sync_controller:
            self._sync_controller.set_frame_offset(value)

    def _on_ab_loop_changed(self):
        if self._active_core:
            has_loop = self._active_core.has_ab_loop
            self._btn_ab.blockSignals(True)
            self._btn_ab.setChecked(has_loop)
            self._btn_ab.blockSignals(False)
            if has_loop:
                self._loop_bar.set_loop_markers(self._active_core.loop_in, self._active_core.loop_out, self._active_core.duration)
            else:
                self._loop_bar.set_loop_markers(None, None, self._active_core.duration)
            self._update_time_display(self._active_core.position, self._active_core.duration)

    def _on_slider_loop_in(self, ms: int):
        if self._active_core:
            self._active_core.set_loop_in(ms)

    def _on_slider_loop_out(self, ms: int):
        if self._active_core:
            self._active_core.set_loop_out(ms)

    def _populate_options_menu(self):
        self._options_menu.clear()

        # Image Sequence Mode checkbox
        seq_action = self._options_menu.addAction("Image Sequence Mode")
        seq_action.setCheckable(True)
        seq_action.setChecked(self._sequence_mode)
        seq_action.toggled.connect(self._on_sequence_mode_toggled)

        # Open Folder action (only visible in sequence mode)
        if self._sequence_mode:
            self._options_menu.addAction("Open Folder...", self._on_open_folder)

        self._options_menu.addSeparator()

        current_label = _SPEED_OPTIONS[self._current_speed_index]
        speed_menu = self._options_menu.addMenu(f"Speed: {current_label}")
        speed_menu.setWindowFlags(speed_menu.windowFlags() | Qt.WindowType.NoDropShadowWindowHint)
        for i, label in enumerate(_SPEED_OPTIONS):
            speed_menu.addAction(label, lambda checked=False, idx=i: self._on_speed_selected(idx))

        self._options_menu.addSeparator()

        # Opacity slider row
        opacity_widget = QWidget()
        opacity_layout = QHBoxLayout(opacity_widget)
        menu_pad_h = int(scale_by_dpi(12, self))
        menu_pad_v = int(scale_by_dpi(4, self))
        opacity_layout.setContentsMargins(menu_pad_h, menu_pad_v, menu_pad_h, menu_pad_v)
        opacity_layout.setSpacing(int(scale_by_dpi(8, self)))

        opacity_label = QLabel("Opacity")
        opacity_label.setStyleSheet("color: #CCCCCC;")
        opacity_layout.addWidget(opacity_label)

        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(10, 100)
        opacity_slider.setValue(self._opacity_value)
        opacity_slider.setMinimumWidth(int(scale_by_dpi(80, self)))
        opacity_layout.addWidget(opacity_slider, stretch=1)

        value_label = QLabel(f"{self._opacity_value}%")
        value_label.setFixedWidth(int(scale_by_dpi(32, self)))
        value_label.setStyleSheet("color: #CCCCCC;")
        opacity_layout.addWidget(value_label)

        def _on_opacity_slider_changed(val: int):
            self._opacity_value = val
            value_label.setText(f"{val}%")
            if self._btn_opacity.isChecked():
                self.setWindowOpacity(val / 100.0)

        opacity_slider.valueChanged.connect(_on_opacity_slider_changed)

        action = QWidgetAction(self._options_menu)
        action.setDefaultWidget(opacity_widget)
        self._options_menu.addAction(action)

    # ------------------------------------------------------------------
    # Signal handlers — sync
    # ------------------------------------------------------------------

    @error_handler
    def _on_sync_toggled(self, checked: bool):
        if not self._sync_controller:
            return
        if checked:
            maya_fps = command.get_maya_fps()
            self._sync_controller.set_fps(maya_fps)
            self._sync_controller.enable()
            if self._active_core:
                self._active_core.set_fps(maya_fps)
                video_fps = self._active_core.get_video_fps()
                if video_fps is not None and abs(video_fps - maya_fps) > 0.1:
                    cmds.warning(
                        f"Sync Player: Video FPS ({video_fps:.4g}) differs from Maya FPS ({maya_fps:.4g}). "
                        "Frame stepping and frame display may not match the video."
                    )
        else:
            self._sync_controller.disable()
        if self._active_core:
            self._active_core.set_ab_enforcement(not checked)
        self._set_sync_locked(checked)

    # ------------------------------------------------------------------
    # Signal handlers — opacity
    # ------------------------------------------------------------------

    @error_handler
    def _on_opacity_toggled(self, checked: bool):
        if checked:
            self.setWindowOpacity(self._opacity_value / 100.0)
        else:
            self.setWindowOpacity(1.0)

    def _set_sync_locked(self, locked: bool):
        """Enable or disable player controls based on Maya sync state."""
        enabled = not locked
        self._btn_play_pause.setEnabled(enabled)
        self._btn_prev.setEnabled(enabled)
        self._btn_next.setEnabled(enabled)
        self._btn_ab.setEnabled(enabled)
        self._btn_loop.setEnabled(enabled)
        self._seek_slider.setEnabled(enabled)
        self._loop_bar.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Sequence mode
    # ------------------------------------------------------------------

    @error_handler
    def _on_sequence_mode_toggled(self, checked: bool):
        """Handle sequence mode checkbox toggle."""
        if checked == self._sequence_mode:
            return

        # Disable sync if active
        if self._sync_controller and self._sync_controller.is_enabled:
            self._btn_sync.blockSignals(True)
            self._btn_sync.setChecked(False)
            self._btn_sync.blockSignals(False)
            self._sync_controller.disable()
            self._set_sync_locked(False)

        # Stop current playback
        if self._active_core:
            self._active_core.stop()

        self._sequence_mode = checked

        # Switch active core
        old_core = self._active_core
        if checked:
            new_core = self._sequence_core
        else:
            new_core = self._player_core

        self._disconnect_core_signals(old_core)
        self._connect_core_signals(new_core)
        self._active_core = new_core

        # Switch display widgets
        self._video_widget.hide()
        self._image_display.hide()
        self._placeholder.show()

        # Reset UI state
        self._seek_slider.setRange(0, 0)
        self._loop_bar.set_total_ms(0)
        self._loop_bar.set_loop_markers(None, None, 0)
        self._time_label.setText("00:00 / 00:00    [ 0 / 0 ]")
        self._fps_label.setText(f"{command.DEFAULT_FPS:.0f}fps")
        self._btn_ab.setEnabled(False)
        self._btn_loop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._btn_play_pause.blockSignals(True)
        self._btn_play_pause.setChecked(False)
        self._btn_play_pause.blockSignals(False)

        # Recreate sync controller with new active core
        if self._sync_controller:
            self._sync_controller.cleanup()
        self._sync_controller = command.MayaSyncController(self._active_core)
        if self._offset_spin.value() != 0:
            self._sync_controller.set_frame_offset(self._offset_spin.value())

        # Update audio controls
        self._update_audio_controls()

        self.setWindowTitle("Sync Player")
        logger.info("Sequence mode: %s", "ON" if checked else "OFF")

    def _update_audio_controls(self) -> None:
        """Enable or disable audio controls based on current mode."""
        audio_enabled = not self._sequence_mode
        self._btn_mute.setEnabled(audio_enabled)
        self._volume_slider.setEnabled(audio_enabled)

    def _start_ffmpeg_extraction(self, path: str) -> None:
        """Start extracting JPEG frames from a video file using ffmpeg.

        Args:
            path: Video file path.
        """
        if shutil.which("ffmpeg") is None:
            om2.MGlobal.displayError("Sync Player: ffmpeg not found. Please install ffmpeg and add it to PATH.")
            return

        if self._extractor is not None:
            self._extractor.cancel()
            self._extractor.wait(3000)

        self._placeholder.hide()
        self._video_widget.hide()
        self._image_display.hide()
        self._progress_overlay.setGeometry(self._video_container.rect())
        self._progress_overlay.show()
        self._progress_overlay.raise_()
        self._progress_bar.setValue(0)
        self._progress_label.setText(f"Extracting frames from {os.path.basename(path)}...")

        self._extractor = FfmpegExtractor(path, parent=self)
        self._extractor.progress_changed.connect(self._on_extraction_progress)
        self._extractor.extraction_finished.connect(self._on_extraction_finished)
        self._extractor.extraction_failed.connect(self._on_extraction_failed)
        self._extractor.start()

    def _on_extraction_progress(self, current: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(current / total * 100))
        self._progress_label.setText(f"Extracting frames... {current}/{total}")

    def _on_extraction_cancel(self) -> None:
        if self._extractor is not None:
            self._extractor.cancel()
            self._extractor.wait(3000)
            self._extractor = None
        self._progress_overlay.hide()
        self._placeholder.show()

    @error_handler
    def _on_extraction_finished(self, output_folder: str):
        self._progress_overlay.hide()
        self._extractor = None
        self._temp_dirs.append(output_folder)
        self._load_image_sequence(output_folder)

    @error_handler
    def _on_extraction_failed(self, error: str):
        self._progress_overlay.hide()
        self._extractor = None
        self._placeholder.show()
        om2.MGlobal.displayError(f"Sync Player: Frame extraction failed: {error}")

    def _load_image_sequence(self, folder: str) -> None:
        """Load an image sequence from a folder into the sequence core.

        Args:
            folder: Path to folder containing image files.
        """
        maya_fps = command.get_maya_fps()
        self._sequence_core.set_fps(maya_fps)

        self._placeholder.hide()
        self._video_widget.hide()
        self._image_display.show()

        self._sequence_core.load(folder)
        self.setWindowTitle(f"Sync Player - {os.path.basename(folder)} (sequence)")

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "volume": self._volume_slider.value(),
            "muted": self._btn_mute.isChecked(),
            "frame_offset": self._offset_spin.value(),
            "speed_index": self._current_speed_index,
            "opacity_value": self._opacity_value,
            "sequence_mode": self._sequence_mode,
        }

    def _apply_settings(self, data: dict) -> None:
        volume = data.get("volume", 100)
        self._volume_slider.setValue(volume)
        if self._active_core:
            self._active_core.set_volume(volume)

        muted = data.get("muted", False)
        self._btn_mute.setChecked(muted)
        if self._active_core:
            self._active_core.set_muted(muted)

        frame_offset = data.get("frame_offset", 0)
        self._offset_spin.setValue(frame_offset)
        if self._sync_controller:
            self._sync_controller.set_frame_offset(frame_offset)

        speed_index = data.get("speed_index", _DEFAULT_SPEED_INDEX)
        self._on_speed_selected(speed_index)

        self._opacity_value = data.get("opacity_value", 50)

        sequence_mode = data.get("sequence_mode", False)
        if sequence_mode != self._sequence_mode:
            self._on_sequence_mode_toggled(sequence_mode)

    def _restore_settings(self):
        data = self._settings.load_settings("default")
        if data:
            self._apply_settings(data)

    def _save_settings(self):
        self._settings.save_settings(self._collect_settings(), "default")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # Opacity shortcuts (available even during sync)
        if ctrl and key == Qt.Key.Key_T:
            self._btn_opacity.toggle()
            return
        if ctrl and key == Qt.Key.Key_Up:
            self._opacity_value = min(100, self._opacity_value + 10)
            if self._btn_opacity.isChecked():
                self.setWindowOpacity(self._opacity_value / 100.0)
            return
        if ctrl and key == Qt.Key.Key_Down:
            self._opacity_value = max(10, self._opacity_value - 10)
            if self._btn_opacity.isChecked():
                self.setWindowOpacity(self._opacity_value / 100.0)
            return
        if ctrl and key == Qt.Key.Key_0:
            self._opacity_value = 100
            self._btn_opacity.blockSignals(True)
            self._btn_opacity.setChecked(False)
            self._btn_opacity.blockSignals(False)
            self.setWindowOpacity(1.0)
            return

        if self._sync_controller and self._sync_controller.is_enabled:
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_Space:
            self._btn_play_pause.toggle()
            return
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self._btn_next.click()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self._btn_prev.click()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        """Keep progress overlay sized to match container."""
        super().resizeEvent(event)
        if self._progress_overlay is not None and self._progress_overlay.isVisible():
            QTimer.singleShot(0, self._sync_overlay_geometry)

    def _sync_overlay_geometry(self):
        if self._progress_overlay is not None:
            self._progress_overlay.setGeometry(self._video_container.rect())

    def closeEvent(self, event):
        self._save_settings()

        # Cancel extractor if running
        if self._extractor is not None:
            self._extractor.cancel()
            self._extractor.wait(3000)
            self._extractor = None

        if self._sync_controller:
            self._sync_controller.cleanup()
        if self._active_core:
            self._active_core.stop()
        if self._sequence_core:
            self._sequence_core.cleanup()

        # Clean up temp directories
        for temp_dir in self._temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._temp_dirs.clear()

        super().closeEvent(event)


def show_ui():
    """Show the Sync Player window (singleton)."""
    global _instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass
    _instance = MainWindow(get_maya_main_window())
    _instance.show()
    return _instance
