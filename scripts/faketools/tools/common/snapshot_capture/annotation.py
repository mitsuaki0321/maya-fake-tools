"""Annotation data models for snapshot capture.

This module defines dataclasses for different annotation types that can be
overlaid on captured images. All positions are stored as ratios (0.0-1.0)
relative to the image size for resolution independence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union
import uuid


def _generate_id() -> str:
    """Generate a unique annotation ID.

    Returns:
        Short UUID string.
    """
    return str(uuid.uuid4())[:8]


@dataclass
class TextAnnotation:
    """Text annotation with optional background.

    Attributes:
        id: Unique identifier.
        text: Text content to display.
        x: Horizontal position (0.0-1.0 ratio).
        y: Vertical position (0.0-1.0 ratio).
        font_size: Font size in points.
        color: Text color as RGB tuple.
        background_color: Background color as RGBA tuple, or None for no background.
    """

    text: str
    x: float
    y: float
    font_size: int = 16
    color: tuple[int, int, int] = (255, 255, 255)
    background_color: tuple[int, int, int, int] | None = (0, 0, 0, 180)
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["text"]:
        """Return annotation type identifier."""
        return "text"


@dataclass
class ArrowAnnotation:
    """Arrow annotation from start point to end point.

    Attributes:
        id: Unique identifier.
        start_x: Start horizontal position (0.0-1.0 ratio).
        start_y: Start vertical position (0.0-1.0 ratio).
        end_x: End horizontal position (0.0-1.0 ratio).
        end_y: End vertical position (0.0-1.0 ratio).
        color: Arrow color as RGB tuple.
        line_width: Line thickness in pixels.
    """

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    color: tuple[int, int, int] = (255, 0, 0)
    line_width: int = 3
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["arrow"]:
        """Return annotation type identifier."""
        return "arrow"


@dataclass
class RectangleAnnotation:
    """Rectangle annotation (outline only).

    Attributes:
        id: Unique identifier.
        x: Left position (0.0-1.0 ratio).
        y: Top position (0.0-1.0 ratio).
        width: Width (0.0-1.0 ratio).
        height: Height (0.0-1.0 ratio).
        color: Outline color as RGB tuple.
        line_width: Line thickness in pixels.
    """

    x: float
    y: float
    width: float
    height: float
    color: tuple[int, int, int] = (255, 255, 0)
    line_width: int = 2
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["rectangle"]:
        """Return annotation type identifier."""
        return "rectangle"


@dataclass
class EllipseAnnotation:
    """Ellipse/circle annotation (outline only).

    Attributes:
        id: Unique identifier.
        center_x: Center horizontal position (0.0-1.0 ratio).
        center_y: Center vertical position (0.0-1.0 ratio).
        radius_x: Horizontal radius (0.0-1.0 ratio).
        radius_y: Vertical radius (0.0-1.0 ratio).
        color: Outline color as RGB tuple.
        line_width: Line thickness in pixels.
    """

    center_x: float
    center_y: float
    radius_x: float
    radius_y: float
    color: tuple[int, int, int] = (0, 255, 0)
    line_width: int = 2
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["ellipse"]:
        """Return annotation type identifier."""
        return "ellipse"


@dataclass
class LineAnnotation:
    """Line annotation (no arrowhead).

    Attributes:
        id: Unique identifier.
        start_x: Start horizontal position (0.0-1.0 ratio).
        start_y: Start vertical position (0.0-1.0 ratio).
        end_x: End horizontal position (0.0-1.0 ratio).
        end_y: End vertical position (0.0-1.0 ratio).
        color: Line color as RGB tuple.
        line_width: Line thickness in pixels.
    """

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    color: tuple[int, int, int] = (255, 0, 0)
    line_width: int = 3
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["line"]:
        """Return annotation type identifier."""
        return "line"


@dataclass
class NumberAnnotation:
    """Numbered circle annotation.

    Attributes:
        id: Unique identifier.
        x: Center horizontal position (0.0-1.0 ratio).
        y: Center vertical position (0.0-1.0 ratio).
        radius: Circle radius (0.0-1.0 ratio, relative to image width).
        number: Display number.
        color: Circle outline color as RGB tuple.
        line_width: Line thickness in pixels.
    """

    x: float
    y: float
    radius: float = 0.02  # Default ~20px at 1000px width
    number: int = 1
    color: tuple[int, int, int] = (255, 0, 0)
    line_width: int = 2
    id: str = field(default_factory=_generate_id)

    @property
    def annotation_type(self) -> Literal["number"]:
        """Return annotation type identifier."""
        return "number"


# Type alias for any annotation type
AnnotationType = Union[TextAnnotation, ArrowAnnotation, RectangleAnnotation, EllipseAnnotation, LineAnnotation, NumberAnnotation]


@dataclass
class AnnotationLayer:
    """Container for multiple annotations.

    Attributes:
        annotations: List of annotation objects.
        apply_to_all_frames: If True, apply to all frames in animation.
            If False, apply only to specific frames.
        frame_indices: Frame indices to apply annotations to (if apply_to_all_frames is False).
    """

    annotations: list[AnnotationType] = field(default_factory=list)
    apply_to_all_frames: bool = True
    frame_indices: list[int] = field(default_factory=list)

    def add(self, annotation: AnnotationType) -> None:
        """Add an annotation to the layer.

        Args:
            annotation: Annotation to add.
        """
        self.annotations.append(annotation)

    def remove(self, annotation_id: str) -> bool:
        """Remove an annotation by ID.

        Args:
            annotation_id: ID of annotation to remove.

        Returns:
            True if annotation was found and removed.
        """
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                del self.annotations[i]
                return True
        return False

    def get(self, annotation_id: str) -> AnnotationType | None:
        """Get an annotation by ID.

        Args:
            annotation_id: ID of annotation to find.

        Returns:
            Annotation object or None if not found.
        """
        for ann in self.annotations:
            if ann.id == annotation_id:
                return ann
        return None

    def clear(self) -> None:
        """Remove all annotations."""
        self.annotations.clear()

    def __len__(self) -> int:
        """Return number of annotations."""
        return len(self.annotations)

    def __iter__(self):
        """Iterate over annotations."""
        return iter(self.annotations)


# Default colors for annotation types
DEFAULT_COLORS = {
    "text": (255, 255, 255),
    "arrow": (255, 0, 0),
    "rectangle": (255, 255, 0),
    "ellipse": (0, 255, 0),
    "line": (255, 0, 0),
    "number": (255, 0, 0),
}

# Default line widths
DEFAULT_LINE_WIDTHS = {
    "arrow": 3,
    "rectangle": 2,
    "ellipse": 2,
    "line": 3,
}

# Default number size (diameter in pixels)
DEFAULT_NUMBER_SIZE = 24
