"""Component Snap command layer.

Snaps source components (mesh vertices, curve/surface CVs, lattice points)
to target mesh positions using various matching methods.
Supports soft selection weights for gradual falloff.
"""

from __future__ import annotations

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np

from ....operations import component_selection

logger = getLogger(__name__)

_SUPPORTED_COMP_PATTERNS = (".vtx[", ".cv[", ".pt[")


# -- Matching methods --------------------------------------------------------


def _get_closest_positions(
    source_positions: np.ndarray,
    target_mesh: str,
    space: int,
) -> np.ndarray:
    """Get closest points on the target mesh surface for each source position.

    Args:
        source_positions: Source positions as (N, 3) array in world space.
        target_mesh: Target mesh name.
        space: MSpace constant for the returned positions (kWorld or kObject).

    Returns:
        np.ndarray: Closest surface positions as (N, 3) array in the requested space.
    """
    sel = om.MSelectionList()
    sel.add(target_mesh)
    dag_path = sel.getDagPath(0)
    if dag_path.apiType() == om.MFn.kTransform:
        dag_path.extendToShape()

    fn_mesh = om.MFnMesh(dag_path)

    result = []
    for pos in source_positions:
        point = om.MPoint(float(pos[0]), float(pos[1]), float(pos[2]))
        closest_point, _ = fn_mesh.getClosestPoint(point, space)
        result.append([closest_point.x, closest_point.y, closest_point.z])

    return np.array(result)


def _match_by_nearest_component(
    source_positions: np.ndarray,
    target_mesh: str,
) -> list[int]:
    """Match source to target by nearest vertex (component).

    Args:
        source_positions: Source positions as (N, 3) array in world space.
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


def _extract_node_name(component: str) -> str | None:
    """Extract the node name from a component string.

    Args:
        component: Component string (e.g. "pSphere1.vtx[0]", "curve1.cv[3]").

    Returns:
        str | None: Node name, or None if not a supported component.
    """
    for pattern in _SUPPORTED_COMP_PATTERNS:
        if pattern in component:
            return component.split(pattern, 1)[0]
    return None


def _extract_index(component: str) -> int:
    """Extract a single integer index from a component string for index matching.

    Supports single-indexed components (vtx[N], cv[N]).
    Raises ValueError for multi-indexed components (cv[U][V], pt[S][T][U]).

    Args:
        component: Component string.

    Returns:
        int: The component index.

    Raises:
        ValueError: If multi-indexed or unsupported component type.
    """
    for pattern in _SUPPORTED_COMP_PATTERNS:
        if pattern not in component:
            continue
        _, idx_part = component.split(pattern, 1)
        idx_str = idx_part.rstrip("]")
        if "[" not in idx_str:
            return int(idx_str)
        raise ValueError(f"Index matching is not supported for multi-indexed components: {component}")
    raise ValueError(f"Unsupported component type: {component}")


# -- Public API --------------------------------------------------------------


def get_selection_data() -> dict[str, dict[str, float]]:
    """Get current selection data for the snap operation.

    When soft selection is enabled, component weights reflect the soft selection falloff.
    When soft selection is disabled, all selected components get a weight of 1.0.

    Supports mesh vertices (.vtx), curve/surface CVs (.cv), and lattice points (.pt).

    Returns:
        dict[str, dict[str, float]]: {node_name: {component_string: weight}}
    """
    soft_select_enabled = cmds.softSelect(query=True, softSelectEnabled=True)

    if soft_select_enabled:
        raw = component_selection.get_unique_selections()
    else:
        selection = cmds.ls(selection=True, flatten=True) or []
        raw = {comp: 1.0 for comp in selection if any(p in comp for p in _SUPPORTED_COMP_PATTERNS)}

    result: dict[str, dict[str, float]] = {}
    for comp, weight in raw.items():
        node = _extract_node_name(comp)
        if node is not None:
            result.setdefault(node, {})[comp] = weight
    return result


def snap(
    components: dict[str, float],
    target_mesh: str,
    method: str = "index",
    space: str = "world",
    blend: float = 1.0,
) -> int:
    """Snap source components toward target mesh vertex positions.

    Args:
        components: {component_string: weight} for source components.
        target_mesh: Target mesh transform name.
        method: Matching method - "index", "closest_position", or "nearest_component".
        space: Coordinate space - "world" or "local".
        blend: Blend rate (0.0 to 1.0). 1.0 = full snap.

    Returns:
        int: Number of components snapped.

    Raises:
        ValueError: If method or space is invalid.
    """
    if method not in ("index", "closest_position", "nearest_component"):
        raise ValueError(f"Invalid method: {method}")

    if space not in ("world", "local"):
        raise ValueError(f"Invalid space: {space}")

    comp_list = sorted(components.keys())
    if not comp_list:
        return 0

    ws = space == "world"
    mspace = om.MSpace.kWorld if ws else om.MSpace.kObject

    # Get source positions via cmds.xform (works for vtx, cv, pt)
    source_positions = np.array([cmds.xform(c, query=True, translation=True, worldSpace=ws, objectSpace=not ws) for c in comp_list])
    logger.debug(f"source components: {len(comp_list)}, first={comp_list[0]}, pos={source_positions[0]}")

    # Determine target positions
    world_positions = source_positions if ws else np.array([cmds.xform(c, query=True, translation=True, worldSpace=True) for c in comp_list])

    if method == "index":
        target_indices = [_extract_index(c) for c in comp_list]
        target_vtx_count = cmds.polyEvaluate(target_mesh, vertex=True)
        for idx in target_indices:
            if idx >= target_vtx_count:
                raise RuntimeError(f"Index {idx} exceeds target vertex count ({target_vtx_count}).")
        target_all_points = _get_mesh_points(target_mesh, mspace)
        target_positions = target_all_points[target_indices]
    elif method == "closest_position":
        target_positions = _get_closest_positions(world_positions, target_mesh, mspace)
    else:
        target_indices = _match_by_nearest_component(world_positions, target_mesh)
        target_all_points = _get_mesh_points(target_mesh, mspace)
        target_positions = target_all_points[target_indices]

    # Apply snap with blend and soft selection weight
    for i, comp in enumerate(comp_list):
        weight = components[comp]
        factor = blend * weight
        new_pos = source_positions[i] + (target_positions[i] - source_positions[i]) * factor
        cmds.xform(
            comp,
            translation=(float(new_pos[0]), float(new_pos[1]), float(new_pos[2])),
            worldSpace=ws,
            objectSpace=not ws,
        )

    logger.info(f"Snapped {len(comp_list)} components: method={method}, space={space}, blend={blend:.2f}")
    return len(comp_list)
