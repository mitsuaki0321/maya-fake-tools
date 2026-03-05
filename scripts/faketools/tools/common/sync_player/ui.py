"""Sync Player UI layer.

Full-featured playback window with seek slider, transport controls,
volume, speed, loop toggle, and Maya sync toggle.
"""

from __future__ import annotations

from logging import getLogger
import os
from pathlib import Path

from ....lib_ui import (
    BaseMainWindow,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
)
from ....lib_ui.base_window import get_margins, get_spacing
from ....lib_ui.qt_compat import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    Qt,
    QVideoWidget,
    QWidget,
    get_open_file_name,
)
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.icon_button import IconButton, IconButtonStyle, IconToggleButton
from . import command

logger = getLogger(__name__)

_instance = None

_ICONS_DIR = str(Path(__file__).parent / "icons")

_SPEED_OPTIONS = ["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]
_SPEED_VALUES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
_DEFAULT_SPEED_INDEX = 3  # 1.0x


class _VideoDropWidget(QVideoWidget):
    """QVideoWidget with drag-and-drop support."""

    def __init__(self, parent: MainWindow):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._main_window = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(command.SUPPORTED_FORMATS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(command.SUPPORTED_FORMATS):
                self._main_window.load_video(path)
                return


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
        self._was_paused_before_seek = False
        self._settings = ToolSettingsManager(tool_name="sync_player", category="common")

        self._setup_ui()

        width, height = get_relative_size(self, width_ratio=3.0, height_ratio=2.5)
        self.resize(width, height)
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the full UI."""
        spacing = get_spacing(self, direction="vertical")
        self.central_layout.setSpacing(int(spacing * 0.5))

        # Video display (with D&D)
        self._video_widget = _VideoDropWidget(self)
        self.central_layout.addWidget(self._video_widget, stretch=1)

        # Player core + sync controller
        self._player_core = command.VideoPlayerCore(self._video_widget, parent=self)
        self._player_core.position_changed.connect(self._on_position_changed)
        self._player_core.duration_changed.connect(self._on_duration_changed)
        self._player_core.state_changed.connect(self._on_state_changed)
        self._sync_controller = command.MayaSyncController(self._player_core)

        # Seek slider
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.central_layout.addWidget(self._seek_slider)

        # Time row: "00:00 / 00:00" left, "24fps" right
        time_row = QWidget()
        time_layout = QHBoxLayout(time_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        self._time_label = QLabel("00:00 / 00:00")
        time_layout.addWidget(self._time_label)
        time_layout.addStretch()
        self._fps_label = QLabel(f"{command.DEFAULT_FPS:.0f}fps")
        time_layout.addWidget(self._fps_label)
        self.central_layout.addWidget(time_row)

        # Controls row
        controls = QWidget()
        ctrl_layout = QHBoxLayout(controls)
        left, top, right, bottom = get_margins(self)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(int(get_spacing(self, direction="horizontal") * 0.3))

        # -- Left: transport buttons --
        self._btn_prev = IconButton(icon_name="frame_prev", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_prev.setToolTip("Previous frame")
        self._btn_prev.clicked.connect(self._on_step_backward)
        ctrl_layout.addWidget(self._btn_prev)

        self._btn_play_pause = IconToggleButton(icon_on="pause", icon_off="play", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_play_pause.setToolTip("Play / Pause")
        self._btn_play_pause.toggled.connect(self._on_play_pause_toggled)
        ctrl_layout.addWidget(self._btn_play_pause)

        self._btn_next = IconButton(icon_name="frame_next", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_next.setToolTip("Next frame")
        self._btn_next.clicked.connect(self._on_step_forward)
        ctrl_layout.addWidget(self._btn_next)

        # -- Middle: loop + speed --
        ctrl_layout.addSpacing(int(left * 0.5))

        self._btn_loop = IconToggleButton(icon_on="loop_on", icon_off="loop_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_loop.setToolTip("Loop")
        self._btn_loop.toggled.connect(self._on_loop_toggled)
        ctrl_layout.addWidget(self._btn_loop)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(_SPEED_OPTIONS)
        self._speed_combo.setCurrentIndex(_DEFAULT_SPEED_INDEX)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        ctrl_layout.addWidget(self._speed_combo)

        ctrl_layout.addStretch()

        # -- Right: volume + sync --
        self._btn_mute = IconToggleButton(icon_on="volume_off", icon_off="volume_on", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_mute.setToolTip("Mute")
        self._btn_mute.toggled.connect(self._on_mute_toggled)
        ctrl_layout.addWidget(self._btn_mute)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setFixedWidth(int(get_relative_size(self, width_ratio=0.6)[0]))
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_layout.addWidget(self._volume_slider)

        ctrl_layout.addSpacing(int(left * 0.5))

        self._btn_sync = IconToggleButton(icon_on="sync_on", icon_off="sync_off", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_ICONS_DIR)
        self._btn_sync.setToolTip("Maya Sync")
        self._btn_sync.toggled.connect(self._on_sync_toggled)
        ctrl_layout.addWidget(self._btn_sync)

        self.central_layout.addWidget(controls)

        # Open button (file dialog fallback)
        self._add_open_action()

    def _add_open_action(self):
        """Add File > Open menu action."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        open_action = file_menu.addAction("Open Video...")
        open_action.triggered.connect(self._on_open)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_video(self, path: str) -> None:
        """Load a video file.

        Args:
            path: Absolute file path.
        """
        if self._player_core:
            self._player_core.load(path)
            self.setWindowTitle(f"Sync Player - {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Signal handlers — transport
    # ------------------------------------------------------------------

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
        self._was_paused_before_seek = False
        if self._player_core:
            from ....lib_ui.qt_compat import get_playback_state

            if get_playback_state(self._player_core.player) != "playing":
                self._was_paused_before_seek = True
                self._player_core.set_muted(True)
                self._player_core.play()

    def _on_seek_released(self):
        self._seeking = False
        if self._player_core:
            self._player_core.seek(self._seek_slider.value())
            if self._was_paused_before_seek:
                self._player_core.pause()
                self._player_core.set_muted(self._btn_mute.isChecked())

    def _on_seek_moved(self, position: int):
        if self._player_core:
            self._player_core.seek(position)
        self._time_label.setText(f"{command.format_time(position)} / {command.format_time(self._seek_slider.maximum())}")

    # ------------------------------------------------------------------
    # Signal handlers — player feedback
    # ------------------------------------------------------------------

    def _on_position_changed(self, position: int):
        if not self._seeking:
            self._seek_slider.setValue(position)
            self._time_label.setText(f"{command.format_time(position)} / {command.format_time(self._seek_slider.maximum())}")

    def _on_duration_changed(self, duration: int):
        self._seek_slider.setRange(0, duration)
        self._time_label.setText(f"{command.format_time(0)} / {command.format_time(duration)}")

    def _on_state_changed(self, state: str):
        is_playing = state == "playing"
        self._btn_play_pause.blockSignals(True)
        self._btn_play_pause.setChecked(is_playing)
        self._btn_play_pause.blockSignals(False)

    # ------------------------------------------------------------------
    # Signal handlers — loop / speed / volume / mute
    # ------------------------------------------------------------------

    @error_handler
    def _on_loop_toggled(self, checked: bool):
        if self._player_core:
            self._player_core.set_loop(checked)

    @error_handler
    def _on_speed_changed(self, index: int):
        if self._player_core and 0 <= index < len(_SPEED_VALUES):
            self._player_core.set_playback_rate(_SPEED_VALUES[index])

    @error_handler
    def _on_volume_changed(self, value: int):
        if self._player_core:
            self._player_core.set_volume(value)

    @error_handler
    def _on_mute_toggled(self, checked: bool):
        if self._player_core:
            self._player_core.set_muted(checked)

    # ------------------------------------------------------------------
    # Signal handlers — sync
    # ------------------------------------------------------------------

    @error_handler
    def _on_sync_toggled(self, checked: bool):
        if not self._sync_controller:
            return
        if checked:
            fps = command.get_maya_fps()
            self._sync_controller.set_fps(fps)
            self._sync_controller.enable()
            if self._player_core:
                self._player_core.set_fps(fps)
            self._fps_label.setText(f"{fps:.4g}fps")
            self._seek_slider.setEnabled(False)
        else:
            self._sync_controller.disable()
            self._seek_slider.setEnabled(True)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "volume": self._volume_slider.value(),
            "muted": self._btn_mute.isChecked(),
            "loop": self._btn_loop.isChecked(),
            "speed_index": self._speed_combo.currentIndex(),
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

        loop = data.get("loop", False)
        self._btn_loop.setChecked(loop)
        if self._player_core:
            self._player_core.set_loop(loop)

        speed_index = data.get("speed_index", _DEFAULT_SPEED_INDEX)
        if 0 <= speed_index < len(_SPEED_VALUES):
            self._speed_combo.setCurrentIndex(speed_index)
            if self._player_core:
                self._player_core.set_playback_rate(_SPEED_VALUES[speed_index])

    def _restore_settings(self):
        data = self._settings.load_settings("default")
        if data:
            self._apply_settings(data)

    def _save_settings(self):
        self._settings.save_settings(self._collect_settings(), "default")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            if self._player_core:
                self._player_core.toggle_play_pause()
            return
        if key == Qt.Key.Key_Right:
            if self._player_core:
                self._player_core.step_forward()
            return
        if key == Qt.Key.Key_Left:
            if self._player_core:
                self._player_core.step_backward()
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
