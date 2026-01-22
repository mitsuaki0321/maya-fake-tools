"""GIF export handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from .base import BaseExportHandler

if TYPE_CHECKING:
    from ..annotation import AnnotationLayer


class GifExportHandler(BaseExportHandler):
    """Export handler for animated GIF format.

    Uses PIL/Pillow for GIF encoding. Always available since PIL
    is a required dependency.
    """

    name = "GIF"
    extension = ".gif"
    supports_animation = True
    supports_transparency = True

    @classmethod
    def is_available(cls) -> bool:
        """GIF handler is always available (PIL is required).

        Returns:
            True.
        """
        return True

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
        """Export images as animated GIF.

        Args:
            images: List of PIL Image objects.
            output_path: Output file path.
            fps: Frames per second for GIF playback.
            background_color: RGB tuple or None for transparent.
            loop: If True, GIF loops forever. If False, plays once.
            quality: Quality preset (ignored for GIF - always uses adaptive palette).
            annotations: Optional annotation layer to render on images.

        Returns:
            Output file path.

        Raises:
            ValueError: If no images provided.
        """
        from ..annotation_renderer import render_annotations_to_frames
        from ..image import composite_with_background

        if not images:
            raise ValueError("No images to save")

        # Apply annotations if provided
        if annotations and len(annotations) > 0:
            images = render_annotations_to_frames(images, annotations)

        # Calculate duration per frame in milliseconds
        duration = int(1000 / fps)

        # Process images
        gif_images = []
        for img in images:
            img = composite_with_background(img, background_color)

            if background_color is None:
                # Transparent GIF: use RGBA and specify transparency
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                # Convert to palette with transparency
                alpha = img.split()[3]
                img = img.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
                # Set transparent color index for pixels with low alpha
                mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
                img.paste(255, mask)  # Index 255 will be transparent
                gif_images.append(img)
            else:
                # Solid background: convert to palette
                if img.mode != "RGB":
                    img = img.convert("RGB")
                gif_images.append(img.convert("P", palette=Image.ADAPTIVE, colors=256))

        # Save as animated GIF
        # loop=0 means loop forever, loop=1 means play once
        loop_count = 0 if loop else 1

        if background_color is None:
            # With transparency
            gif_images[0].save(
                output_path,
                save_all=True,
                append_images=gif_images[1:],
                duration=duration,
                loop=loop_count,
                transparency=255,
                disposal=2,  # Restore to background
            )
        else:
            # Without transparency
            gif_images[0].save(
                output_path,
                save_all=True,
                append_images=gif_images[1:],
                duration=duration,
                loop=loop_count,
            )

        return output_path

    @classmethod
    def get_quality_options(cls) -> list[str]:
        """GIF doesn't have quality options.

        Returns:
            Empty list (GIF uses adaptive palette).
        """
        return []
