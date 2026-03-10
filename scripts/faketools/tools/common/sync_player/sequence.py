"""Image sequence playback core for Sync Player.

Provides SequencePlayerCore with the same signal/method interface as
VideoPlayerCore, plus supporting classes for image display, frame caching,
and ffmpeg-based video-to-JPEG extraction.
"""

from __future__ import annotations

from collections import OrderedDict
import contextlib
import json
from logging import getLogger
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from ....lib_ui.qt_compat import (
    QColor,
    QImage,
    QObject,
    QPainter,
    QRect,
    QThread,
    QTimer,
    QWidget,
    Signal,
)

logger = getLogger(__name__)

DEFAULT_FPS = 24.0
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_NUMBER_PATTERN = re.compile(r"(\d+)")


# ----------------------------------------------------------------------
# FrameCache — LRU OrderedDict
# ----------------------------------------------------------------------


class FrameCache:
    """LRU cache for decoded image frames.

    Args:
        capacity: Maximum number of frames to cache.
    """

    def __init__(self, capacity: int = 50):
        self._capacity = max(1, capacity)
        self._cache: OrderedDict[int, QImage] = OrderedDict()

    def get(self, frame: int) -> QImage | None:
        """Retrieve a cached frame, moving it to most-recently-used.

        Args:
            frame: Frame number.

        Returns:
            QImage or None if not cached.
        """
        if frame in self._cache:
            self._cache.move_to_end(frame)
            return self._cache[frame]
        return None

    def put(self, frame: int, image: QImage) -> None:
        """Store a frame, evicting oldest if at capacity.

        Args:
            frame: Frame number.
            image: Decoded frame as QImage.
        """
        if frame in self._cache:
            self._cache.move_to_end(frame)
            self._cache[frame] = image
            return
        if len(self._cache) >= self._capacity:
            self._cache.popitem(last=False)
        self._cache[frame] = image

    def contains(self, frame: int) -> bool:
        """Check if a frame is cached."""
        return frame in self._cache

    def clear(self) -> None:
        """Remove all cached frames."""
        self._cache.clear()

    def prefetch_range(self, center: int, radius: int = 12) -> list[int]:
        """Get list of uncached frame numbers around center.

        Args:
            center: Center frame number.
            radius: Number of frames around center to consider.

        Returns:
            list[int]: Frame numbers not yet cached.
        """
        needed = []
        for offset in range(radius + 1):
            for f in (center + offset, center - offset):
                if f >= 0 and f not in self._cache:
                    needed.append(f)
        return needed


# ----------------------------------------------------------------------
# Folder scanning
# ----------------------------------------------------------------------


def _scan_image_folder(folder_path: str) -> list[Path]:
    """Scan folder for numbered image files and sort by frame number.

    Uses the last number group in the filename stem as the sort key.

    Args:
        folder_path: Path to folder containing image sequence.

    Returns:
        list[Path]: Sorted list of image file paths.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return []

    images: list[tuple[int, Path]] = []
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS:
            match = _NUMBER_PATTERN.findall(f.stem)
            if match:
                frame_num = int(match[-1])
                images.append((frame_num, f))

    images.sort(key=lambda x: x[0])
    return [p for _, p in images]


# ----------------------------------------------------------------------
# ffprobe
# ----------------------------------------------------------------------


class _ProbeResult:
    """Parsed ffprobe metadata."""

    __slots__ = ("fps", "total_frames", "width", "height")

    def __init__(self, fps: float, total_frames: int, width: int, height: int):
        self.fps = fps
        self.total_frames = total_frames
        self.width = width
        self.height = height


def _probe_video(path: str) -> _ProbeResult | None:
    """Extract video metadata using ffprobe.

    Args:
        path: Video file path.

    Returns:
        _ProbeResult or None on failure.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            logger.error("ffprobe failed: %s", result.stderr)
            return None

        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))

                fps = DEFAULT_FPS
                avg_rate = stream.get("avg_frame_rate", "")
                r_rate = stream.get("r_frame_rate", "")
                rate_text = avg_rate if avg_rate and avg_rate != "0/0" else r_rate
                if "/" in rate_text:
                    num, den = rate_text.split("/")
                    if float(den) > 0:
                        fps = float(num) / float(den)
                elif rate_text:
                    fps = float(rate_text)
                if fps <= 0:
                    fps = DEFAULT_FPS

                nb_frames = stream.get("nb_frames")
                if nb_frames and nb_frames != "N/A":
                    total_frames = int(nb_frames)
                else:
                    duration = float(data.get("format", {}).get("duration", 0))
                    total_frames = max(1, int(duration * fps))

                return _ProbeResult(fps, total_frames, width, height)
    except Exception as e:
        logger.error("ffprobe error: %s", e)
    return None


# ----------------------------------------------------------------------
# ImageDisplayWidget
# ----------------------------------------------------------------------


class ImageDisplayWidget(QWidget):
    """Widget that displays QImage frames via paintEvent with aspect-ratio fit."""

    open_requested = Signal()

    def __init__(self, focus_widget: QWidget | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._frame: QImage | None = None
        self._focus_widget = focus_widget
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#0D0D0D"))
        self.setPalette(palette)

    def set_frame(self, image: QImage) -> None:
        """Set the current frame to display.

        Args:
            image: The decoded frame as QImage.
        """
        self._frame = image
        self.update()

    def clear_frame(self) -> None:
        """Clear the displayed frame."""
        self._frame = None
        self.update()

    def paintEvent(self, event) -> None:
        if self._frame is None or self._frame.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        img_w, img_h = self._frame.width(), self._frame.height()
        wgt_w, wgt_h = self.width(), self.height()
        if img_w <= 0 or img_h <= 0:
            painter.end()
            return

        scale = min(wgt_w / img_w, wgt_h / img_h)
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        x = (wgt_w - draw_w) // 2
        y = (wgt_h - draw_h) // 2
        painter.drawImage(QRect(x, y, draw_w, draw_h), self._frame)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if self._focus_widget is not None:
            self._focus_widget.setFocus()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.open_requested.emit()


# ----------------------------------------------------------------------
# FfmpegExtractor — QThread for video → JPEG sequence conversion
# ----------------------------------------------------------------------


class FfmpegExtractor(QThread):
    """Extracts JPEG frames from a video file using ffmpeg.

    Signals:
        progress_changed(current, total): Extraction progress.
        extraction_finished(output_folder): Path to extracted frames.
        extraction_failed(error_message): Extraction error.
    """

    progress_changed = Signal(int, int)
    extraction_finished = Signal(str)
    extraction_failed = Signal(str)

    def __init__(self, video_path: str, parent: QObject | None = None):
        super().__init__(parent)
        self._video_path = video_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._output_dir: str = ""
        self._total_frames = 0

    def run(self) -> None:
        """Probe video then extract all frames as JPEG sequence."""
        probe = _probe_video(self._video_path)
        if probe is None:
            self.extraction_failed.emit(f"Failed to probe video: {self._video_path}")
            return

        self._total_frames = probe.total_frames

        self._output_dir = tempfile.mkdtemp(prefix="sync_player_seq_")
        output_pattern = str(Path(self._output_dir) / "frame_%06d.jpg")

        cmd = [
            "ffmpeg",
            "-i",
            self._video_path,
            "-qscale:v",
            "2",
            "-start_number",
            "0",
            output_pattern,
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            frame_pattern = re.compile(r"frame=\s*(\d+)")
            for line in self._process.stderr:
                if self._cancelled:
                    break
                m = frame_pattern.search(line)
                if m:
                    current = int(m.group(1))
                    self.progress_changed.emit(current, self._total_frames)

            self._process.wait(timeout=5)

            if self._cancelled:
                shutil.rmtree(self._output_dir, ignore_errors=True)
                return

            if self._process.returncode != 0:
                shutil.rmtree(self._output_dir, ignore_errors=True)
                self.extraction_failed.emit(f"ffmpeg exited with code {self._process.returncode}")
                return

            self.extraction_finished.emit(self._output_dir)

        except Exception as e:
            shutil.rmtree(self._output_dir, ignore_errors=True)
            self.extraction_failed.emit(str(e))
        finally:
            self._process = None

    def cancel(self) -> None:
        """Cancel the extraction."""
        self._cancelled = True
        if self._process is not None:
            with contextlib.suppress(OSError):
                self._process.kill()


# ----------------------------------------------------------------------
# SequencePlayerCore — ms-based API matching VideoPlayerCore
# ----------------------------------------------------------------------


class SequencePlayerCore(QObject):
    """Image sequence player with the same signal/method interface as VideoPlayerCore.

    Internally frame-based, but exposes an ms-based API for transparent
    interchangeability with VideoPlayerCore.
    """

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(str)
    video_fps_detected = Signal(float)
    video_ready = Signal()
    load_failed = Signal(str)
    ab_loop_changed = Signal()

    def __init__(self, display: ImageDisplayWidget, parent: QObject | None = None):
        super().__init__(parent)
        self._display = display
        self._fps = DEFAULT_FPS
        self._playback_rate = 1.0
        self._current_frame = 0
        self._playing = False
        self._loop = False
        self._file_paths: list[Path] = []

        self._loop_in: int | None = None
        self._loop_out: int | None = None
        self._ab_enforcement = True
        self._suppress_auto_play = False

        self._cache = FrameCache(capacity=50)

        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._advance_frame)

    # ------------------------------------------------------------------
    # Frame / ms conversion
    # ------------------------------------------------------------------

    def _frame_to_ms(self, frame: int) -> int:
        if self._fps <= 0:
            return 0
        # +0.5 seeks to the centre of the frame's time window so that
        # int(ms * fps / 1000) round-trips back to the correct frame.
        return int(round((frame + 0.5) / self._fps * 1000.0))

    def _ms_to_frame(self, ms: int) -> int:
        if ms <= 0 or self._fps <= 0:
            return 0
        return int(ms * self._fps / 1000.0)

    # ------------------------------------------------------------------
    # Media loading
    # ------------------------------------------------------------------

    def load(self, folder_path: str) -> None:
        """Load an image sequence from a folder.

        Args:
            folder_path: Path to folder containing numbered images.
        """
        self.stop()
        self._cache.clear()
        self._file_paths = _scan_image_folder(folder_path)

        if not self._file_paths:
            self.load_failed.emit(f"No image files found in {folder_path}")
            return

        self._current_frame = 0
        total_ms = self._frame_to_ms(len(self._file_paths))
        self.video_fps_detected.emit(self._fps)
        self.duration_changed.emit(total_ms)

        self._show_frame(0)
        self.video_ready.emit()
        logger.info("SequencePlayerCore: loaded %d images from %s", len(self._file_paths), folder_path)

    def has_media(self) -> bool:
        """Check if a sequence is loaded."""
        return len(self._file_paths) > 0

    def get_video_fps(self) -> float | None:
        """Return None — no native video FPS for image sequences."""
        return None

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self) -> None:
        """Start playback."""
        if not self._file_paths:
            return
        self._playing = True
        self._update_timer_interval()
        self._play_timer.start()
        self.state_changed.emit("playing")

    def pause(self) -> None:
        """Pause playback."""
        self._playing = False
        self._play_timer.stop()
        self.state_changed.emit("paused")

    def stop(self) -> None:
        """Stop playback and reset to frame 0."""
        self._playing = False
        self._play_timer.stop()
        self._current_frame = 0
        self._display.clear_frame()
        self.state_changed.emit("stopped")

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self._playing:
            self.pause()
        else:
            self.play()

    def seek(self, ms: int) -> None:
        """Seek to a position in milliseconds.

        Args:
            ms: Target position in milliseconds.
        """
        frame = self._ms_to_frame(ms)
        total = len(self._file_paths)
        frame = max(0, min(frame, total - 1)) if total > 0 else 0
        self._current_frame = frame
        self._show_frame(frame)
        self.position_changed.emit(self._frame_to_ms(frame))

    def step_forward(self) -> None:
        """Advance by one frame."""
        total = len(self._file_paths)
        if total <= 0:
            return
        new_frame = min(self._current_frame + 1, total - 1)
        self._current_frame = new_frame
        self._show_frame(new_frame)
        self.position_changed.emit(self._frame_to_ms(new_frame))

    def step_backward(self) -> None:
        """Step back by one frame."""
        if not self._file_paths:
            return
        new_frame = max(0, self._current_frame - 1)
        self._current_frame = new_frame
        self._show_frame(new_frame)
        self.position_changed.emit(self._frame_to_ms(new_frame))

    def get_playback_state(self) -> str:
        """Get current playback state.

        Returns:
            str: "playing", "paused", or "stopped".
        """
        if self._playing:
            return "playing"
        if self._file_paths:
            return "paused"
        return "stopped"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def set_playback_rate(self, rate: float) -> None:
        """Set playback speed multiplier.

        Args:
            rate: Speed multiplier (e.g. 0.5, 1.0, 2.0).
        """
        self._playback_rate = max(0.1, rate)
        if self._playing:
            self._update_timer_interval()

    def set_volume(self, volume: int) -> None:
        """No-op — image sequences have no audio."""

    def set_muted(self, muted: bool) -> None:
        """No-op — image sequences have no audio."""

    def set_loop(self, enabled: bool) -> None:
        """Enable or disable loop playback.

        Args:
            enabled: True to enable looping.
        """
        self._loop = enabled

    def set_fps(self, fps: float) -> None:
        """Set the FPS for playback timing.

        Args:
            fps: Frames per second.
        """
        if fps > 0:
            self._fps = fps
            if self._playing:
                self._update_timer_interval()

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
        """Enable or disable A-B loop position enforcement."""
        self._ab_enforcement = enabled

    def set_auto_play_suppressed(self, suppressed: bool) -> None:
        """Suppress automatic playback restart."""
        self._suppress_auto_play = suppressed

    @property
    def is_loading(self) -> bool:
        """Always False for image sequences."""
        return False

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
        """Total duration in milliseconds."""
        return self._frame_to_ms(len(self._file_paths))

    @property
    def position(self) -> int:
        """Current position in milliseconds."""
        return self._frame_to_ms(self._current_frame)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release resources."""
        self._play_timer.stop()
        self._cache.clear()
        self._file_paths.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_timer_interval(self) -> None:
        interval = max(1, int(1000.0 / self._fps / self._playback_rate))
        self._play_timer.setInterval(interval)

    def _advance_frame(self) -> None:
        """Advance to next frame during playback."""
        total = len(self._file_paths)
        if total <= 0:
            return

        next_frame = self._current_frame + 1
        current_ms = self._frame_to_ms(next_frame)

        # A-B loop enforcement
        if self.has_ab_loop and self._ab_enforcement and current_ms >= self._loop_out:
            if self._loop:
                next_frame = self._ms_to_frame(self._loop_in)
            else:
                next_frame = self._ms_to_frame(self._loop_out)
                self.pause()
                self._current_frame = min(next_frame, total - 1)
                self._show_frame(self._current_frame)
                self.position_changed.emit(self._frame_to_ms(self._current_frame))
                return

        # End of sequence
        if next_frame >= total:
            if self._loop:
                start_frame = self._ms_to_frame(self._loop_in) if self._loop_in is not None else 0
                next_frame = start_frame
            elif not self._suppress_auto_play:
                self.pause()
                return
            else:
                return

        self._current_frame = next_frame
        self._show_frame(next_frame)
        self.position_changed.emit(self._frame_to_ms(next_frame))

    def _show_frame(self, frame: int) -> None:
        """Load and display a frame.

        Args:
            frame: Frame index into _file_paths.
        """
        if frame < 0 or frame >= len(self._file_paths):
            return

        cached = self._cache.get(frame)
        if cached is not None:
            self._display.set_frame(cached)
            return

        path = self._file_paths[frame]
        image = QImage(str(path))
        if image.isNull():
            logger.warning("SequencePlayerCore: failed to load %s", path)
            return

        self._cache.put(frame, image)
        self._display.set_frame(image)
