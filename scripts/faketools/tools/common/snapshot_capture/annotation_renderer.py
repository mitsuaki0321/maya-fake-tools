"""Annotation renderer using PIL.

Renders annotation objects onto PIL images. Follows the same patterns
as input_overlay.py for consistent drawing behavior.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

    from .annotation import AnnotationLayer, AnnotationType


def render_annotations(
    image: Image.Image,
    annotations: AnnotationLayer | list[AnnotationType],
) -> Image.Image:
    """Render all annotations onto an image.

    Args:
        image: PIL Image to draw on (will be copied).
        annotations: AnnotationLayer or list of annotation objects.

    Returns:
        New image with annotations rendered.
    """
    from .annotation import AnnotationLayer

    if isinstance(annotations, AnnotationLayer):
        annotation_list = list(annotations)
    else:
        annotation_list = annotations

    if not annotation_list:
        return image

    # Create copy to avoid modifying original
    result = image.copy()
    if result.mode != "RGBA":
        result = result.convert("RGBA")

    for annotation in annotation_list:
        result = _render_annotation(result, annotation)

    return result


def render_annotations_to_frames(
    images: list[Image.Image],
    annotations: AnnotationLayer,
) -> list[Image.Image]:
    """Render annotations onto a list of frames.

    Respects the apply_to_all_frames and frame_indices settings
    in the AnnotationLayer.

    Args:
        images: List of PIL Image frames.
        annotations: AnnotationLayer with annotations and frame settings.

    Returns:
        List of images with annotations rendered.
    """
    if not annotations or len(annotations) == 0:
        return images

    result = []
    for i, img in enumerate(images):
        if annotations.apply_to_all_frames or i in annotations.frame_indices:
            result.append(render_annotations(img, annotations))
        else:
            result.append(img)

    return result


def _render_annotation(image: Image.Image, annotation: AnnotationType) -> Image.Image:
    """Render a single annotation onto an image.

    Args:
        image: PIL Image to draw on.
        annotation: Annotation object.

    Returns:
        Image with annotation rendered.
    """
    from .annotation import ArrowAnnotation, EllipseAnnotation, LineAnnotation, NumberAnnotation, RectangleAnnotation, TextAnnotation

    if isinstance(annotation, TextAnnotation):
        return _render_text(image, annotation)
    elif isinstance(annotation, ArrowAnnotation):
        return _render_arrow(image, annotation)
    elif isinstance(annotation, RectangleAnnotation):
        return _render_rectangle(image, annotation)
    elif isinstance(annotation, EllipseAnnotation):
        return _render_ellipse(image, annotation)
    elif isinstance(annotation, LineAnnotation):
        return _render_line(image, annotation)
    elif isinstance(annotation, NumberAnnotation):
        return _render_number(image, annotation)
    return image


def _render_text(image: Image.Image, annotation) -> Image.Image:
    """Render text annotation.

    Args:
        image: PIL Image to draw on.
        annotation: TextAnnotation object.

    Returns:
        Image with text rendered.
    """
    from PIL import Image, ImageDraw

    # Convert ratio to pixel position
    x = int(annotation.x * image.width)
    y = int(annotation.y * image.height)

    # Scale font size based on image resolution
    # Base resolution is 640x360, scale font accordingly
    scale_factor = max(image.width / 640, image.height / 360)
    scaled_font_size = max(10, int(annotation.font_size * scale_factor))

    # Try to load font
    font = _get_font(scaled_font_size)

    # Create temporary draw to measure text
    temp_draw = ImageDraw.Draw(image)
    text_bbox = temp_draw.textbbox((0, 0), annotation.text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Padding for background
    padding = int(4 * scale_factor)

    # Draw background if specified
    if annotation.background_color is not None:
        # Create overlay for semi-transparent background
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        bg_color = annotation.background_color
        overlay_draw.rounded_rectangle(
            [
                x - padding,
                y - padding,
                x + text_width + padding,
                y + text_height + padding,
            ],
            radius=int(4 * scale_factor),
            fill=bg_color,
        )

        # Composite overlay
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        image = Image.alpha_composite(image, overlay)

    # Draw text
    draw = ImageDraw.Draw(image)
    draw.text((x, y), annotation.text, fill=annotation.color, font=font)

    return image


def _render_arrow(image: Image.Image, annotation) -> Image.Image:
    """Render arrow annotation.

    Args:
        image: PIL Image to draw on.
        annotation: ArrowAnnotation object.

    Returns:
        Image with arrow rendered.
    """
    from PIL import ImageDraw

    # Convert ratio to pixel positions
    start_x = int(annotation.start_x * image.width)
    start_y = int(annotation.start_y * image.height)
    end_x = int(annotation.end_x * image.width)
    end_y = int(annotation.end_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    draw = ImageDraw.Draw(image)
    color = annotation.color

    # Draw main line
    draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=line_width)

    # Draw arrowhead
    _draw_arrowhead(draw, start_x, start_y, end_x, end_y, color, line_width)

    return image


def _draw_arrowhead(
    draw,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    color: tuple,
    line_width: int,
):
    """Draw an arrowhead at the end point of a line.

    Args:
        draw: PIL ImageDraw object.
        start_x: Line start X.
        start_y: Line start Y.
        end_x: Line end X (arrow tip).
        end_y: Line end Y (arrow tip).
        color: Arrow color.
        line_width: Line width for scaling.
    """
    # Calculate arrow angle
    angle = math.atan2(end_y - start_y, end_x - start_x)

    # Arrowhead parameters (scale with line width)
    arrow_length = line_width * 4
    arrow_angle = math.pi / 6  # 30 degrees

    # Calculate arrowhead points
    left_x = end_x - arrow_length * math.cos(angle - arrow_angle)
    left_y = end_y - arrow_length * math.sin(angle - arrow_angle)
    right_x = end_x - arrow_length * math.cos(angle + arrow_angle)
    right_y = end_y - arrow_length * math.sin(angle + arrow_angle)

    # Draw filled triangle arrowhead
    draw.polygon(
        [(end_x, end_y), (left_x, left_y), (right_x, right_y)],
        fill=color,
    )


def _render_rectangle(image: Image.Image, annotation) -> Image.Image:
    """Render rectangle annotation.

    Args:
        image: PIL Image to draw on.
        annotation: RectangleAnnotation object.

    Returns:
        Image with rectangle rendered.
    """
    from PIL import ImageDraw

    # Convert ratio to pixel positions
    x = int(annotation.x * image.width)
    y = int(annotation.y * image.height)
    w = int(annotation.width * image.width)
    h = int(annotation.height * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    draw = ImageDraw.Draw(image)
    draw.rectangle(
        [x, y, x + w, y + h],
        outline=annotation.color,
        width=line_width,
    )

    return image


def _render_ellipse(image: Image.Image, annotation) -> Image.Image:
    """Render ellipse annotation.

    Args:
        image: PIL Image to draw on.
        annotation: EllipseAnnotation object.

    Returns:
        Image with ellipse rendered.
    """
    from PIL import ImageDraw

    # Convert ratio to pixel positions
    cx = int(annotation.center_x * image.width)
    cy = int(annotation.center_y * image.height)
    rx = int(annotation.radius_x * image.width)
    ry = int(annotation.radius_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    draw = ImageDraw.Draw(image)
    draw.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        outline=annotation.color,
        width=line_width,
    )

    return image


def _render_line(image: Image.Image, annotation) -> Image.Image:
    """Render line annotation (no arrowhead).

    Args:
        image: PIL Image to draw on.
        annotation: LineAnnotation object.

    Returns:
        Image with line rendered.
    """
    from PIL import ImageDraw

    # Convert ratio to pixel positions
    start_x = int(annotation.start_x * image.width)
    start_y = int(annotation.start_y * image.height)
    end_x = int(annotation.end_x * image.width)
    end_y = int(annotation.end_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    draw = ImageDraw.Draw(image)
    draw.line([(start_x, start_y), (end_x, end_y)], fill=annotation.color, width=line_width)

    return image


def _render_number(image: Image.Image, annotation) -> Image.Image:
    """Render numbered circle annotation.

    Args:
        image: PIL Image to draw on.
        annotation: NumberAnnotation object.

    Returns:
        Image with numbered circle rendered.
    """
    from PIL import ImageDraw

    # Convert ratio to pixel positions
    cx = int(annotation.x * image.width)
    cy = int(annotation.y * image.height)

    # Scale size based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    size = max(16, int(annotation.size * scale_factor))
    r = size // 2

    draw = ImageDraw.Draw(image)

    # Draw filled circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=annotation.color)

    # Draw number text (white)
    font_size = int(size * 0.65)
    font = _get_font(font_size)
    text = str(annotation.number)

    # Get text size for centering
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Center text in circle
    text_x = cx - text_width // 2
    text_y = cy - text_height // 2 - text_bbox[1]  # Adjust for baseline offset

    draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)

    return image


def _get_font(size: int):
    """Get a font for text rendering.

    Attempts to load system fonts, falls back to PIL default.

    Args:
        size: Font size in points.

    Returns:
        PIL ImageFont object.
    """
    from PIL import ImageFont

    # Try common font paths
    font_paths = [
        "arial.ttf",
        "Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue

    # Fall back to default font
    return ImageFont.load_default()
