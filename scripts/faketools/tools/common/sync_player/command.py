"""Sync Player command layer.

Core playback logic using QMediaPlayer with PySide2/PySide6 compatibility,
plus Maya timeline sync via OpenMaya callbacks.
"""

from __future__ import annotations

import contextlib
from logging import getLogger

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ....lib_ui.qt_compat import (
    QMediaPlayer,
    QObject,
    QTimer,
    QUrl,
    Signal,
    connect_frame_signal,
    connect_state_changed,
    create_media_player,
    disconnect_frame_signal,
    get_playback_state,
    get_video_fps,
    is_pyside2,
    set_media_source,
    set_player_volume,
)

logger = getLogger(__name__)

VIDEO_FILTER = "Video Files (*.mov *.avi *.mp4 *.wmv);;All Files (*)"

DEFAULT_FPS = 24.0


def _media_status_name(status) -> str:
    """Get human-readable name for a QMediaPlayer.MediaStatus value."""
    if is_pyside2():
        return {
            QMediaPlayer.UnknownMediaStatus: "UnknownMediaStatus",
            QMediaPlayer.NoMedia: "NoMedia",
            QMediaPlayer.LoadingMedia: "LoadingMedia",
            QMediaPlayer.LoadedMedia: "LoadedMedia",
            QMediaPlayer.StalledMedia: "StalledMedia",
            QMediaPlayer.BufferingMedia: "BufferingMedia",
            QMediaPlayer.BufferedMedia: "BufferedMedia",
            QMediaPlayer.EndOfMedia: "EndOfMedia",
            QMediaPlayer.InvalidMedia: "InvalidMedia",
        }.get(status, f"Unknown({status})")
    ms = QMediaPlayer.MediaStatus
    return {
        ms.NoMedia: "NoMedia",
        ms.LoadingMedia: "LoadingMedia",
        ms.LoadedMedia: "LoadedMedia",
        ms.StalledMedia: "StalledMedia",
        ms.BufferingMedia: "BufferingMedia",
        ms.BufferedMedia: "BufferedMedia",
        ms.EndOfMedia: "EndOfMedia",
        ms.InvalidMedia: "InvalidMedia",
    }.get(status, f"Unknown({status})")


def format_time(ms: int) -> str:
    """Format milliseconds as MM:SS.

    Args:
        ms: Time in milliseconds.

    Returns:
        str: Formatted time string.
    """
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def ms_to_frame(ms: int, fps: float) -> int:
    """Convert milliseconds to a frame number.

    Args:
        ms: Time in milliseconds.
        fps: Frames per second.

    Returns:
        int: Frame number (0-based).
    """
    if ms <= 0 or fps <= 0:
        return 0
    return int(ms * fps / 1000.0)


class VideoPlayerCore(QObject):
    """Core video playback controller.

    Wraps QMediaPlayer with PySide2/PySide6 compatibility and provides
    a unified API for playback control.
    """

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(str)
    video_fps_detected = Signal(float)
    video_ready = Signal()
    load_failed = Signal(str)
    ab_loop_changed = Signal()

    def __init__(self, video_output, parent: QObject | None = None):
        super().__init__(parent)
        self._video_output = video_output
        self._loop = False
        self._fps = DEFAULT_FPS
        self._pending_pause = False
        self._loaded_path: str = ""
        self._retry_count = 0
        self._verifying = False

        self._frame_source: QObject | None = None
        self._stall_timer: QTimer | None = None
        self._verify_phase = 0  # 0=idle, 1=waiting-for-frame, 2=waiting-for-frame-zero

        self._loop_in: int | None = None
        self._loop_out: int | None = None
        self._ab_enforcement = True
        self._suppress_auto_play = False

        self._player: QMediaPlayer | None = None
        self._audio_output = None
        self._init_player()

    # ------------------------------------------------------------------
    # Player lifecycle
    # ------------------------------------------------------------------

    def _init_player(self) -> None:
        """Create a QMediaPlayer and wire up all signals."""
        player, audio_output = create_media_player(self)
        self._player = player
        self._audio_output = audio_output

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        connect_state_changed(self._player, self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        if is_pyside2():
            self._player.error.connect(self._on_player_error)
        else:
            self._player.errorOccurred.connect(self._on_player_error_occurred)

    def _recreate_player(self) -> None:
        """Destroy the current QMediaPlayer and create a fresh instance.

        Used to recover from WMF backend stalls where the player becomes
        permanently unresponsive despite correct API-level state transitions.
        """
        self._cleanup_verify()
        if self._player is not None:
            self._player.blockSignals(True)
            self._player.stop()
            self._player.deleteLater()

        logger.debug("Recreating QMediaPlayer instance")
        self._init_player()

    # ------------------------------------------------------------------
    # Media loading
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """Load a video file.

        Stops any current playback, sets the new source, then plays briefly
        so the player reaches a seekable (paused) state with the first frame.

        Args:
            path: Absolute file path.
        """
        # Reset retry counter when loading a new file (not an internal retry).
        if path != self._loaded_path:
            self._retry_count = 0
        self._loaded_path = path

        # Stop first to ensure a clean pipeline state.
        self._player.stop()

        # Reconnect video output to force Qt to refresh the rendering
        # pipeline.  On Windows the D3D11 video surface can become stale
        # between loads, resulting in audio/metadata working but no frames
        # being rendered (black screen).
        self._player.setVideoOutput(self._video_output)

        # Set pending_pause BEFORE set_media_source so that synchronous
        # BufferedMedia callbacks (common for cached local files) can see it.
        self._pending_pause = True
        self._cleanup_verify()

        logger.debug("load(): setting source (retry=%d): %s", self._retry_count, path)
        set_media_source(self._player, path)

        # If BufferedMedia already fired synchronously during set_media_source,
        # _pending_pause is now False and the player is paused at frame 0.
        if self._pending_pause:
            self._player.play()
            logger.debug("load(): play() called (async buffering)")
        else:
            logger.debug("load(): pending pause already completed (sync buffering)")

        logger.info("Loaded: %s", path)

    def has_media(self) -> bool:
        """Check if media is loaded."""
        if is_pyside2():
            return self._player.media().canonicalUrl() != QUrl()
        else:
            return self._player.source() != QUrl()

    def get_video_fps(self) -> float | None:
        """Get the loaded video's native frame rate.

        Returns:
            float | None: Video FPS if available, None otherwise.
        """
        return get_video_fps(self._player)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self) -> None:
        """Start playback."""
        self._player.play()

    def pause(self) -> None:
        """Pause playback."""
        self._player.pause()

    def stop(self) -> None:
        """Stop playback and reset position."""
        self._player.stop()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        state = get_playback_state(self._player)
        if state == "playing":
            self.pause()
        else:
            self.play()

    def step_forward(self) -> None:
        """Advance by one frame based on current FPS."""
        frame_ms = int(1000.0 / self._fps)
        new_pos = self._player.position() + frame_ms
        duration = self._player.duration()
        if duration > 0:
            new_pos = min(new_pos, duration)
        self._player.setPosition(new_pos)

    def step_backward(self) -> None:
        """Step back by one frame based on current FPS."""
        frame_ms = int(1000.0 / self._fps)
        new_pos = max(0, self._player.position() - frame_ms)
        self._player.setPosition(new_pos)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def seek(self, ms: int) -> None:
        """Seek to a position in milliseconds.

        Args:
            ms: Target position in milliseconds.
        """
        self._player.setPosition(ms)

    def set_playback_rate(self, rate: float) -> None:
        """Set playback speed multiplier.

        Args:
            rate: Speed multiplier (e.g. 0.5, 1.0, 2.0).
        """
        self._player.setPlaybackRate(rate)

    def set_volume(self, volume: int) -> None:
        """Set volume level.

        Args:
            volume: Volume 0-100.
        """
        target = self._audio_output if self._audio_output else self._player
        set_player_volume(target, volume)

    def set_muted(self, muted: bool) -> None:
        """Set mute state.

        Args:
            muted: True to mute.
        """
        if is_pyside2():
            self._player.setMuted(muted)
        else:
            if self._audio_output:
                self._audio_output.setMuted(muted)

    def set_loop(self, enabled: bool) -> None:
        """Enable or disable loop playback.

        Args:
            enabled: True to enable looping.
        """
        self._loop = enabled

    def set_fps(self, fps: float) -> None:
        """Set the FPS used for frame stepping.

        Args:
            fps: Frames per second.
        """
        if fps > 0:
            self._fps = fps

    @property
    def fps(self) -> float:
        """Current FPS setting."""
        return self._fps

    # ------------------------------------------------------------------
    # A-B Loop
    # ------------------------------------------------------------------

    def set_loop_in(self, ms: int | None) -> None:
        """Set the A (in) point for A-B loop.

        Args:
            ms: Position in milliseconds, or None to clear.
        """
        if ms is not None and self._loop_out is not None and ms > self._loop_out:
            ms, self._loop_out = self._loop_out, ms
        min_gap = int(1000.0 / self._fps)
        if ms is not None and self._loop_out is not None and self._loop_out - ms < min_gap:
            self._loop_out = ms + min_gap
        self._loop_in = ms
        self.ab_loop_changed.emit()

    def set_loop_out(self, ms: int | None) -> None:
        """Set the B (out) point for A-B loop.

        Args:
            ms: Position in milliseconds, or None to clear.
        """
        if ms is not None and self._loop_in is not None and ms < self._loop_in:
            self._loop_in, ms = ms, self._loop_in
        min_gap = int(1000.0 / self._fps)
        if ms is not None and self._loop_in is not None and ms - self._loop_in < min_gap:
            ms = self._loop_in + min_gap
        self._loop_out = ms
        self.ab_loop_changed.emit()

    def clear_ab_loop(self) -> None:
        """Clear A-B loop points."""
        self._loop_in = None
        self._loop_out = None
        self.ab_loop_changed.emit()

    def set_ab_enforcement(self, enabled: bool) -> None:
        """Enable or disable A-B loop position enforcement.

        Args:
            enabled: False to suspend enforcement (e.g. during Maya sync).
        """
        self._ab_enforcement = enabled

    def set_auto_play_suppressed(self, suppressed: bool) -> None:
        """Suppress automatic playback restart (e.g. EndOfMedia loop).

        Args:
            suppressed: True to prevent auto-play from media status callbacks.
        """
        self._suppress_auto_play = suppressed

    @property
    def is_loading(self) -> bool:
        """True while the player is in a load/verify transitional state."""
        return self._pending_pause or self._verifying

    @property
    def loop_in(self) -> int | None:
        """A (in) point in milliseconds."""
        return self._loop_in

    @property
    def loop_out(self) -> int | None:
        """B (out) point in milliseconds."""
        return self._loop_out

    @property
    def has_ab_loop(self) -> bool:
        """True if both A and B points are set."""
        return self._loop_in is not None and self._loop_out is not None

    @property
    def duration(self) -> int:
        """Current media duration in milliseconds."""
        return self._player.duration()

    @property
    def position(self) -> int:
        """Current playback position in milliseconds."""
        return self._player.position()

    @property
    def player(self) -> QMediaPlayer:
        """Access the underlying QMediaPlayer."""
        return self._player

    # ------------------------------------------------------------------
    # Internal signal handlers
    # ------------------------------------------------------------------

    def _on_position_changed(self, position: int) -> None:
        if self.has_ab_loop and self._ab_enforcement and position >= self._loop_out:
            if self._loop:
                self._player.setPosition(self._loop_in)
            else:
                self._player.setPosition(self._loop_out)
                self._player.pause()
        self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int) -> None:
        self.duration_changed.emit(duration)

    def _on_state_changed(self, player: QMediaPlayer) -> None:
        state = get_playback_state(player)
        self.state_changed.emit(state)

    def _on_media_status_changed(self, status: int) -> None:
        """Handle media status changes.

        - Pending pause: pause as soon as media is buffered after load().
        - Loop: restart from beginning when end of media is reached.
        """
        status_name = _media_status_name(status)
        state = get_playback_state(self._player)
        logger.debug(
            "MediaStatus: %s | playback: %s | pending_pause: %s | duration: %d",
            status_name,
            state,
            self._pending_pause,
            self._player.duration(),
        )

        # Detect buffered state to complete pending pause
        if is_pyside2():
            buffered = status == QMediaPlayer.BufferedMedia
            end_of_media = status == QMediaPlayer.EndOfMedia
        else:
            buffered = status == QMediaPlayer.MediaStatus.BufferedMedia
            end_of_media = status == QMediaPlayer.MediaStatus.EndOfMedia

        if self._pending_pause and buffered:
            self._pending_pause = False
            state = get_playback_state(self._player)
            if state == "playing":
                self._player.pause()
            self._player.setPosition(0)
            logger.debug("Pending pause completed (was %s): at position 0", state)
            video_fps = self.get_video_fps()
            if video_fps is not None:
                self.video_fps_detected.emit(video_fps)
            # Schedule backend health check.
            QTimer.singleShot(300, self._verify_backend)
            return

        if self._loop and end_of_media and not self._suppress_auto_play:
            start_pos = self._loop_in if self._loop_in is not None else 0
            self._player.setPosition(start_pos)
            self._player.play()

    # ------------------------------------------------------------------
    # Backend health check — detect WMF silent stall and retry once
    # ------------------------------------------------------------------

    def _verify_backend(self) -> None:
        """Play and wait for actual frame output to confirm the backend works.

        Uses QVideoProbe (PySide2) or QVideoSink.videoFrameChanged (PySide6)
        to detect real frame decoding instead of relying on position changes.
        Falls back to position-based detection if frame signals are unavailable.
        """
        if self._pending_pause or not self.has_media():
            return  # Another load started; skip stale verification.
        self._verifying = True
        self._verify_phase = 1

        self._frame_source = connect_frame_signal(self._player, self._video_output, self._on_verify_frame)

        self._player.play()

        # Timeout fallback — if no frame signal fires, check position instead.
        self._stall_timer = QTimer(self)
        self._stall_timer.setSingleShot(True)
        self._stall_timer.timeout.connect(self._on_verify_timeout)
        self._stall_timer.start(500)

    def _on_verify_frame(self, _frame) -> None:
        """Handle a decoded video frame during backend verification.

        Phase 1: First frame received proves the backend is alive.
                 Seek to 0 so the renderer decodes frame 0.
        Phase 2: A frame after the seek-to-0 confirms frame 0 is rendered.
                 Pause and emit video_ready.
        """
        if not self._verifying:
            return

        if self._verify_phase == 1:
            self._verify_phase = 2
            self._player.setPosition(0)
            logger.debug("Backend verified: frame decoded, seeking to 0")
        elif self._verify_phase == 2:
            self._cleanup_verify()
            self._player.pause()
            self._player.setPosition(0)
            logger.debug("Load complete: frame 0 rendered and paused")
            self.video_ready.emit()

    def _on_verify_timeout(self) -> None:
        """Handle verification timeout — frame signal did not fire.

        Falls back to position-based check: if position advanced the backend
        is likely working (frame signal unsupported); otherwise stall/retry.
        """
        if not self._verifying:
            return
        self._cleanup_verify()

        pos = self._player.position()
        self._player.pause()

        if pos > 0:
            # Position advanced but no frame signal — proceed anyway.
            self._player.setPosition(0)
            logger.warning("Verify timeout but pos=%d; frame signal may not be supported", pos)
            self.video_ready.emit()
            return

        # Position stuck at 0 — backend is stalled.
        if self._retry_count < 1:
            self._retry_count += 1
            logger.warning(
                "Backend stall detected (pos=0), recreating player and retrying load (%d): %s",
                self._retry_count,
                self._loaded_path,
            )
            self._recreate_player()
            self.load(self._loaded_path)
        else:
            msg = f"Sync Player: Failed to load video after retry: {self._loaded_path}"
            logger.error(
                "Backend stall persists after player recreation: %s",
                self._loaded_path,
            )
            om2.MGlobal.displayError(msg)
            self.load_failed.emit(msg)

    def _cleanup_verify(self) -> None:
        """Disconnect frame signal and cancel stall timer."""
        self._verifying = False
        self._verify_phase = 0
        if self._frame_source is not None:
            disconnect_frame_signal(self._frame_source, self._on_verify_frame)
            self._frame_source = None
        if self._stall_timer is not None:
            self._stall_timer.stop()
            self._stall_timer.deleteLater()
            self._stall_timer = None

    def _on_player_error(self, error) -> None:
        """Handle QMediaPlayer error (PySide2)."""
        msg = f"Sync Player: {self._player.errorString()}"
        logger.error("Player error: %s - %s", error, self._player.errorString())
        om2.MGlobal.displayError(msg)
        self.load_failed.emit(msg)

    def _on_player_error_occurred(self, error, message: str) -> None:
        """Handle QMediaPlayer errorOccurred (PySide6)."""
        msg = f"Sync Player: {message}"
        logger.error("Player error: %s - %s", error, message)
        om2.MGlobal.displayError(msg)
        self.load_failed.emit(msg)


# ----------------------------------------------------------------------
# Maya FPS mapping
# ----------------------------------------------------------------------

_TIME_UNIT_TO_FPS: dict[str, float] = {
    "game": 15.0,
    "film": 24.0,
    "pal": 25.0,
    "ntsc": 30.0,
    "show": 48.0,
    "palf": 50.0,
    "ntscf": 60.0,
    "2fps": 2.0,
    "3fps": 3.0,
    "4fps": 4.0,
    "5fps": 5.0,
    "6fps": 6.0,
    "8fps": 8.0,
    "10fps": 10.0,
    "12fps": 12.0,
    "16fps": 16.0,
    "20fps": 20.0,
    "23.976fps": 23.976,
    "29.97fps": 29.97,
    "29.97df": 29.97,
    "40fps": 40.0,
    "47.952fps": 47.952,
    "59.94fps": 59.94,
    "75fps": 75.0,
    "80fps": 80.0,
    "100fps": 100.0,
    "120fps": 120.0,
    "125fps": 125.0,
    "150fps": 150.0,
    "200fps": 200.0,
    "240fps": 240.0,
    "250fps": 250.0,
    "300fps": 300.0,
    "375fps": 375.0,
    "400fps": 400.0,
    "500fps": 500.0,
    "600fps": 600.0,
    "750fps": 750.0,
    "1000fps": 1000.0,
    "1200fps": 1200.0,
    "1500fps": 1500.0,
    "2000fps": 2000.0,
    "3000fps": 3000.0,
    "6000fps": 6000.0,
    "44100fps": 44100.0,
    "48000fps": 48000.0,
}


def get_maya_fps() -> float:
    """Get the current Maya scene FPS.

    Returns:
        float: Frames per second.
    """
    unit = cmds.currentUnit(query=True, time=True)
    return _TIME_UNIT_TO_FPS.get(unit, DEFAULT_FPS)


# ----------------------------------------------------------------------
# Maya timeline sync
# ----------------------------------------------------------------------


class MayaSyncController:
    """Synchronizes video playback position with Maya's timeline.

    Uses MDGMessage.addTimeChangeCallback to seek the video to the
    corresponding position on every Maya time change. The video player
    is kept paused at all times — only the position is updated via
    seek, ensuring frame-accurate sync without risking auto-play from
    the WMF backend.
    """

    def __init__(self, player_core: VideoPlayerCore):
        self._player_core = player_core
        self._fps = DEFAULT_FPS
        self._callbacks: list[int] = []
        self._frame_offset: int = 0
        self._pending_seek_ms: int | None = None
        self._throttle_timer = QTimer()
        self._throttle_timer.setInterval(30)
        self._throttle_timer.timeout.connect(self._apply_pending_seek)

    def _frame_to_ms(self, frame: float) -> int:
        """Convert a frame number to milliseconds.

        Seeks to the centre of the frame's time window to avoid
        boundary ambiguity in the media backend.

        Args:
            frame: Frame number.

        Returns:
            int: Position in milliseconds.
        """
        adjusted = frame - self._frame_offset
        return max(0, int(round((adjusted + 0.5) / self._fps * 1000.0)))

    def set_fps(self, fps: float) -> None:
        """Set FPS for frame-to-millisecond conversion.

        Args:
            fps: Frames per second.
        """
        if fps > 0:
            self._fps = fps

    def set_frame_offset(self, offset: int) -> None:
        """Set frame offset for sync mapping.

        Args:
            offset: Frame offset (e.g. 100 maps Maya frame 101 to video frame 1).
        """
        self._frame_offset = offset

    def enable(self) -> None:
        """Start syncing video to Maya timeline.

        Pauses the video and seeks to the current Maya time.
        """
        self.disable()

        self._player_core.pause()
        self._player_core.set_auto_play_suppressed(True)

        cb_time = om2.MDGMessage.addTimeChangeCallback(self._on_time_changed)
        self._callbacks.append(cb_time)

        current_frame = cmds.currentTime(query=True)
        self._player_core.seek(self._frame_to_ms(current_frame))
        self._throttle_timer.start()

        logger.info("Maya sync enabled (%.2f fps)", self._fps)

    def disable(self) -> None:
        """Stop syncing and remove all callbacks."""
        self._throttle_timer.stop()
        self._pending_seek_ms = None
        self._player_core.set_auto_play_suppressed(False)
        for cb in self._callbacks:
            with contextlib.suppress(RuntimeError):
                om2.MMessage.removeCallback(cb)
        self._callbacks.clear()
        logger.info("Maya sync disabled")

    def cleanup(self) -> None:
        """Ensure all callbacks are removed. Call on window close."""
        self.disable()

    @property
    def is_enabled(self) -> bool:
        """Check if sync is active."""
        return len(self._callbacks) > 0

    def _on_time_changed(self, mtime, _client_data) -> None:
        """Called every time Maya's current time changes.

        Stores the target position for the throttle timer to apply.
        Direct seeking is avoided to prevent overwhelming the WMF
        decoder during rapid timeline scrubbing.
        """
        self._pending_seek_ms = self._frame_to_ms(mtime.value)

    def _apply_pending_seek(self) -> None:
        """Apply the latest pending seek position (called by throttle timer)."""
        if self._pending_seek_ms is not None:
            self._player_core.seek(self._pending_seek_ms)
            self._pending_seek_ms = None
