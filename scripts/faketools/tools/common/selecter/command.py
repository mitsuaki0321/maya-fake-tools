"""
Duplicate and rename the node.
"""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ....lib import lib_name, lib_shape
from ....lib.lib_selection import get_hierarchy, get_top_nodes

logger = getLogger(__name__)


def solve_rename(nodes: list[str], regex_name: str, **kwargs) -> list[str]:
    """Solve the node name.

    Args:
        nodes (list[str]): The target node list.
        regex_name (str): The new name.

    Keyword Args:
        start_alphabet (int): The start alphabet. Default is 1.
        start_number (int): The start number. Default is 1.

    Notes:
        - If dagNode and nonDagNode are mixed, an error will be output.

    Returns:
        list[str]: The renamed node list.
    """
    logger.debug("Start Rename")

    # Check node
    if not nodes:
        cmds.error("Nodes are not specified.")
    elif not isinstance(nodes, list):
        cmds.error("Nodes must be a list.")

    # Node exists
    not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
    if not_exists_nodes:
        cmds.error(f"Nodes do not exist: {not_exists_nodes}")

    dag_nodes = []
    non_dag_nodes = []
    for node in nodes:
        if cmds.objExists(node):
            if cmds.ls(node, dag=True):
                dag_nodes.append(node)
            else:
                non_dag_nodes.append(node)

    if dag_nodes and non_dag_nodes:
        cmds.error("DagNode and nonDagNode are mixed.")

    start_alpha = kwargs.get("start_alpha", "A")
    start_number = kwargs.get("start_number", 1)

    if dag_nodes:
        local_names = [node.split("|")[-1] for node in dag_nodes]
        new_names = lib_name.solve_names(local_names, regex_name, start_alpha=start_alpha, start_number=start_number)

        result_nodes = _rename_dag_nodes(dag_nodes, new_names)

        logger.debug("End dagNode")

        return result_nodes

    if non_dag_nodes:
        new_names = lib_name.solve_names(non_dag_nodes, regex_name, start_alpha=start_alpha, start_number=start_number)

        result_nodes = _rename_non_dag_nodes(non_dag_nodes, new_names)

        logger.debug("End nonDagNode")

        return result_nodes


def substitute_rename(nodes: list[str], regex_name: str, replace_name: str) -> list[str]:
    """Substitute the node name.

    Args:
        nodes (list[str]): The target node list.
        regex_name (str): The name to substitute.
        replace_name (str): The new name.

    Returns:
        list[str]: The substituted node list.
    """
    logger.debug("Start Rename")

    # Check node
    if not nodes:
        cmds.error("Nodes are not specified.")
    elif not isinstance(nodes, list):
        cmds.error("Nodes must be a list.")

    # Node exists
    not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
    if not_exists_nodes:
        cmds.error(f"Nodes do not exist: {not_exists_nodes}")

    dag_nodes = []
    non_dag_nodes = []
    for node in nodes:
        if cmds.objExists(node):
            if cmds.ls(node, dag=True):
                dag_nodes.append(node)
            else:
                non_dag_nodes.append(node)

    if dag_nodes and non_dag_nodes:
        cmds.error("DagNode and nonDagNode are mixed.")

    if dag_nodes:
        local_names = [node.split("|")[-1] for node in dag_nodes]
        new_names = lib_name.substitute_names(local_names, regex_name, replace_name)

        result_nodes = _rename_dag_nodes(dag_nodes, new_names)

        logger.debug("End dagNode")

        return result_nodes

    if non_dag_nodes:
        new_names = lib_name.substitute_names(non_dag_nodes, regex_name, replace_name)

        result_nodes = _rename_non_dag_nodes(non_dag_nodes, new_names)

        logger.debug("End nonDagNode")

        return result_nodes


def _rename_dag_nodes(node_names: list[str], new_names: list[str]) -> list[str]:
    """Rename the dag nodes.

    Args:
        node_names (list[str]): The target node list.
        new_names (list[str]): The new name list.

    Returns:
        list[str]: The renamed node list.

    Notes:
        - Uses Maya API to maintain object references during hierarchy changes.
        - Uses cmds.rename() for undo support.
        - Retrieves current path before each rename to handle parent path changes.
    """
    # Get MObjects for all nodes first (to handle hierarchy changes)
    sel = om.MSelectionList()
    for node_name in node_names:
        sel.add(node_name)

    # Store MObjects
    mobjects = []
    for i in range(sel.length()):
        dag_path = sel.getDagPath(i)
        mobjects.append(dag_path.node())

    result_nodes = []
    for mobject, new_name in zip(mobjects, new_names):
        # Get current path from MObject (updates even if parent renamed)
        dag_path = om.MDagPath.getAPathTo(mobject)
        current_path = dag_path.fullPathName()
        dag_node_fn = om.MFnDagNode(dag_path)

        # Get old name for logging
        old_local_name = dag_node_fn.name()

        # Rename using cmds (for undo support)
        result_name = cmds.rename(current_path, new_name)
        result_nodes.append(result_name)

        # Get new name for logging
        new_local_name = result_name.split("|")[-1]

        if old_local_name == new_local_name:
            logger.debug(f"The name has not changed before and after: {old_local_name} -> {new_local_name}")
        else:
            logger.debug(f"Renamed: {old_local_name} -> {new_local_name}")

    return result_nodes


def _rename_non_dag_nodes(nodes: list[str], new_names: list[str]) -> list[str]:
    """Rename the non dag nodes.

    Args:
        nodes (list[str]): The target node list.
        new_names (list[str]): The new name list.

    Returns:
        list[str]: The renamed node list.
    """
    result_nodes = []
    for node, new_name in zip(nodes, new_names):
        if node == new_name:
            result_nodes.append(node)
        else:
            new_name = cmds.rename(node, new_name)
            result_nodes.append(new_name)

        logger.debug(f"Renamed: {node} -> {new_name}")

    return result_nodes


def substitute_duplicate(nodes: list[str], regex_name: str, replace_name: str) -> list[str]:
    """Substitute the duplicate node name.

    Args:
        nodes (list[str]): The target node list.
        regex_name (str): The name to substitute.
        replace_name (str): The new name.

    Raises:
        RuntimeError: DagNode and nonDagNode are mixed.

    Returns:
        list[str]: The substituted node list.
    """
    # Check node
    if not nodes:
        cmds.error("Nodes are not specified.")
    elif not isinstance(nodes, list):
        cmds.error("Nodes must be a list.")

    # Node exists
    not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
    if not_exists_nodes:
        cmds.error(f"Nodes do not exist: {not_exists_nodes}")

    dag_nodes = []
    non_dag_nodes = []
    for node in nodes:
        if cmds.objExists(node):
            if cmds.ls(node, dag=True):
                dag_nodes.append(node)
            else:
                non_dag_nodes.append(node)

    if dag_nodes and non_dag_nodes:
        cmds.error("DagNode and nonDagNode are mixed.")

    if dag_nodes:
        transform_nodes = []
        for node in dag_nodes:
            if "transform" in cmds.nodeType(node, inherited=True):
                transform_nodes.append(node)
            elif "shape" in cmds.nodeType(node, inherited=True):
                transform_node = cmds.listRelatives(node, parent=True, f=True)[0]
                transform_nodes.append(transform_node)

        # Get only the top of the hierarchy for nodes with duplicate hierarchy
        transform_nodes = get_top_nodes(transform_nodes)

        logger.debug(f"Before rename nodes: {transform_nodes}")

        result_nodes = []
        for transform_node in transform_nodes:
            dup_nodes = cmds.duplicate(transform_node, rc=True)

            hierarchy_nodes = get_hierarchy([transform_node], include_shape=True)
            local_names = [lib_name.get_local_name(node) for node in hierarchy_nodes]
            new_names = lib_name.substitute_names(local_names, regex_name, replace_name)

            rename_nodes = _rename_dag_nodes(dup_nodes, new_names)

            result_nodes.extend(rename_nodes)

        return result_nodes

    if non_dag_nodes:
        logger.debug(f"Before rename nodes: {non_dag_nodes}")

        new_names = lib_name.substitute_names(non_dag_nodes, regex_name, replace_name)
        dup_nodes = cmds.duplicate(non_dag_nodes, rc=True)
        result_nodes = _rename_non_dag_nodes(dup_nodes, new_names)

        return result_nodes


def substitute_duplicate_original(nodes: list[str], regex_name: str, replace_name: str) -> list[str]:
    """Duplicate the original shape of the shape node and replace it with the specified name.

    Args:
        nodes (list[str]): The target node list.
        regex_name (str): The name to substitute.
        replace_name (str): The new name.

    Notes:
        - Target node type is shape node. Only mesh, nurbsSurface, nurbsCurve.

    Returns:
        list[str]: The substituted node list.
    """
    # Check node
    if not nodes:
        cmds.error("Nodes are not specified.")
    elif not isinstance(nodes, list):
        cmds.error("Nodes must be a list.")

    # Node exists
    not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
    if not_exists_nodes:
        cmds.error(f"Nodes do not exist: {not_exists_nodes}")

    # Duplicate original shape
    dup_nodes = []
    name_nodes = []
    for node in nodes:
        shp = cmds.listRelatives(node, shapes=True, f=True)
        if not shp:
            cmds.warning(f"Node has no shape: {node}")
            continue

        if cmds.nodeType(shp[0]) not in ["mesh", "nurbsSurface", "nurbsCurve"]:
            cmds.warning(f"Node is not a shape: {node}")
            continue

        orig_transform = lib_shape.duplicate_original_shape(shp[0])
        dup_nodes.append(orig_transform)
        name_nodes.append(node)

    if not dup_nodes:
        cmds.warning("No original shape duplicated.")
        return []

    # Substitute name
    new_names = lib_name.substitute_names(name_nodes, regex_name, replace_name)
    result_nodes = _rename_non_dag_nodes(dup_nodes, new_names)

    return result_nodes
