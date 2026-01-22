"""Snapshot Capture - viewport capture functions."""

from __future__ import annotations

from pathlib import Path
import tempfile

import maya.cmds as cmds
from PIL import Image

from .constants import DISPLAY_MODES


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
    images = []
    original_frame = cmds.currentTime(query=True)

    # Use temp file
    temp_dir = tempfile.gettempdir()
    output_base = str(Path(temp_dir) / "snapshot_capture_gif_temp")

    try:
        # Ensure viewport is ready before first capture
        cmds.currentTime(start_frame)
        cmds.refresh(force=True)

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
                offScreen=True,
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
