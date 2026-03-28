"""Mesh Mirror command layer.

Provides mirror and flip operations for single-mesh symmetry
and dual-mesh correspondence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np

from ....lib.lib_symmetry import (
    CorrespondenceMethod,
    CorrespondenceResult,
    SymmetryMethod,
    SymmetryResult,
    build_correspondence_table,
    build_symmetry_table,
)

logger = getLogger(__name__)


# =====================================================================
# Data types
# =====================================================================


@dataclass
class CheckResult:
    """Symmetry / correspondence check results for UI display."""

    matched_count: int
    center_count: int
    failed_count: int
    failed_indices: list[int] = field(default_factory=list)


# =====================================================================
# Public: Validation
# =====================================================================


def validate_mesh(transform: str) -> str:
    """Validate that *transform* has a mesh shape and return the shape name.

    Args:
        transform: Maya transform node name.

    Returns:
        Full path of the mesh shape node.

    Raises:
        ValueError: If the node doesn't exist or has no mesh shape.
    """
    if not cmds.objExists(transform):
        raise ValueError(f"Node does not exist: {transform}")

    shapes = cmds.listRelatives(transform, shapes=True, type="mesh", fullPath=True) or []
    if not shapes:
        raise ValueError(f"No mesh shape found: {transform}")

    return shapes[0]


def validate_same_topology(mesh_a: str, mesh_b: str) -> bool:
    """Check if two mesh transforms have identical topology.

    Args:
        mesh_a: First mesh transform name.
        mesh_b: Second mesh transform name.

    Returns:
        True if topology matches.
    """
    shape_a = validate_mesh(mesh_a)
    shape_b = validate_mesh(mesh_b)

    fn_a = _get_mesh_fn(shape_a)
    fn_b = _get_mesh_fn(shape_b)

    if fn_a.numVertices != fn_b.numVertices:
        return False
    if fn_a.numEdges != fn_b.numEdges:
        return False
    if fn_a.numPolygons != fn_b.numPolygons:
        return False

    return all(list(fn_a.getPolygonVertices(i)) == list(fn_b.getPolygonVertices(i)) for i in range(fn_a.numPolygons))


# =====================================================================
# Public: Table Building + Check
# =====================================================================


def build_single_table(base: str, method: str, threshold: float) -> SymmetryResult:
    """Build symmetry table from a base mesh.

    Args:
        base: Base mesh transform name (should be symmetric).
        method: ``"position"`` or ``"topology"``.
        threshold: Distance threshold.

    Returns:
        :class:`SymmetryResult`.
    """
    shape = validate_mesh(base)
    positions = _read_positions(shape)
    faces = _read_faces(shape) if method == "topology" else None

    sym_method = SymmetryMethod(method)
    return build_symmetry_table(positions, faces=faces, threshold=threshold, method=sym_method)


def build_dual_table(base_a: str, base_b: str, method: str, threshold: float) -> CorrespondenceResult:
    """Build correspondence table from a base mesh pair.

    Args:
        base_a: Base mesh A transform name.
        base_b: Base mesh B transform name.
        method: ``"index"``, ``"position"``, or ``"topology"``.
        threshold: Distance threshold.

    Returns:
        :class:`CorrespondenceResult`.
    """
    shape_a = validate_mesh(base_a)
    shape_b = validate_mesh(base_b)
    pos_a = _read_positions(shape_a)
    pos_b = _read_positions(shape_b)

    corr_method = CorrespondenceMethod(method)
    faces_a = _read_faces(shape_a) if method == "topology" else None
    faces_b = _read_faces(shape_b) if method == "topology" else None

    return build_correspondence_table(pos_a, pos_b, faces_a=faces_a, faces_b=faces_b, method=corr_method, threshold=threshold)


def get_check_result_single(table: SymmetryResult) -> CheckResult:
    """Extract check statistics from a symmetry table."""
    return CheckResult(
        matched_count=len(table.pair_map),
        center_count=len(table.center_indices),
        failed_count=len(table.failed_vertices),
        failed_indices=list(table.failed_vertices),
    )


def get_check_result_dual(table: CorrespondenceResult) -> CheckResult:
    """Extract check statistics from a correspondence table."""
    return CheckResult(
        matched_count=len(table.pair_map),
        center_count=0,
        failed_count=len(table.failed_vertices_a) + len(table.failed_vertices_b),
        failed_indices=list(table.failed_vertices_a),
    )


def select_failed_vertices(mesh: str, indices: list[int]) -> None:
    """Select failed vertices in Maya viewport.

    Args:
        mesh: Mesh transform name.
        indices: Vertex indices to select.
    """
    if not indices:
        cmds.select(clear=True)
        return

    components = [f"{mesh}.vtx[{i}]" for i in indices]
    cmds.select(components, replace=True)


# =====================================================================
# Public: Operations — Single mesh
# =====================================================================


class SingleMeshOperation:
    """Mirror / flip operations for a single mesh with internal symmetry."""

    def __init__(self, target: str, base: str, table: SymmetryResult):
        """Initialize with target mesh, base mesh, and symmetry table.

        Args:
            target: Target mesh transform name (to modify).
            base: Base mesh transform name (symmetric reference).
            table: Symmetry table built from the base mesh.
        """
        self._target = target
        self._base = base
        self._table = table

    def mirror(self, direction: str) -> None:
        """Mirror vertex positions from one side to the other.

        Args:
            direction: ``"+x"`` copies +X side to -X side.
                ``"-x"`` copies -X side to +X side.
        """
        target_shape = validate_mesh(self._target)
        target_pos = _read_positions(target_shape)
        new_pos = target_pos.copy()

        pair_map = self._table.pair_map
        center_indices = self._table.center_indices

        # Snap center vertices to X=0
        if center_indices:
            for ci in center_indices:
                new_pos[ci, 0] = 0.0

        # Copy source side to destination side
        for neg_idx, pos_idx in pair_map.items():
            if direction == "+x":
                # +X is source → overwrite -X
                new_pos[neg_idx] = new_pos[pos_idx].copy()
                new_pos[neg_idx, 0] = -new_pos[neg_idx, 0]
            else:
                # -X is source → overwrite +X
                new_pos[pos_idx] = new_pos[neg_idx].copy()
                new_pos[pos_idx, 0] = -new_pos[pos_idx, 0]

        # Delta fallback for failed vertices
        if self._table.failed_vertices:
            base_shape = validate_mesh(self._base)
            base_pos = _read_positions(base_shape)
            new_pos = _apply_delta_fallback_single(new_pos, target_pos, base_pos, self._table, direction)

        _write_positions(self._target, target_pos, new_pos)
        logger.info("Mirror single: %s (direction=%s, pairs=%d)", self._target, direction, len(pair_map))

    def flip(self) -> None:
        """Flip all vertex positions by negating X and reversing normals."""
        num_vtx = cmds.polyEvaluate(self._target, v=True)
        if num_vtx == 0:
            return

        cmds.scale(-1.0, 1.0, 1.0, f"{self._target}.vtx[0:{num_vtx - 1}]", pivot=[0, 0, 0], r=True)
        cmds.polyNormal(self._target, normalMode=0, userNormalMode=0, ch=False)
        logger.info("Flip single: %s", self._target)


# =====================================================================
# Public: Operations — Dual mesh
# =====================================================================


class DualMeshOperation:
    """Mirror / flip operations between two meshes."""

    def __init__(
        self,
        target_a: str,
        target_b: str,
        base_a: str,
        base_b: str,
        table: CorrespondenceResult,
    ):
        """Initialize with target pair, base pair, and correspondence table.

        Args:
            target_a: Target mesh A transform name.
            target_b: Target mesh B transform name.
            base_a: Base mesh A transform name.
            base_b: Base mesh B transform name.
            table: Correspondence table built from the base pair.
        """
        self._target_a = target_a
        self._target_b = target_b
        self._base_a = base_a
        self._base_b = base_b
        self._table = table

    def mirror(self, direction: str) -> None:
        """Mirror vertex positions from one mesh to the other.

        Args:
            direction: ``"a_to_b"`` copies A (mirrored) to B.
                ``"b_to_a"`` copies B (mirrored) to A.
        """
        shape_a = validate_mesh(self._target_a)
        shape_b = validate_mesh(self._target_b)
        pos_a = _read_positions(shape_a)
        pos_b = _read_positions(shape_b)

        pair_map = self._table.pair_map

        if direction == "a_to_b":
            new_b = pos_b.copy()
            for a_idx, b_idx in pair_map.items():
                new_b[b_idx] = pos_a[a_idx].copy()
                new_b[b_idx, 0] = -new_b[b_idx, 0]

            # Delta fallback for failed vertices
            if self._table.failed_vertices_a:
                new_b = self._apply_delta_fallback(pos_a, pos_b, new_b, direction)

            _write_positions(self._target_b, pos_b, new_b)
        else:
            new_a = pos_a.copy()
            reverse_map = {b: a for a, b in pair_map.items()}
            for b_idx, a_idx in reverse_map.items():
                new_a[a_idx] = pos_b[b_idx].copy()
                new_a[a_idx, 0] = -new_a[a_idx, 0]

            if self._table.failed_vertices_b:
                new_a = self._apply_delta_fallback(pos_a, pos_b, new_a, direction)

            _write_positions(self._target_a, pos_a, new_a)

        logger.info("Mirror dual: %s -> %s (pairs=%d)", self._target_a, self._target_b, len(pair_map))

    def flip(self) -> None:
        """Exchange vertex positions between two meshes with X negation."""
        shape_a = validate_mesh(self._target_a)
        shape_b = validate_mesh(self._target_b)
        pos_a = _read_positions(shape_a)
        pos_b = _read_positions(shape_b)

        pair_map = self._table.pair_map

        new_a = pos_a.copy()
        new_b = pos_b.copy()

        for a_idx, b_idx in pair_map.items():
            new_a[a_idx] = pos_b[b_idx].copy()
            new_a[a_idx, 0] = -new_a[a_idx, 0]

            new_b[b_idx] = pos_a[a_idx].copy()
            new_b[b_idx, 0] = -new_b[b_idx, 0]

        # Delta fallback for failed vertices
        if self._table.failed_vertices_a or self._table.failed_vertices_b:
            base_shape_a = validate_mesh(self._base_a)
            base_shape_b = validate_mesh(self._base_b)
            base_a = _read_positions(base_shape_a)
            base_b = _read_positions(base_shape_b)

            for a_idx in self._table.failed_vertices_a:
                delta = pos_a[a_idx] - base_a[a_idx]
                delta[0] = -delta[0]
                new_b[a_idx] = base_b[a_idx] + delta

            for b_idx in self._table.failed_vertices_b:
                delta = pos_b[b_idx] - base_b[b_idx]
                delta[0] = -delta[0]
                new_a[b_idx] = base_a[b_idx] + delta

        _write_positions(self._target_a, pos_a, new_a)
        _write_positions(self._target_b, pos_b, new_b)
        logger.info("Flip dual: %s <-> %s (pairs=%d)", self._target_a, self._target_b, len(pair_map))

    def _apply_delta_fallback(
        self,
        pos_a: np.ndarray,
        pos_b: np.ndarray,
        new_dest: np.ndarray,
        direction: str,
    ) -> np.ndarray:
        """Apply delta fallback for unmatched vertices in dual mesh mirror."""
        base_shape_a = validate_mesh(self._base_a)
        base_shape_b = validate_mesh(self._base_b)
        base_a = _read_positions(base_shape_a)
        base_b = _read_positions(base_shape_b)

        if direction == "a_to_b":
            for a_idx in self._table.failed_vertices_a:
                delta = pos_a[a_idx] - base_a[a_idx]
                delta[0] = -delta[0]
                new_dest[a_idx] = base_b[a_idx] + delta
        else:
            for b_idx in self._table.failed_vertices_b:
                delta = pos_b[b_idx] - base_b[b_idx]
                delta[0] = -delta[0]
                new_dest[b_idx] = base_a[b_idx] + delta

        return new_dest


# =====================================================================
# Private: Maya I/O
# =====================================================================


def _get_mesh_fn(shape: str) -> om.MFnMesh:
    """Get MFnMesh from a shape name."""
    sel = om.MSelectionList()
    sel.add(shape)
    return om.MFnMesh(sel.getDagPath(0))


def _read_positions(shape: str) -> np.ndarray:
    """Read vertex positions as numpy array (OpenMaya, read-only).

    Args:
        shape: Mesh shape node full path.

    Returns:
        ``(N, 3)`` vertex positions in world space.
    """
    fn = _get_mesh_fn(shape)
    pts = fn.getPoints(om.MSpace.kWorld)
    n = fn.numVertices

    arr = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        arr[i] = [pts[i].x, pts[i].y, pts[i].z]
    return arr


def _read_faces(shape: str) -> np.ndarray:
    """Read face vertex indices as numpy array (OpenMaya, read-only).

    Args:
        shape: Mesh shape node full path.

    Returns:
        ``(F, V)`` face vertex index array (assumes uniform face size).
    """
    fn = _get_mesh_fn(shape)
    num_faces = fn.numPolygons

    faces = []
    for i in range(num_faces):
        faces.append(list(fn.getPolygonVertices(i)))
    return np.array(faces)


def _write_positions(mesh: str, old_pos: np.ndarray, new_pos: np.ndarray) -> None:
    """Write only changed vertex positions using cmds (undo-safe).

    Args:
        mesh: Mesh transform name.
        old_pos: Original positions ``(N, 3)``.
        new_pos: New positions ``(N, 3)``.
    """
    diff = np.any(np.abs(old_pos - new_pos) > 1e-10, axis=1)
    changed = np.where(diff)[0]

    for idx in changed:
        p = new_pos[idx]
        cmds.xform(f"{mesh}.vtx[{idx}]", ws=True, t=[float(p[0]), float(p[1]), float(p[2])])

    logger.debug("Updated %d / %d vertices on %s", len(changed), len(old_pos), mesh)


# =====================================================================
# Private: Delta fallback
# =====================================================================


def _apply_delta_fallback_single(
    new_pos: np.ndarray,
    target_pos: np.ndarray,
    base_pos: np.ndarray,
    table: SymmetryResult,
    direction: str,
) -> np.ndarray:
    """Apply delta fallback for unmatched vertices in single mesh mirror.

    For each failed vertex, use the base mesh's pair_map to find the pair,
    compute delta from base, and apply the mirrored delta to the other side.
    """
    # The base mesh table should cover all vertices. But for vertices that
    # failed even in the base, we skip them.
    pair_map = table.pair_map

    for vi in table.failed_vertices:
        # Find this vertex's pair from any available mapping
        paired = None
        for neg, pos in pair_map.items():
            if neg == vi:
                paired = pos
                break
            if pos == vi:
                paired = neg
                break

        if paired is None:
            logger.warning("No pair found for failed vertex %d, skipping.", vi)
            continue

        delta = target_pos[vi] - base_pos[vi]
        delta[0] = -delta[0]

        if direction == "+x":
            new_pos[vi] = base_pos[paired] + delta
        else:
            new_pos[paired] = base_pos[vi] + delta
            new_pos[paired, 0] = -new_pos[paired, 0]

    return new_pos
