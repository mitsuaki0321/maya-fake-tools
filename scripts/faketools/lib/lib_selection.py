"""Node selection functions."""

from contextlib import contextmanager
from logging import getLogger
import re
from typing import Optional

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


def _validate_nodes(nodes: list[str]) -> None:
    """Validate nodes list.

    Args:
        nodes (list[str]): The node list to validate.

    Raises:
        ValueError: If nodes are not specified, not a list, don't exist, or are not unique.
    """
    if not nodes:
        raise ValueError("Nodes are not specified.")
    if not isinstance(nodes, list):
        raise ValueError("Nodes must be a list.")

    not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
    if not_exists_nodes:
        raise ValueError(f"Nodes do not exist: {not_exists_nodes}")

    # Check uniqueness for each node
    for node in nodes:
        found_nodes = cmds.ls(node)
        if len(found_nodes) > 1:
            long_nodes = cmds.ls(node, long=True)
            raise ValueError(f"Multiple nodes found with name '{node}'. Please use full path:\n" + "\n".join(f"  - {n}" for n in long_nodes))


def _validate_dag_nodes(nodes: list[str]) -> None:
    """Validate that nodes are DAG nodes.

    Args:
        nodes (list[str]): The node list to validate.

    Raises:
        ValueError: If nodes are not specified, not a list, don't exist, or are not DAG nodes.
    """
    _validate_nodes(nodes)

    not_dag_nodes = [node for node in nodes if "dagNode" not in cmds.nodeType(node, inherited=True)]
    if not_dag_nodes:
        raise ValueError(f"Nodes are not dagNode: {not_dag_nodes}")


def _to_fullpath(nodes: list[str], fullpath: bool) -> list[str]:
    """Convert nodes to fullpath if requested.

    Args:
        nodes (list[str]): The node list.
        fullpath (bool): If True, return full path.

    Returns:
        list[str]: The converted node list.
    """
    if not nodes:
        return []

    if fullpath:
        return cmds.ls(nodes, long=True)
    else:
        return nodes


def filter_by_type(nodes: list[str], node_type: str, invert_match: bool = False, fullpath: bool = False) -> list[str]:
    """Filter nodes by Maya node type.

    Args:
        nodes (list[str]): Nodes to filter.
        node_type (str): Maya node type to filter by (e.g., "transform", "joint", "mesh").
        invert_match (bool): If True, return nodes that do NOT match the type. Default is False.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Filtered nodes matching the criteria.

    Raises:
        ValueError: If nodes are invalid, don't exist, or are not unique.

    Example:
        >>> filter_by_type(["pCube1", "joint1", "pSphere1"], "joint")
        ["joint1"]
        >>> filter_by_type(["pCube1", "joint1"], "joint", invert_match=True)
        ["pCube1"]
    """
    _validate_nodes(nodes)

    filtered_nodes = []
    for node in nodes:
        node_types = cmds.nodeType(node, inherited=True)
        if invert_match:
            if node_type not in node_types:
                filtered_nodes.append(node)
        else:
            if node_type in node_types:
                filtered_nodes.append(node)

    return _to_fullpath(filtered_nodes, fullpath)


def filter_by_regex(nodes: list[str], regex: str, invert_match: bool = False, ignorecase: bool = False, fullpath: bool = False) -> list[str]:
    """Filter nodes by regular expression pattern.

    Args:
        nodes (list[str]): Nodes to filter.
        regex (str): Regular expression pattern to match against node names.
        invert_match (bool): If True, return nodes that do NOT match the pattern. Default is False.
        ignorecase (bool): If True, perform case-insensitive matching. Default is False.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Filtered nodes matching the criteria.

    Raises:
        ValueError: If nodes are invalid, don't exist, or are not unique.

    Example:
        >>> filter_by_regex(["ctrl_L", "ctrl_R", "joint1"], r"ctrl_.*")
        ["ctrl_L", "ctrl_R"]
        >>> filter_by_regex(["CTRL_L", "ctrl_R"], r"ctrl_.*", ignorecase=True)
        ["CTRL_L", "ctrl_R"]
    """
    _validate_nodes(nodes)

    pattern = re.compile(regex, re.IGNORECASE) if ignorecase else re.compile(regex)

    filtered_nodes = []
    for node in nodes:
        if invert_match:
            if not pattern.match(node):
                filtered_nodes.append(node)
        else:
            if pattern.match(node):
                filtered_nodes.append(node)

    return _to_fullpath(filtered_nodes, fullpath)


def get_parents(nodes: list[str], fullpath: bool = False) -> list[str]:
    """Get immediate parent nodes from multiple nodes.

    Collects the direct parent of each input node. Duplicates are automatically removed.

    Args:
        nodes (list[str]): Nodes to get parents from.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Unique parent nodes.

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_parents(["joint2", "joint3"])  # joint1|joint2, joint1|joint3
        ["joint1"]
        >>> get_parents(["pCube1", "pSphere1"])
        ["persp", "top"]  # If they have different parents
    """
    _validate_dag_nodes(nodes)

    result_nodes = []
    for node in nodes:
        parent = cmds.listRelatives(node, parent=True, path=True)
        if parent and parent[0] not in result_nodes:
            result_nodes.append(parent[0])

    return _to_fullpath(result_nodes, fullpath)


def get_all_parents(node: str, fullpath: bool = False, reverse: bool = False) -> list[str]:
    """Get all ancestor nodes from a single node up to the root.

    Walks up the hierarchy from the node to the scene root, collecting all parents.

    Args:
        node (str): Node to get ancestors from.
        fullpath (bool): If True, return results as full paths. Default is False.
        reverse (bool): If True, return root-to-node order instead of node-to-root. Default is False.

    Returns:
        list[str]: All ancestor nodes. Empty list if node has no parent.
            - If reverse=False: [direct parent, grandparent, ..., root]
            - If reverse=True: [root, ..., grandparent, direct parent]

    Raises:
        ValueError: If node is invalid, doesn't exist, is not unique, or is not a DAG node.

    Example:
        >>> get_all_parents("joint3")  # Hierarchy: joint1|joint2|joint3
        ["joint2", "joint1"]
        >>> get_all_parents("joint3", reverse=True)
        ["joint1", "joint2"]
        >>> get_all_parents("joint3", fullpath=True)
        ["joint1|joint2", "joint1"]
    """
    _validate_dag_nodes([node])

    parents = []
    current = node

    while True:
        parent = cmds.listRelatives(current, parent=True, path=True)
        if not parent:
            break

        parents.append(parent[0])
        current = parent[0]

    if reverse:
        parents.reverse()

    return _to_fullpath(parents, fullpath)


def get_children(nodes: list[str], include_shape: bool = False, fullpath: bool = False) -> list[str]:
    """Get immediate child nodes from multiple nodes.

    Collects direct children of each input node. Duplicates are automatically removed.

    Args:
        nodes (list[str]): Nodes to get children from.
        include_shape (bool): If True, include shape nodes in results. Default is False (transforms only).
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Unique child nodes.

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_children(["group1", "group2"])
        ["pCube1", "pSphere1", "joint1"]
        >>> get_children(["pCube1"], include_shape=True)
        ["pCubeShape1"]
    """
    _validate_dag_nodes(nodes)

    result_nodes = []
    for node in nodes:
        if include_shape:
            children = cmds.listRelatives(node, children=True, path=True)
        else:
            children = cmds.listRelatives(node, children=True, path=True, type="transform")

        if children:
            for child in children:
                if child not in result_nodes:
                    result_nodes.append(child)

    return _to_fullpath(result_nodes, fullpath)


def get_siblings(nodes: list[str], fullpath: bool = False) -> list[str]:
    """Get sibling transform nodes from multiple nodes.

    Collects all transform siblings (nodes sharing the same parent) for each input node.
    Duplicates are automatically removed. Input nodes are included in results.

    Args:
        nodes (list[str]): Nodes to get siblings from.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Unique sibling nodes (including input nodes).

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_siblings(["joint2"])  # Siblings: joint1, joint2, joint3
        ["joint1", "joint2", "joint3"]
        >>> get_siblings(["pCube1", "pSphere1"])  # Both are top-level nodes
        ["pCube1", "pSphere1", "pCylinder1"]  # All top-level transforms
    """
    _validate_dag_nodes(nodes)

    result_nodes = []
    for node in nodes:
        if "transform" not in cmds.nodeType(node, inherited=True):
            continue

        parent = cmds.listRelatives(node, parent=True, path=True)
        if parent:
            children = cmds.listRelatives(parent[0], children=True, path=True, type="transform")
            if children:
                for child in children:
                    if child not in result_nodes:
                        result_nodes.append(child)
        else:
            world_nodes = cmds.ls(assemblies=True, long=True)
            for world_node in world_nodes:
                if world_node in ["|persp", "|top", "|front", "|side"]:
                    continue

                if world_node not in result_nodes:
                    result_nodes.append(world_node)

    return _to_fullpath(result_nodes, fullpath)


def get_shapes(nodes: list[str], shape_type: Optional[str] = None, fullpath: bool = False) -> list[str]:
    """Get shape nodes from transform nodes.

    Retrieves shape nodes (geometry) from transform nodes. Duplicates are automatically removed.

    Args:
        nodes (list[str]): Transform nodes to get shapes from.
        shape_type (str | None): Filter by shape type (e.g., "mesh", "nurbsCurve"). None returns all shapes.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Shape nodes.

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_shapes(["pCube1", "pSphere1"])
        ["pCubeShape1", "pSphereShape1"]
        >>> get_shapes(["pCube1", "nurbsCircle1"], shape_type="mesh")
        ["pCubeShape1"]  # Only mesh shapes
    """
    _validate_dag_nodes(nodes)

    shapes = get_children(nodes, include_shape=True, fullpath=True)
    if not shapes:
        return []

    if shape_type:
        filtered_shapes = cmds.ls(shapes, type=shape_type, long=True)
    else:
        filtered_shapes = shapes

    return _to_fullpath(filtered_shapes, fullpath)


def get_hierarchy(nodes: list[str], include_shape: bool = False, fullpath: bool = False) -> list[str]:
    """Get complete hierarchies (nodes and all descendants) from multiple nodes.

    Recursively collects each input node and all its descendants. Duplicates are automatically removed.

    Args:
        nodes (list[str]): Root nodes to get hierarchies from.
        include_shape (bool): If True, include shape nodes in results. Default is False (transforms only).
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: All nodes in the hierarchies (including input nodes).

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_hierarchy(["group1"])  # group1 contains joint1|joint2|joint3
        ["group1", "joint1", "joint2", "joint3"]
        >>> get_hierarchy(["pCube1"], include_shape=True)
        ["pCube1", "pCubeShape1"]
    """
    _validate_dag_nodes(nodes)

    result_nodes = []

    def _get_children_recursive(node: str):
        """Recursively collect node and all descendants."""
        if node not in result_nodes:
            result_nodes.append(node)

        if "transform" not in cmds.nodeType(node, inherited=True):
            return

        if include_shape:
            children = cmds.listRelatives(node, children=True, path=True)
        else:
            children = cmds.listRelatives(node, children=True, path=True, type="transform")

        if children:
            for child in children:
                _get_children_recursive(child)

    for node in nodes:
        _get_children_recursive(node)

    return _to_fullpath(result_nodes, fullpath)


def get_leaf_nodes(nodes: list[str], fullpath: bool = False) -> list[str]:
    """Get leaf nodes (nodes with no transform children) from hierarchies.

    Finds all leaf/end nodes within the hierarchies of the input nodes.
    A leaf node is a transform with no transform children.

    Args:
        nodes (list[str]): Root nodes to search hierarchies.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: All leaf nodes in the hierarchies.

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_leaf_nodes(["group1"])  # group1|joint1|joint2|joint3 (joint3 is leaf)
        ["joint3"]
        >>> get_leaf_nodes(["arm_rig"])  # Multiple end joints
        ["hand_L", "hand_R", "clavicle_end"]
    """
    _validate_dag_nodes(nodes)

    hierarchy_nodes = get_hierarchy(nodes, include_shape=False, fullpath=True)

    result_nodes = []
    for node in hierarchy_nodes:
        children = cmds.listRelatives(node, children=True, path=True, type="transform")
        if not children:
            result_nodes.append(node)

    return _to_fullpath(result_nodes, fullpath)


def get_top_nodes(nodes: list[str], fullpath: bool = False) -> list[str]:
    """Get top-level nodes from a selection (remove descendants).

    Filters input nodes to return only those that are not descendants of other input nodes.
    Useful for getting root nodes when a mix of parents and children are selected.

    Args:
        nodes (list[str]): Nodes to filter.
        fullpath (bool): If True, return results as full paths. Default is False.

    Returns:
        list[str]: Top-level nodes (no node is a descendant of another).

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, or are not DAG nodes.

    Example:
        >>> get_top_nodes(["joint1", "joint1|joint2", "joint1|joint2|joint3"])
        ["joint1"]
        >>> get_top_nodes(["group1", "group2"])  # Both are roots
        ["group1", "group2"]
    """
    _validate_dag_nodes(nodes)

    long_nodes = cmds.ls(nodes, long=True)
    sorted_nodes = sorted(long_nodes, key=lambda x: x.count("|"), reverse=True)

    except_nodes = []
    for node in sorted_nodes:
        for comp_node in sorted_nodes:
            if node == comp_node:
                continue

            if node.startswith(comp_node):
                except_nodes.append(node)
                break

    result_nodes = [node for node in sorted_nodes if node not in except_nodes]

    return _to_fullpath(result_nodes, fullpath)


def reorder_outliner(nodes: list[str], mode: str = "name", reverse: bool = False) -> None:
    """Reorder nodes in Maya outliner.

    Reorders sibling nodes in the outliner based on sorting criteria.
    All nodes must be siblings (share the same parent).
    Nodes not specified in the input list will keep their original positions.

    Args:
        nodes (list[str]): Nodes to reorder. All nodes must be siblings (same parent).
        mode (str): Sorting mode:
            - "name": Sort alphabetically by node name (default)
            - "name_reversed": Sort alphabetically by reversed node name
        reverse (bool): If True, reverse the final sort order. Default is False.

    Raises:
        ValueError: If nodes are invalid, don't exist, are not unique, are not DAG nodes,
                   or are not all in the same hierarchy level (different parents).

    Example:
        >>> # Original order: ['joint1', 'joint3', 'joint2', 'joint4']
        >>> reorder_outliner(["joint3", "joint2"], mode="name")
        # Result: ['joint1', 'joint2', 'joint3', 'joint4']
        # joint1 and joint4 keep their positions, only joint3 and joint2 are sorted

        >>> reorder_outliner(["node_C", "node_A", "node_B"], mode="name", reverse=True)
        # Result: node_C, node_B, node_A (if these are the only children)

        >>> reorder_outliner(["abc", "cba", "bca"], mode="name_reversed")
        # Result: abc, bca, cba (sorted by reversed names: cba, acb, abc)
    """
    _validate_dag_nodes(nodes)

    # Get full paths for all nodes
    long_nodes = cmds.ls(nodes, long=True)

    # Check if all nodes have the same parent
    parents = set()
    parent_node = None
    for node in long_nodes:
        parent = cmds.listRelatives(node, parent=True, fullPath=True)
        parent_path = parent[0] if parent else None
        parents.add(parent_path)
        if parent_node is None:
            parent_node = parent_path

    if len(parents) > 1:
        parent_list = [p if p else "world" for p in sorted(parents)]
        raise ValueError(f"All nodes must be siblings (same parent). Found nodes with different parents: {parent_list}")

    # Get all siblings in their current outliner order
    if parent_node:
        all_siblings = cmds.listRelatives(parent_node, children=True, fullPath=True, type="transform") or []
    else:
        # World nodes (top-level)
        all_siblings = cmds.ls(assemblies=True, long=True)

    # Create set for quick lookup
    input_node_set = set(long_nodes)

    # Sort only the input nodes based on mode
    if mode == "name":
        # Sort by node name (without path)
        sorted_input_nodes = sorted(long_nodes, key=lambda x: x.split("|")[-1])
    elif mode == "name_reversed":
        # Sort by reversed node name
        sorted_input_nodes = sorted(long_nodes, key=lambda x: x.split("|")[-1][::-1])
    else:
        raise ValueError(f"Invalid mode '{mode}'. Must be 'name' or 'name_reversed'.")

    if reverse:
        sorted_input_nodes = sorted_input_nodes[::-1]

    # Create final order by replacing input nodes with sorted versions
    # while keeping other nodes in their original positions
    final_order = []
    sorted_index = 0

    for sibling in all_siblings:
        if sibling in input_node_set:
            # Replace with sorted node from the input list
            final_order.append(sorted_input_nodes[sorted_index])
            sorted_index += 1
        else:
            # Keep original position for nodes not in input list
            final_order.append(sibling)

    # Reorder nodes in the outliner according to final order
    for node in final_order:
        cmds.reorder(node, back=True)


@contextmanager
def restore_selection():
    """Context manager to preserve and restore Maya's current selection.

    Captures the current selection before executing code, then restores it afterwards.
    Handles cases where selected nodes are deleted during the operation.

    Yields:
        None

    Example:
        >>> with restore_selection():
        ...     cmds.select("pCube1")
        ...     # Do operations that change selection
        >>> # Original selection is now restored

        >>> # If nodes are deleted, only existing nodes are restored
        >>> with restore_selection():
        ...     cmds.delete("pCube1")  # Delete a selected node
        >>> # Only remaining selected nodes are restored
    """
    initial_selection = cmds.ls(selection=True, long=True)
    try:
        yield
    finally:
        if not initial_selection:
            cmds.select(cl=True)
        else:
            exists_nodes = []
            not_exists_nodes = []
            for node in initial_selection:
                if cmds.objExists(node):
                    exists_nodes.append(node)
                else:
                    not_exists_nodes.append(node)

            if not_exists_nodes:
                cmds.warning(f"Nodes do not exist: {not_exists_nodes}")

            if exists_nodes:
                cmds.select(exists_nodes, replace=True)
            else:
                cmds.select(cl=True)


__all__ = [
    "is_unique_node",
    "filter_by_type",
    "filter_by_regex",
    "get_parents",
    "get_all_parents",
    "get_children",
    "get_siblings",
    "get_shapes",
    "get_hierarchy",
    "get_leaf_nodes",
    "get_top_nodes",
    "reorder_outliner",
    "restore_selection",
]
