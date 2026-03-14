"""Layer data model and LayerStack for vpcomp.

Defines CameraLayer, ImageLayer, SequenceLayer dataclasses and a LayerStack
that manages ordering, addition/removal, duplicate-camera validation, and
per-type count limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from logging import getLogger
import os
from typing import Union

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer type enum
# ---------------------------------------------------------------------------


class LayerType(Enum):
    CAMERA = "camera"
    IMAGE = "image"
    SEQUENCE = "sequence"

    @property
    def label(self) -> str:
        return _LAYER_TYPE_LABELS[self]


_LAYER_TYPE_LABELS = {
    LayerType.CAMERA: "CAM",
    LayerType.IMAGE: "IMG",
    LayerType.SEQUENCE: "SEQ",
}


class FitMode(Enum):
    VIEWPORT_HEIGHT = "viewport_height"
    VIEWPORT_WIDTH = "viewport_width"
    FILMGATE_HEIGHT = "filmgate_height"
    FILMGATE_WIDTH = "filmgate_width"


# ---------------------------------------------------------------------------
# Layer dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CameraLayer:
    """A camera + objectSet scene render layer."""

    name: str
    camera: str  # Camera node name (immutable after creation)
    object_set: str  # objectSet name (auto-created: vpcomp_<camera>_set)
    visible: bool = True

    layer_type: LayerType = field(default=LayerType.CAMERA, init=False, repr=False)

    def validate(self) -> list[str]:
        """Validate that camera and objectSet exist in the Maya scene.

        Returns a list of error messages (empty = valid).
        """
        import maya.cmds as cmds  # type: ignore

        errors: list[str] = []
        if not cmds.objExists(self.camera):
            errors.append(f"Camera does not exist: {self.camera}")
        if not cmds.objExists(self.object_set):
            errors.append(f"ObjectSet does not exist: {self.object_set}")
        elif cmds.nodeType(self.object_set) != "objectSet":
            errors.append(f"Node is not an objectSet: {self.object_set}")
        return errors


@dataclass
class ImageLayer:
    """A single static image overlay layer."""

    name: str
    file_path: str  # Absolute path to image file (PNG/JPG)
    fit_mode: FitMode = FitMode.VIEWPORT_HEIGHT
    visible: bool = True

    layer_type: LayerType = field(default=LayerType.IMAGE, init=False, repr=False)

    def validate(self) -> list[str]:
        """Validate that the image file exists.

        Returns a list of error messages (empty = valid).
        """
        errors: list[str] = []
        if not os.path.isfile(self.file_path):
            errors.append(f"Image file not found: {self.file_path}")
        return errors


@dataclass
class SequenceLayer:
    """A numbered image sequence layer synced to the Maya timeline."""

    name: str
    file_pattern: str  # printf-style path, e.g. "img.%04d.png"
    frame_start: int
    frame_end: int
    fit_mode: FitMode = FitMode.VIEWPORT_HEIGHT
    visible: bool = True

    layer_type: LayerType = field(default=LayerType.SEQUENCE, init=False, repr=False)

    def validate(self) -> list[str]:
        """Validate that at least one frame file exists.

        Returns a list of error messages (empty = valid).
        """
        errors: list[str] = []
        found_any = False
        for frame in range(self.frame_start, self.frame_end + 1):
            try:
                path = self.file_pattern % frame
            except (TypeError, ValueError):
                errors.append(f"Invalid file_pattern: {self.file_pattern}")
                return errors
            if os.path.isfile(path):
                found_any = True
                break
        if not found_any:
            errors.append(f"No sequence frames found for pattern: {self.file_pattern} (range {self.frame_start}-{self.frame_end})")
        return errors


# Union of all layer types
Layer = Union[CameraLayer, ImageLayer, SequenceLayer]


# ---------------------------------------------------------------------------
# LayerStack
# ---------------------------------------------------------------------------

# Default per-type maximum layer counts (configurable)
DEFAULT_MAX_CAMERA_LAYERS = 3
DEFAULT_MAX_IMAGE_LAYERS = 3
DEFAULT_MAX_SEQUENCE_LAYERS = 3


class LayerStack:
    """Ordered collection of compositing layers.

    Index 0 = backmost, last index = frontmost.
    """

    def __init__(
        self,
        *,
        max_camera: int = DEFAULT_MAX_CAMERA_LAYERS,
        max_image: int = DEFAULT_MAX_IMAGE_LAYERS,
        max_sequence: int = DEFAULT_MAX_SEQUENCE_LAYERS,
    ) -> None:
        self._layers: list[Layer] = []
        self._max: dict[LayerType, int] = {
            LayerType.CAMERA: max_camera,
            LayerType.IMAGE: max_image,
            LayerType.SEQUENCE: max_sequence,
        }

    # -- read access --------------------------------------------------------

    @property
    def layers(self) -> list[Layer]:
        """Return a shallow copy of the layer list."""
        return list(self._layers)

    def __len__(self) -> int:
        return len(self._layers)

    def __getitem__(self, index: int) -> Layer:
        return self._layers[index]

    # -- queries ------------------------------------------------------------

    def cameras_in_use(self) -> set[str]:
        """Return the set of camera names already used by CameraLayers."""
        return {layer.camera for layer in self._layers if isinstance(layer, CameraLayer)}

    def count_by_type(self, layer_type: LayerType) -> int:
        return sum(1 for layer in self._layers if layer.layer_type == layer_type)

    # -- mutators -----------------------------------------------------------

    def add(self, layer: Layer) -> None:
        """Append *layer* to the top (front) of the stack.

        Raises:
            ValueError: If a CameraLayer uses a camera already in the stack.
            RuntimeError: If the per-type limit is exceeded.
        """
        self._check_limits(layer)
        if isinstance(layer, CameraLayer):
            if layer.camera in self.cameras_in_use():
                raise ValueError(f"Camera already in use: {layer.camera}")
        self._layers.append(layer)
        logger.debug("Layer added: %s (type=%s)", layer.name, layer.layer_type.value)

    def remove(self, index: int) -> Layer:
        """Remove and return the layer at *index*.

        Raises:
            IndexError: If *index* is out of range.
        """
        layer = self._layers.pop(index)
        logger.debug("Layer removed: %s (index=%d)", layer.name, index)
        return layer

    def move(self, from_index: int, to_index: int) -> None:
        """Move a layer from *from_index* to *to_index*.

        Raises:
            IndexError: If either index is out of range.
        """
        if from_index == to_index:
            return
        n = len(self._layers)
        if not (0 <= from_index < n) or not (0 <= to_index < n):
            raise IndexError(f"Index out of range: from={from_index} to={to_index} len={n}")
        layer = self._layers.pop(from_index)
        self._layers.insert(to_index, layer)
        logger.debug("Layer moved: %s %d -> %d", layer.name, from_index, to_index)

    def replace_layers(self, new_layers: list[Layer]) -> None:
        """Replace the internal layer list (used by DnD reorder)."""
        self._layers = list(new_layers)

    def clear(self) -> None:
        """Remove all layers."""
        self._layers.clear()
        logger.debug("LayerStack cleared")

    # -- validation ---------------------------------------------------------

    def validate_all(self) -> dict[int, list[str]]:
        """Validate every layer.

        Returns:
            Dict mapping layer index to its list of error strings.
            Only indices with errors are included; empty dict = all valid.
        """
        errors: dict[int, list[str]] = {}
        for i, layer in enumerate(self._layers):
            layer_errors = layer.validate()
            if layer_errors:
                errors[i] = layer_errors
        return errors

    # -- internals ----------------------------------------------------------

    def _check_limits(self, layer: Layer) -> None:
        lt = layer.layer_type
        current = self.count_by_type(lt)
        limit = self._max.get(lt, 0)
        if current >= limit:
            raise RuntimeError(f"Maximum {lt.value} layers ({limit}) reached")
