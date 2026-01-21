"""Base class for export handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

    from ..annotation import AnnotationLayer


class BaseExportHandler(ABC):
    """Abstract base class for export handlers.

    Subclasses define how to export captured images to different file formats.
    Each handler specifies the format name, extension, and export capabilities.
    """

    # Format information
    name: str = ""
    extension: str = ""

    # Capability flags
    supports_animation: bool = True
    supports_transparency: bool = False

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this handler is available.

        Returns:
            True if the handler can be used (dependencies satisfied).
        """
        pass

    @classmethod
    def get_availability_message(cls) -> str | None:
        """Get a message explaining why this handler is unavailable.

        Returns:
            Message string if unavailable, None if available.
        """
        return None

    @classmethod
    @abstractmethod
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
        """Export images to the target format.

        Args:
            images: List of PIL Image objects.
            output_path: Output file path.
            fps: Frames per second for animation.
            background_color: RGB tuple or None for transparent.
            loop: If True, animation loops. If False, plays once.
            quality: Quality preset ("high", "medium", "low").
            annotations: Optional annotation layer to render on images.

        Returns:
            Output file path.

        Raises:
            ValueError: If no images provided or invalid parameters.
            RuntimeError: If export fails.
        """
        pass

    @classmethod
    def get_quality_options(cls) -> list[str]:
        """Get available quality presets.

        Returns:
            List of quality preset names.
        """
        return ["high", "medium", "low"]
