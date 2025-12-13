"""
weight_io.py - Fast weight I/O

Fast weight read/write with skinCluster.
Uses batch API (MFnSkinCluster.getWeights/setWeights),
avoiding per-value writes via cmds.setAttr.
"""

from logging import getLogger
from typing import Optional, Union

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds
import numpy as np

logger = getLogger(__name__)


def _get_dag_path(node: Union[str, om.MDagPath]) -> om.MDagPath:
    """Get MDagPath from node name.

    Args:
        node: Node name or MDagPath.

    Returns:
        MDagPath for the node.
    """
    if isinstance(node, om.MDagPath):
        return node

    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)


def _get_depend_node(node: str) -> om.MObject:
    """Get MObject from node name.

    Args:
        node: Node name.

    Returns:
        MObject for the node.
    """
    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDependNode(0)


def _get_shape_node(node: str) -> str:
    """Get shape node from transform node.

    Args:
        node: Transform or shape node name.

    Returns:
        Shape node name.

    Raises:
        ValueError: If no mesh shape is found.
    """
    if cmds.objectType(node) == "mesh":
        return node

    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True)
    if shapes:
        return shapes[0]

    raise ValueError(f"No mesh shape found for: {node}")


def get_skincluster(mesh: str) -> str:
    """Get skinCluster from mesh.

    Args:
        mesh: Mesh node name.

    Returns:
        skinCluster node name.

    Raises:
        RuntimeError: If no skinCluster is found on the mesh.
    """
    mesh_shape = _get_shape_node(mesh)

    history = cmds.listHistory(mesh_shape, pruneDagObjects=True) or []
    for node in history:
        if cmds.objectType(node) == "skinCluster":
            return node

    raise RuntimeError(f"No skinCluster found on: {mesh}")


def get_or_create_skincluster(mesh: str, influences: list[str]) -> str:
    """Get existing skinCluster or create a new one.

    Args:
        mesh: Mesh node name.
        influences: List of influence (joint) names.

    Returns:
        skinCluster node name.
    """
    try:
        skin = get_skincluster(mesh)
        logger.debug(f"Found existing skinCluster: {skin}")
        return skin
    except RuntimeError:
        # Create new skinCluster
        logger.debug(f"Creating new skinCluster for {mesh} with {len(influences)} influences")
        result = cmds.skinCluster(
            mesh,
            influences,
            toSelectedBones=True,
            bindMethod=0,  # closest distance
            skinMethod=0,  # classic linear
            normalizeWeights=1,
            weightDistribution=0,
            removeUnusedInfluence=False,
            name=mesh + "_skinCluster",
        )
        logger.info(f"Created skinCluster: {result[0]}")
        return result[0]


def get_influence_names(skincluster: str) -> list[str]:
    """Get list of influence (joint) names from skinCluster.

    Args:
        skincluster: skinCluster node name.

    Returns:
        List of influence names.
    """
    return cmds.skinCluster(skincluster, query=True, influence=True) or []


def get_influence_indices(skincluster: str) -> dict[str, int]:
    """Get mapping from influence name to index.

    Args:
        skincluster: skinCluster node name.

    Returns:
        Dictionary mapping influence name to its index.
    """
    influences = get_influence_names(skincluster)
    return {name: i for i, name in enumerate(influences)}


def get_all_weights(mesh: str, skincluster: Optional[str] = None) -> tuple[np.ndarray, list[str]]:
    """Get weights for all vertices in batch (fast).

    Args:
        mesh: Mesh node name.
        skincluster: skinCluster node name. Auto-detected if None.

    Returns:
        Tuple of (weights, influences) where:
            - weights: (num_verts, num_influences) float64 weight array.
            - influences: List of influence names.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    # Get all vertex weights in batch
    # getWeights(dagPath, components) - MObject() for components means all vertices
    weights_flat, num_influences = skin_fn.getWeights(dag_path, om.MObject())

    # Reshape flat array to (num_verts, num_influences)
    num_verts = len(weights_flat) // num_influences
    weights = np.array(weights_flat, dtype=np.float64).reshape(num_verts, num_influences)

    # Get influence names
    influences = get_influence_names(skincluster)

    return weights, influences


def set_all_weights(
    mesh: str,
    weights: np.ndarray,
    skincluster: Optional[str] = None,
    normalize: bool = True,
) -> None:
    """Set weights for all vertices in batch (fast).

    Args:
        mesh: Mesh node name.
        weights: (num_verts, num_influences) weight array.
        skincluster: skinCluster node name. Auto-detected if None.
        normalize: Whether to normalize weights after setting.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    num_verts, num_influences = weights.shape

    # Create component for all vertices
    comp_fn = om.MFnSingleIndexedComponent()
    vertex_comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements(list(range(num_verts)))

    # Influence index array
    influence_indices = om.MIntArray(list(range(num_influences)))

    # Weight array (flat)
    weights_flat = om.MDoubleArray(weights.flatten().tolist())

    # Set in batch
    skin_fn.setWeights(dag_path, vertex_comp, influence_indices, weights_flat, normalize)


def set_weights_for_vertices(
    mesh: str,
    vertex_indices: list[int],
    weights: np.ndarray,
    skincluster: Optional[str] = None,
    normalize: bool = True,
) -> None:
    """Set weights for specified vertices in batch.

    Args:
        mesh: Mesh node name.
        vertex_indices: List of vertex indices to set weights for.
        weights: (len(vertex_indices), num_influences) weight array.
        skincluster: skinCluster node name. Auto-detected if None.
        normalize: Whether to normalize weights after setting.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    num_influences = weights.shape[1]

    # Create component for specified vertices
    comp_fn = om.MFnSingleIndexedComponent()
    vertex_comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements(vertex_indices)

    # Influence index array
    influence_indices = om.MIntArray(list(range(num_influences)))

    # Weight array (flat)
    weights_flat = om.MDoubleArray(weights.flatten().tolist())

    # Set in batch
    skin_fn.setWeights(dag_path, vertex_comp, influence_indices, weights_flat, normalize)


def copy_skincluster_influences(source_mesh: str, target_mesh: str) -> str:
    """Copy skinCluster influences from source mesh to target.

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.

    Returns:
        Target skinCluster node name.
    """
    source_skin = get_skincluster(source_mesh)
    influences = get_influence_names(source_skin)

    return get_or_create_skincluster(target_mesh, influences)


def get_weights_at_vertices(mesh: str, vertex_indices: list[int], skincluster: Optional[str] = None) -> np.ndarray:
    """Get weights for specified vertices.

    Args:
        mesh: Mesh node name.
        vertex_indices: List of vertex indices to get weights for.
        skincluster: skinCluster node name. Auto-detected if None.

    Returns:
        (len(vertex_indices), num_influences) float64 weight array.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    # Create component for specified vertices
    comp_fn = om.MFnSingleIndexedComponent()
    vertex_comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements(vertex_indices)

    # Get weights
    weights_flat, num_influences = skin_fn.getWeights(dag_path, vertex_comp)

    # Reshape
    num_verts = len(vertex_indices)
    weights = np.array(weights_flat, dtype=np.float64).reshape(num_verts, num_influences)

    return weights


def get_vertex_weights(mesh: str, vertex_index: int, skincluster: Optional[str] = None) -> tuple[list[float], list[str]]:
    """Get weights for a single vertex with influence names.

    Args:
        mesh: Mesh node name.
        vertex_index: Index of the vertex.
        skincluster: skinCluster node name. Auto-detected if None.

    Returns:
        Tuple of (weights, influences) where:
            - weights: List of weight values (non-zero only).
            - influences: List of corresponding influence names.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    # Create component for single vertex
    comp_fn = om.MFnSingleIndexedComponent()
    vertex_comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements([vertex_index])

    # Get weights
    weights_flat, num_influences = skin_fn.getWeights(dag_path, vertex_comp)

    # Get influence names
    influences = get_influence_names(skincluster)

    # Filter to non-zero weights
    result_weights = []
    result_influences = []

    for i, w in enumerate(weights_flat):
        if w > 0.0001:
            result_weights.append(w)
            result_influences.append(influences[i])

    return result_weights, result_influences


def set_vertex_weights(
    mesh: str,
    vertex_index: int,
    weights: list[float],
    influences: list[str],
    skincluster: Optional[str] = None,
    normalize: bool = True,
) -> None:
    """Set weights for a single vertex by influence names.

    Args:
        mesh: Mesh node name.
        vertex_index: Index of the vertex.
        weights: List of weight values.
        influences: List of influence names corresponding to weights.
        skincluster: skinCluster node name. Auto-detected if None.
        normalize: Whether to normalize weights after setting.
    """
    mesh_shape = _get_shape_node(mesh)

    if skincluster is None:
        skincluster = get_skincluster(mesh)

    # Get MFnSkinCluster
    skin_obj = _get_depend_node(skincluster)
    skin_fn = oma.MFnSkinCluster(skin_obj)

    # Get mesh DagPath
    dag_path = _get_dag_path(mesh_shape)

    # Get influence index mapping
    all_influences = get_influence_names(skincluster)
    influence_to_idx = {name: i for i, name in enumerate(all_influences)}

    # Build full weight array for all influences
    full_weights = [0.0] * len(all_influences)
    for w, inf in zip(weights, influences):
        if inf in influence_to_idx:
            full_weights[influence_to_idx[inf]] = w

    # Create component for single vertex
    comp_fn = om.MFnSingleIndexedComponent()
    vertex_comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements([vertex_index])

    # Influence index array (all influences)
    influence_indices = om.MIntArray(list(range(len(all_influences))))

    # Weight array
    weights_array = om.MDoubleArray(full_weights)

    # Set weights
    skin_fn.setWeights(dag_path, vertex_comp, influence_indices, weights_array, normalize)


def interpolate_weights_barycentric(weights: np.ndarray, bary_coords: np.ndarray, vert_indices: np.ndarray) -> np.ndarray:
    """Interpolate weights using barycentric coordinates.

    Args:
        weights: (N, num_influences) weight array for all vertices.
        bary_coords: (3,) array of barycentric coordinates.
        vert_indices: (3,) array of triangle vertex indices.

    Returns:
        (num_influences,) array of interpolated weights.
    """
    w0 = weights[vert_indices[0]]
    w1 = weights[vert_indices[1]]
    w2 = weights[vert_indices[2]]

    interpolated = bary_coords[0] * w0 + bary_coords[1] * w1 + bary_coords[2] * w2

    return interpolated


def prune_small_weights(weights: np.ndarray, threshold: float = 0.0001) -> np.ndarray:
    """Remove small weights and normalize.

    Args:
        weights: (num_verts, num_influences) weight array.
        threshold: Weights below this value are set to 0.

    Returns:
        Weight array with small weights removed and rows normalized.
    """
    pruned = weights.copy()
    pruned[pruned < threshold] = 0.0

    # Normalize (each row sums to 1)
    row_sums = pruned.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0  # Prevent division by zero
    pruned = pruned / row_sums

    return pruned
