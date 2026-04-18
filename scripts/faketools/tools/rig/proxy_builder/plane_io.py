"""Plane specification, metadata embedding, and scene-level export/import.

Each plane created by :func:`.plane_command.create_plane_at_joint` has its
:class:`PlaneSpec` JSON-encoded onto the transform as the
``proxyBuilderMetadata`` attribute. :func:`export_planes_to_file` scans
the scene for such planes and writes a rig-agnostic JSON file;
:func:`import_planes_from_file` replays that file against the current scene
(optionally under a namespace), recreating every plane whose joint still
exists.

Complex joints such as shoulders, hips, and fingers are *not* intended to
round-trip through this system — they should be built by a dedicated
recipe script per rig.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
from logging import getLogger
from pathlib import Path
from typing import Literal, Optional

import maya.cmds as cmds

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


METADATA_ATTR = "proxyBuilderMetadata"
METADATA_VERSION = 1

RotationMode = Literal["joint", "aim", "manual"]
AimTarget = Literal["auto", "parent", "chain"]


@dataclass(frozen=True)
class PlaneSpec:
    """Specification for recreating a joint-driven cutting plane.

    Captures every parameter ``create_plane_at_joint`` needs so the plane
    can be regenerated later against the same rig (or a namespaced copy of
    it) without manual input.

    Attributes:
        joint (str): Joint the plane is placed at.
        rotation_mode (RotationMode): How plane orientation is computed.
            ``"joint"`` uses the joint's world rotation; ``"aim"`` aims
            along *aim_target*; ``"manual"`` uses the explicit *rotation*.
        axis (tuple[float, float, float]): Plane normal in the primitive's
            local frame before world rotation is applied.
        aim_joint (Optional[str]): Explicit aim target joint for
            ``rotation_mode="aim"``. Overrides *aim_target* when set.
        aim_target (AimTarget): Aim heuristic used when *aim_joint* is
            None — ``"auto"`` prefers child joints, ``"parent"`` always
            aims away from the parent, ``"chain"`` uses a parent→child
            vector.
        rotation (Optional[tuple[float, float, float]]): Explicit Euler
            rotation (degrees) for ``rotation_mode="manual"``.
        target_mesh (Optional[str]): Reference mesh for raycast-based
            automatic sizing. ``None`` disables auto-sizing; the plane
            falls back to using *size_scale* as its edge length when
            *size* is also None.
        size (Optional[tuple[float, float]]): Explicit (width, height).
            Overrides any auto-sizing.
        spans (tuple[int, int]): Polygon subdivision counts ``(U, V)``.
        size_scale (float): Auto-sized dimensions are multiplied by this.
            When *target_mesh* is None this is used directly as the edge
            length in world units.
        size_ratio_threshold (float): Outlier-rejection ratio for the
            raycast auto-size algorithm — opposite-direction distances
            whose ratio exceeds this are replaced by a symmetric short
            distance. See ``plane_command._resolve_axis_size``.
    """

    joint: str
    rotation_mode: RotationMode = "joint"
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0)
    aim_joint: Optional[str] = None
    aim_target: AimTarget = "auto"
    rotation: Optional[tuple[float, float, float]] = None
    target_mesh: Optional[str] = None
    size: Optional[tuple[float, float]] = None
    spans: tuple[int, int] = (1, 1)
    size_scale: float = 1.0
    size_ratio_threshold: float = 3.0

    # -- serialization --------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict including the schema version."""
        payload = asdict(self)
        payload["version"] = METADATA_VERSION
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> PlaneSpec:
        """Reconstruct a :class:`PlaneSpec` from a JSON-decoded dict.

        Unknown keys (e.g. future schema additions) are ignored with a
        warning. JSON lists representing tuple fields are coerced back to
        tuples so equality and hashing remain consistent.
        """
        version = data.get("version", METADATA_VERSION)
        if version != METADATA_VERSION:
            logger.warning("PlaneSpec metadata version %s, current is %s — attempting to load anyway", version, METADATA_VERSION)

        tuple_fields = {"axis", "rotation", "size", "spans"}
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs: dict = {}
        for key, value in data.items():
            if key == "version":
                continue
            if key not in known_fields:
                logger.warning("PlaneSpec.from_dict: ignoring unknown field '%s'", key)
                continue
            if key in tuple_fields and isinstance(value, list):
                kwargs[key] = tuple(value)
            else:
                kwargs[key] = value
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Per-plane metadata embedding
# ---------------------------------------------------------------------------


def embed_metadata(plane_name: str, spec: PlaneSpec) -> None:
    """Write *spec* onto *plane_name* as a JSON string attribute.

    The attribute is added on first write and overwritten on subsequent
    calls. Presence of the attribute is what :func:`export_planes_to_file`
    uses to decide whether a plane is round-trippable.
    """
    if not cmds.attributeQuery(METADATA_ATTR, node=plane_name, exists=True):
        cmds.addAttr(plane_name, longName=METADATA_ATTR, dataType="string")
    cmds.setAttr(f"{plane_name}.{METADATA_ATTR}", json.dumps(spec.to_dict()), type="string")


def read_metadata(plane_name: str) -> Optional[PlaneSpec]:
    """Return the :class:`PlaneSpec` stored on *plane_name*, or ``None``.

    Missing attribute, empty value, or malformed JSON all map to ``None``.
    The caller can then decide whether to treat the plane as a managed
    one or ignore it.
    """
    if not cmds.attributeQuery(METADATA_ATTR, node=plane_name, exists=True):
        return None
    raw = cmds.getAttr(f"{plane_name}.{METADATA_ATTR}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        logger.warning("read_metadata: failed to decode '%s.%s': %s", plane_name, METADATA_ATTR, exc)
        return None
    return PlaneSpec.from_dict(data)


# ---------------------------------------------------------------------------
# Scene-level export / import
# ---------------------------------------------------------------------------


def export_planes_to_file(
    path: str,
    planes: Optional[list[str]] = None,
) -> list[str]:
    """Write the specs of every managed plane in the scene to a JSON file.

    Args:
        path (str): Destination file path.
        planes (Optional[list[str]]): Restrict export to these transforms.
            When ``None`` (default) every node carrying the
            ``proxyBuilderMetadata`` attribute is considered.

    Returns:
        list[str]: Names of the planes that were actually written to the
            file. Planes without valid metadata are silently skipped.
    """
    if planes is None:
        planes = _find_managed_planes()

    entries: list[dict] = []
    exported: list[str] = []
    for plane in planes:
        spec = read_metadata(plane)
        if spec is None:
            logger.debug("export_planes_to_file: '%s' has no valid metadata, skipping", plane)
            continue
        entries.append({"plane_name": plane, "spec": spec.to_dict()})
        exported.append(plane)

    doc = {
        "version": METADATA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "planes": entries,
    }
    Path(path).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    logger.info("Exported %d plane(s) to %s", len(exported), path)
    return exported


def import_planes_from_file(
    path: str,
    target_mesh_override: Optional[str] = None,
) -> list[str]:
    """Recreate planes from a file written by :func:`export_planes_to_file`.

    Each entry's spec is validated against the current scene and fed back
    into :func:`.plane_command.create_plane_at_joint`. Joints that don't
    resolve are warned and skipped; aim joints / target meshes that don't
    resolve are cleared so the plane still creates with reasonable
    fallbacks. Existing planes with the same auto-generated name are also
    skipped (never overwritten).

    Args:
        path (str): Source JSON file.
        target_mesh_override (Optional[str]): When provided, every imported
            plane's ``target_mesh`` is replaced with this exact value.
            Useful when the target scene's body mesh has a different name
            than the source scene's. Defaults to ``None`` (keep the stored
            target mesh).

    Returns:
        list[str]: Names of the planes that were successfully created.
    """
    from . import plane_command  # local import avoids circular dependency

    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = doc.get("planes", [])

    created: list[str] = []
    for entry in entries:
        raw_spec = entry.get("spec")
        if raw_spec is None:
            logger.warning("import_planes_from_file: entry missing 'spec', skipping")
            continue
        spec = PlaneSpec.from_dict(raw_spec)
        if target_mesh_override is not None:
            spec = replace(spec, target_mesh=target_mesh_override)

        if not cmds.objExists(spec.joint):
            logger.warning("Skipping import: joint '%s' does not exist", spec.joint)
            continue
        if spec.aim_joint and not cmds.objExists(spec.aim_joint):
            logger.warning("aim_joint '%s' not found — clearing", spec.aim_joint)
            spec = replace(spec, aim_joint=None)
        if spec.target_mesh and not cmds.objExists(spec.target_mesh):
            logger.warning("target_mesh '%s' not found — clearing", spec.target_mesh)
            spec = replace(spec, target_mesh=None)

        expected_name = plane_command.plane_name_for_joint(spec.joint)
        if cmds.objExists(expected_name):
            logger.warning("Skipping import: plane '%s' already exists", expected_name)
            continue

        plane = plane_command.create_plane_at_joint(spec)
        created.append(plane)

    logger.info("Imported %d plane(s) from %s", len(created), path)
    return created


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _find_managed_planes() -> list[str]:
    """Return every transform in the scene that carries the metadata attr."""
    matches = cmds.ls(f"*.{METADATA_ATTR}", objectsOnly=True) or []
    return sorted(set(matches))


__all__ = [
    "METADATA_ATTR",
    "METADATA_VERSION",
    "AimTarget",
    "PlaneSpec",
    "RotationMode",
    "embed_metadata",
    "export_planes_to_file",
    "import_planes_from_file",
    "read_metadata",
]
