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
    asymmetric_count: int = 0
    asymmetric_indices: list[int] = field(default_factory=list)


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


def get_check_result_single(target: str, table: SymmetryResult, threshold: float) -> CheckResult:
    """Check target mesh symmetry using the base mesh's table.

    Args:
        target: Target mesh transform name.
        table: Symmetry table built from the base mesh.
        threshold: Distance threshold for asymmetry detection.

    Returns:
        Check result with asymmetric vertex information.
    """
    shape = validate_mesh(target)
    positions = _read_positions(shape)

    asymmetric: list[int] = []
    for neg_idx, pos_idx in table.pair_map.items():
        mirrored = positions[pos_idx].copy()
        mirrored[0] = -mirrored[0]
        dist = np.linalg.norm(positions[neg_idx] - mirrored)
        if dist > threshold:
            asymmetric.append(neg_idx)
            asymmetric.append(pos_idx)

    return CheckResult(
        matched_count=len(table.pair_map),
        center_count=len(table.center_indices),
        failed_count=len(table.failed_vertices),
        failed_indices=list(table.failed_vertices),
        asymmetric_count=len(asymmetric),
        asymmetric_indices=asymmetric,
    )


def get_check_result_dual(target_a: str, target_b: str, table: CorrespondenceResult, threshold: float) -> CheckResult:
    """Check dual mesh correspondence using the base pair's table.

    Args:
        target_a: Target mesh A transform name.
        target_b: Target mesh B transform name.
        table: Correspondence table built from the base pair.
        threshold: Distance threshold for asymmetry detection.

    Returns:
        Check result with asymmetric vertex information.
    """
    shape_a = validate_mesh(target_a)
    shape_b = validate_mesh(target_b)
    pos_a = _read_positions(shape_a)
    pos_b = _read_positions(shape_b)

    asymmetric: list[int] = []
    for a_idx, b_idx in table.pair_map.items():
        mirrored_a = pos_a[a_idx].copy()
        mirrored_a[0] = -mirrored_a[0]
        dist = np.linalg.norm(pos_b[b_idx] - mirrored_a)
        if dist > threshold:
            asymmetric.append(a_idx)

    return CheckResult(
        matched_count=len(table.pair_map),
        center_count=0,
        failed_count=len(table.failed_vertices_a) + len(table.failed_vertices_b),
        failed_indices=list(table.failed_vertices_a),
        asymmetric_count=len(asymmetric),
        asymmetric_indices=asymmetric,
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

    def mirror(self, direction: str, fallback: str = "closest_point") -> None:
        """Mirror vertex positions from one side to the other.

        Args:
            direction: ``"+x"`` copies +X side to -X side.
                ``"-x"`` copies -X side to +X side.
            fallback: ``"closest_point"`` or ``"laplacian"`` for failed vertices.
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
                new_pos[neg_idx] = new_pos[pos_idx].copy()
                new_pos[neg_idx, 0] = -new_pos[neg_idx, 0]
            else:
                new_pos[pos_idx] = new_pos[neg_idx].copy()
                new_pos[pos_idx, 0] = -new_pos[pos_idx, 0]

        # Fallback for failed vertices on the destination side
        if self._table.failed_vertices:
            dest_failed = _get_destination_failed_single(self._table.failed_vertices, target_pos, direction)
            if dest_failed:
                if fallback == "laplacian":
                    new_pos = _fallback_laplacian(target_shape, dest_failed, new_pos)
                else:
                    new_pos = _fallback_closest_point(target_shape, dest_failed, new_pos)

        _write_positions(self._target, target_pos, new_pos)
        cmds.select(self._target, r=True)
        logger.info("Mirror single: %s (direction=%s, pairs=%d, fallback=%s)", self._target, direction, len(pair_map), fallback)

    def flip(self, fallback: str = "closest_point") -> None:
        """Flip by exchanging L/R pair positions and negating center X.

        Args:
            fallback: ``"closest_point"`` or ``"laplacian"`` for failed vertices.
        """
        target_shape = validate_mesh(self._target)
        target_pos = _read_positions(target_shape)
        new_pos = target_pos.copy()

        pair_map = self._table.pair_map
        center_indices = self._table.center_indices

        # Exchange pair positions with X mirror so vertices stay on their side
        for neg_idx, pos_idx in pair_map.items():
            new_pos[neg_idx] = target_pos[pos_idx].copy()
            new_pos[neg_idx, 0] = -new_pos[neg_idx, 0]

            new_pos[pos_idx] = target_pos[neg_idx].copy()
            new_pos[pos_idx, 0] = -new_pos[pos_idx, 0]

        # Negate X for center vertices
        if center_indices:
            for ci in center_indices:
                new_pos[ci, 0] = -new_pos[ci, 0]

        # Fallback for failed vertices (both sides need processing in flip)
        if self._table.failed_vertices:
            if fallback == "laplacian":
                new_pos = _fallback_laplacian(target_shape, self._table.failed_vertices, new_pos)
            else:
                new_pos = _fallback_closest_point(target_shape, self._table.failed_vertices, new_pos)

        _write_positions(self._target, target_pos, new_pos)
        cmds.select(self._target, r=True)
        logger.info("Flip single: %s (pairs=%d, center=%d, fallback=%s)", self._target, len(pair_map), len(center_indices), fallback)


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

    def mirror(self, direction: str, fallback: str = "closest_point") -> None:
        """Mirror vertex positions from one mesh to the other.

        Args:
            direction: ``"a_to_b"`` copies A (mirrored) to B.
                ``"b_to_a"`` copies B (mirrored) to A.
            fallback: ``"closest_point"`` or ``"laplacian"`` for failed vertices.
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

            if self._table.failed_vertices_b:
                if fallback == "laplacian":
                    new_b = _fallback_laplacian(shape_b, self._table.failed_vertices_b, new_b)
                else:
                    new_b = _fallback_closest_point(shape_a, self._table.failed_vertices_b, new_b)

            _write_positions(self._target_b, pos_b, new_b)
        else:
            new_a = pos_a.copy()
            reverse_map = {b: a for a, b in pair_map.items()}
            for b_idx, a_idx in reverse_map.items():
                new_a[a_idx] = pos_b[b_idx].copy()
                new_a[a_idx, 0] = -new_a[a_idx, 0]

            if self._table.failed_vertices_a:
                if fallback == "laplacian":
                    new_a = _fallback_laplacian(shape_a, self._table.failed_vertices_a, new_a)
                else:
                    new_a = _fallback_closest_point(shape_b, self._table.failed_vertices_a, new_a)

            _write_positions(self._target_a, pos_a, new_a)

        cmds.select([self._target_a, self._target_b], r=True)
        logger.info("Mirror dual: %s -> %s (pairs=%d, fallback=%s)", self._target_a, self._target_b, len(pair_map), fallback)

    def flip(self, fallback: str = "closest_point") -> None:
        """Exchange vertex positions between two meshes with X negation.

        Args:
            fallback: ``"closest_point"`` or ``"laplacian"`` for failed vertices.
        """
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

        # Fallback for failed vertices
        if self._table.failed_vertices_a:
            if fallback == "laplacian":
                new_a = _fallback_laplacian(shape_a, self._table.failed_vertices_a, new_a)
            else:
                new_a = _fallback_closest_point(shape_b, self._table.failed_vertices_a, new_a)

        if self._table.failed_vertices_b:
            if fallback == "laplacian":
                new_b = _fallback_laplacian(shape_b, self._table.failed_vertices_b, new_b)
            else:
                new_b = _fallback_closest_point(shape_a, self._table.failed_vertices_b, new_b)

        _write_positions(self._target_a, pos_a, new_a)
        _write_positions(self._target_b, pos_b, new_b)
        cmds.select([self._target_a, self._target_b], r=True)
        logger.info("Flip dual: %s <-> %s (pairs=%d, fallback=%s)", self._target_a, self._target_b, len(pair_map), fallback)


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
        ``(N, 3)`` vertex positions in object space.
    """
    fn = _get_mesh_fn(shape)
    pts = fn.getPoints(om.MSpace.kObject)
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
    return np.array(faces, dtype=object)


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
        cmds.xform(f"{mesh}.vtx[{idx}]", os=True, t=[float(p[0]), float(p[1]), float(p[2])])

    logger.debug("Updated %d / %d vertices on %s", len(changed), len(old_pos), mesh)


# =====================================================================
# Private: Failed vertex fallback
# =====================================================================


def _get_destination_failed_single(
    failed_vertices: list[int],
    positions: np.ndarray,
    direction: str,
) -> list[int]:
    """Get failed vertices that are on the destination side.

    Args:
        failed_vertices: All failed vertex indices.
        positions: Vertex positions ``(N, 3)``.
        direction: ``"+x"`` or ``"-x"``.

    Returns:
        Failed vertex indices on the destination side.
    """
    result = []
    for vi in failed_vertices:
        x = positions[vi, 0]
        if direction == "+x" and x < 0:
            # +X → -X: destination is -X side
            result.append(vi)
        elif direction == "-x" and x > 0:
            # -X → +X: destination is +X side
            result.append(vi)
    return result


def _fallback_closest_point(
    shape: str,
    failed_indices: list[int],
    new_positions: np.ndarray,
) -> np.ndarray:
    """Fallback using closest point on mesh surface.

    For each failed vertex, mirrors its position and finds the closest
    point on the original mesh surface, then mirrors back.

    Args:
        shape: Mesh shape node full path (original, unmodified in Maya).
        failed_indices: Vertex indices to process.
        new_positions: Position array to update in-place.

    Returns:
        Updated position array.
    """
    if not failed_indices:
        return new_positions

    sel = om.MSelectionList()
    sel.add(shape)
    dag = sel.getDagPath(0)
    fn = om.MFnMesh(dag)

    for idx in failed_indices:
        mirrored = om.MPoint(-new_positions[idx, 0], new_positions[idx, 1], new_positions[idx, 2])
        closest, _ = fn.getClosestPoint(mirrored, om.MSpace.kObject)
        new_positions[idx] = [-closest.x, closest.y, closest.z]

    logger.debug("Closest point fallback: processed %d vertices", len(failed_indices))
    return new_positions


def _fallback_laplacian(
    shape: str,
    failed_indices: list[int],
    new_positions: np.ndarray,
    max_iterations: int = 20,
    tolerance: float = 1e-6,
) -> np.ndarray:
    """Fallback using Laplacian smoothing from neighbor vertices.

    Iteratively averages failed vertex positions from their connected
    neighbors. Converges when neighbors are already processed (paired).

    Args:
        shape: Mesh shape node full path.
        failed_indices: Vertex indices to process.
        new_positions: Position array to update in-place.
        max_iterations: Maximum smoothing iterations.
        tolerance: Convergence threshold.

    Returns:
        Updated position array.
    """
    if not failed_indices:
        return new_positions

    sel = om.MSelectionList()
    sel.add(shape)
    dag = sel.getDagPath(0)
    mit = om.MItMeshVertex(dag)

    # Build connectivity map for failed vertices
    neighbors: dict[int, list[int]] = {}
    for idx in failed_indices:
        mit.setIndex(idx)
        neighbors[idx] = list(mit.getConnectedVertices())

    for iteration in range(max_iterations):
        prev = new_positions[failed_indices].copy()

        for idx in failed_indices:
            nbr_indices = neighbors[idx]
            if not nbr_indices:
                continue
            new_positions[idx] = np.mean(new_positions[nbr_indices], axis=0)

        # Check convergence
        diff = np.max(np.abs(new_positions[failed_indices] - prev))
        if diff < tolerance:
            logger.debug("Laplacian fallback converged at iteration %d", iteration + 1)
            break

    logger.debug("Laplacian fallback: processed %d vertices (%d iterations)", len(failed_indices), iteration + 1)
    return new_positions
