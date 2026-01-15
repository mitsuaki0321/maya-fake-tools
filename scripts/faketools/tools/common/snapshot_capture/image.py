"""Snapshot Capture - image processing functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


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
    from PIL import Image

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
) -> str:
    """Save image as PNG.

    Args:
        image: PIL Image object.
        output_path: Output file path.
        background_color: RGB tuple or None for transparent.

    Returns:
        Output file path.
    """
    image = composite_with_background(image, background_color)
    image.save(output_path, "PNG")
    return output_path


def save_gif(
    images: list[Image.Image],
    output_path: str,
    fps: int = 24,
    background_color: tuple[int, int, int] | None = None,
) -> str:
    """Save images as animated GIF.

    Args:
        images: List of PIL Image objects.
        output_path: Output file path.
        fps: Frames per second for GIF playback.
        background_color: RGB tuple or None for transparent.

    Returns:
        Output file path.
    """
    from PIL import Image

    if not images:
        raise ValueError("No images to save")

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
    if background_color is None:
        # With transparency
        gif_images[0].save(
            output_path,
            save_all=True,
            append_images=gif_images[1:],
            duration=duration,
            loop=0,
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
            loop=0,
        )

    return output_path
