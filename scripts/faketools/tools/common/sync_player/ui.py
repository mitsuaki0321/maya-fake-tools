"""Sync Player UI layer.

Full-featured playback window with seek slider, transport controls,
volume, speed, loop toggle, and Maya sync toggle.
"""

from __future__ import annotations

from logging import getLogger
import os
from pathlib import Path

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ....lib_ui import (
    BaseMainWindow,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
    icons,
)
from ....lib_ui.base_window import get_spacing
from ....lib_ui.qt_compat import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QIcon,
    QLabel,
    QMenu,
    QPainter,
    QPen,
    QRect,
    QSize,
    QSizePolicy,
    QSlider,
    QSpinBox,
    Qt,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QVideoWidget,
    QWidget,
    Signal,
    get_open_file_name,
    get_playback_state,
)
from ....lib_ui.ui_utils import get_relative_size, scale_by_dpi
from ....lib_ui.widgets.icon_button import IconButton, IconButtonStyle, IconToggleButton, IconToolButton
from . import command

logger = getLogger(__name__)

_instance = None

_ICONS_DIR = str(Path(__file__).parent / "icons")

_SPEED_OPTIONS = ["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]
_SPEED_VALUES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
_DEFAULT_SPEED_INDEX = 3  # 1.0x


class _LoopRangeBar(QWidget):
    """Dedicated A-B loop range bar with draggable markers."""

    loop_in_changed = Signal(int)
    loop_out_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop_in_ms: int | None = None
        self._loop_out_ms: int | None = None
        self._total_ms: int = 0
        self._dragging: str | None = None
        self.setMouseTracking(True)
        self.setFixedHeight(int(scale_by_dpi(16, self)))

    def set_loop_markers(self, loop_in: int | None, loop_out: int | None, total_ms: int) -> None:
        """Update A-B loop marker positions.

        Args:
            loop_in: A point in milliseconds, or None.
            loop_out: B point in milliseconds, or None.
            total_ms: Total duration in milliseconds.
        """
        self._loop_in_ms = loop_in
        self._loop_out_ms = loop_out
        self._total_ms = total_ms
        self.update()

    def set_total_ms(self, ms: int) -> None:
        """Update total duration.

        Args:
            ms: Total duration in milliseconds.
        """
        self._total_ms = ms
        self.update()

    def _value_to_pixel(self, ms: int) -> int:
        if self._total_ms <= 0:
            return 0
        return int(ms / self._total_ms * self.width())

    def _pixel_to_value(self, px: int) -> int:
        if self.width() <= 0 or self._total_ms <= 0:
            return 0
        ratio = max(0.0, min(1.0, px / self.width()))
        return int(ratio * self._total_ms)

    def _hit_test(self, x: int) -> str | None:
        if self._loop_in_ms is None or self._loop_out_ms is None:
            return None
        grab_px = int(scale_by_dpi(6, self))
        x_a = self._value_to_pixel(self._loop_in_ms)
        x_b = self._value_to_pixel(self._loop_out_ms)
        dist_a = abs(x - x_a)
        dist_b = abs(x - x_b)
        if dist_a <= grab_px and dist_b <= grab_px:
            return "in" if dist_a <= dist_b else "out"
        if dist_a <= grab_px:
            return "in"
        if dist_b <= grab_px:
            return "out"
        return None

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test(event.pos().x())
            if hit:
                self._dragging = hit
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            value = self._pixel_to_value(event.pos().x())
            value = max(0, min(self._total_ms, value))
            if self._dragging == "in" and self._loop_out_ms is not None:
                value = min(value, self._loop_out_ms - 1)
                self.loop_in_changed.emit(max(0, value))
            elif self._dragging == "out" and self._loop_in_ms is not None:
                value = max(value, self._loop_in_ms + 1)
                self.loop_out_changed.emit(min(self._total_ms, value))
            event.accept()
            return
        if self._loop_in_ms is not None and self._loop_out_ms is not None:
            if self._hit_test(event.pos().x()):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self.unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self._loop_in_ms is None or self._loop_out_ms is None:
            return
        w = self.width()
        h = self.height()
        x_a = self._value_to_pixel(self._loop_in_ms)
        x_b = self._value_to_pixel(self._loop_out_ms)
        disabled = not self.isEnabled()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors
        accent = QColor("#555555") if disabled else QColor("#4A9EFF")
        highlight = QColor(85, 85, 85, 60) if disabled else QColor(74, 158, 255, 90)

        # Rail line
        rail_h = max(1, int(scale_by_dpi(3, self)))
        rail_y = (h - rail_h) // 2
        painter.fillRect(QRect(0, rail_y, w, rail_h), QColor("#2A2A2A"))

        # A-B highlight
        painter.fillRect(QRect(x_a, rail_y, x_b - x_a, rail_h), highlight)

        # A line
        line_w = max(1, int(scale_by_dpi(2, self)))
        pen = QPen(accent)
        pen.setWidth(line_w)
        painter.setPen(pen)
        painter.drawLine(x_a, 0, x_a, h)

        # B line
        painter.drawLine(x_b, 0, x_b, h)

        # A/B labels
        font_size = max(1, int(scale_by_dpi(11, self)))
        font = QFont()
        font.setPixelSize(font_size)
        font.setBold(True)
        painter.setFont(font)

        label_offset = int(scale_by_dpi(2, self))
        fm = painter.fontMetrics()
        painter.drawText(x_a + label_offset, font_size, "A")
        painter.drawText(x_b - label_offset - fm.horizontalAdvance("B"), font_size, "B")

        painter.end()


class _OffsetSpinBox(QSpinBox):
    """QSpinBox that returns focus to the parent MainWindow on Enter/Escape or focus loss."""

    def __init__(self, main_window: MainWindow, parent=None):
        super().__init__(parent)
        self._main_window = main_window

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._main_window.setFocus()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if event.reason() != Qt.FocusReason.ActiveWindowFocusReason:
            self._main_window.setFocus()


class _SeekSlider(QSlider):
    """Seek slider with click-to-jump behavior."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum() and self.width() > 0:
            ratio = max(0.0, min(1.0, event.pos().x() / self.width()))
            value = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
            self.setValue(value)
        super().mousePressEvent(event)


class _PlaceholderWidget(QWidget):
    """Empty-state placeholder with icon and instruction text."""

    def __init__(self, main_window: MainWindow, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#0D0D0D"))
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Monitor icon
        icon_size = int(scale_by_dpi(64, self))
        icon_path = icons.get_path("monitor", base_dir=_ICONS_DIR)
        pixmap = QIcon(icon_path).pixmap(QSize(icon_size, icon_size))
        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Instruction text
        font_size = max(11, int(scale_by_dpi(13, self)))
        text_label = QLabel("Double-click to open")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"color: rgba(255, 255, 255, 0.4); font-size: {font_size}px;")
        layout.addWidget(text_label)

    def mousePressEvent(self, event):
        self._main_window.setFocus()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._main_window._on_open()


class _VideoWidget(QVideoWidget):
    """QVideoWidget with double-click support for opening files."""

    def __init__(self, parent: MainWindow):
        super().__init__(parent)
        self._main_window = parent

    def mousePressEvent(self, event):
        self._main_window.setFocus()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        sync = self._main_window._sync_controller
        if sync is not None and sync.is_enabled:
            return
        if self._main_window._is_playing():
            cmds.warning("Sync Player: Cannot open a new video while playing")
            return
        self._main_window._on_open()


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
        self._current_speed_index = _DEFAULT_SPEED_INDEX
        self._settings = ToolSettingsManager(tool_name="sync_player", category="common")

        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._on_load_timeout)

        # Timer to pause playback when scrub goes idle (mouse stops or click).
        self._scrub_pause_timer = QTimer(self)
        self._scrub_pause_timer.setSingleShot(True)
        self._scrub_pause_timer.setInterval(50)
        self._scrub_pause_timer.timeout.connect(self._on_scrub_pause)

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

        # Video area — placeholder shown until a video is loaded
        self._video_container = QWidget()
        container_layout = QVBoxLayout(self._video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._placeholder = _PlaceholderWidget(self)
        container_layout.addWidget(self._placeholder)

        self._video_widget = _VideoWidget(self)
        self._video_widget.hide()
        container_layout.addWidget(self._video_widget)

        self.central_layout.addWidget(self._video_container, stretch=1)

        # Player core + sync controller
        self._player_core = command.VideoPlayerCore(self._video_widget, parent=self)
        self._player_core.position_changed.connect(self._on_position_changed)
        self._player_core.duration_changed.connect(self._on_duration_changed)
        self._player_core.state_changed.connect(self._on_state_changed)
        self._player_core.video_fps_detected.connect(self._on_video_fps_detected)
        self._player_core.video_ready.connect(self._on_video_ready)
        self._player_core.load_failed.connect(self._on_load_failed)
        self._player_core.ab_loop_changed.connect(self._on_ab_loop_changed)
        self._sync_controller = command.MayaSyncController(self._player_core)

        # -- bottom_widget: scrub + controls container --
        border_w = max(1, int(scale_by_dpi(1, self)))
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet(f"QWidget#SyncPlayerBottom {{ background-color: #1A1A1A; border-top: {border_w}px solid #333333; }}")
        bottom_widget.setObjectName("SyncPlayerBottom")
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, int(scale_by_dpi(4, self)))
        bottom_layout.setSpacing(0)

        # -- scrub section --
        # scrub header row: time_label (left) + fps_label (right)
        scrub_header = QWidget()
        scrub_header_layout = QHBoxLayout(scrub_header)
        pad_v = int(scale_by_dpi(6, self))
        scrub_header_layout.setContentsMargins(left, pad_v, left, 0)
        scrub_header_layout.setSpacing(0)
        self._time_label = QLabel("00:00 / 00:00    [ 0 / 0 ]")
        scrub_header_layout.addWidget(self._time_label)
        scrub_header_layout.addStretch()
        self._fps_label = QLabel(f"{command.DEFAULT_FPS:.0f}fps")
        scrub_header_layout.addWidget(self._fps_label)
        bottom_layout.addWidget(scrub_header)

        # seek slider
        self._seek_slider = _SeekSlider(Qt.Orientation.Horizontal)
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

        self._loop_bar = _LoopRangeBar(self)
        self._loop_bar.loop_in_changed.connect(self._on_slider_loop_in)
        self._loop_bar.loop_out_changed.connect(self._on_slider_loop_out)

        slider_wrap = QWidget()
        slider_wrap_layout = QVBoxLayout(slider_wrap)
        pad_slider_top = int(scale_by_dpi(2, self))
        pad_slider_bottom = int(scale_by_dpi(4, self))
        slider_wrap_layout.setContentsMargins(left, pad_slider_top, left, pad_slider_bottom)
        slider_wrap_layout.setSpacing(int(scale_by_dpi(4, self)))
        slider_wrap_layout.addWidget(self._seek_slider)
        slider_wrap_layout.addWidget(self._loop_bar)
        bottom_layout.addWidget(slider_wrap)

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

        # Separator helper
        sep_h = int(scale_by_dpi(18, self))
        sep_border = max(1, int(scale_by_dpi(1, self)))

        def _make_vline():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFixedHeight(sep_h)
            line.setStyleSheet(f"QFrame {{ color: #333333; border: none; border-left: {sep_border}px solid #333333; }}")
            return line

        # -- Left group: speed | vline | loop | sync --
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(h_spacing)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        sep_margin = int(scale_by_dpi(12, self))

        self._btn_ab = IconToggleButton(icon_on="ab_on", icon_off="ab_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_ab.setToolTip("A-B Loop")
        self._btn_ab.setIconSize(btn_icon_size)
        self._btn_ab.setFixedSize(btn_size, btn_size)
        self._btn_ab.setEnabled(False)
        self._btn_ab.toggled.connect(self._on_ab_toggled)
        left_layout.addWidget(self._btn_ab)

        self._btn_loop = IconToggleButton(icon_on="loop_on", icon_off="loop_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_loop.setToolTip("Loop")
        self._btn_loop.setIconSize(btn_icon_size)
        self._btn_loop.setFixedSize(btn_size, btn_size)
        self._btn_loop.setEnabled(False)
        self._btn_loop.toggled.connect(self._on_loop_toggled)
        left_layout.addWidget(self._btn_loop)

        self._btn_sync = IconToggleButton(icon_on="sync_on", icon_off="sync_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_sync.setToolTip("Maya Sync")
        self._btn_sync.setIconSize(btn_icon_size)
        self._btn_sync.setFixedSize(btn_size, btn_size)
        self._btn_sync.setEnabled(False)
        self._btn_sync.toggled.connect(self._on_sync_toggled)
        left_layout.addWidget(self._btn_sync)

        left_layout.addSpacing(sep_margin)
        left_layout.addWidget(_make_vline())
        left_layout.addSpacing(sep_margin)

        offset_label = QLabel("Offset")
        offset_label.setStyleSheet("color: #999999;")
        left_layout.addWidget(offset_label)

        left_layout.addSpacing(int(scale_by_dpi(4, self)))

        self._offset_spin = _OffsetSpinBox(self)
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

        ctrl_layout.addWidget(left_widget, stretch=1)

        # -- Center group: prev | play | next --
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(h_spacing)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._btn_prev = IconButton(icon_name="frame_prev", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_prev.setToolTip("Previous frame")
        self._btn_prev.setIconSize(btn_icon_size)
        self._btn_prev.setFixedSize(btn_size, btn_size)
        self._btn_prev.clicked.connect(self._on_step_backward)
        center_layout.addWidget(self._btn_prev)

        self._btn_play_pause = IconToggleButton(icon_on="pause", icon_off="play", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_play_pause.setToolTip("Play / Pause")
        self._btn_play_pause.setIconSize(play_btn_icon_size)
        self._btn_play_pause.setFixedSize(play_btn_size, play_btn_size)
        self._btn_play_pause.toggled.connect(self._on_play_pause_toggled)
        center_layout.addWidget(self._btn_play_pause)

        self._btn_next = IconButton(icon_name="frame_next", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_next.setToolTip("Next frame")
        self._btn_next.setIconSize(btn_icon_size)
        self._btn_next.setFixedSize(btn_size, btn_size)
        self._btn_next.clicked.connect(self._on_step_forward)
        center_layout.addWidget(self._btn_next)

        ctrl_layout.addWidget(center_widget, stretch=0)

        # -- Right group: mute | volume | vline --
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(h_spacing)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        right_layout.addStretch(1)

        self._btn_mute = IconToggleButton(icon_on="volume_off", icon_off="volume_on", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
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
        right_layout.addWidget(_make_vline())
        right_layout.addSpacing(sep_margin)

        self._options_btn = IconToolButton(
            icon_name="options",
            style_mode=IconButtonStyle.TRANSPARENT,
            auto_size=False,
            icon_dir=_ICONS_DIR,
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

        ctrl_layout.addWidget(right_widget, stretch=1)

        # Focus policy: all controls NoFocus so keyPressEvent handles shortcuts
        for widget in (
            self._seek_slider,
            self._loop_bar,
            self._btn_ab,
            self._btn_loop,
            self._btn_sync,
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_video(self, path: str) -> None:
        """Load a video file.

        Args:
            path: Absolute file path.
        """
        if self._player_core:
            self._player_core.clear_ab_loop()
            self.setCursor(Qt.CursorShape.WaitCursor)
            self._load_timer.start(10000)
            self._placeholder.hide()
            self._video_widget.show()
            self._player_core.load(path)
            self.setWindowTitle(f"Sync Player - {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Time display helper
    # ------------------------------------------------------------------

    def _update_time_display(self, position_ms: int, duration_ms: int) -> None:
        """Update the time label with time and frame numbers."""
        fps = self._player_core.fps if self._player_core else command.DEFAULT_FPS
        current_frame = command.ms_to_frame(position_ms, fps)
        total_frames = command.ms_to_frame(duration_ms, fps)
        time_text = f"{command.format_time(position_ms)} / {command.format_time(duration_ms)}"
        frame_text = f"[ {current_frame} / {total_frames} ]"
        display = f"{time_text}    {frame_text}"
        if self._player_core and self._player_core.has_ab_loop:
            a_text = command.format_time(self._player_core.loop_in)
            b_text = command.format_time(self._player_core.loop_out)
            a_frame = command.ms_to_frame(self._player_core.loop_in, fps)
            b_frame = command.ms_to_frame(self._player_core.loop_out, fps)
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
        path, _ = get_open_file_name(
            self,
            caption="Open Video",
            filter=command.VIDEO_FILTER,
        )
        if path:
            self.load_video(path)

    @error_handler
    def _on_play_pause_toggled(self, checked: bool):
        if self._player_core:
            if checked:
                self._player_core.play()
            else:
                self._player_core.pause()

    @error_handler
    def _on_step_forward(self):
        if self._player_core:
            self._player_core.step_forward()

    @error_handler
    def _on_step_backward(self):
        if self._player_core:
            self._player_core.step_backward()

    # ------------------------------------------------------------------
    # Signal handlers — seek
    # ------------------------------------------------------------------

    def _on_seek_pressed(self):
        self._seeking = True
        self._was_playing_before_seek = False
        self._was_muted_before_seek = False
        if self._player_core:
            self._was_playing_before_seek = get_playback_state(self._player_core.player) == "playing"
            self._was_muted_before_seek = self._btn_mute.isChecked()
            # Mute audio during scrub. The player is kept in playing
            # state so the WMF backend renders frames on setPosition,
            # but a short idle timer pauses it when the mouse stops
            # to prevent unwanted playback.
            if not self._was_muted_before_seek:
                self._player_core.set_muted(True)
            self._player_core.set_ab_enforcement(False)
            self._player_core.seek(self._seek_slider.value())
            self._player_core.play()
            self._scrub_pause_timer.start()
            self._update_time_display(self._seek_slider.value(), self._seek_slider.maximum())

    def _on_seek_released(self):
        self._scrub_pause_timer.stop()
        self._seeking = False
        if self._player_core:
            self._player_core.seek(self._seek_slider.value())
            if self._was_playing_before_seek:
                self._player_core.play()
            else:
                # Brief play to force the WMF backend to render the
                # final frame, then pause via the timer.
                self._player_core.play()
                self._scrub_pause_timer.start()
            if not self._was_muted_before_seek:
                self._player_core.set_muted(False)
            self._player_core.set_ab_enforcement(True)
            self._update_time_display(self._seek_slider.value(), self._seek_slider.maximum())

    def _on_seek_moved(self, position: int):
        if self._player_core:
            # Resume playing if the idle timer paused us.
            if get_playback_state(self._player_core.player) != "playing":
                self._player_core.play()
            self._player_core.seek(position)
            self._scrub_pause_timer.start()
        self._update_time_display(position, self._seek_slider.maximum())

    def _on_scrub_pause(self):
        """Pause the player when scrub goes idle (mouse stopped or click)."""
        if self._player_core and get_playback_state(self._player_core.player) == "playing":
            self._player_core.pause()

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
        if self._seeking or self._scrub_pause_timer.isActive():
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
        self._placeholder.show()

    def _on_load_timeout(self):
        self.unsetCursor()
        self._btn_ab.setEnabled(False)
        self._btn_loop.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._video_widget.hide()
        self._placeholder.show()
        om2.MGlobal.displayError("Sync Player: Video load timed out")

    # ------------------------------------------------------------------
    # Signal handlers — loop / speed / volume / mute
    # ------------------------------------------------------------------

    @error_handler
    def _on_ab_toggled(self, checked: bool):
        if not self._player_core:
            return
        if checked:
            if not self._player_core.has_media():
                self._btn_ab.blockSignals(True)
                self._btn_ab.setChecked(False)
                self._btn_ab.blockSignals(False)
                return
            self._player_core.set_loop_in(0)
            self._player_core.set_loop_out(self._player_core.duration)
        else:
            self._player_core.clear_ab_loop()

    @error_handler
    def _on_loop_toggled(self, checked: bool):
        if self._player_core:
            self._player_core.set_loop(checked)

    @error_handler
    def _on_speed_selected(self, index: int):
        if 0 <= index < len(_SPEED_VALUES):
            self._current_speed_index = index
            if self._player_core:
                self._player_core.set_playback_rate(_SPEED_VALUES[index])

    @error_handler
    def _on_volume_changed(self, value: int):
        if self._player_core:
            self._player_core.set_volume(value)

    @error_handler
    def _on_mute_toggled(self, checked: bool):
        if self._player_core:
            self._player_core.set_muted(checked)

    @error_handler
    def _on_offset_changed(self, value: int):
        if self._sync_controller:
            self._sync_controller.set_frame_offset(value)

    def _on_ab_loop_changed(self):
        if self._player_core:
            has_loop = self._player_core.has_ab_loop
            self._btn_ab.blockSignals(True)
            self._btn_ab.setChecked(has_loop)
            self._btn_ab.blockSignals(False)
            if has_loop:
                self._loop_bar.set_loop_markers(self._player_core.loop_in, self._player_core.loop_out, self._player_core.duration)
            else:
                self._loop_bar.set_loop_markers(None, None, self._player_core.duration)
            self._update_time_display(self._player_core.position, self._player_core.duration)

    def _on_slider_loop_in(self, ms: int):
        if self._player_core:
            self._player_core.set_loop_in(ms)

    def _on_slider_loop_out(self, ms: int):
        if self._player_core:
            self._player_core.set_loop_out(ms)

    def _populate_options_menu(self):
        self._options_menu.clear()
        current_label = _SPEED_OPTIONS[self._current_speed_index]
        speed_menu = self._options_menu.addMenu(f"Speed: {current_label}")
        speed_menu.setWindowFlags(speed_menu.windowFlags() | Qt.WindowType.NoDropShadowWindowHint)
        for i, label in enumerate(_SPEED_OPTIONS):
            speed_menu.addAction(label, lambda checked=False, idx=i: self._on_speed_selected(idx))

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
            if self._player_core:
                self._player_core.set_fps(maya_fps)
                video_fps = self._player_core.get_video_fps()
                if video_fps is not None and abs(video_fps - maya_fps) > 0.1:
                    cmds.warning(
                        f"Sync Player: Video FPS ({video_fps:.4g}) differs from Maya FPS ({maya_fps:.4g}). "
                        "Frame stepping and frame display may not match the video."
                    )
        else:
            self._sync_controller.disable()
        if self._player_core:
            self._player_core.set_ab_enforcement(not checked)
        self._set_sync_locked(checked)

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
    # Settings persistence
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "volume": self._volume_slider.value(),
            "muted": self._btn_mute.isChecked(),
            "frame_offset": self._offset_spin.value(),
            "speed_index": self._current_speed_index,
        }

    def _apply_settings(self, data: dict) -> None:
        volume = data.get("volume", 100)
        self._volume_slider.setValue(volume)
        if self._player_core:
            self._player_core.set_volume(volume)

        muted = data.get("muted", False)
        self._btn_mute.setChecked(muted)
        if self._player_core:
            self._player_core.set_muted(muted)

        frame_offset = data.get("frame_offset", 0)
        self._offset_spin.setValue(frame_offset)
        if self._sync_controller:
            self._sync_controller.set_frame_offset(frame_offset)

        speed_index = data.get("speed_index", _DEFAULT_SPEED_INDEX)
        self._on_speed_selected(speed_index)

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
        if self._sync_controller and self._sync_controller.is_enabled:
            super().keyPressEvent(event)
            return
        key = event.key()
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

    def closeEvent(self, event):
        self._save_settings()
        if self._sync_controller:
            self._sync_controller.cleanup()
        if self._player_core:
            self._player_core.stop()
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
