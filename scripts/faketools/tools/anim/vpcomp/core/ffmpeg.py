"""FFmpeg detection, scene FPS query, and PNG-sequence-to-MP4 encoding."""

from __future__ import annotations

from logging import getLogger
import shutil
import subprocess

import maya.cmds as cmds  # type: ignore

logger = getLogger(__name__)

# Maya time-unit name → FPS  (from Maya docs / ppiPlayblast)
TIME_UNIT: dict[str, float] = {
    "game": 15,
    "film": 24,
    "pal": 25,
    "ntsc": 30,
    "show": 48,
    "palf": 50,
    "ntscf": 60,
    "2fps": 2,
    "3fps": 3,
    "4fps": 4,
    "5fps": 5,
    "6fps": 6,
    "8fps": 8,
    "10fps": 10,
    "12fps": 12,
    "16fps": 16,
    "20fps": 20,
    "23.976fps": 23.976,
    "29.97fps": 29.97,
    "40fps": 40,
    "47.952fps": 47.952,
    "59.94fps": 59.94,
    "75fps": 75,
    "100fps": 100,
    "120fps": 120,
    "125fps": 125,
    "150fps": 150,
    "200fps": 200,
    "240fps": 240,
    "250fps": 250,
    "300fps": 300,
    "375fps": 375,
    "400fps": 400,
    "500fps": 500,
    "600fps": 600,
    "750fps": 750,
    "1200fps": 1200,
    "1500fps": 1500,
    "2000fps": 2000,
    "3000fps": 3000,
    "6000fps": 6000,
}


def get_scene_fps() -> float:
    """Return the current Maya scene FPS from ``currentUnit(time=True)``."""
    try:
        unit = cmds.currentUnit(q=True, time=True)
        return TIME_UNIT.get(unit, 24.0)
    except Exception as exc:
        logger.warning("get_scene_fps() failed, defaulting to 24.0: %s", exc)
        return 24.0


def find_ffmpeg() -> str | None:
    """Return the path to *ffmpeg* if found on PATH, else ``None``."""
    return shutil.which("ffmpeg")


def check_ffmpeg() -> str:
    """Return the path to *ffmpeg*, raising :class:`RuntimeError` if absent."""
    path = find_ffmpeg()
    if path is None:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg and ensure it is accessible from the system PATH.")
    return path


def encode_sequence_to_mp4(
    image_dir: str,
    filename_pattern: str,
    output_path: str,
    fps: float,
    frame_start: int,
    width: int,
    height: int,
) -> None:
    """Encode a numbered PNG sequence into an H.264 MP4.

    Parameters:
        image_dir:        Directory containing the source PNGs.
        filename_pattern: printf-style pattern relative to *image_dir*
                          (e.g. ``"vpcomp_%04d.png"``).
        output_path:      Destination ``.mp4`` file path.
        fps:              Frame rate for the output video.
        frame_start:      First frame number in the sequence.
        width:            Source image width  (used for even-dimension pad).
        height:           Source image height (used for even-dimension pad).
    """
    ffmpeg = check_ffmpeg()

    # H.264 requires even width/height — pad if necessary
    pad_w = width + (width % 2)
    pad_h = height + (height % 2)
    vf = f"pad={pad_w}:{pad_h}:0:0:black"

    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        str(frame_start),
        "-i",
        f"{image_dir}/{filename_pattern}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        output_path,
    ]

    logger.info("Running ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}):\n{result.stderr}")
