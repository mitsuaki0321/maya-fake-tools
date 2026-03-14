"""Layer stack serialization — export/import as JSON.

Maya-independent pure Python module.  Uses only ``json`` and ``os``.
"""

from __future__ import annotations

import json
from logging import getLogger

from .model import (
    CameraLayer,
    FitMode,
    ImageLayer,
    Layer,
    LayerStack,
    SequenceLayer,
)

logger = getLogger(__name__)

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Layer ↔ dict
# ---------------------------------------------------------------------------


def layer_to_dict(layer: Layer) -> dict:
    """Serialize a single layer to a plain dict."""
    if isinstance(layer, CameraLayer):
        return {
            "layer_type": layer.layer_type.value,
            "name": layer.name,
            "camera": layer.camera,
            "object_set": layer.object_set,
        }
    if isinstance(layer, ImageLayer):
        return {
            "layer_type": layer.layer_type.value,
            "name": layer.name,
            "file_path": layer.file_path,
            "fit_mode": layer.fit_mode.value,
        }
    if isinstance(layer, SequenceLayer):
        return {
            "layer_type": layer.layer_type.value,
            "name": layer.name,
            "file_pattern": layer.file_pattern,
            "frame_start": layer.frame_start,
            "frame_end": layer.frame_end,
            "fit_mode": layer.fit_mode.value,
        }
    raise ValueError(f"Unknown layer type: {type(layer)}")


def layer_from_dict(d: dict) -> Layer:
    """Deserialize a single layer from a dict.

    Raises ``ValueError`` on unrecognised keys / values.
    """
    lt = d.get("layer_type")
    if lt == "camera":
        return CameraLayer(
            name=d["name"],
            camera=d["camera"],
            object_set=d["object_set"],
        )
    if lt == "image":
        return ImageLayer(
            name=d["name"],
            file_path=d["file_path"],
            fit_mode=FitMode(d["fit_mode"]),
        )
    if lt == "sequence":
        return SequenceLayer(
            name=d["name"],
            file_pattern=d["file_pattern"],
            frame_start=d["frame_start"],
            frame_end=d["frame_end"],
            fit_mode=FitMode(d["fit_mode"]),
        )
    raise ValueError(f"Unknown layer_type: {lt!r}")


# ---------------------------------------------------------------------------
# Stack ↔ dict
# ---------------------------------------------------------------------------


def stack_to_dict(stack: LayerStack) -> dict:
    """Serialize an entire *LayerStack* to a dict (ready for ``json.dump``)."""
    return {
        "version": SCHEMA_VERSION,
        "layers": [layer_to_dict(layer) for layer in stack.layers],
    }


def stack_from_dicts(data: dict) -> tuple[list[Layer], list[str]]:
    """Deserialize layers from a previously exported dict.

    Returns ``(layers, warnings)`` where *warnings* lists human-readable
    messages for any layers that could not be parsed.  Layers that fail
    deserialization are silently skipped.

    Raises ``ValueError`` if the schema version is unsupported.
    """
    version = data.get("version", 0)
    if version > SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema version {version} (max supported: {SCHEMA_VERSION})")

    layers: list[Layer] = []
    warnings: list[str] = []

    for i, entry in enumerate(data.get("layers", [])):
        try:
            layers.append(layer_from_dict(entry))
        except (KeyError, ValueError, TypeError) as exc:
            msg = f"Layer {i}: {exc}"
            warnings.append(msg)
            logger.warning("Skipping invalid layer dict: %s", msg)

    return layers, warnings


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def export_stack(stack: LayerStack, file_path: str) -> None:
    """Write *stack* to *file_path* as pretty-printed JSON."""
    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(stack_to_dict(stack), fp, indent=2, ensure_ascii=False)
    logger.info("Exported %d layer(s) to %s", len(stack), file_path)


def import_stack(file_path: str) -> tuple[dict, None] | tuple[None, str]:
    """Read a JSON file and return ``(data, None)`` on success.

    On failure returns ``(None, error_message)``.
    """
    try:
        with open(file_path, encoding="utf-8") as fp:
            data = json.load(fp)
        return data, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
