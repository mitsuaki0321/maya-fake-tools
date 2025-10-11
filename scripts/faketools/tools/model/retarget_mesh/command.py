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
        np.ndarray: The vertex positions.
    """
    points = np.array(mesh.get_vertex_positions())
    points = np.delete(points, 3, axis=1)

    return points


def _compute_src_indices(
    kd_tree: KDTree,
    trg_indices: list[int],
    trg_points: np.ndarray,
    trg_mesh_vtx: MeshVertex,
    src_mesh_vtx: MeshVertex,
    radius_multiplier: float,
) -> list[int]:
    """Compute the source indices.

    Args:
        kd_tree (KDTree): The KDTree object.
        trg_indices (list[int]): The target indices.
        trg_points (np.ndarray): The target points.
        trg_mesh_vtx (MeshVertex): The target mesh vertex.
        src_mesh_vtx (MeshVertex): The source mesh vertex.
        radius_multiplier (float): The radius multiplier.

    Returns:
        list[int]: The source indices.
    """
    distances, _ = kd_tree.query(trg_points)
    point_distance = np.max(distances) * radius_multiplier
    trg_vertices = trg_mesh_vtx.get_components_from_indices(trg_indices, component_type="vertex")
    src_selection_vertices = _get_points_from_soft_selection(trg_vertices, src_mesh_vtx.get_mesh_name(), radius=point_distance)

    return src_mesh_vtx.get_components_indices(src_selection_vertices, component_type="vertex")


def retarget_mesh(
    src_mesh: str, dst_meshes: list[str], trg_meshes: list[str], *, is_create: bool = True, max_vertices: int = 1000, radius_multiplier: float = 1.0
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
                _compute_src_indices(src_kd_tree, indices, trg_points[indices], trg_mesh_vtx, src_mesh_vtx, radius_multiplier)
                for indices in data["target_indices"]
            ]
        else:
            data["target_indices"] = [range(trg_mesh_vtx.num_vertices())]
            data["src_indices"] = [
                _compute_src_indices(src_kd_tree, range(trg_mesh_vtx.num_vertices()), trg_points, trg_mesh_vtx, src_mesh_vtx, radius_multiplier)
            ]

        trg_mesh_data[trg_mesh] = data

    # Process each destination mesh and apply deformations
    deform_mesh_transforms = []
    for dst_mesh in dst_meshes:
        if not is_same_topology(src_mesh, dst_mesh):
            raise ValueError(f"The topology of the source and destination meshes must be the same: {src_mesh} -> {dst_mesh}.")

        dst_mesh_vtx = MeshVertex(dst_mesh)
        dst_points = _get_positions(dst_mesh_vtx)

        dst_transform = cmds.listRelatives(dst_mesh_vtx._mesh_name, parent=True)[0]
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

            for trg_indices, src_indices in zip(trg_index_list, src_index_list, strict=False):
                rbf_deform = lib_retarget.RBFDeform(src_points[src_indices])
                weight_x, weight_y, weight_z = rbf_deform.compute_weights(dst_points[src_indices])
                computed_points = rbf_deform.compute_points(trg_positions[trg_indices], weight_x, weight_y, weight_z)

                for i, index in enumerate(trg_indices):
                    cmds.xform(f"{deform_mesh}.vtx[{index}]", t=computed_points[i], ws=True)

            cmds.select(deform_mesh, r=True)
            cmds.refresh()

            deform_mesh_transforms.append(deform_transform)

            logger.debug(f"Re targeted mesh: {deform_transform}.")

    return deform_mesh_transforms
