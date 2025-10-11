"""Shape node functions."""

from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


def duplicate_original_shape(shape: str) -> str:
    """Duplicate the original shape nodes.

    Args:
        shape (str): The shape node.

    Returns:
        str: The duplicated original shape node.
    """
    if not cmds.objExists(shape):
        raise ValueError(f"Node does not exist: {shape}")

    if cmds.nodeType(shape) not in ["mesh", "nurbsSurface", "nurbsCurve"]:
        raise ValueError(f"Unsupported type: {shape}")

    transform = cmds.listRelatives(shape, p=True)[0]

    # Get original shape
    original_shape = get_original_shape(shape)
    if not original_shape:
        raise ValueError(f"Failed to get the original shape: {shape}")

    # Duplicate
    shape_type = cmds.nodeType(shape)
    transform_name = transform.split("|")[-1]

    new_shape = cmds.createNode(shape_type, ss=True)
    new_transform = cmds.listRelatives(new_shape, p=True)[0]

    # Copy the transform
    mat = cmds.xform(transform, q=True, ws=True, m=True)
    cmds.xform(new_transform, ws=True, m=mat)

    # Copy the shape
    connect_shapes(original_shape, new_shape, only_copy=True)

    # Assign the initial shader
    cmds.sets(new_transform, edit=True, forceElement="initialShadingGroup")

    new_transform = cmds.rename(new_transform, f"{transform_name}_original")

    return new_transform


def get_original_shape(shape: str) -> str:
    """Get the original shape nodes.

    Args:
        shape (str): The shape node.

    Returns:
        str: The original shape node.
    """
    if not cmds.objExists(shape):
        raise ValueError(f"Node does not exist: {shape}")

    input_plug = dict(mesh="inMesh", nurbsSurface="create", nurbsCurve="create")
    shape_type = cmds.nodeType(shape)

    if shape_type not in input_plug:
        raise ValueError(f"Unsupported shape type: {shape_type}")

    plug_chains = cmds.geometryAttrInfo(f"{shape}.{input_plug[shape_type]}", outputPlugChain=True)
    if not plug_chains:
        return shape

    for plug_chain in plug_chains:
        node, _ = plug_chain.split(".")
        if cmds.nodeType(node) == shape_type:
            return node

    return shape


def connect_shapes(src_shape: str, dest_shape: str, **kwargs) -> None:
    """Connect or copy the shapes.

    Args:
        src_shape (str): The source shape node.
        dest_shape (str): The destination shape node.

    Keyword Args:
        only_copy (bool): Whether to only copy the shapes. Default is False.

    Raises:
        ValueError: If the source shape is already connected.If the force_connect is False.
    """
    if not cmds.objExists(src_shape):
        raise ValueError(f"Node does not exist: {src_shape}")

    if not cmds.objExists(dest_shape):
        raise ValueError(f"Node does not exist: {dest_shape}")

    if "geometryShape" not in cmds.nodeType(src_shape, inherited=True):
        raise ValueError(f"Node is not a geometryShape: {src_shape}")

    if "geometryShape" not in cmds.nodeType(dest_shape, inherited=True):
        raise ValueError(f"Node is not a geometryShape: {dest_shape}")

    src_node_type = cmds.nodeType(src_shape)
    dest_node_type = cmds.nodeType(dest_shape)

    if src_node_type != dest_node_type:
        raise ValueError(f"Different shape type: {src_node_type} != {dest_node_type}")

    if src_node_type not in ["mesh", "nurbsSurface", "nurbsCurve"]:
        raise ValueError(f"Unsupported shape type: {src_shape} and {dest_shape}")

    only_copy = kwargs.get("only_copy", False)

    shape_plugs = {"mesh": ["outMesh", "inMesh"], "nurbsSurface": ["local", "create"], "nurbsCurve": ["local", "create"]}

    dest_orig_shape = dest_shape
    plug_chains = cmds.geometryAttrInfo(f"{dest_shape}.{shape_plugs[src_node_type][1]}", outputPlugChain=True)
    if plug_chains:
        plug_nodes = cmds.ls(plug_chains, objectsOnly=True)

        # Check if the shape is already connected
        for plug_node in plug_nodes:
            if plug_node == src_shape:
                cmds.warning(f"Shape is already connected: {src_shape} -> {dest_shape}")
                return

        # Check the connection node type
        first_plug_type = cmds.nodeType(plug_nodes[0])
        if first_plug_type != dest_node_type:
            raise ValueError(f"The type of the found connection node does not match: {dest_node_type} != {first_plug_type}")
        dest_orig_shape = plug_nodes[0]

    cmds.connectAttr(f"{src_shape}.{shape_plugs[src_node_type][0]}", f"{dest_orig_shape}.{shape_plugs[dest_node_type][1]}", f=True)
    if only_copy:
        cmds.refresh()
        cmds.dgdirty(dest_orig_shape)
        cmds.disconnectAttr(f"{src_shape}.{shape_plugs[src_node_type][0]}", f"{dest_orig_shape}.{shape_plugs[dest_node_type][1]}")
        cmds.refresh()
        cmds.dgdirty(dest_orig_shape)

        logger.debug(f"Copied shapes: {src_shape} -> {dest_orig_shape}")
    else:
        logger.debug(f"Connected shapes: {src_shape} -> {dest_orig_shape}")


def check_topology(src_shape: str, dest_shape: str) -> bool:
    """Check the topology.

    Args:
        src_shape (str): The source shape node.
        dest_shape (str): The destination shape node.

    Returns:
        bool: Whether the topology is the same.
    """
    if not cmds.objExists(src_shape):
        raise ValueError(f"Node does not exist: {src_shape}")

    if not cmds.objExists(dest_shape):
        raise ValueError(f"Node does not exist: {dest_shape}")

    src_node_type = cmds.nodeType(src_shape)
    dest_node_type = cmds.nodeType(dest_shape)

    if src_node_type != dest_node_type:
        raise ValueError(f"Different node type: {src_node_type} != {dest_node_type}")

    if src_node_type not in ["mesh", "nurbsSurface", "nurbsCurve"]:
        raise ValueError(f"Unsupported shape type: {src_shape} and {dest_shape}")

    if src_node_type == "mesh":
        src_vtx_count = cmds.polyEvaluate(src_shape, v=True)
        dest_vtx_count = cmds.polyEvaluate(dest_shape, v=True)

        if src_vtx_count != dest_vtx_count:
            logger.debug(f"Different vertex count: {src_shape} != {dest_shape}")
            return False

        src_edge_count = cmds.polyEvaluate(src_shape, e=True)
        dest_edge_count = cmds.polyEvaluate(dest_shape, e=True)

        if src_edge_count != dest_edge_count:
            logger.debug(f"Different edge count: {src_shape} != {dest_shape}")
            return False

        src_face_count = cmds.polyEvaluate(src_shape, f=True)
        dest_face_count = cmds.polyEvaluate(dest_shape, f=True)

        if src_face_count != dest_face_count:
            logger.debug(f"Different face count: {src_shape} != {dest_shape}")
            return False

        return True
    elif src_node_type == "nurbsSurface":
        src_spans_u = cmds.getAttr(f"{src_shape}.spansU")
        dest_spans_u = cmds.getAttr(f"{dest_shape}.spansU")

        if src_spans_u != dest_spans_u:
            logger.debug(f"Different spansU: {src_shape} != {dest_shape}")
            return False

        src_spans_v = cmds.getAttr(f"{src_shape}.spansV")
        dest_spans_v = cmds.getAttr(f"{dest_shape}.spansV")

        if src_spans_v != dest_spans_v:
            logger.debug(f"Different spansV: {src_shape} != {dest_shape}")
            return False

        return True
    elif src_node_type == "nurbsCurve":
        src_degree = cmds.getAttr(f"{src_shape}.degree")
        dest_degree = cmds.getAttr(f"{dest_shape}.degree")

        if src_degree != dest_degree:
            logger.debug(f"Different degree: {src_shape} != {dest_shape}")
            return False

        src_spans = cmds.getAttr(f"{src_shape}.spans")
        dest_spans = cmds.getAttr(f"{dest_shape}.spans")

        if src_spans != dest_spans:
            logger.debug(f"Different spans: {src_shape} != {dest_shape}")
            return False

        return True
    else:
        raise ValueError(f"Unsupported shape type: {src_node_type}")


__all__ = [
    "duplicate_original_shape",
    "get_original_shape",
    "connect_shapes",
    "check_topology",
]
