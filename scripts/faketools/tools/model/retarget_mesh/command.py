"""Retarget mesh to another mesh command."""

import logging

import maya.cmds as cmds
import numpy as np
from scipy.spatial import KDTree

from ....lib import lib_cluster, lib_retarget, lib_selection
from ....lib.lib_mesh import is_same_topology
from ....lib.lib_mesh_vertex import MeshVertex
from ....operations import component_selection

logger = logging.getLogger(__name__)


def _get_points_from_soft_selection(src_objs: list[str], trg_mesh: str, *, radius: float = 1.0) -> list[str]:
    """Get the points from the soft selection.

    Args:
        src_objs (list[str]): The source objects.
        trg_mesh (str): The target mesh.
        radius (float): The radius.

    Returns:
        list[str]: The points from the soft selection.
    """
    with lib_selection.restore_selection():
        cmds.select(src_objs, r=True)
        cmds.softSelect(e=True, ssd=radius, ssf=2, sse=True)  # Set soft selection radius and change to global space

        sel_components: dict = component_selection.get_unique_selections(filter_geometries=[trg_mesh])

        cmds.softSelect(e=True, sse=False)

    if not sel_components:
        logger.warning(f"No components selected: {trg_mesh}.")
        return []

    return list(sel_components.keys())


def _get_positions(mesh: MeshVertex) -> np.ndarray:
    """Get the vertex positions of the mesh.

    Args:
        mesh (MeshVertex): The MeshVertex object.

    Returns:
        np.ndarray: The vertex positions as (N, 3) array.
    """
    # Get positions as float lists directly for better performance
    points = mesh.get_vertex_positions(as_float=True)
    return np.array(points, dtype=np.float32)


def _compute_src_indices(
    kd_tree: KDTree,
    trg_indices: list[int],
    trg_points: np.ndarray,
    trg_mesh_vtx: MeshVertex,
    src_mesh_vtx: MeshVertex,
    radius_multiplier: float,
    *,
    min_src_vertices: int = 10,
    max_iterations: int = 10,
) -> list[int]:
    """Compute the source indices with adaptive radius adjustment.

    This function ensures that a minimum number of source vertices are found
    by adaptively increasing the search radius if necessary.

    Args:
        kd_tree (KDTree): The KDTree object.
        trg_indices (list[int]): The target indices.
        trg_points (np.ndarray): The target points.
        trg_mesh_vtx (MeshVertex): The target mesh vertex.
        src_mesh_vtx (MeshVertex): The source mesh vertex.
        radius_multiplier (float): The radius multiplier.
        min_src_vertices (int): Minimum number of source vertices to find (default: 10).
        max_iterations (int): Maximum iterations for adaptive radius adjustment (default: 10).

    Returns:
        list[int]: The source indices.
    """
    distances, _ = kd_tree.query(trg_points)
    base_distance = np.max(distances)
    point_distance = base_distance * radius_multiplier

    # Adaptive radius adjustment to ensure minimum source vertices
    current_multiplier = radius_multiplier
    iteration = 0

    while iteration < max_iterations:
        trg_vertices = trg_mesh_vtx.get_components_from_indices(trg_indices, component_type="vertex")
        src_selection_vertices = _get_points_from_soft_selection(trg_vertices, src_mesh_vtx.get_mesh_name(), radius=point_distance)

        if not src_selection_vertices:
            logger.warning(f"No source vertices found with radius {point_distance:.4f}, increasing radius...")
            current_multiplier *= 1.5
            point_distance = base_distance * current_multiplier
            iteration += 1
            continue

        src_indices = src_mesh_vtx.get_components_indices(src_selection_vertices, component_type="vertex")

        # Check if we have enough source vertices
        if len(src_indices) >= min_src_vertices:
            if iteration > 0:
                logger.info(f"Found {len(src_indices)} source vertices after {iteration} iterations (radius: {point_distance:.4f})")
            return src_indices

        # Not enough vertices, increase radius
        logger.debug(f"Only found {len(src_indices)} source vertices (need {min_src_vertices}), increasing radius...")
        current_multiplier *= 1.5
        point_distance = base_distance * current_multiplier
        iteration += 1

    # Return whatever we found after max iterations
    if src_selection_vertices:
        src_indices = src_mesh_vtx.get_components_indices(src_selection_vertices, component_type="vertex")
        logger.warning(f"Reached max iterations ({max_iterations}), using {len(src_indices)} source vertices (radius: {point_distance:.4f})")
        return src_indices

    # Fallback: use all source vertices
    logger.error("Failed to find any source vertices, using all source vertices as fallback")
    return list(range(src_mesh_vtx.num_vertices()))


def retarget_mesh(
    src_mesh: str,
    dst_meshes: list[str],
    trg_meshes: list[str],
    *,
    is_create: bool = True,
    max_vertices: int = 1000,
    radius_multiplier: float = 1.0,
    min_src_vertices: int = 10,
    max_iterations: int = 10,
) -> list[str]:
    """Retarget the mesh to another mesh.

    Notes:
        - Applies the deformation of two meshes with the same topology to the specified mesh.
        - src_mesh and dst_meshes must have the same topology.
        - The determination of the same topology is only based on the number of vertices, so it is not strictly determined.

    Args:
        src_mesh (str): The source mesh for deformation.
        dst_meshes (list[str]): The target meshes for deformation. They must have the same topology as src_mesh.
        trg_meshes (list[str]): The meshes to be deformed.
        is_create (bool): If True, create new meshes by duplicating trg_meshes. If False, modify trg_meshes directly.
        max_vertices (int): The maximum number of vertices to use when referencing trg_mesh.
                            If less than this, vertices are split and referenced.
        radius_multiplier (float): The radius multiplier when selecting vertices from trg_mesh to src_mesh.
                                   Increase this value for better fitting of small or distant meshes.
        min_src_vertices (int): Minimum number of source vertices to find for reliable RBF deformation.
                                Lower values may result in less accurate deformation.
        max_iterations (int): Maximum iterations for adaptive radius adjustment.
                              Higher values allow more attempts to find sufficient vertices.

    Returns:
        list[str]: The retargeted meshes (transform nodes).

    Raises:
        ValueError: If required meshes are not specified, don't exist, or have incompatible topology.
    """
    if not src_mesh or not dst_meshes or not trg_meshes:
        raise ValueError("Required meshes are not specified.")

    if not cmds.objExists(src_mesh):
        raise ValueError(f"Source mesh does not exist: {src_mesh}.")

    not_exists_dst_meshes = [mesh for mesh in dst_meshes if not cmds.objExists(mesh)]
    if not_exists_dst_meshes:
        raise ValueError(f"Destination meshes do not exist: {not_exists_dst_meshes}.")

    not_exists_trg_meshes = [mesh for mesh in trg_meshes if not cmds.objExists(mesh)]
    if not_exists_trg_meshes:
        raise ValueError(f"Target meshes do not exist: {not_exists_trg_meshes}.")

    if not is_create and len(dst_meshes) > 1:
        raise ValueError("When not creating, only one destination mesh can be specified.")

    src_mesh_vtx = MeshVertex(src_mesh)
    src_points = _get_positions(src_mesh_vtx)
    src_kd_tree = KDTree(src_points)

    if src_mesh_vtx.num_vertices() < 4:
        raise ValueError(f"The source mesh must have at least 4 vertices: {src_mesh}.")

    # Compute target mesh data for each target mesh
    trg_mesh_data = {}
    for trg_mesh in trg_meshes:
        trg_mesh_vtx = MeshVertex(trg_mesh)
        trg_points = _get_positions(trg_mesh_vtx)

        data = {}
        data["trg_positions"] = trg_points
        if trg_mesh_vtx.num_vertices() > max_vertices:
            data["target_indices"] = lib_cluster.KMeansClustering(trg_mesh).get_clusters(int(trg_mesh_vtx.num_vertices() / max_vertices))
            data["src_indices"] = [
                _compute_src_indices(
                    src_kd_tree,
                    indices,
                    trg_points[indices],
                    trg_mesh_vtx,
                    src_mesh_vtx,
                    radius_multiplier,
                    min_src_vertices=min_src_vertices,
                    max_iterations=max_iterations,
                )
                for indices in data["target_indices"]
            ]
        else:
            data["target_indices"] = [range(trg_mesh_vtx.num_vertices())]
            data["src_indices"] = [
                _compute_src_indices(
                    src_kd_tree,
                    range(trg_mesh_vtx.num_vertices()),
                    trg_points,
                    trg_mesh_vtx,
                    src_mesh_vtx,
                    radius_multiplier,
                    min_src_vertices=min_src_vertices,
                    max_iterations=max_iterations,
                )
            ]

        trg_mesh_data[trg_mesh] = data

    # Process each destination mesh and apply deformations
    deform_mesh_transforms = []
    for dst_mesh in dst_meshes:
        if not is_same_topology(src_mesh, dst_mesh):
            raise ValueError(f"The topology of the source and destination meshes must be the same: {src_mesh} -> {dst_mesh}.")

        dst_mesh_vtx = MeshVertex(dst_mesh)
        dst_points = _get_positions(dst_mesh_vtx)

        dst_transform = cmds.listRelatives(dst_mesh_vtx.get_mesh_name(), parent=True)[0]
        dst_position = cmds.xform(dst_transform, q=True, ws=True, t=True)

        for trg_mesh in trg_mesh_data:
            trg_positions = trg_mesh_data[trg_mesh]["trg_positions"]
            trg_index_list = trg_mesh_data[trg_mesh]["target_indices"]
            src_index_list = trg_mesh_data[trg_mesh]["src_indices"]

            if is_create:
                deform_mesh = cmds.listRelatives(cmds.duplicate(trg_mesh)[0], shapes=True, noIntermediate=True)[0]
            else:
                deform_mesh = trg_mesh

            deform_transform = cmds.listRelatives(deform_mesh, parent=True)[0]
            cmds.xform(deform_transform, ws=True, t=dst_position)

            # Create MeshVertex instance for batch vertex position updates
            deform_mesh_vtx = MeshVertex(deform_mesh)

            for trg_indices, src_indices in zip(trg_index_list, src_index_list):
                rbf_deform = lib_retarget.RBFDeform(src_points[src_indices])
                weight_x, weight_y, weight_z = rbf_deform.compute_weights(dst_points[src_indices])
                computed_points = rbf_deform.compute_points(trg_positions[trg_indices], weight_x, weight_y, weight_z)

                # Batch update vertex positions for better performance
                deform_mesh_vtx.set_vertex_positions(computed_points, list(trg_indices))

            deform_mesh_transforms.append(deform_transform)

            logger.debug(f"Re targeted mesh: {deform_transform}.")

    return deform_mesh_transforms
