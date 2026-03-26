"""Component Snap command layer.

Snaps source mesh vertices to target mesh positions using various matching methods.
Supports soft selection weights for gradual falloff.
"""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np

from ....operations import component_selection

logger = getLogger(__name__)


# -- Matching methods --------------------------------------------------------


def _match_by_index(
    source_indices: list[int],
    target_mesh: str,
) -> list[int]:
    """Match source to target by vertex index.

    Args:
        source_indices: Source vertex indices.
        target_mesh: Target mesh name.

    Returns:
        list[int]: Matched target indices (same as source).

    Raises:
        RuntimeError: If source index exceeds target vertex count.
    """
    target_vtx_count = cmds.polyEvaluate(target_mesh, vertex=True)
    for idx in source_indices:
        if idx >= target_vtx_count:
            raise RuntimeError(f"Source vertex index {idx} exceeds target vertex count ({target_vtx_count}).")
    return list(source_indices)


def _match_by_closest_position(
    source_positions: np.ndarray,
    target_mesh: str,
) -> list[int]:
    """Match source to target by closest point on surface.

    Uses MFnMesh.getClosestPoint to find the nearest surface point,
    then returns the closest vertex to that surface point.

    Args:
        source_positions: Source positions as (N, 3) array.
        target_mesh: Target mesh name.

    Returns:
        list[int]: Matched target vertex indices.
    """
    sel = om.MSelectionList()
    sel.add(target_mesh)
    dag_path = sel.getDagPath(0)
    if dag_path.apiType() == om.MFn.kTransform:
        dag_path.extendToShape()

    fn_mesh = om.MFnMesh(dag_path)
    target_points = fn_mesh.getPoints(om.MSpace.kWorld)
    target_np = np.array([[p.x, p.y, p.z] for p in target_points])

    matched_indices = []
    for pos in source_positions:
        point = om.MPoint(float(pos[0]), float(pos[1]), float(pos[2]))
        closest_point, face_id = fn_mesh.getClosestPoint(point, om.MSpace.kWorld)
        cp = np.array([closest_point.x, closest_point.y, closest_point.z])

        face_verts = fn_mesh.getPolygonVertices(face_id)
        face_positions = target_np[face_verts]
        distances = np.linalg.norm(face_positions - cp, axis=1)
        matched_indices.append(face_verts[int(np.argmin(distances))])

    return matched_indices


def _match_by_nearest_component(
    source_positions: np.ndarray,
    target_mesh: str,
) -> list[int]:
    """Match source to target by nearest vertex (component).

    Args:
        source_positions: Source positions as (N, 3) array.
        target_mesh: Target mesh name.

    Returns:
        list[int]: Matched target vertex indices.
    """
    sel = om.MSelectionList()
    sel.add(target_mesh)
    dag_path = sel.getDagPath(0)
    if dag_path.apiType() == om.MFn.kTransform:
        dag_path.extendToShape()

    fn_mesh = om.MFnMesh(dag_path)
    target_points = fn_mesh.getPoints(om.MSpace.kWorld)
    target_np = np.array([[p.x, p.y, p.z] for p in target_points])

    matched_indices = []
    for pos in source_positions:
        distances = np.linalg.norm(target_np - pos, axis=1)
        matched_indices.append(int(np.argmin(distances)))

    return matched_indices


# -- Core helpers ------------------------------------------------------------


def _get_dag_path(mesh_name: str) -> om.MDagPath:
    """Get MDagPath for a mesh, extending to shape if needed.

    Args:
        mesh_name: Maya mesh or transform name.

    Returns:
        om.MDagPath: The dag path to the shape node.
    """
    sel = om.MSelectionList()
    sel.add(mesh_name)
    dag_path = sel.getDagPath(0)
    if dag_path.apiType() == om.MFn.kTransform:
        dag_path.extendToShape()
    return dag_path


def _get_mesh_points(mesh_name: str, space: int) -> np.ndarray:
    """Get all vertex positions of a mesh.

    Args:
        mesh_name: Maya mesh name.
        space: MSpace constant (kWorld or kObject).

    Returns:
        np.ndarray: Vertex positions as (N, 3) array.
    """
    fn_mesh = om.MFnMesh(_get_dag_path(mesh_name))
    points = fn_mesh.getPoints(space)
    return np.array([[p.x, p.y, p.z] for p in points])


def _set_vertex_positions(mesh_name: str, index_positions: dict[int, np.ndarray], world_space: bool) -> None:
    """Set vertex positions using cmds.xform (undo-safe).

    Args:
        mesh_name: Maya mesh transform name.
        index_positions: {vertex_index: (x, y, z)} positions to set.
        world_space: If True, set in world space; otherwise object space.
    """
    for idx, pos in index_positions.items():
        cmds.xform(
            f"{mesh_name}.vtx[{idx}]",
            translation=(float(pos[0]), float(pos[1]), float(pos[2])),
            worldSpace=world_space,
            objectSpace=not world_space,
        )


def _parse_vertex_components(components: dict[str, float]) -> dict[str, dict[int, float]]:
    """Parse component strings into per-mesh vertex index/weight mapping.

    Args:
        components: Dict of component string to weight (e.g. {"pSphere1.vtx[0]": 0.8}).

    Returns:
        dict[str, dict[int, float]]: {mesh_name: {vertex_index: weight}}.
    """
    result = {}
    for comp, weight in components.items():
        if ".vtx[" not in comp:
            continue
        mesh_name, vtx_part = comp.split(".vtx[", 1)
        idx = int(vtx_part.rstrip("]"))
        if mesh_name not in result:
            result[mesh_name] = {}
        result[mesh_name][idx] = weight
    return result


# -- Public API --------------------------------------------------------------


def get_selection_data() -> dict[str, dict[int, float]]:
    """Get current selection data for the snap operation.

    When soft selection is enabled, vertex weights reflect the soft selection falloff.
    When soft selection is disabled, all selected vertices get a weight of 1.0.

    Returns:
        dict[str, dict[int, float]]: {mesh_name: {vertex_index: weight}}
    """
    soft_select_enabled = cmds.softSelect(query=True, softSelectEnabled=True)

    if soft_select_enabled:
        components = component_selection.get_unique_selections()
        return _parse_vertex_components(components)

    # Normal selection: all weights = 1.0
    selection = cmds.ls(selection=True, flatten=True) or []
    result: dict[str, dict[int, float]] = {}
    for comp in selection:
        if ".vtx[" not in comp:
            continue
        mesh_name, vtx_part = comp.split(".vtx[", 1)
        idx = int(vtx_part.rstrip("]"))
        if mesh_name not in result:
            result[mesh_name] = {}
        result[mesh_name][idx] = 1.0
    return result


def snap(
    source_mesh: str,
    target_mesh: str,
    vertex_weights: dict[int, float],
    method: str = "index",
    space: str = "world",
    blend: float = 1.0,
) -> int:
    """Snap source vertices toward target mesh positions.

    Args:
        source_mesh: Source mesh transform name.
        target_mesh: Target mesh transform name.
        vertex_weights: {vertex_index: soft_selection_weight} for source vertices.
        method: Matching method - "index", "closest_position", or "nearest_component".
        space: Coordinate space - "world" or "local".
        blend: Blend rate (0.0 to 1.0). 1.0 = full snap.

    Returns:
        int: Number of vertices snapped.

    Raises:
        ValueError: If method or space is invalid.
        RuntimeError: If source mesh equals target mesh.
    """
    if source_mesh == target_mesh:
        raise RuntimeError("Source and target must be different meshes.")

    if method not in ("index", "closest_position", "nearest_component"):
        raise ValueError(f"Invalid method: {method}")

    if space not in ("world", "local"):
        raise ValueError(f"Invalid space: {space}")

    mspace = om.MSpace.kWorld if space == "world" else om.MSpace.kObject

    source_indices = sorted(vertex_weights.keys())
    if not source_indices:
        logger.debug("No source indices found.")
        return 0

    logger.debug(f"source_indices ({len(source_indices)}): {source_indices[:10]}...")

    source_all_points = _get_mesh_points(source_mesh, mspace)
    source_positions = source_all_points[source_indices]
    logger.debug(f"source_positions[0]: {source_positions[0] if len(source_positions) > 0 else 'N/A'}")

    # Match to target
    if method == "index":
        target_indices = _match_by_index(source_indices, target_mesh)
    elif method == "closest_position":
        # Use world space for matching regardless of snap space
        if mspace == om.MSpace.kObject:
            world_positions = _get_mesh_points(source_mesh, om.MSpace.kWorld)[source_indices]
        else:
            world_positions = source_positions
        target_indices = _match_by_closest_position(world_positions, target_mesh)
    else:
        if mspace == om.MSpace.kObject:
            world_positions = _get_mesh_points(source_mesh, om.MSpace.kWorld)[source_indices]
        else:
            world_positions = source_positions
        target_indices = _match_by_nearest_component(world_positions, target_mesh)

    logger.debug(f"target_indices ({len(target_indices)}): {target_indices[:10]}...")

    target_all_points = _get_mesh_points(target_mesh, mspace)
    target_positions = target_all_points[target_indices]
    logger.debug(f"target_positions[0]: {target_positions[0] if len(target_positions) > 0 else 'N/A'}")

    # Apply snap with blend and soft selection weight
    new_positions = {}
    for i, src_idx in enumerate(source_indices):
        weight = vertex_weights[src_idx]
        factor = blend * weight
        displacement = target_positions[i] - source_positions[i]
        new_positions[src_idx] = source_positions[i] + displacement * factor

    if new_positions:
        first_idx = next(iter(new_positions))
        logger.debug(
            f"vtx[{first_idx}]: src={source_positions[0]} -> new={new_positions[first_idx]}, "
            f"target={target_positions[0]}, factor={blend * vertex_weights[first_idx]:.4f}"
        )

    logger.debug(f"Setting {len(new_positions)} vertex positions on {source_mesh}, world_space={space == 'world'}")
    _set_vertex_positions(source_mesh, new_positions, world_space=(space == "world"))

    logger.info(f"Snapped {len(source_indices)} vertices: method={method}, space={space}, blend={blend:.2f}")
    return len(source_indices)
