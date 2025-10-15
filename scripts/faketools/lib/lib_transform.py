"""Transform utility functions."""

from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


def _validate_and_get_transform(node: str) -> str:
    """Validate and return the transform node, raising detailed errors if invalid.

    Args:
        node (str): The node name to validate.

    Returns:
        str: The validated node name.

    Raises:
        ValueError: If node is not specified, doesn't exist, is not unique, or is not a transform.
    """
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

    return validated_node


def freeze_transform(node: str) -> None:
    """Freeze the transform of the specified node and its children.

    Args:
        node (str): The target transform node.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.
        RuntimeError: If the node has connected transform attributes.

    Notes:
        - Even if the transform attributes of the children are locked, they will be forcibly unlocked and processed.
        - If any transform attributes (tx, ty, tz, rx, ry, rz, sx, sy, sz) are connected, the operation will fail.
        - For joint nodes, also handles joint orient attributes (jox, joy, joz).
    """
    node = _validate_and_get_transform(node)

    # Check if transform attributes are connected
    for attr in ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]:
        if cmds.connectionInfo(f"{node}.{attr}", isDestination=True):
            logger.debug(f"Connected attribute: {node}.{attr}")
            raise RuntimeError(f"Failed to freeze transform because connections exist: {node}")

    # Check locked attributes on the target node
    locked_attrs = cmds.listAttr(node, locked=True) or []

    # Temporarily unlock locked attributes
    for attr in locked_attrs:
        cmds.setAttr(f"{node}.{attr}", lock=False)

    try:
        # Get all descendant nodes
        nodes = cmds.listRelatives(node, ad=True, path=True, type="transform") or []
        nodes.append(node)

        # Unlock the locked attributes of children
        locked_data = {}
        for child_node in nodes:
            attrs = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "jox", "joy", "joz"]
            child_locked_attrs = []
            for attr in attrs:
                if cmds.nodeType(child_node) == "joint":
                    if cmds.getAttr(f"{child_node}.{attr}", lock=True):
                        child_locked_attrs.append(attr)
                        cmds.setAttr(f"{child_node}.{attr}", lock=False)
                else:
                    if attr in ["jox", "joy", "joz"]:
                        continue
                    if cmds.getAttr(f"{child_node}.{attr}", lock=True):
                        child_locked_attrs.append(attr)
                        cmds.setAttr(f"{child_node}.{attr}", lock=False)

            if child_locked_attrs:
                locked_data[child_node] = child_locked_attrs
                logger.debug(f"Unlocked attributes: {child_node} -> {child_locked_attrs}")

        # Freeze the transform
        cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=0, pn=True)
        logger.debug(f"Freeze transform: {node}")

        # Lock the previously locked attributes
        for child_node, attrs in locked_data.items():
            for attr in attrs:
                cmds.setAttr(f"{child_node}.{attr}", lock=True)

    finally:
        # Re-lock the originally locked attributes
        for attr in locked_attrs:
            cmds.setAttr(f"{node}.{attr}", lock=True)


def freeze_transform_pivot(node: str) -> None:
    """Freeze the pivot of the specified node without affecting transform values.

    Args:
        node (str): The target transform node.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.
        RuntimeError: If the node has connected transform attributes.

    Notes:
        - This freezes only the pivot, keeping the transform values unchanged.
        - If any transform attributes (tx, ty, tz, rx, ry, rz, sx, sy, sz) are connected, the operation will fail.
    """
    node = _validate_and_get_transform(node)

    # Check if transform attributes are connected
    for attr in ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]:
        if cmds.connectionInfo(f"{node}.{attr}", isDestination=True):
            logger.debug(f"Connected attribute: {node}.{attr}")
            raise RuntimeError(f"Failed to freeze pivot because connections exist: {node}")

    # Check locked attributes
    locked_attrs = cmds.listAttr(node, locked=True) or []

    # Temporarily unlock locked attributes
    for attr in locked_attrs:
        cmds.setAttr(f"{node}.{attr}", lock=False)

    try:
        # Freeze the pivot (apply=False)
        cmds.makeIdentity(node, apply=False, t=True, r=True, s=True, n=0, pn=True)
        logger.debug(f"Freeze pivot: {node}")

    finally:
        # Re-lock the originally locked attributes
        for attr in locked_attrs:
            cmds.setAttr(f"{node}.{attr}", lock=True)


def freeze_mesh_vertices(node: str) -> None:
    """Freeze the vertices of the specified mesh node.

    Args:
        node (str): The target mesh transform node.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.
        RuntimeError: If the node has connected transform attributes.

    Notes:
        - This freezes only the vertices, keeping the transform values unchanged.
        - If any transform attributes (tx, ty, tz, rx, ry, rz, sx, sy, sz) are connected, the operation will fail.
    """
    node = _validate_and_get_transform(node)

    shapes = cmds.listRelatives(node, shapes=True, pa=True, type="mesh", ni=True) or []
    if not shapes:
        logger.warning(f"No mesh shapes found under: {node}, skipping.")
        return
    else:
        mesh = shapes[0]

    try:
        cmds.polyCollapseTweaks(mesh)
    except RuntimeError:
        vertex_count = cmds.polyEvaluate(mesh, vertex=True)
        for i in range(vertex_count):
            current_pos = cmds.getAttr(f"{mesh}.pnts[{i}]")[0]
            if current_pos != (0.0, 0.0, 0.0):
                cmds.setAttr(f"{mesh}.pnts[{i}]", 0.0, 0.0, 0.0)

    logger.debug(f"Froze mesh vertices for node: {node}")


__all__ = [
    "freeze_transform",
    "freeze_transform_pivot",
]
