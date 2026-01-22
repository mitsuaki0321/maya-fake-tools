"""Input overlay drawing for captured images.

Draws cursor, click indicators, and keyboard overlay on captured images.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from .input_monitor import ClickEvent

# Click indicator colors (RGB)
CLICK_COLORS = {
    "left": (66, 133, 244),  # Blue
    "right": (234, 67, 53),  # Red
    "middle": (52, 168, 83),  # Green
    "double": (251, 188, 5),  # Yellow/Orange
}

# Click indicator settings
CLICK_RADIUS = 20
CLICK_RING_WIDTH = 3


def draw_cursor(
    image: Image.Image,
    cursor_screen_pos: tuple[int, int],
    capture_bbox: tuple[int, int, int, int],
) -> Image.Image:
    """Draw a simple arrow cursor on the image.

    Args:
        image: PIL Image to draw on.
        cursor_screen_pos: Cursor position in screen coordinates (x, y).
        capture_bbox: Capture region bounding box (left, top, right, bottom).

    Returns:
        Image with cursor drawn.
    """
    # Calculate cursor position relative to capture region
    rel_x = cursor_screen_pos[0] - capture_bbox[0]
    rel_y = cursor_screen_pos[1] - capture_bbox[1]

    # Check if cursor is within capture region
    if not (0 <= rel_x < image.width and 0 <= rel_y < image.height):
        return image

    # Create copy to avoid modifying original
    result = image.copy()
    draw = ImageDraw.Draw(result)

    # Draw simple arrow cursor shape
    # Arrow polygon points (tip at cursor position)
    cursor_points = [
        (rel_x, rel_y),  # Tip
        (rel_x, rel_y + 18),  # Bottom left
        (rel_x + 4, rel_y + 14),  # Inner corner
        (rel_x + 12, rel_y + 14),  # Right bottom
    ]

    # Draw cursor with black outline and white fill
    draw.polygon(cursor_points, fill=(255, 255, 255), outline=(0, 0, 0))

    return result


def draw_click_indicators(
    image: Image.Image,
    click_events: list[ClickEvent],
    capture_bbox: tuple[int, int, int, int],
) -> Image.Image:
    """Draw click indicators (circles) on the image.

    Args:
        image: PIL Image to draw on.
        click_events: List of recent click events.
        capture_bbox: Capture region bounding box (left, top, right, bottom).

    Returns:
        Image with click indicators drawn.
    """
    if not click_events:
        return image

    result = image.copy()
    draw = ImageDraw.Draw(result)

    for click in click_events:
        # Calculate position relative to capture region
        rel_x = click.x - capture_bbox[0]
        rel_y = click.y - capture_bbox[1]

        # Check if within capture region
        if not (0 <= rel_x < image.width and 0 <= rel_y < image.height):
            continue

        color = CLICK_COLORS.get(click.click_type, CLICK_COLORS["left"])

        if click.click_type == "double":
            # Double click: two concentric circles
            _draw_ring(draw, rel_x, rel_y, CLICK_RADIUS, CLICK_RING_WIDTH, color)
            _draw_ring(draw, rel_x, rel_y, CLICK_RADIUS - 8, CLICK_RING_WIDTH, color)
        else:
            # Single click: one circle
            _draw_ring(draw, rel_x, rel_y, CLICK_RADIUS, CLICK_RING_WIDTH, color)

    return result


def _draw_ring(draw, cx: int, cy: int, radius: int, width: int, color: tuple):
    """Draw a ring (unfilled circle) at the specified position.

    Args:
        draw: PIL ImageDraw object.
        cx: Center x coordinate.
        cy: Center y coordinate.
        radius: Outer radius.
        width: Ring width.
        color: RGB color tuple.
    """
    # Draw outer circle
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=color,
        width=width,
    )


def draw_key_overlay(
    image: Image.Image,
    pressed_keys: list[str],
    position: str = "bottom_left",
) -> Image.Image:
    """Draw pressed keys overlay on image.

    Args:
        image: PIL Image to draw on.
        pressed_keys: List of currently pressed key names.
        position: Overlay position ("bottom_left", "bottom_right", "top_left", "top_right").

    Returns:
        Image with key overlay drawn.
    """
    if not pressed_keys:
        return image

    result = image.copy()

    # Build key display text
    key_text = " + ".join(pressed_keys)

    # Try to load a font, fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        try:
            # Try common font paths
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except OSError:
            font = ImageFont.load_default()

    # Calculate text size
    temp_draw = ImageDraw.Draw(result)
    text_bbox = temp_draw.textbbox((0, 0), key_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Padding
    padding = 6
    box_width = text_width + padding * 2
    box_height = text_height + padding * 2

    # Calculate position
    margin = 8
    if position == "bottom_left":
        box_x = margin
        box_y = image.height - box_height - margin
    elif position == "bottom_right":
        box_x = image.width - box_width - margin
        box_y = image.height - box_height - margin
    elif position == "top_left":
        box_x = margin
        box_y = margin
    else:  # top_right
        box_x = image.width - box_width - margin
        box_y = margin

    # Create semi-transparent overlay
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Draw rounded rectangle background
    overlay_draw.rounded_rectangle(
        [box_x, box_y, box_x + box_width, box_y + box_height],
        radius=4,
        fill=(0, 0, 0, 180),
    )

    # Composite overlay onto result
    if result.mode != "RGBA":
        result = result.convert("RGBA")
    result = Image.alpha_composite(result, overlay)

    # Draw text
    draw = ImageDraw.Draw(result)
    draw.text(
        (box_x + padding, box_y + padding),
        key_text,
        fill=(255, 255, 255),
        font=font,
    )

    return result
