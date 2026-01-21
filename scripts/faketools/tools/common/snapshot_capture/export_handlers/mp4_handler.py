"""MP4 export handler using FFmpeg."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING

from .base import BaseExportHandler

if TYPE_CHECKING:
    from PIL import Image

    from ..annotation import AnnotationLayer

logger = logging.getLogger(__name__)

# Quality presets for H.264 encoding
# CRF: 0-51, lower = better quality, 18-28 is typical range
# Preset: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
QUALITY_PRESETS = {
    "high": {"crf": 18, "preset": "slow"},
    "medium": {"crf": 23, "preset": "medium"},
    "low": {"crf": 28, "preset": "fast"},
}


class Mp4ExportHandler(BaseExportHandler):
    """Export handler for MP4 video format.

    Uses FFmpeg for H.264/AAC encoding. Requires FFmpeg to be installed
    and available in system PATH or common installation locations.
    """

    name = "MP4"
    extension = ".mp4"
    supports_animation = True
    supports_transparency = False

    _ffmpeg_path: str | None = None
    _ffmpeg_checked: bool = False

    @classmethod
    def _find_ffmpeg(cls) -> str | None:
        """Find FFmpeg executable path.

        Searches PATH first, then common installation locations.

        Returns:
            Path to ffmpeg executable, or None if not found.
        """
        if cls._ffmpeg_checked:
            return cls._ffmpeg_path

        cls._ffmpeg_checked = True

        # Try PATH first
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            cls._ffmpeg_path = ffmpeg_path
            logger.debug(f"Found FFmpeg in PATH: {ffmpeg_path}")
            return cls._ffmpeg_path

        # Common installation locations (Windows)
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
            os.path.expanduser(r"~\AppData\Local\ffmpeg\bin\ffmpeg.exe"),
        ]

        for path in common_paths:
            if os.path.isfile(path):
                cls._ffmpeg_path = path
                logger.debug(f"Found FFmpeg at: {path}")
                return cls._ffmpeg_path

        logger.debug("FFmpeg not found")
        return None

    @classmethod
    def is_available(cls) -> bool:
        """Check if FFmpeg is available.

        Returns:
            True if FFmpeg is found.
        """
        return cls._find_ffmpeg() is not None

    @classmethod
    def get_availability_message(cls) -> str | None:
        """Get message if FFmpeg is not available.

        Returns:
            Message explaining how to install FFmpeg, or None if available.
        """
        if cls.is_available():
            return None
        return "FFmpeg not found. Install FFmpeg and add to PATH."

    @classmethod
    def export(
        cls,
        images: list[Image.Image],
        output_path: str,
        fps: int = 24,
        background_color: tuple[int, int, int] | None = None,
        loop: bool = True,
        quality: str = "medium",
        annotations: AnnotationLayer | None = None,
    ) -> str:
        """Export images as MP4 video.

        Args:
            images: List of PIL Image objects.
            output_path: Output file path.
            fps: Frames per second.
            background_color: RGB tuple or None (defaults to black).
            loop: Ignored for MP4 (videos don't loop natively).
            quality: Quality preset ("high", "medium", "low").
            annotations: Optional annotation layer to render on images.

        Returns:
            Output file path.

        Raises:
            ValueError: If no images provided.
            RuntimeError: If FFmpeg is not available or encoding fails.
        """
        from ..annotation_renderer import render_annotations_to_frames
        from ..image import composite_with_background

        if not images:
            raise ValueError("No images to save")

        # Apply annotations if provided
        if annotations and len(annotations) > 0:
            images = render_annotations_to_frames(images, annotations)

        ffmpeg_path = cls._find_ffmpeg()
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Install FFmpeg and add to PATH.")

        # Get quality settings
        quality_settings = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])
        crf = quality_settings["crf"]
        preset = quality_settings["preset"]

        # Default background for MP4 (no transparency)
        if background_color is None:
            background_color = (0, 0, 0)  # Black background

        # Create temporary directory for frames
        temp_dir = tempfile.mkdtemp(prefix="snapshot_mp4_")
        try:
            # Save frames as PNG sequence
            for i, img in enumerate(images):
                img = composite_with_background(img, background_color)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                frame_path = os.path.join(temp_dir, f"frame_{i:06d}.png")
                img.save(frame_path, "PNG")

            # Build FFmpeg command
            input_pattern = os.path.join(temp_dir, "frame_%06d.png")
            cmd = [
                ffmpeg_path,
                "-y",  # Overwrite output
                "-framerate",
                str(fps),
                "-i",
                input_pattern,
                "-c:v",
                "libx264",
                "-crf",
                str(crf),
                "-preset",
                preset,
                "-pix_fmt",
                "yuv420p",  # Compatibility
                "-movflags",
                "+faststart",  # Web playback optimization
                output_path,
            ]

            logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"FFmpeg failed: {error_msg}")
                raise RuntimeError(f"FFmpeg encoding failed: {error_msg}")

            logger.debug(f"MP4 exported: {output_path}")
            return output_path

        finally:
            # Clean up temporary files
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

    @classmethod
    def get_quality_options(cls) -> list[str]:
        """Get available quality presets.

        Returns:
            List of quality preset names.
        """
        return ["high", "medium", "low"]
