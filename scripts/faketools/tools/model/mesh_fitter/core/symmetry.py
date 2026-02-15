"""Symmetry detection and enforcement — position-based and topology-based.

Supports:
    - Position-based (KDTree): fast, works with vertices only
    - Topology-based (BFS): robust, uses face connectivity to trace symmetry

Symmetry axis: fixed to X-axis (symmetric about YZ plane).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import enum
from logging import getLogger

import numpy as np
from scipy.spatial import cKDTree

logger = getLogger(__name__)


# =============================================================================
# Public types
# =============================================================================


class SymmetryMethod(enum.Enum):
    """Method for building the symmetry table."""

    POSITION = "position"
    TOPOLOGY = "topology"


@dataclass
class SymmetryResult:
    """Result of symmetry table construction.

    Attributes:
        center_indices: Vertex indices on the symmetry plane.
        pair_map: ``{negative_x_index: positive_x_index}`` mapping.
        failed_vertices: Vertices that could not be matched.
    """

    center_indices: list[int]
    pair_map: dict[int, int]
    failed_vertices: list[int] = field(default_factory=list)


# =============================================================================
# Internal data classes (topology method)
# =============================================================================


@dataclass
class _Face:
    index: int
    vertices: list[int]
    edges: list[int]
    is_done: bool = False


@dataclass
class _Edge:
    index: int
    vertices: tuple[int, int]
    faces: list[int]


@dataclass
class _MeshTopology:
    faces: dict[int, _Face]
    edges: dict[int, _Edge]
    vertex_positions: list[tuple[float, float, float]]
    vertex_to_edges: dict[int, list[int]]
    num_vertices: int


@dataclass
class _Task:
    face_a_index: int
    face_b_index: int
    edge_a_index: int
    edge_b_index: int


@dataclass
class _Shell:
    vertices: set[int]
    faces: set[int]
    centroid: tuple[float, float, float]


# =============================================================================
# Topology construction (from numpy arrays, no Maya dependency)
# =============================================================================


def _build_topology_from_arrays(vertices: np.ndarray, faces: np.ndarray) -> _MeshTopology:
    """Build topology from vertex positions and face index arrays."""
    num_vertices = len(vertices)
    vertex_positions = [(float(v[0]), float(v[1]), float(v[2])) for v in vertices]

    edge_key_to_idx: dict[tuple[int, int], int] = {}
    edges: dict[int, _Edge] = {}
    faces_dict: dict[int, _Face] = {}
    vertex_to_edges: dict[int, list[int]] = {i: [] for i in range(num_vertices)}
    next_edge_idx = 0

    for fi in range(len(faces)):
        face_verts = [int(v) for v in faces[fi]]
        face_edges: list[int] = []
        n = len(face_verts)

        for i in range(n):
            v0 = face_verts[i]
            v1 = face_verts[(i + 1) % n]
            key = (min(v0, v1), max(v0, v1))

            if key not in edge_key_to_idx:
                eidx = next_edge_idx
                next_edge_idx += 1
                edge_key_to_idx[key] = eidx
                edges[eidx] = _Edge(index=eidx, vertices=(v0, v1), faces=[fi])
                vertex_to_edges[v0].append(eidx)
                vertex_to_edges[v1].append(eidx)
            else:
                eidx = edge_key_to_idx[key]
                edges[eidx].faces.append(fi)

            face_edges.append(eidx)

        faces_dict[fi] = _Face(index=fi, vertices=face_verts, edges=face_edges)

    return _MeshTopology(
        faces=faces_dict,
        edges=edges,
        vertex_positions=vertex_positions,
        vertex_to_edges=vertex_to_edges,
        num_vertices=num_vertices,
    )


# =============================================================================
# Shell detection and classification
# =============================================================================


def _detect_shells(topology: _MeshTopology) -> list[_Shell]:
    """Detect connected components (shells) via BFS."""
    visited: set[int] = set()
    shells: list[_Shell] = []

    for start_vtx in range(topology.num_vertices):
        if start_vtx in visited:
            continue

        shell_vertices: set[int] = set()
        shell_faces: set[int] = set()
        queue: deque[int] = deque([start_vtx])

        while queue:
            vtx = queue.popleft()
            if vtx in visited:
                continue
            visited.add(vtx)
            shell_vertices.add(vtx)

            for edge_idx in topology.vertex_to_edges[vtx]:
                edge = topology.edges[edge_idx]
                for f in edge.faces:
                    shell_faces.add(f)
                other = edge.vertices[1] if edge.vertices[0] == vtx else edge.vertices[0]
                if other not in visited:
                    queue.append(other)

        if shell_vertices:
            n = len(shell_vertices)
            cx = sum(topology.vertex_positions[v][0] for v in shell_vertices) / n
            cy = sum(topology.vertex_positions[v][1] for v in shell_vertices) / n
            cz = sum(topology.vertex_positions[v][2] for v in shell_vertices) / n
            shells.append(
                _Shell(
                    vertices=shell_vertices,
                    faces=shell_faces,
                    centroid=(cx, cy, cz),
                )
            )

    return shells


def _classify_shells(shells: list[_Shell], threshold: float) -> tuple[list[_Shell], list[_Shell], list[_Shell]]:
    """Classify shells into (left, right, center) by centroid X."""
    left: list[_Shell] = []
    right: list[_Shell] = []
    center: list[_Shell] = []

    for shell in shells:
        cx = shell.centroid[0]
        if cx < -threshold:
            left.append(shell)
        elif cx > threshold:
            right.append(shell)
        else:
            center.append(shell)

    return left, right, center


def _pair_shells(
    left_shells: list[_Shell],
    right_shells: list[_Shell],
    threshold: float,
) -> list[tuple[_Shell, _Shell]]:
    """Pair left and right shells by mirrored centroid distance."""
    pairs: list[tuple[_Shell, _Shell]] = []
    used_right: set[int] = set()

    for left_shell in left_shells:
        best_idx: int | None = None
        best_dist = float("inf")

        for i, right_shell in enumerate(right_shells):
            if i in used_right:
                continue
            dy = right_shell.centroid[1] - left_shell.centroid[1]
            dz = right_shell.centroid[2] - left_shell.centroid[2]
            dist = (dy * dy + dz * dz) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx is not None and best_dist < threshold:
            pairs.append((left_shell, right_shells[best_idx]))
            used_right.add(best_idx)

    return pairs


# =============================================================================
# BFS helpers
# =============================================================================


def _find_center_edges(topology: _MeshTopology, center_vertices: set[int]) -> list[int]:
    """Find edges where both endpoints are center vertices (with 2 faces)."""
    result: list[int] = []
    for edge_idx, edge in topology.edges.items():
        v0, v1 = edge.vertices
        if v0 in center_vertices and v1 in center_vertices and len(edge.faces) == 2:
                result.append(edge_idx)
    return result


def _is_ccw(face_vertices: list[int], edge_vertices: tuple[int, int]) -> bool:
    """Check if edge traverses in CCW direction within the face."""
    v0, v1 = edge_vertices
    try:
        idx0 = face_vertices.index(v0)
        idx1 = face_vertices.index(v1)
    except ValueError:
        return False
    n = len(face_vertices)
    return (idx0 + 1) % n == idx1


def _rotate_list(lst: list, start_value) -> list:
    """Rotate list so that *start_value* is first."""
    try:
        idx = lst.index(start_value)
    except ValueError:
        return lst[:]
    return lst[idx:] + lst[:idx]


def _align_face_vertices(
    face_a_verts: list[int],
    face_b_verts: list[int],
    edge_a: _Edge,
    edge_b: _Edge,
) -> list[tuple[int, int]]:
    """Align vertices of two faces via shared edges and return pair list."""
    start_a = edge_a.vertices[0]
    start_b = edge_b.vertices[0]

    verts_a = _rotate_list(face_a_verts, start_a)
    verts_b = _rotate_list(face_b_verts, start_b)

    if not verts_a or not verts_b:
        return []

    is_a_ccw = _is_ccw(face_a_verts, edge_a.vertices)
    is_b_ccw = _is_ccw(face_b_verts, edge_b.vertices)

    if is_a_ccw == is_b_ccw:
        second_b = edge_b.vertices[1]
        verts_b = _rotate_list(verts_b, second_b)
        verts_b = verts_b[::-1]
        verts_b = _rotate_list(verts_b, second_b)
    else:
        verts_b = verts_b[::-1]
        verts_b = _rotate_list(verts_b, start_b)

    return list(zip(verts_a, verts_b))


def _determine_left_right(topology: _MeshTopology, face_a_idx: int, face_b_idx: int) -> tuple[int, int]:
    """Return ``(left_face_idx, right_face_idx)`` by centroid X."""
    face_a = topology.faces[face_a_idx]
    face_b = topology.faces[face_b_idx]

    cx_a = sum(topology.vertex_positions[v][0] for v in face_a.vertices) / len(face_a.vertices)
    cx_b = sum(topology.vertex_positions[v][0] for v in face_b.vertices) / len(face_b.vertices)

    if cx_a < cx_b:
        return face_a_idx, face_b_idx
    return face_b_idx, face_a_idx


# =============================================================================
# BFS symmetry traversal — connected mesh
# =============================================================================


def _bfs_symmetry(topology: _MeshTopology, start_edge: int, center_vertices: set[int]) -> tuple[dict[int, int], dict[int, int]]:
    """BFS from a center edge, returning ``(vertex_table, edge_pairs)``."""
    edge = topology.edges[start_edge]
    if len(edge.faces) != 2:
        logger.warning("Start edge %d does not have 2 adjacent faces", start_edge)
        return {}, {}

    left_face_idx, right_face_idx = _determine_left_right(topology, edge.faces[0], edge.faces[1])

    vertex_table: dict[int, int] = {}
    edge_pairs: dict[int, int] = {}

    for v in edge.vertices:
        vertex_table[v] = v

    edge_pairs[start_edge] = start_edge

    queue: deque[_Task] = deque()
    queue.append(
        _Task(
            face_a_index=left_face_idx,
            face_b_index=right_face_idx,
            edge_a_index=start_edge,
            edge_b_index=start_edge,
        )
    )

    for face in topology.faces.values():
        face.is_done = False

    while queue:
        task = queue.popleft()

        face_a = topology.faces[task.face_a_index]
        face_b = topology.faces[task.face_b_index]

        if face_a.is_done and face_b.is_done:
            continue

        face_a.is_done = True
        face_b.is_done = True

        edge_a = topology.edges[task.edge_a_index]
        edge_b = topology.edges[task.edge_b_index]

        pairs = _align_face_vertices(face_a.vertices, face_b.vertices, edge_a, edge_b)

        if not pairs:
            logger.warning(
                "Failed to align vertices for faces %d and %d",
                task.face_a_index,
                task.face_b_index,
            )
            continue

        for va, vb in pairs:
            if va not in vertex_table:
                vertex_table[va] = vb
            if vb not in vertex_table:
                vertex_table[vb] = va

        edges_a = _rotate_list(face_a.edges, task.edge_a_index)
        edges_b = _rotate_list(face_b.edges, task.edge_b_index)

        is_a_ccw = _is_ccw(face_a.vertices, edge_a.vertices)
        is_b_ccw = _is_ccw(face_b.vertices, edge_b.vertices)

        if is_a_ccw == is_b_ccw:
            edges_b = edges_b[::-1]
            edges_b = _rotate_list(edges_b, task.edge_b_index)
        else:
            edges_b = edges_b[::-1]
            edges_b = _rotate_list(edges_b, task.edge_b_index)

        for ea_idx, eb_idx in zip(edges_a, edges_b):
            if ea_idx not in edge_pairs:
                edge_pairs[ea_idx] = eb_idx
            if eb_idx not in edge_pairs:
                edge_pairs[eb_idx] = ea_idx

            ea = topology.edges[ea_idx]
            eb = topology.edges[eb_idx]

            next_face_a = None
            next_face_b = None

            for f in ea.faces:
                if f != task.face_a_index:
                    next_face_a = f
                    break

            for f in eb.faces:
                if f != task.face_b_index:
                    next_face_b = f
                    break

            if next_face_a is not None and next_face_b is not None:
                next_a = topology.faces[next_face_a]
                next_b = topology.faces[next_face_b]

                if not next_a.is_done or not next_b.is_done:
                    queue.append(
                        _Task(
                            face_a_index=next_face_a,
                            face_b_index=next_face_b,
                            edge_a_index=ea_idx,
                            edge_b_index=eb_idx,
                        )
                    )

    return vertex_table, edge_pairs


# =============================================================================
# BFS symmetry traversal — separated shells
# =============================================================================


def _bfs_between_shells(
    topology: _MeshTopology,
    left_shell: _Shell,
    right_shell: _Shell,
) -> dict[int, int]:
    """Match vertices between two separate shells via topology BFS."""
    if len(left_shell.vertices) != len(right_shell.vertices):
        logger.warning(
            "Shell vertex count mismatch: left=%d, right=%d",
            len(left_shell.vertices),
            len(right_shell.vertices),
        )

    left_faces = [topology.faces[f] for f in left_shell.faces]
    right_faces = [topology.faces[f] for f in right_shell.faces]

    if not left_faces or not right_faces:
        return {}

    # Find closest mirrored face pair as BFS seed
    best_left_face: _Face | None = None
    best_right_face: _Face | None = None
    best_dist = float("inf")

    for lf in left_faces:
        lf_cx = sum(topology.vertex_positions[v][0] for v in lf.vertices) / len(lf.vertices)
        lf_cy = sum(topology.vertex_positions[v][1] for v in lf.vertices) / len(lf.vertices)
        lf_cz = sum(topology.vertex_positions[v][2] for v in lf.vertices) / len(lf.vertices)
        mirrored_x = -lf_cx

        for rf in right_faces:
            rf_cx = sum(topology.vertex_positions[v][0] for v in rf.vertices) / len(rf.vertices)
            rf_cy = sum(topology.vertex_positions[v][1] for v in rf.vertices) / len(rf.vertices)
            rf_cz = sum(topology.vertex_positions[v][2] for v in rf.vertices) / len(rf.vertices)

            dx = rf_cx - mirrored_x
            dy = rf_cy - lf_cy
            dz = rf_cz - lf_cz
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5

            if dist < best_dist:
                best_dist = dist
                best_left_face = lf
                best_right_face = rf

    if best_left_face is None or best_right_face is None:
        return {}

    if len(best_left_face.vertices) != len(best_right_face.vertices):
        logger.warning(
            "Starting face vertex count mismatch: left=%d, right=%d",
            len(best_left_face.vertices),
            len(best_right_face.vertices),
        )
        return {}

    # Find closest mirrored vertex pair within the seed faces
    best_left_vtx: int | None = None
    best_right_vtx: int | None = None
    best_vtx_dist = float("inf")

    for lv in best_left_face.vertices:
        lpos = topology.vertex_positions[lv]
        mirrored_x = -lpos[0]
        for rv in best_right_face.vertices:
            rpos = topology.vertex_positions[rv]
            dx = rpos[0] - mirrored_x
            dy = rpos[1] - lpos[1]
            dz = rpos[2] - lpos[2]
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            if dist < best_vtx_dist:
                best_vtx_dist = dist
                best_left_vtx = lv
                best_right_vtx = rv

    if best_left_vtx is None or best_right_vtx is None:
        return {}

    # Initial vertex alignment from seed face
    left_vtx_idx = best_left_face.vertices.index(best_left_vtx)
    right_vtx_idx = best_right_face.vertices.index(best_right_vtx)

    left_verts_rotated = best_left_face.vertices[left_vtx_idx:] + best_left_face.vertices[:left_vtx_idx]
    right_verts_rotated = best_right_face.vertices[right_vtx_idx:] + best_right_face.vertices[:right_vtx_idx]
    right_verts_rotated = right_verts_rotated[::-1]
    right_verts_rotated = [right_verts_rotated[-1]] + right_verts_rotated[:-1]

    vertex_table: dict[int, int] = {}
    for lv, rv in zip(left_verts_rotated, right_verts_rotated):
        vertex_table[lv] = rv
        vertex_table[rv] = lv

    # BFS from seed faces
    for face in topology.faces.values():
        face.is_done = False
    best_left_face.is_done = True
    best_right_face.is_done = True

    queue: deque[_Task] = deque()

    # Seed the queue from edges of the starting faces
    for le_idx in best_left_face.edges:
        le = topology.edges[le_idx]
        if le.vertices[0] not in vertex_table or le.vertices[1] not in vertex_table:
            continue

        expected_rv0 = vertex_table[le.vertices[0]]
        expected_rv1 = vertex_table[le.vertices[1]]

        matching_re_idx: int | None = None
        for re_idx in best_right_face.edges:
            re = topology.edges[re_idx]
            if (re.vertices[0] == expected_rv0 and re.vertices[1] == expected_rv1) or (
                re.vertices[0] == expected_rv1 and re.vertices[1] == expected_rv0
            ):
                matching_re_idx = re_idx
                break

        if matching_re_idx is None:
            continue

        for next_lf in le.faces:
            if next_lf == best_left_face.index:
                continue
            if topology.faces[next_lf].is_done:
                continue

            re = topology.edges[matching_re_idx]
            for next_rf in re.faces:
                if next_rf == best_right_face.index:
                    continue
                if topology.faces[next_rf].is_done:
                    continue

                queue.append(
                    _Task(
                        face_a_index=next_lf,
                        face_b_index=next_rf,
                        edge_a_index=le_idx,
                        edge_b_index=matching_re_idx,
                    )
                )
                break

    # Main BFS loop
    while queue:
        task = queue.popleft()

        face_a = topology.faces[task.face_a_index]
        face_b = topology.faces[task.face_b_index]

        if face_a.is_done and face_b.is_done:
            continue

        face_a.is_done = True
        face_b.is_done = True

        edge_a = topology.edges[task.edge_a_index]
        start_a = edge_a.vertices[0]
        start_b = vertex_table.get(start_a, topology.edges[task.edge_b_index].vertices[0])

        verts_a = _rotate_list(face_a.vertices, start_a)
        verts_b = _rotate_list(face_b.vertices, start_b)

        if len(verts_a) != len(verts_b):
            continue

        verts_b = verts_b[::-1]
        verts_b = _rotate_list(verts_b, start_b)

        for va, vb in zip(verts_a, verts_b):
            if va not in vertex_table:
                vertex_table[va] = vb
            if vb not in vertex_table:
                vertex_table[vb] = va

        for le_idx in face_a.edges:
            le = topology.edges[le_idx]
            if le.vertices[0] not in vertex_table or le.vertices[1] not in vertex_table:
                continue

            expected_rv0 = vertex_table[le.vertices[0]]
            expected_rv1 = vertex_table[le.vertices[1]]

            matching_re_idx = None
            for re_idx in face_b.edges:
                re = topology.edges[re_idx]
                if (re.vertices[0] == expected_rv0 and re.vertices[1] == expected_rv1) or (
                    re.vertices[0] == expected_rv1 and re.vertices[1] == expected_rv0
                ):
                    matching_re_idx = re_idx
                    break

            if matching_re_idx is None:
                continue

            for next_lf in le.faces:
                if next_lf == task.face_a_index:
                    continue
                if topology.faces[next_lf].is_done:
                    continue

                re = topology.edges[matching_re_idx]
                for next_rf in re.faces:
                    if next_rf == task.face_b_index:
                        continue
                    if topology.faces[next_rf].is_done:
                        continue

                    queue.append(
                        _Task(
                            face_a_index=next_lf,
                            face_b_index=next_rf,
                            edge_a_index=le_idx,
                            edge_b_index=matching_re_idx,
                        )
                    )
                    break

    return vertex_table


# =============================================================================
# Position-based fallback for unmatched topology vertices
# =============================================================================


def _fallback_by_position(
    topology: _MeshTopology,
    unmatched_left: list[int],
    matched_right: set[int],
    threshold: float,
) -> tuple[dict[int, int], list[int]]:
    """Match remaining vertices by mirrored position (KDTree)."""
    right_candidates = [i for i in range(topology.num_vertices) if topology.vertex_positions[i][0] > 0 and i not in matched_right]

    if not right_candidates or not unmatched_left:
        return {}, list(unmatched_left)

    right_positions = np.array([topology.vertex_positions[i] for i in right_candidates])
    tree = cKDTree(right_positions)

    left_positions = np.array([topology.vertex_positions[i] for i in unmatched_left])
    mirrored = left_positions.copy()
    mirrored[:, 0] = -mirrored[:, 0]

    distances, nearest = tree.query(mirrored)

    matched: dict[int, int] = {}
    failed: list[int] = []

    for i, left_idx in enumerate(unmatched_left):
        if distances[i] < threshold:
            matched[left_idx] = right_candidates[nearest[i]]
        else:
            failed.append(left_idx)

    return matched, failed


# =============================================================================
# Method implementations
# =============================================================================


def _build_by_position(
    vertices: np.ndarray,
    center_indices: list[int] | None,
    threshold: float,
) -> SymmetryResult:
    """Position-based symmetry using KDTree (original method)."""
    verts = np.asarray(vertices)

    # Center vertices
    if center_indices is None:
        center_indices = np.where(np.abs(verts[:, 0]) < threshold)[0].tolist()

    # Split into +X and -X sides (excluding center)
    pos_indices = np.where(verts[:, 0] >= threshold)[0]
    neg_indices = np.where(verts[:, 0] <= -threshold)[0]

    if len(pos_indices) == 0 or len(neg_indices) == 0:
        return SymmetryResult(center_indices=center_indices, pair_map={})

    # Build KDTree of +X vertices
    pos_verts = verts[pos_indices]
    tree = cKDTree(pos_verts)

    # For each -X vertex, mirror across X=0 and find nearest +X vertex
    neg_verts = verts[neg_indices].copy()
    neg_verts[:, 0] = -neg_verts[:, 0]

    distances, nearest = tree.query(neg_verts)

    pair_map: dict[int, int] = {}
    for i, neg_idx in enumerate(neg_indices):
        if distances[i] < threshold:
            pair_map[int(neg_idx)] = int(pos_indices[nearest[i]])

    # Resolve many-to-one collisions (co-located vertices / UV seams)
    # Use KDTree query_ball_point + cache instead of O(n^2) full scan
    pos_to_negs: dict[int, list[int]] = defaultdict(list)
    for neg_idx, pos_idx in pair_map.items():
        pos_to_negs[pos_idx].append(neg_idx)

    # Map from pos_indices local index to global index
    pos_local_to_global: dict[int, int] = {}
    pos_global_to_local: dict[int, int] = {}
    for local_j, global_j in enumerate(pos_indices):
        pos_local_to_global[local_j] = int(global_j)
        pos_global_to_local[int(global_j)] = local_j

    colocated_cache: dict[int, list[int]] = {}

    for pos_idx, neg_group in pos_to_negs.items():
        if len(neg_group) <= 1:
            continue
        local_j = pos_global_to_local[pos_idx]
        if local_j in colocated_cache:
            colocated_pos = colocated_cache[local_j]
        else:
            ball = tree.query_ball_point(pos_verts[local_j], threshold)
            colocated_pos = sorted(int(pos_indices[j]) for j in ball)
            # Cache for all members of this group
            for j in ball:
                colocated_cache[j] = colocated_pos
        neg_sorted = sorted(neg_group)
        for k in range(min(len(neg_sorted), len(colocated_pos))):
            pair_map[neg_sorted[k]] = colocated_pos[k]

    return SymmetryResult(center_indices=center_indices, pair_map=pair_map)


def _build_by_topology(
    vertices: np.ndarray,
    faces: np.ndarray,
    center_indices: list[int] | None,
    threshold: float,
) -> SymmetryResult:
    """Topology-based symmetry using BFS face traversal."""
    topology = _build_topology_from_arrays(vertices, faces)

    # Position-based center detection
    if center_indices is None:
        center_indices = [i for i in range(topology.num_vertices) if abs(topology.vertex_positions[i][0]) < threshold]
    center_set = set(center_indices)

    shells = _detect_shells(topology)
    logger.debug("Detected %d shells", len(shells))

    left_shells, right_shells, center_shells = _classify_shells(shells, threshold)
    logger.debug(
        "Classified shells: left=%d, right=%d, center=%d",
        len(left_shells),
        len(right_shells),
        len(center_shells),
    )

    vertex_table: dict[int, int] = {}
    topology_center: list[int] = []

    # Process center shells (connected meshes with center edges)
    for shell in center_shells:
        shell_center_verts = shell.vertices & center_set
        center_edges = _find_center_edges(topology, shell_center_verts)

        if center_edges:
            shell_vtx_table, _ = _bfs_symmetry(topology, center_edges[0], shell_center_verts)
            vertex_table.update(shell_vtx_table)

            for v, opp in shell_vtx_table.items():
                if v == opp:
                    topology_center.append(v)

    # Process separated shell pairs
    shell_pairs = _pair_shells(left_shells, right_shells, threshold * 100)
    logger.debug("Paired %d left-right shell pairs", len(shell_pairs))

    for left_shell, right_shell in shell_pairs:
        shell_vtx_table = _bfs_between_shells(topology, left_shell, right_shell)
        vertex_table.update(shell_vtx_table)

    # Convert vertex_table to pair_map (neg_x -> pos_x)
    left_verts: set[int] = set()
    right_verts: set[int] = set()

    for i in range(topology.num_vertices):
        pos = topology.vertex_positions[i]
        if i in center_set or (i in vertex_table and vertex_table[i] == i):
            continue
        if pos[0] < 0:
            left_verts.add(i)
        elif pos[0] > 0:
            right_verts.add(i)

    pair_map: dict[int, int] = {}
    matched_left: set[int] = set()
    matched_right: set[int] = set()

    for v, opp in vertex_table.items():
        if v == opp:
            continue
        pos_v = topology.vertex_positions[v]
        pos_opp = topology.vertex_positions[opp]
        if pos_v[0] < pos_opp[0]:
            pair_map[v] = opp
            matched_left.add(v)
            matched_right.add(opp)
        else:
            pair_map[opp] = v
            matched_left.add(opp)
            matched_right.add(v)

    # Fallback for unmatched left vertices
    unmatched_left = [v for v in left_verts if v not in matched_left]
    failed_vertices: list[int] = []

    if unmatched_left:
        logger.warning(
            "Topology match failed for %d vertices. Attempting position-based fallback.",
            len(unmatched_left),
        )
        fallback_pairs, still_failed = _fallback_by_position(topology, unmatched_left, matched_right, threshold)
        pair_map.update(fallback_pairs)
        failed_vertices = still_failed

        if still_failed:
            logger.warning(
                "Position-based fallback also failed for %d vertices",
                len(still_failed),
            )

    # Use topology-detected center if available, else position-based
    final_center = topology_center if topology_center else center_indices

    return SymmetryResult(
        center_indices=final_center,
        pair_map=pair_map,
        failed_vertices=failed_vertices,
    )


# =============================================================================
# Public API
# =============================================================================


def build_symmetry_table(
    vertices: np.ndarray,
    faces: np.ndarray | None = None,
    center_indices: list[int] | None = None,
    threshold: float = 0.001,
    method: SymmetryMethod = SymmetryMethod.POSITION,
) -> SymmetryResult:
    """Build a symmetry table mapping -X vertices to +X counterparts.

    Args:
        vertices: ``(N, 3)`` vertex positions. Symmetry plane is X=0.
        faces: ``(F, V)`` face vertex indices. Required for ``TOPOLOGY`` method.
        center_indices: Explicit center vertex indices. If *None*, auto-detect
            vertices with ``|x| < threshold``.
        threshold: Distance threshold for center detection and pair matching.
        method: :class:`SymmetryMethod` — ``POSITION`` (KDTree) or
            ``TOPOLOGY`` (BFS face traversal).

    Returns:
        :class:`SymmetryResult` with *center_indices*, *pair_map*, and
        *failed_vertices*.
    """
    if method is SymmetryMethod.TOPOLOGY:
        if faces is None:
            raise ValueError("faces array is required for SymmetryMethod.TOPOLOGY")
        return _build_by_topology(vertices, faces, center_indices, threshold)

    return _build_by_position(vertices, center_indices, threshold)


def symmetrize_vertices(
    vertices: np.ndarray,
    center_indices: list[int],
    pair_map: dict[int, int],
    source_side: str = "positive",
) -> np.ndarray:
    """Apply symmetry by copying one side to the other across X=0.

    Args:
        vertices: ``(N, 3)`` vertex positions.
        center_indices: Indices of center vertices (snapped to X=0).
        pair_map: ``{negative_x_index: positive_x_index}`` mapping.
        source_side: ``"positive"`` copies +X to -X,
            ``"negative"`` copies -X to +X.

    Returns:
        Symmetrized vertex positions ``(N, 3)``.
    """
    result = np.array(vertices, dtype=float)

    # Snap center vertices to X=0
    if center_indices:
        ci = np.asarray(center_indices)
        result[ci, 0] = 0.0

    # Copy source side to destination side
    for neg_idx, pos_idx in pair_map.items():
        if source_side == "positive":
            result[neg_idx] = result[pos_idx].copy()
            result[neg_idx, 0] = -result[neg_idx, 0]
        else:
            result[pos_idx] = result[neg_idx].copy()
            result[pos_idx, 0] = -result[pos_idx, 0]

    return result
