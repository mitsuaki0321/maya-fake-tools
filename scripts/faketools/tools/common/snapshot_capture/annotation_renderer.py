"""Annotation renderer using aggdraw for antialiased drawing.

Renders annotation objects onto PIL images with antialiasing support.
Falls back to PIL ImageDraw if aggdraw is not available.
"""

from __future__ import annotations

import logging
import math
import os
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from .annotation import AnnotationLayer, AnnotationType

logger = logging.getLogger(__name__)

# Try to import aggdraw for antialiased drawing
try:
    import aggdraw

    AGGDRAW_AVAILABLE = True
except ImportError:
    AGGDRAW_AVAILABLE = False
    logger.warning("aggdraw not available, falling back to PIL (no antialiasing)")


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
    from .annotation import (
        ArrowAnnotation,
        EllipseAnnotation,
        FreehandAnnotation,
        LineAnnotation,
        NumberAnnotation,
        RectangleAnnotation,
        TextAnnotation,
    )

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
    elif isinstance(annotation, FreehandAnnotation):
        return _render_freehand(image, annotation)
    return image


def _color_to_aggdraw(color: tuple) -> str:
    """Convert RGB/RGBA tuple to aggdraw color string.

    Args:
        color: RGB or RGBA tuple.

    Returns:
        Color string in format suitable for aggdraw.
    """
    if len(color) == 3:
        return f"rgb({color[0]},{color[1]},{color[2]})"
    else:
        return f"rgba({color[0]},{color[1]},{color[2]},{color[3]})"


def _render_text(image: Image.Image, annotation) -> Image.Image:
    """Render text annotation.

    Note: Text rendering uses PIL ImageDraw as aggdraw has limited text support.

    Args:
        image: PIL Image to draw on.
        annotation: TextAnnotation object.

    Returns:
        Image with text rendered.
    """
    # Convert ratio to pixel position
    x = int(annotation.x * image.width)
    y = int(annotation.y * image.height)

    # Scale font size based on image resolution
    # Base resolution is 640x360, scale font accordingly
    scale_factor = max(image.width / 640, image.height / 360)
    scaled_font_size = max(10, int(annotation.font_size * scale_factor))

    # Try to load font (with bold if specified)
    bold = getattr(annotation, "bold", False)
    font = _get_font(scaled_font_size, bold=bold)

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
    """Render arrow annotation with antialiasing.

    Args:
        image: PIL Image to draw on.
        annotation: ArrowAnnotation object.

    Returns:
        Image with arrow rendered.
    """
    # Convert ratio to pixel positions
    start_x = int(annotation.start_x * image.width)
    start_y = int(annotation.start_y * image.height)
    end_x = int(annotation.end_x * image.width)
    end_y = int(annotation.end_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)
        brush = aggdraw.Brush(_color_to_aggdraw(color))

        # Draw main line
        draw.line([start_x, start_y, end_x, end_y], pen)

        # Draw arrowhead
        _draw_arrowhead_aggdraw(draw, start_x, start_y, end_x, end_y, brush, line_width)

        draw.flush()
    else:
        draw = ImageDraw.Draw(image)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=line_width)
        _draw_arrowhead_pil(draw, start_x, start_y, end_x, end_y, color, line_width)

    return image


def _draw_arrowhead_aggdraw(draw, start_x: int, start_y: int, end_x: int, end_y: int, brush, line_width: int):
    """Draw an arrowhead using aggdraw.

    Args:
        draw: aggdraw.Draw object.
        start_x: Line start X.
        start_y: Line start Y.
        end_x: Line end X (arrow tip).
        end_y: Line end Y (arrow tip).
        brush: aggdraw.Brush for fill.
        line_width: Line width for scaling.
    """
    angle = math.atan2(end_y - start_y, end_x - start_x)
    arrow_length = line_width * 4
    arrow_angle = math.pi / 6  # 30 degrees

    left_x = end_x - arrow_length * math.cos(angle - arrow_angle)
    left_y = end_y - arrow_length * math.sin(angle - arrow_angle)
    right_x = end_x - arrow_length * math.cos(angle + arrow_angle)
    right_y = end_y - arrow_length * math.sin(angle + arrow_angle)

    draw.polygon([end_x, end_y, left_x, left_y, right_x, right_y], brush)


def _draw_arrowhead_pil(draw, start_x: int, start_y: int, end_x: int, end_y: int, color: tuple, line_width: int):
    """Draw an arrowhead using PIL (fallback).

    Args:
        draw: PIL ImageDraw object.
        start_x: Line start X.
        start_y: Line start Y.
        end_x: Line end X (arrow tip).
        end_y: Line end Y (arrow tip).
        color: Arrow color.
        line_width: Line width for scaling.
    """
    angle = math.atan2(end_y - start_y, end_x - start_x)
    arrow_length = line_width * 4
    arrow_angle = math.pi / 6  # 30 degrees

    left_x = end_x - arrow_length * math.cos(angle - arrow_angle)
    left_y = end_y - arrow_length * math.sin(angle - arrow_angle)
    right_x = end_x - arrow_length * math.cos(angle + arrow_angle)
    right_y = end_y - arrow_length * math.sin(angle + arrow_angle)

    draw.polygon([(end_x, end_y), (left_x, left_y), (right_x, right_y)], fill=color)


def _render_rectangle(image: Image.Image, annotation) -> Image.Image:
    """Render rectangle annotation with antialiasing.

    Args:
        image: PIL Image to draw on.
        annotation: RectangleAnnotation object.

    Returns:
        Image with rectangle rendered.
    """
    # Convert ratio to pixel positions
    x = int(annotation.x * image.width)
    y = int(annotation.y * image.height)
    w = int(annotation.width * image.width)
    h = int(annotation.height * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)

        # aggdraw rectangle takes [x1, y1, x2, y2]
        draw.rectangle([x, y, x + w, y + h], pen)
        draw.flush()
    else:
        draw = ImageDraw.Draw(image)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=line_width)

    return image


def _render_ellipse(image: Image.Image, annotation) -> Image.Image:
    """Render ellipse annotation with antialiasing.

    Args:
        image: PIL Image to draw on.
        annotation: EllipseAnnotation object.

    Returns:
        Image with ellipse rendered.
    """
    # Convert ratio to pixel positions
    cx = int(annotation.center_x * image.width)
    cy = int(annotation.center_y * image.height)
    rx = int(annotation.radius_x * image.width)
    ry = int(annotation.radius_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)

        # aggdraw ellipse takes [x1, y1, x2, y2]
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], pen)
        draw.flush()
    else:
        draw = ImageDraw.Draw(image)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=color, width=line_width)

    return image


def _render_line(image: Image.Image, annotation) -> Image.Image:
    """Render line annotation with antialiasing.

    Args:
        image: PIL Image to draw on.
        annotation: LineAnnotation object.

    Returns:
        Image with line rendered.
    """
    # Convert ratio to pixel positions
    start_x = int(annotation.start_x * image.width)
    start_y = int(annotation.start_y * image.height)
    end_x = int(annotation.end_x * image.width)
    end_y = int(annotation.end_y * image.height)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)

        draw.line([start_x, start_y, end_x, end_y], pen)
        draw.flush()
    else:
        draw = ImageDraw.Draw(image)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=line_width)

    return image


def _render_freehand(image: Image.Image, annotation) -> Image.Image:
    """Render freehand annotation with antialiasing.

    Supports pressure-sensitive strokes when pressure data is available.

    Args:
        image: PIL Image to draw on.
        annotation: FreehandAnnotation object.

    Returns:
        Image with freehand path rendered.
    """
    if not annotation.points or len(annotation.points) < 2:
        return image

    # Convert ratio points to pixel positions (keep as float for precision)
    pixel_points = [(x * image.width, y * image.height) for x, y in annotation.points]

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    base_line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    # Check if we have pressure data
    pressures = getattr(annotation, "pressures", None)
    has_pressure = pressures is not None and len(pressures) == len(annotation.points)

    if has_pressure:
        # Render with variable width based on pressure
        return _render_freehand_with_pressure(image, pixel_points, pressures, color, base_line_width, scale_factor)
    else:
        # Render with uniform width (original behavior)
        return _render_freehand_uniform(image, pixel_points, color, base_line_width)


def _render_freehand_uniform(image: Image.Image, pixel_points: list[tuple[float, float]], color: tuple, line_width: int) -> Image.Image:
    """Render freehand path with uniform line width.

    Args:
        image: PIL Image to draw on.
        pixel_points: List of pixel coordinates.
        color: Line color.
        line_width: Line width in pixels.

    Returns:
        Image with freehand path rendered.
    """
    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)

        # Apply Catmull-Rom spline interpolation for smoother curves
        interpolated = _catmull_rom_spline(pixel_points, segments_per_curve=4)

        # Use Path object for smoother rendering than line()
        path = aggdraw.Path()
        path.moveto(interpolated[0][0], interpolated[0][1])
        for x, y in interpolated[1:]:
            path.lineto(x, y)

        draw.path(path, None, pen)  # None for fill, pen for stroke
        draw.flush()

        # Draw circles at endpoints to simulate round caps
        radius = line_width / 2.0
        if radius > 0.5:
            brush = aggdraw.Brush(_color_to_aggdraw(color))
            sx, sy = interpolated[0]
            ex, ey = interpolated[-1]
            draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius], brush)
            draw.ellipse([ex - radius, ey - radius, ex + radius, ey + radius], brush)
            draw.flush()
    else:
        # PIL fallback: use Catmull-Rom spline interpolation for smoother curves
        interpolated = _catmull_rom_spline(pixel_points, segments_per_curve=4)
        int_points = [(int(round(x)), int(round(y))) for x, y in interpolated]

        draw = ImageDraw.Draw(image)
        # Draw the interpolated polyline
        draw.line(int_points, fill=color, width=line_width, joint="curve")

        # Draw circles at endpoints to simulate round caps
        radius = line_width // 2
        if radius > 0:
            start_x, start_y = int_points[0]
            end_x, end_y = int_points[-1]
            draw.ellipse([start_x - radius, start_y - radius, start_x + radius, start_y + radius], fill=color)
            draw.ellipse([end_x - radius, end_y - radius, end_x + radius, end_y + radius], fill=color)

    return image


def _render_freehand_with_pressure(
    image: Image.Image,
    pixel_points: list[tuple[float, float]],
    pressures: list[float],
    color: tuple,
    base_line_width: int,
    scale_factor: float,
) -> Image.Image:
    """Render freehand path with pressure-sensitive variable width.

    Args:
        image: PIL Image to draw on.
        pixel_points: List of pixel coordinates.
        pressures: List of pressure values (0.0-1.0) for each point.
        color: Line color.
        base_line_width: Base line width (maximum width at full pressure).
        scale_factor: Resolution scale factor.

    Returns:
        Image with pressure-sensitive freehand path rendered.
    """
    # Minimum width as a fraction of base width
    min_width_ratio = 0.2
    min_width = max(1, int(base_line_width * min_width_ratio))

    # Interpolate points and pressures using Catmull-Rom spline
    interpolated_points = _catmull_rom_spline(pixel_points, segments_per_curve=4)
    interpolated_pressures = _interpolate_pressures(pressures, len(pixel_points), len(interpolated_points))

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)

        # Draw segments with varying width
        for i in range(len(interpolated_points) - 1):
            x1, y1 = interpolated_points[i]
            x2, y2 = interpolated_points[i + 1]

            # Calculate width based on average pressure of segment
            p1 = interpolated_pressures[i]
            p2 = interpolated_pressures[i + 1]
            avg_pressure = (p1 + p2) / 2.0

            # Map pressure to width (pressure 0 -> min_width, pressure 1 -> base_line_width)
            segment_width = min_width + avg_pressure * (base_line_width - min_width)
            segment_width = max(1, int(round(segment_width)))

            pen = aggdraw.Pen(_color_to_aggdraw(color), segment_width)
            draw.line([x1, y1, x2, y2], pen)

            # Draw circle at joint for smooth connection
            if i > 0:
                radius = segment_width / 2.0
                brush = aggdraw.Brush(_color_to_aggdraw(color))
                draw.ellipse([x1 - radius, y1 - radius, x1 + radius, y1 + radius], brush)

        draw.flush()

        # Draw circles at endpoints for round caps
        start_width = max(1, int(min_width + interpolated_pressures[0] * (base_line_width - min_width)))
        end_width = max(1, int(min_width + interpolated_pressures[-1] * (base_line_width - min_width)))

        brush = aggdraw.Brush(_color_to_aggdraw(color))
        sx, sy = interpolated_points[0]
        ex, ey = interpolated_points[-1]
        sr = start_width / 2.0
        er = end_width / 2.0
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], brush)
        draw.ellipse([ex - er, ey - er, ex + er, ey + er], brush)
        draw.flush()

    else:
        # PIL fallback: draw circles along the path with varying size
        draw = ImageDraw.Draw(image)

        for i, (x, y) in enumerate(interpolated_points):
            pressure = interpolated_pressures[i]
            width = min_width + pressure * (base_line_width - min_width)
            radius = max(1, int(width / 2))
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)

        # Also draw lines between points for continuity
        for i in range(len(interpolated_points) - 1):
            x1, y1 = interpolated_points[i]
            x2, y2 = interpolated_points[i + 1]
            p1 = interpolated_pressures[i]
            p2 = interpolated_pressures[i + 1]
            avg_pressure = (p1 + p2) / 2.0
            segment_width = max(1, int(min_width + avg_pressure * (base_line_width - min_width)))
            draw.line([(int(x1), int(y1)), (int(x2), int(y2))], fill=color, width=segment_width)

    return image


def _interpolate_pressures(pressures: list[float], original_count: int, target_count: int) -> list[float]:
    """Interpolate pressure values to match interpolated point count.

    Args:
        pressures: Original pressure values.
        original_count: Number of original points.
        target_count: Number of interpolated points.

    Returns:
        List of interpolated pressure values.
    """
    if target_count <= 1:
        return pressures[:target_count] if pressures else [1.0]

    if len(pressures) < 2:
        return [pressures[0] if pressures else 1.0] * target_count

    result = []
    for i in range(target_count):
        # Map target index to original index range
        t = i / (target_count - 1) * (len(pressures) - 1)
        idx = int(t)
        frac = t - idx

        if idx >= len(pressures) - 1:
            result.append(pressures[-1])
        else:
            # Linear interpolation between adjacent pressure values
            p1 = pressures[idx]
            p2 = pressures[idx + 1]
            result.append(p1 + frac * (p2 - p1))

    return result


def _catmull_rom_spline(points: list[tuple[float, float]], segments_per_curve: int = 4) -> list[tuple[float, float]]:
    """Generate smooth curve points using Catmull-Rom spline interpolation.

    Args:
        points: List of control points (x, y).
        segments_per_curve: Number of interpolated segments between each pair of points.

    Returns:
        List of interpolated points forming a smooth curve.
    """
    if len(points) < 2:
        return points
    if len(points) == 2:
        return points

    result = []

    # Extend points at start and end for proper interpolation
    extended = [points[0]] + list(points) + [points[-1]]

    for i in range(1, len(extended) - 2):
        p0 = extended[i - 1]
        p1 = extended[i]
        p2 = extended[i + 1]
        p3 = extended[i + 2]

        # Generate interpolated points between p1 and p2
        for j in range(segments_per_curve):
            t = j / segments_per_curve

            # Catmull-Rom spline formula
            t2 = t * t
            t3 = t2 * t

            x = 0.5 * (
                (2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            result.append((x, y))

    # Add the last point
    result.append(points[-1])

    return result


def _render_number(image: Image.Image, annotation) -> Image.Image:
    """Render numbered circle annotation with antialiasing.

    Args:
        image: PIL Image to draw on.
        annotation: NumberAnnotation object.

    Returns:
        Image with numbered circle rendered.
    """
    # Convert ratio to pixel positions
    cx = int(annotation.x * image.width)
    cy = int(annotation.y * image.height)
    r = int(annotation.radius * image.width)

    # Scale line width based on image resolution
    scale_factor = max(image.width / 640, image.height / 360)
    line_width = max(1, int(annotation.line_width * scale_factor))

    color = annotation.color

    if AGGDRAW_AVAILABLE:
        draw = aggdraw.Draw(image)
        pen = aggdraw.Pen(_color_to_aggdraw(color), line_width)

        # Draw outline circle
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], pen)
        draw.flush()
    else:
        draw = ImageDraw.Draw(image)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=line_width)

    # Draw number text using PIL (aggdraw has limited text support)
    pil_draw = ImageDraw.Draw(image)
    font_size = max(10, int(r * 1.2))
    font = _get_font(font_size)
    text = str(annotation.number)

    # Use anchor="mm" for middle-middle alignment
    pil_draw.text((cx, cy), text, fill=color, font=font, anchor="mm")

    return image


def _get_font(size: int, bold: bool = False):
    """Get a font for text rendering.

    Attempts to load bundled Noto Sans fonts first, then system fonts,
    falls back to PIL default.

    Args:
        size: Font size in points.
        bold: Whether to use bold font.

    Returns:
        PIL ImageFont object.
    """
    # Get path to bundled fonts directory
    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")

    # Try bundled Noto Sans fonts first (guaranteed to exist)
    if bold:
        bundled_font = os.path.join(fonts_dir, "NotoSans-Bold.ttf")
    else:
        bundled_font = os.path.join(fonts_dir, "NotoSans-Regular.ttf")

    try:
        return ImageFont.truetype(bundled_font, size)
    except OSError:
        pass  # Fall through to system fonts

    # Fallback to system fonts (bold and regular variants)
    if bold:
        font_paths = [
            "arialbd.ttf",
            "Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
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
