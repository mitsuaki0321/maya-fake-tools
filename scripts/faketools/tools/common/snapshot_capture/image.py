"""Snapshot Capture - image processing functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .annotation import AnnotationLayer


def composite_with_background(
    image: Image.Image,
    background_color: tuple[int, int, int] | None,
) -> Image.Image:
    """Composite image with background color.

    Args:
        image: PIL Image object (RGBA).
        background_color: RGB tuple or None for transparent.

    Returns:
        Composited image (RGB if color specified, RGBA if transparent).
    """
    if background_color is None:
        # Keep transparency
        if image.mode != "RGBA":
            return image.convert("RGBA")
        return image

    # Composite with background color
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    background = Image.new("RGB", image.size, background_color)
    background.paste(image, mask=image.split()[3])
    return background


def save_png(
    image: Image.Image,
    output_path: str,
    background_color: tuple[int, int, int] | None = None,
    annotations: AnnotationLayer | None = None,
) -> str:
    """Save image as PNG.

    Args:
        image: PIL Image object.
        output_path: Output file path.
        background_color: RGB tuple or None for transparent.
        annotations: Optional annotation layer to render on image.

    Returns:
        Output file path.
    """
    # Apply annotations if provided
    if annotations and len(annotations) > 0:
        from .annotation_renderer import render_annotations

        image = render_annotations(image, annotations)

    image = composite_with_background(image, background_color)
    image.save(output_path, "PNG")
    return output_path


def save_gif(
    images: list[Image.Image] | list[tuple[Image.Image, float]],
    output_path: str,
    fps: int = 24,
    background_color: tuple[int, int, int] | None = None,
    loop: bool = True,
    annotations: AnnotationLayer | None = None,
) -> str:
    """Save images as animated GIF.

    This function delegates to GifExportHandler for the actual export.
    Kept for backward compatibility.

    Args:
        images: List of PIL Image objects, or list of (Image, timestamp) tuples
            for variable frame timing.
        output_path: Output file path.
        fps: Frames per second for GIF playback (used for fixed timing or last frame).
        background_color: RGB tuple or None for transparent.
        loop: If True, GIF loops forever. If False, plays once.
        annotations: Optional annotation layer to render on images.

    Returns:
        Output file path.
    """
    from .export_handlers import GifExportHandler

    return GifExportHandler.export(
        images=images,
        output_path=output_path,
        fps=fps,
        background_color=background_color,
        loop=loop,
        annotations=annotations,
    )


def save_mp4(
    images: list[Image.Image] | list[tuple[Image.Image, float]],
    output_path: str,
    fps: int = 24,
    background_color: tuple[int, int, int] | None = None,
    loop: bool = True,
    quality: str = "medium",
    annotations: AnnotationLayer | None = None,
) -> str:
    """Save images as MP4 video.

    Requires FFmpeg to be installed and available in PATH.

    Args:
        images: List of PIL Image objects, or list of (Image, timestamp) tuples
            for timing-aware export.
        output_path: Output file path.
        fps: Frames per second (overridden by average fps from timestamps if provided).
        background_color: RGB tuple or None (defaults to black).
        loop: Ignored for MP4.
        quality: Quality preset ("high", "medium", "low").
        annotations: Optional annotation layer to render on images.

    Returns:
        Output file path.

    Raises:
        RuntimeError: If FFmpeg is not available.
    """
    from .export_handlers import Mp4ExportHandler

    return Mp4ExportHandler.export(
        images=images,
        output_path=output_path,
        fps=fps,
        background_color=background_color,
        loop=loop,
        quality=quality,
        annotations=annotations,
    )
