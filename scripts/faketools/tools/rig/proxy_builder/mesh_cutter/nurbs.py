"""Cut a polygon mesh along NURBS surface intersections."""

from collections import deque
from logging import getLogger
from typing import Optional

import maya.api.OpenMaya as om
import maya.cmds as cmds

from .utility import filter_cut_line_edges, get_dag_path

logger = getLogger(__name__)

# Clamp t values within this threshold of vertices
T_CLAMP = 0.01

# Threshold for near-vertex deduplication.
# When the NURBS passes close to a mesh vertex, both edges sharing that vertex
# may register an intersection. Edges with t below this threshold are removed
# if the adjacent edge on the other side of the shared vertex already has a
# t above (1 - threshold).
VERTEX_DEDUP_THRESHOLD = 0.03


def cut(cutter_name: str, target_name: str) -> list[int]:
    """Cut a target mesh along a NURBS surface intersection.

    Args:
        cutter_name (str): NURBS surface node name.
        target_name (str): Polygon mesh node name.

    Returns:
        list[int]: New edge indices created by the cut.
    """
    verts_before = om.MFnMesh(get_dag_path(target_name)).numVertices
    cut_edges = _find_cut_edges(target_name, cutter_name)
    _split_edges(target_name, cut_edges)
    return filter_cut_line_edges(target_name, verts_before)


def _find_cut_edges(mesh_name: str, nurbs_name: str) -> list[tuple[int, float]]:
    """Find mesh edges that straddle a NURBS surface.

    Casts a ray along each edge (v0 -> v1) and checks for intersection
    with the NURBS surface. If the intersection lies within the edge
    range (t: 0-1), the edge is marked as a cut edge. t values near
    vertices (< T_CLAMP or > 1-T_CLAMP) are clamped so the split
    point stays on the edge rather than coinciding with a vertex.

    Args:
        mesh_name (str): Polygon mesh node name.
        nurbs_name (str): NURBS surface node name.

    Returns:
        list[tuple[int, float]]: (edge index, t value). t is clamped to [T_CLAMP, 1-T_CLAMP].
    """
    mesh_dag = get_dag_path(mesh_name)
    nurbs_dag = get_dag_path(nurbs_name)
    nurbs_fn = om.MFnNurbsSurface(nurbs_dag)

    mesh_fn = om.MFnMesh(mesh_dag)
    points = mesh_fn.getPoints(om.MSpace.kWorld)

    # Pre-compute the NURBS world-inverse matrix so that world-space rays
    # can be transformed into the surface's object space for intersection.
    nurbs_world_inv = nurbs_dag.inclusiveMatrixInverse()
    nurbs_world_matrix = nurbs_dag.inclusiveMatrix()

    cut_edges: list[tuple[int, float]] = []

    edge_it = om.MItMeshEdge(mesh_dag)
    while not edge_it.isDone():
        v0 = edge_it.vertexId(0)
        v1 = edge_it.vertexId(1)

        pt_a = points[v0]
        pt_b = points[v1]
        direction = om.MVector(pt_b - pt_a)
        edge_length = direction.length()

        if edge_length > 1e-10:
            t = _ray_intersect(nurbs_fn, om.MPoint(pt_a), direction, edge_length, nurbs_world_inv, nurbs_world_matrix)
            if t is not None:
                t = max(T_CLAMP, min(1.0 - T_CLAMP, t))
                cut_edges.append((edge_it.index(), t))

        edge_it.next()

    cut_edges = _deduplicate_vertex_hits(mesh_dag, cut_edges)
    return cut_edges


def _deduplicate_vertex_hits(
    mesh_dag: om.MDagPath,
    cut_edges: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    """Remove duplicate near-vertex intersections.

    When the NURBS surface passes close to a mesh vertex, both edges sharing
    that vertex can register an intersection (one with t near 0, the other
    with t near 1).  This keeps the t-near-1 edge and removes the t-near-0
    edge, since both describe the same intersection point.

    Args:
        mesh_dag (om.MDagPath): MDagPath of the mesh.
        cut_edges (list[tuple[int, float]]): (edge index, t value).

    Returns:
        list[tuple[int, float]]: Filtered list with near-vertex duplicates removed.
    """
    th = VERTEX_DEDUP_THRESHOLD
    near_zero_eids = {eid for eid, t in cut_edges if t < th}
    if not near_zero_eids:
        return cut_edges

    near_one_eids = {eid for eid, t in cut_edges if t > 1.0 - th}

    # Collect vertex IDs for edges that are candidates
    candidate_eids = near_zero_eids | near_one_eids
    edge_verts: dict[int, tuple[int, int]] = {}
    edge_it = om.MItMeshEdge(mesh_dag)
    while not edge_it.isDone():
        eid = edge_it.index()
        if eid in candidate_eids:
            edge_verts[eid] = (edge_it.vertexId(0), edge_it.vertexId(1))
        edge_it.next()

    # Map vertex -> near-one edge whose t-near-1 end touches that vertex
    v_covered: set[int] = set()
    for eid in near_one_eids:
        if eid in edge_verts:
            v_covered.add(edge_verts[eid][1])

    # Remove near-zero edges whose t-near-0 vertex is already covered
    remove: set[int] = set()
    for eid in near_zero_eids:
        if eid in edge_verts and edge_verts[eid][0] in v_covered:
            remove.add(eid)

    if not remove:
        return cut_edges

    logger.debug("dedup removed %d near-vertex edges: %s", len(remove), sorted(remove))
    return [(eid, t) for eid, t in cut_edges if eid not in remove]


def _split_edges(mesh_name: str, cut_edges: list[tuple[int, float]]) -> int:
    """Split cut edges at their NURBS intersection points.

    Groups adjacent cut edges into chains and executes one polySplit
    per chain to add cut lines to the mesh. Chains with only one edge
    are skipped.

    Args:
        mesh_name (str): Polygon mesh node name.
        cut_edges (list[tuple[int, float]]): Output of _find_cut_edges, [(edge_id, t), ...].

    Returns:
        int: Number of polySplit operations executed.
    """
    if not cut_edges:
        return 0

    mesh_dag = get_dag_path(mesh_name)

    param_map = dict(cut_edges)
    edge_ids = set(param_map.keys())

    chains = _build_chains(mesh_dag, edge_ids)

    split_count = 0
    for chain, is_closed in chains:
        # Single-edge chains cannot be split with polySplit
        if len(chain) < 2:
            logger.warning(
                "Chain with 1 edge (edge %d) skipped: needs at least 2 edges for polySplit",
                chain[0],
            )
            continue

        insert_list = [(eid, param_map[eid]) for eid in chain]

        if is_closed:
            first_eid = chain[0]
            insert_list.append((first_eid, param_map[first_eid]))

        try:
            cmds.polySplit(
                mesh_name,
                insertpoint=insert_list,
                insertWithEdgeFlow=True,
                ch=False,
            )
            split_count += 1
        except RuntimeError as e:
            logger.warning("polySplit failed: %s", e)

    return split_count


def _ray_intersect(
    nurbs_fn: om.MFnNurbsSurface,
    ray_origin: om.MPoint,
    ray_direction: om.MVector,
    edge_length: float,
    nurbs_world_inv: om.MMatrix,
    nurbs_world_matrix: om.MMatrix,
) -> Optional[float]:
    """Cast a ray along an edge direction and return the intersection t value.

    The ray (world-space) is transformed into the NURBS surface's object space
    for intersection, then the hit point is transformed back to world space to
    compute the parametric *t* value along the original edge.

    Args:
        nurbs_fn (om.MFnNurbsSurface): NURBS surface function set.
        ray_origin (om.MPoint): Ray origin in world space.
        ray_direction (om.MVector): Ray direction in world space.
        edge_length (float): Length of the mesh edge in world space.
        nurbs_world_inv (om.MMatrix): Inverse inclusive matrix of the NURBS dag path.
        nurbs_world_matrix (om.MMatrix): Inclusive matrix of the NURBS dag path.

    Returns:
        Optional[float]: Intersection position (0-1), or None if no intersection.
    """
    # Transform the world-space ray into the NURBS surface's object space.
    local_origin = ray_origin * nurbs_world_inv
    local_direction = ray_direction * nurbs_world_inv

    try:
        result = nurbs_fn.intersect(local_origin, local_direction, om.MSpace.kObject)
    except RuntimeError:
        return None

    if result is None:
        return None

    hit_point_local = result[0]
    if hit_point_local is None:
        return None

    # Transform the hit point back to world space to measure distance.
    hit_point_world = hit_point_local * nurbs_world_matrix
    hit_dist = om.MVector(hit_point_world - ray_origin).length()
    t = hit_dist / edge_length

    if 0.0 <= t <= 1.0:
        return t

    return None


def _build_chains(mesh_dag: om.MDagPath, edge_ids: set[int]) -> list[tuple[list[int], bool]]:
    """Group cut edges into ordered chains by adjacency.

    Two cut edges sharing a face are considered adjacent. Chains are
    built using a deque, extending in both directions.

    Args:
        mesh_dag (om.MDagPath): MDagPath of the mesh.
        edge_ids (set[int]): Set of cut edge indices.

    Returns:
        list[tuple[list[int], bool]]: (chain, is_closed_loop).
    """
    adjacency: dict[int, set[int]] = {}
    edge_it = om.MItMeshEdge(mesh_dag)
    while not edge_it.isDone():
        eid = edge_it.index()
        if eid in edge_ids:
            neighbors: set[int] = set()
            for fid in edge_it.getConnectedFaces():
                face_it = om.MItMeshPolygon(mesh_dag)
                face_it.setIndex(fid)
                for other_eid in face_it.getEdges():
                    if other_eid != eid and other_eid in edge_ids:
                        neighbors.add(other_eid)
            adjacency[eid] = neighbors
        edge_it.next()

    visited: set[int] = set()
    chains: list[tuple[list[int], bool]] = []

    for start in edge_ids:
        if start in visited:
            continue

        chain: deque[int] = deque([start])
        visited.add(start)

        for append_right in (True, False):
            tip = start
            while True:
                next_edge = None
                for neighbor in adjacency.get(tip, set()):
                    if neighbor not in visited:
                        next_edge = neighbor
                        break
                if next_edge is None:
                    break
                visited.add(next_edge)
                if append_right:
                    chain.append(next_edge)
                else:
                    chain.appendleft(next_edge)
                tip = next_edge

        is_closed = chain[0] in adjacency.get(chain[-1], set())
        chains.append((list(chain), is_closed))

    return chains
