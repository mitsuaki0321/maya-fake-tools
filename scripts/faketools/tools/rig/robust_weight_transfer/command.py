"""Robust Weight Transfer command layer.

Business logic layer that wraps core algorithms for UI.
No decorators are used here - decorators are applied in the UI layer.
"""

from logging import getLogger
from typing import Any, Callable, Optional

import maya.cmds as cmds

from .core import algorithm

logger = getLogger(__name__)


def validate_source_mesh(mesh: str) -> tuple[bool, str]:
    """Validate source mesh has skinCluster.

    Args:
        mesh: Mesh node name.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not mesh:
        return False, "No mesh specified"

    if not cmds.objExists(mesh):
        return False, f"Object does not exist: {mesh}"

    # Check if it's a mesh
    shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True) or []
    if not shapes or cmds.objectType(shapes[0]) != "mesh":
        return False, f"{mesh} is not a mesh"

    # Check if it has skinCluster
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    has_skin = any(cmds.objectType(n) == "skinCluster" for n in history)
    if not has_skin:
        return False, f"{mesh} has no skinCluster"

    return True, ""


def validate_target_mesh(mesh: str, source_mesh: str) -> tuple[bool, str]:
    """Validate target mesh.

    Args:
        mesh: Target mesh node name.
        source_mesh: Source mesh node name.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not mesh:
        return False, "No mesh specified"

    if not cmds.objExists(mesh):
        return False, f"Object does not exist: {mesh}"

    # Check if it's a mesh
    shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True) or []
    if not shapes or cmds.objectType(shapes[0]) != "mesh":
        return False, f"{mesh} is not a mesh"

    # Check if same as source
    if mesh == source_mesh:
        return False, "Target cannot be the same as source"

    return True, ""


def parse_selection() -> dict[str, Optional[set[int]]]:
    """Parse current Maya selection and categorize by mesh.

    Returns:
        Dictionary mapping mesh name to vertex indices set.
        None value means all vertices.
    """
    selection = cmds.ls(selection=True, flatten=True)
    targets: dict[str, Optional[set[int]]] = {}

    for item in selection:
        if ".vtx[" in item:
            # Vertex selection: "mesh.vtx[123]"
            mesh = item.split(".")[0]
            vtx_idx = int(item.split("[")[1].rstrip("]"))

            if mesh not in targets:
                targets[mesh] = set()

            if targets[mesh] is not None:
                targets[mesh].add(vtx_idx)
        else:
            # Object selection
            mesh = item

            # Check if it's a mesh
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True) or []
            if shapes and cmds.objectType(shapes[0]) == "mesh":
                targets[mesh] = None  # None = all vertices

    return targets


def search_matches(
    source_mesh: str,
    target_mesh: str,
    vertex_indices: Optional[list[int]],
    distance_ratio: float,
    angle_degrees: float,
    flip_normals: bool,
    use_kdtree: bool,
    use_deformed_source: bool,
    use_deformed_target: bool,
) -> tuple[list[int], list[int]]:
    """Search for matching vertices between source and target.

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.
        vertex_indices: List of vertex indices to process, or None for all.
        distance_ratio: Distance threshold as ratio of bounding box diagonal.
        angle_degrees: Angle threshold in degrees.
        flip_normals: Whether to allow matching with inverted normals.
        use_kdtree: Whether to use KDTree for faster (but less accurate) matching.
        use_deformed_source: Whether to use deformed source mesh.
        use_deformed_target: Whether to use deformed target mesh.

    Returns:
        Tuple of (matched_indices, unmatched_indices).
    """
    matched, unmatched = algorithm.get_unmatched_vertices(
        source_mesh,
        target_mesh,
        distance_threshold_ratio=distance_ratio,
        angle_threshold_degrees=angle_degrees,
        flip_normals=flip_normals,
        use_kdtree=use_kdtree,
        use_deformed_source=use_deformed_source,
        use_deformed_target=use_deformed_target,
    )

    # Filter for partial selection
    if vertex_indices is not None:
        vertex_set = set(vertex_indices)
        matched = [i for i in matched if i in vertex_set]
        unmatched = [i for i in unmatched if i in vertex_set]

    return matched, unmatched


def transfer_weights(
    source_mesh: str,
    target_mesh: str,
    vertex_indices: Optional[list[int]],
    distance_ratio: float,
    angle_degrees: float,
    flip_normals: bool,
    use_kdtree: bool,
    use_deformed_source: bool,
    use_deformed_target: bool,
    enable_smoothing: bool,
    smooth_iterations: int,
    smooth_alpha: float,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> dict[str, Any]:
    """Transfer weights from source to target mesh.

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.
        vertex_indices: List of vertex indices to process, or None for all.
        distance_ratio: Distance threshold as ratio of bounding box diagonal.
        angle_degrees: Angle threshold in degrees.
        flip_normals: Whether to allow matching with inverted normals.
        use_kdtree: Whether to use KDTree for faster matching.
        use_deformed_source: Whether to use deformed source mesh.
        use_deformed_target: Whether to use deformed target mesh.
        enable_smoothing: Whether to apply smoothing after transfer.
        smooth_iterations: Number of smoothing iterations.
        smooth_alpha: Smoothing alpha value.
        progress_callback: Callback function(message, percent) for progress updates.

    Returns:
        Dictionary containing transfer results:
            - matched_count: Number of matched vertices.
            - unmatched_count: Number of unmatched vertices.
            - total_vertices: Total number of processed vertices.
    """
    result = algorithm.transfer_weights(
        source_mesh,
        target_mesh,
        distance_threshold_ratio=distance_ratio,
        angle_threshold_degrees=angle_degrees,
        flip_normals=flip_normals,
        use_kdtree=use_kdtree,
        use_point_cloud=False,
        smooth=enable_smoothing,
        smooth_iterations=smooth_iterations,
        smooth_alpha=smooth_alpha,
        use_deformed_source=use_deformed_source,
        use_deformed_target=use_deformed_target,
        progress_callback=progress_callback,
        vertex_indices=vertex_indices,
    )

    return result


def average_seam_weights(
    meshes: list[str],
    position_tolerance: float,
    include_internal_seams: bool,
) -> dict[str, Any]:
    """Average weights at coincident vertex positions.

    Args:
        meshes: List of mesh names to process.
        position_tolerance: Maximum distance to consider vertices as coincident.
        include_internal_seams: Whether to include internal seams within each mesh.

    Returns:
        Dictionary containing:
            - success: Whether operation succeeded.
            - seam_groups: Number of seam groups found.
            - vertices_averaged: Number of vertices that were averaged.
    """
    return algorithm.average_seam_weights(
        meshes,
        position_tolerance=position_tolerance,
        include_internal_seams=include_internal_seams,
    )


def select_vertices(mesh: str, vertex_indices: list[int]) -> int:
    """Select vertices in Maya viewport.

    Args:
        mesh: Mesh node name.
        vertex_indices: List of vertex indices to select.

    Returns:
        Number of vertices selected.
    """
    if not vertex_indices:
        return 0

    vtx_list = [f"{mesh}.vtx[{i}]" for i in vertex_indices]
    cmds.select(vtx_list, add=True)
    return len(vtx_list)


def get_mesh_vertex_count(mesh: str) -> int:
    """Get total vertex count of mesh.

    Args:
        mesh: Mesh node name.

    Returns:
        Number of vertices.
    """
    try:
        return cmds.polyEvaluate(mesh, vertex=True)
    except Exception as e:
        logger.debug(f"Failed to get vertex count for {mesh}: {e}")
        return 0
