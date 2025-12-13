"""
deform.py - Deform support

Gets vertex coordinates from mesh at current pose (after deformers applied).
This enables weight transfer in poses other than bind pose.

Reference:
- Maya API Documentation (Autodesk)
- MFnMesh.getPoints() MSpace parameter
"""

from logging import getLogger
from typing import Optional, Union

import maya.api.OpenMaya as om
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


def get_deformed_mesh_data(mesh: str, world_space: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Get mesh data after deformers are applied.

    Returns vertex coordinates and normals at current state
    with skinCluster, blendShape, and other deformers applied.

    Args:
        mesh: Mesh node name.
        world_space: Whether to get coordinates in world space.

    Returns:
        Tuple of (vertices, normals) where:
            - vertices: (N, 3) float32 array of deformed vertex coordinates.
            - normals: (N, 3) float32 array of deformed vertex normals.
    """
    mesh_shape = _get_shape_node(mesh)
    dag_path = _get_dag_path(mesh_shape)
    mesh_fn = om.MFnMesh(dag_path)

    space = om.MSpace.kWorld if world_space else om.MSpace.kObject

    # getPoints returns current deformed state
    points = mesh_fn.getPoints(space)
    num_verts = len(points)

    vertices = np.empty((num_verts, 3), dtype=np.float32)
    for i, p in enumerate(points):
        vertices[i] = (p.x, p.y, p.z)

    # Normals are also at current deformed state
    normals = np.empty((num_verts, 3), dtype=np.float32)
    for i in range(num_verts):
        n = mesh_fn.getVertexNormal(i, True, space)
        normals[i] = (n.x, n.y, n.z)

    return vertices, normals


def get_bind_pose_mesh_data(mesh: str) -> tuple[np.ndarray, np.ndarray]:
    """Get mesh data at bind pose (initial state).

    Uses skinCluster's envelope to temporarily disable deformation
    and retrieve the bind pose shape.

    Args:
        mesh: Mesh node name.

    Returns:
        Tuple of (vertices, normals) where:
            - vertices: (N, 3) float32 array of bind pose vertex coordinates.
            - normals: (N, 3) float32 array of bind pose vertex normals.

    Note:
        This function only works when skinCluster exists.
        Other deformers like blendShape are not considered.
    """
    mesh_shape = _get_shape_node(mesh)

    # Find skinCluster
    skincluster = None
    history = cmds.listHistory(mesh_shape, pruneDagObjects=True) or []
    for node in history:
        if cmds.objectType(node) == "skinCluster":
            skincluster = node
            break

    if skincluster is None:
        # No skinCluster - return current state
        return get_deformed_mesh_data(mesh)

    # Temporarily set envelope to 0 to get bind pose
    original_envelope = cmds.getAttr(f"{skincluster}.envelope")

    try:
        cmds.setAttr(f"{skincluster}.envelope", 0)
        vertices, normals = get_deformed_mesh_data(mesh)
    finally:
        # Restore envelope
        cmds.setAttr(f"{skincluster}.envelope", original_envelope)

    return vertices, normals


def get_intermediate_mesh_data(mesh: str) -> tuple[np.ndarray, np.ndarray]:
    """Get mesh data from intermediate object (Orig shape).

    Returns the completely original shape before any deformers are applied.

    Args:
        mesh: Mesh node name.

    Returns:
        Tuple of (vertices, normals) where:
            - vertices: (N, 3) float32 array of original vertex coordinates.
            - normals: (N, 3) float32 array of original vertex normals.
    """
    # Get transform node
    if cmds.objectType(mesh) == "mesh":
        transform = cmds.listRelatives(mesh, parent=True)[0]
    else:
        transform = mesh

    # Find intermediate object
    all_shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []

    orig_shape = None
    for shape in all_shapes:
        if cmds.getAttr(f"{shape}.intermediateObject"):
            orig_shape = shape
            break

    if orig_shape is None:
        # No intermediate object - return current state
        return get_deformed_mesh_data(mesh)

    # Get data directly from intermediate object
    dag_path = _get_dag_path(orig_shape)
    mesh_fn = om.MFnMesh(dag_path)

    points = mesh_fn.getPoints(om.MSpace.kObject)
    num_verts = len(points)

    vertices = np.empty((num_verts, 3), dtype=np.float32)
    for i, p in enumerate(points):
        vertices[i] = (p.x, p.y, p.z)

    normals = np.empty((num_verts, 3), dtype=np.float32)
    for i in range(num_verts):
        n = mesh_fn.getVertexNormal(i, True, om.MSpace.kObject)
        normals[i] = (n.x, n.y, n.z)

    return vertices, normals


def move_to_bind_pose(joints: Optional[list[str]] = None) -> None:
    """Move joints to bind pose.

    Args:
        joints: List of joint names to move.
            If None, uses current selection or all scene joints.
    """
    if joints is None:
        joints = cmds.ls(selection=True, type="joint")
        if not joints:
            joints = cmds.ls(type="joint")

    # Find dagPose node
    for joint in joints:
        connections = cmds.listConnections(joint, type="dagPose") or []
        for pose in connections:
            if cmds.getAttr(f"{pose}.bindPose"):
                cmds.dagPose(joint, restore=True, name=pose)
                break


def is_at_bind_pose(mesh: str) -> bool:
    """Check if mesh is at bind pose.

    Args:
        mesh: Mesh node name.

    Returns:
        True if all influence joints are at their bind pose positions.
    """
    mesh_shape = _get_shape_node(mesh)

    # Find skinCluster
    skincluster = None
    history = cmds.listHistory(mesh_shape, pruneDagObjects=True) or []
    for node in history:
        if cmds.objectType(node) == "skinCluster":
            skincluster = node
            break

    if skincluster is None:
        return True  # No skinCluster means always at bind pose

    # Get influence joints
    influences = cmds.skinCluster(skincluster, query=True, influence=True) or []

    for joint in influences:
        # Check dagPose
        poses = cmds.listConnections(joint, type="dagPose") or []
        for pose in poses:
            if cmds.getAttr(f"{pose}.bindPose"):
                # Check if bind pose
                try:
                    is_bind = cmds.dagPose(joint, query=True, atPose=True, name=pose)
                    if not is_bind:
                        return False
                except Exception as e:
                    logger.debug(f"Failed to query bind pose for {joint}: {e}")

    return True
