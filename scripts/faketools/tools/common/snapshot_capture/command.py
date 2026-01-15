"""Snapshot Capture command layer.

Pure Maya operations for display and capture functionality.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import maya.cmds as cmds

if TYPE_CHECKING:
    from PIL import Image

# Display mode definitions for modelEditor
DISPLAY_MODES = {
    "shaded": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "textured": {
        "displayAppearance": "smoothShaded",
        "displayTextures": True,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "wireframe": {
        "displayAppearance": "wireframe",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "wireframe_on_shaded": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": True,
        "xray": False,
    },
    "flat": {
        "displayAppearance": "flatShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "x_ray": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": True,
    },
}

# Display mode labels for UI
DISPLAY_MODE_LABELS = {
    "shaded": "Shaded",
    "textured": "Textured",
    "wireframe": "Wireframe",
    "wireframe_on_shaded": "Wireframe on Shaded",
    "flat": "Flat",
    "x_ray": "X-Ray",
}

# Resolution presets
RESOLUTION_PRESETS = {
    "1920x1080 (Full HD)": (1920, 1080),
    "1280x720 (HD)": (1280, 720),
    "800x600": (800, 600),
    "640x480 (VGA)": (640, 480),
    "640x360": (640, 360),
    "512x512": (512, 512),
    "320x240": (320, 240),
    "256x256": (256, 256),
    "128x128": (128, 128),
}

# Default resolution key
DEFAULT_RESOLUTION = "640x360"

# Background color options (None means transparent)
BACKGROUND_COLORS = {
    "Transparent": None,
    "White": (255, 255, 255),
    "Black": (0, 0, 0),
    "Gray": (128, 128, 128),
}

DEFAULT_BACKGROUND = "Transparent"


def set_display_mode(panel_name: str, mode: str) -> None:
    """Apply display mode to model panel.

    Args:
        panel_name: Model panel name.
        mode: Display mode key from DISPLAY_MODES.
    """
    if mode not in DISPLAY_MODES:
        return

    settings = DISPLAY_MODES[mode]
    cmds.modelEditor(panel_name, edit=True, **settings)


def capture_frame(
    panel_name: str,
    width: int,
    height: int,
) -> Image.Image:
    """Capture single frame from model panel using playblast.

    Args:
        panel_name: Model panel name.
        width: Output image width.
        height: Output image height.

    Returns:
        PIL Image object.
    """
    from PIL import Image

    current_frame = cmds.currentTime(query=True)

    # Use temp file
    temp_dir = tempfile.gettempdir()
    output_base = str(Path(temp_dir) / "snapshot_capture_temp")

    # Capture frame using playblast
    cmds.playblast(
        format="image",
        compression="png",
        quality=100,
        width=width,
        height=height,
        startTime=current_frame,
        endTime=current_frame,
        viewer=False,
        showOrnaments=True,
        framePadding=4,
        filename=output_base,
        forceOverwrite=True,
        percent=100,
        offScreen=True,
        editorPanelName=panel_name,
    )

    # Load the captured image
    frame_num = int(current_frame)
    image_path = f"{output_base}.{frame_num:04d}.png"

    if Path(image_path).exists():
        image = Image.open(image_path)
        image = image.copy()  # Copy to memory to allow file deletion
        Path(image_path).unlink()  # Clean up temp file
        return image

    raise RuntimeError(f"Failed to capture frame from panel: {panel_name}")


def capture_viewport_ogs(panel_name: str, width: int, height: int) -> Image.Image:
    """Capture viewport using ogsRender (for real-time recording).

    This method uses Maya's ogsRender command to capture the viewport
    without the flickering issues of playblast.

    Args:
        panel_name: Model panel name.
        width: Output image width.
        height: Output image height.

    Returns:
        PIL Image object.
    """
    from PIL import Image

    # Use temp file
    temp_dir = tempfile.gettempdir()
    output_path = str(Path(temp_dir) / "snapshot_capture_ogs_temp.png")

    # Get the model editor from the panel
    model_editor = cmds.modelPanel(panel_name, query=True, modelEditor=True)

    # Capture using ogsRender
    cmds.ogsRender(
        camera=cmds.modelPanel(panel_name, query=True, camera=True),
        width=width,
        height=height,
        outputFile=output_path,
        currentFrame=True,
        enableMultisample=True,
        view=True,
    )

    # Load the captured image
    if Path(output_path).exists():
        image = Image.open(output_path)
        image = image.copy()  # Copy to memory
        Path(output_path).unlink()  # Clean up temp file
        return image

    raise RuntimeError(f"Failed to capture viewport using ogsRender")


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


def capture_frame_range(
    panel_name: str,
    start_frame: int,
    end_frame: int,
    width: int,
    height: int,
) -> list[Image.Image]:
    """Capture frames from start to end frame.

    Args:
        panel_name: Model panel name.
        start_frame: Start frame number.
        end_frame: End frame number.
        width: Output image width.
        height: Output image height.

    Returns:
        List of PIL Image objects.
    """
    from PIL import Image

    images = []
    original_frame = cmds.currentTime(query=True)

    # Use temp file
    temp_dir = tempfile.gettempdir()
    output_base = str(Path(temp_dir) / "snapshot_capture_gif_temp")

    try:
        for frame in range(start_frame, end_frame + 1):
            # Move to frame
            cmds.currentTime(frame)

            # Capture frame using playblast
            cmds.playblast(
                format="image",
                compression="png",
                quality=100,
                width=width,
                height=height,
                startTime=frame,
                endTime=frame,
                viewer=False,
                showOrnaments=True,
                framePadding=4,
                filename=output_base,
                forceOverwrite=True,
                percent=100,
                editorPanelName=panel_name,
            )

            # Load the captured image
            image_path = f"{output_base}.{frame:04d}.png"

            if Path(image_path).exists():
                image = Image.open(image_path)
                image = image.copy()  # Copy to memory
                Path(image_path).unlink()  # Clean up temp file
                images.append(image)
            else:
                raise RuntimeError(f"Failed to capture frame {frame}")

    finally:
        # Restore original frame
        cmds.currentTime(original_frame)

    return images


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
