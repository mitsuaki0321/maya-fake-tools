"""Transform utility functions."""

from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


def is_unique_node(node: str) -> bool:
    """Check if the node exists and is unique.

    Args:
        node (str): The node name to check.

    Returns:
        bool: True if the node exists and is unique, False otherwise.

    Example:
        >>> is_unique_node("pSphere1")
        True
        >>> is_unique_node("duplicate_name")  # If multiple nodes exist
        False
        >>> is_unique_node("nonexistent")
        False
    """
    if not node:
        return False

    found_nodes = cmds.ls(node)
    return len(found_nodes) == 1


def is_unique_transform(node: str) -> bool:
    """Check if the node exists, is unique, and is a transform node.

    Args:
        node (str): The node name to check.

    Returns:
        bool: True if the node exists, is unique, and is a transform, False otherwise.

    Example:
        >>> is_unique_transform("pSphere1")
        True
        >>> is_unique_transform("pSphereShape1")  # Shape node, not transform
        False
        >>> is_unique_transform("duplicate_name")  # Multiple nodes
        False
    """
    if not is_unique_node(node):
        return False

    found_nodes = cmds.ls(node)
    return "transform" in cmds.nodeType(found_nodes[0], inherited=True)


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


def get_parent(node: str, long: bool = False) -> str | None:
    """Get the parent node of the specified transform.

    Args:
        node (str): The target node.
        long (bool): Return full path if True. Default is False.

    Returns:
        str | None: The parent node, or None if no parent exists.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.
    """
    node = _validate_and_get_transform(node)

    parent = cmds.listRelatives(node, parent=True, path=True)
    if not parent:
        return None

    if long:
        return cmds.ls(parent[0], long=True)[0]
    else:
        return parent[0]


def get_children(node: str, recursive: bool = False, long: bool = False) -> list[str]:
    """Get the children nodes of the specified transform.

    Args:
        node (str): The target node.
        recursive (bool): If True, get all descendants recursively. Default is False.
        long (bool): Return full path if True. Default is False.

    Returns:
        list[str]: The children nodes. Returns [] if no children exist.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.

    Notes:
        - Does not use cmds.listRelatives(ad=True) because Maya returns descendants in reverse order.
        - Only returns transform nodes (excludes shapes).
    """
    node = _validate_and_get_transform(node)

    if not recursive:
        children = cmds.listRelatives(node, children=True, type="transform", path=True)
        if not children:
            return []

        if long:
            return cmds.ls(children, long=True)
        else:
            return children

    # Recursive mode - manual implementation to maintain correct order
    result = []

    def _get_children_recursive(parent_node: str):
        """Get children recursively in correct order."""
        children = cmds.listRelatives(parent_node, children=True, type="transform", path=True)
        if not children:
            return

        for child in children:
            if long:
                child_long = cmds.ls(child, long=True)[0]
                result.append(child_long)
            else:
                result.append(child)
            _get_children_recursive(child)

    _get_children_recursive(node)
    return result


def get_parents(node: str, long: bool = False, reverse: bool = False) -> list[str]:
    """Get all parent nodes from the specified node to the root.

    Args:
        node (str): The target node.
        long (bool): Return full path if True. Default is False.
        reverse (bool): If True, return in reverse order (root to deepest). Default is False.

    Returns:
        list[str]: All parent nodes. Returns [] if no parent exists.
            - If reverse=False: Ordered from deepest (direct parent) to root
            - If reverse=True: Ordered from root to deepest (direct parent)

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.

    Example:
        >>> get_parents("joint1|joint2|joint3")
        ["joint1|joint2", "joint1"]  # Deepest to root order (reverse=False)
        >>> get_parents("joint1|joint2|joint3", reverse=True)
        ["joint1", "joint1|joint2"]  # Root to deepest order (reverse=True)
    """
    node = _validate_and_get_transform(node)

    parents = []
    current = node

    while True:
        parent = cmds.listRelatives(current, parent=True, path=True)
        if not parent:
            break

        if long:
            parent_long = cmds.ls(parent[0], long=True)[0]
            parents.append(parent_long)
        else:
            parents.append(parent[0])

        current = parent[0]

    if reverse:
        parents.reverse()

    return parents


def get_bottoms(node: str, long: bool = False) -> list[str]:
    """Get all leaf nodes (deepest transform nodes without children) under the specified node.

    Args:
        node (str): The target node.
        long (bool): Return full path if True. Default is False.

    Returns:
        list[str]: All leaf transform nodes. Returns [node] if the node itself has no children.

    Raises:
        ValueError: If node doesn't exist, is not unique, or is not a transform.

    Notes:
        - Only returns transform nodes (excludes shapes).
        - A "bottom" node is defined as a transform with no transform children.
    """
    node = _validate_and_get_transform(node)

    # Get all descendants
    all_descendants = get_children(node, recursive=True, long=long)

    # If no descendants, the node itself is the bottom
    if not all_descendants:
        if long:
            return [cmds.ls(node, long=True)[0]]
        else:
            return [node]

    # Filter nodes that have no transform children
    bottoms = []
    for descendant in all_descendants:
        children = cmds.listRelatives(descendant, children=True, type="transform", path=True)
        if not children:
            bottoms.append(descendant)

    return bottoms


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
