"""Input overlay drawing for captured images.

Draws cursor, click indicators, and keyboard overlay on captured images.
All drawing functions modify the image in-place for performance optimization.
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

# Font cache to avoid repeated font loading
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def draw_cursor(
    image: Image.Image,
    cursor_screen_pos: tuple[int, int],
    capture_bbox: tuple[int, int, int, int],
) -> Image.Image:
    """Draw a simple arrow cursor on the image.

    Modifies the image in-place for performance.

    Args:
        image: PIL Image to draw on (modified in-place).
        cursor_screen_pos: Cursor position in screen coordinates (x, y).
        capture_bbox: Capture region bounding box (left, top, right, bottom).

    Returns:
        The same image with cursor drawn.
    """
    # Calculate cursor position relative to capture region
    rel_x = cursor_screen_pos[0] - capture_bbox[0]
    rel_y = cursor_screen_pos[1] - capture_bbox[1]

    # Check if cursor is within capture region
    if not (0 <= rel_x < image.width and 0 <= rel_y < image.height):
        return image

    draw = ImageDraw.Draw(image)

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

    return image


def draw_click_indicators(
    image: Image.Image,
    click_events: list[ClickEvent],
    capture_bbox: tuple[int, int, int, int],
) -> Image.Image:
    """Draw click indicators (circles) on the image.

    Modifies the image in-place for performance.

    Args:
        image: PIL Image to draw on (modified in-place).
        click_events: List of recent click events.
        capture_bbox: Capture region bounding box (left, top, right, bottom).

    Returns:
        The same image with click indicators drawn.
    """
    if not click_events:
        return image

    draw = ImageDraw.Draw(image)

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

    return image


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


def _get_cached_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a cached font or load and cache it.

    Args:
        path: Font file path, or None for default font.
        size: Font size in pixels.

    Returns:
        Cached or newly loaded font.
    """
    key = (path, size)
    if key not in _FONT_CACHE:
        if path is None:
            _FONT_CACHE[key] = ImageFont.load_default()
        else:
            _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _get_overlay_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get font for overlay text with fallback.

    Args:
        size: Font size in pixels.

    Returns:
        Font for overlay text.
    """
    # Try common font paths
    font_paths = ["arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
    for path in font_paths:
        try:
            return _get_cached_font(path, size)
        except OSError:
            continue
    # Fall back to default
    return _get_cached_font(None, size)


def draw_key_overlay(
    image: Image.Image,
    pressed_keys: list[str],
    position: str = "bottom_left",
) -> Image.Image:
    """Draw pressed keys overlay on image.

    Modifies the image in-place for performance.

    Args:
        image: PIL Image to draw on (modified in-place).
        pressed_keys: List of currently pressed key names.
        position: Overlay position ("bottom_left", "bottom_right", "top_left", "top_right").

    Returns:
        The same image with key overlay drawn.
    """
    if not pressed_keys:
        return image

    # Build key display text
    key_text = " + ".join(pressed_keys)

    # Get cached font
    font = _get_overlay_font(14)

    # Calculate text size
    temp_draw = ImageDraw.Draw(image)
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

    # Composite overlay onto image
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    image = Image.alpha_composite(image, overlay)

    # Draw text
    draw = ImageDraw.Draw(image)
    draw.text(
        (box_x + padding, box_y + padding),
        key_text,
        fill=(255, 255, 255),
        font=font,
    )

    return image
