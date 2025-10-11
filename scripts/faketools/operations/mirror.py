"""Mirror transform operations."""

from logging import getLogger
import math

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ..lib.lib_attribute import AttributeLockHandler, is_modifiable

logger = getLogger(__name__)


def mirror_transforms(node: str, axis: str = "x", mirror_position: bool = True, mirror_rotation: bool = True, space: str = "world") -> None:
    """Mirror the transform of the specified node across the specified axis.

    Args:
        node (str): The transform node to mirror.
        axis (str): The axis to mirror across ('x', 'y', or 'z'). Defaults to 'x'.
        mirror_position (bool): Whether to mirror position. Defaults to True.
        mirror_rotation (bool): Whether to mirror rotation. Defaults to True.
        space (str): The space to mirror in ('world' or 'local'). Defaults to 'world'.
            - 'world': Mirror in world space
            - 'local': Mirror in local space (relative to parent)

    Raises:
        ValueError: If node doesn't exist, is not unique, is not a transform, or parameters are invalid.
        RuntimeError: If the node has connected transform attributes.

    Notes:
        - If space is 'world', mirrors the node's world-space transform across the specified axis.
        - If space is 'local', mirrors the node's local-space transform (relative to parent) across the specified axis.
        - If transform attributes are locked, they will be temporarily unlocked.
        - If any transform attributes (tx, ty, tz, rx, ry, rz, sx, sy, sz) are connected, the operation will fail.
        - At least one of mirror_position or mirror_rotation must be True.
    """
    # Validate node
    if not node:
        raise ValueError("Node is not specified.")

    found_nodes = cmds.ls(node)
    if not found_nodes:
        raise ValueError(f"Node does not exist: {node}")

    if len(found_nodes) > 1:
        long_nodes = cmds.ls(node, long=True)
        raise ValueError(f"Multiple nodes found with name '{node}'. Please use full path:\n" + "\n".join(f"  - {n}" for n in long_nodes))

    validated_node = found_nodes[0]

    if "transform" not in cmds.nodeType(validated_node, inherited=True):
        raise ValueError(f"Node is not a transform: {validated_node}")

    node = validated_node

    # Validate axis parameter
    if axis not in ["x", "y", "z"]:
        raise ValueError(f"Invalid axis: {axis}. Must be 'x', 'y', or 'z'.")

    # Validate space parameter
    if space not in ["world", "local"]:
        raise ValueError(f"Invalid space: {space}. Must be 'world' or 'local'.")

    # Validate mirror options
    if not mirror_position and not mirror_rotation:
        raise ValueError("At least one of mirror_position or mirror_rotation must be True.")

    # Check if transform attributes are connected
    for attr in ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]:
        if cmds.connectionInfo(f"{node}.{attr}", isDestination=True):
            logger.debug(f"Connected attribute: {node}.{attr}")
            raise RuntimeError(f"Failed to mirror transform because connections exist: {node}")

    # Check if transform attributes are modifiable
    transform_attributes = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ"]
    not_modifiable_attrs = [attr for attr in transform_attributes if not is_modifiable(node, attr)]
    if not_modifiable_attrs:
        raise ValueError(f"Node attributes are not modifiable: {node} -> {not_modifiable_attrs}")

    # Store and unlock locked attributes
    lock_handler = AttributeLockHandler()
    lock_handler.stock_lock_attrs(node, transform_attributes, include_parent=True)

    try:
        # Create mirror matrix based on axis
        if axis == "x":
            mirror_matrix = om.MMatrix([[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        elif axis == "y":
            mirror_matrix = om.MMatrix([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        else:  # z
            mirror_matrix = om.MMatrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])

        # Get node's world matrix
        world_matrix = cmds.getAttr(f"{node}.worldMatrix")
        world_matrix = om.MMatrix(world_matrix)

        # Calculate mirrored transform based on space
        if space == "local":
            # Get parent node
            parent = cmds.listRelatives(node, parent=True, fullPath=True)

            if parent:
                # Get parent world matrix and its inverse
                parent_world_matrix = cmds.getAttr(f"{parent[0]}.worldMatrix")
                parent_world_matrix = om.MMatrix(parent_world_matrix)
                parent_inverse_matrix = parent_world_matrix.inverse()

                # Calculate local matrix (node's transform relative to parent)
                local_matrix = world_matrix * parent_inverse_matrix

                # Apply mirror to local matrix
                mirrored_local_matrix = local_matrix * mirror_matrix

                # Convert back to world space
                mirrored_world_matrix = mirrored_local_matrix * parent_world_matrix
                logger.debug(f"Mirroring in local space (parent: {parent[0]})")
            else:
                # No parent, treat as world space
                mirrored_world_matrix = world_matrix * mirror_matrix
                logger.debug("No parent found, mirroring in world space")
        else:  # world
            # Mirror in world space
            mirrored_world_matrix = world_matrix * mirror_matrix
            logger.debug("Mirroring in world space")

        # Extract transform components from mirrored matrix
        transform_mat = om.MTransformationMatrix(mirrored_world_matrix)
        position = transform_mat.translation(om.MSpace.kWorld)
        rotation = transform_mat.rotation()
        rotation = [math.degrees(angle) for angle in [rotation.x, rotation.y, rotation.z]]
        scale = transform_mat.scale(om.MSpace.kWorld)

        # Apply mirrored transform
        if mirror_position:
            cmds.xform(node, translation=position, worldSpace=True)
            logger.debug(f"Mirrored position: {node} on {axis} axis in {space} space")

        if mirror_rotation:
            cmds.xform(node, rotation=rotation, scale=scale, worldSpace=True)
            logger.debug(f"Mirrored rotation and scale: {node} on {axis} axis in {space} space")

    finally:
        # Restore locked attributes
        lock_handler.restore_lock_attrs(node)


__all__ = ["mirror_transforms"]
