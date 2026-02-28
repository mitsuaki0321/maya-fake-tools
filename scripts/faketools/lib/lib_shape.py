"""Shape node functions."""

from logging import getLogger
from typing import Optional

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


def combine_meshes(meshes: list[str], name: Optional[str] = None) -> str:
    """Combine multiple meshes into one using polyUnite.

    Shader face assignments are automatically preserved by polyUnite.

    Args:
        meshes (list[str]): Mesh transform names to combine.
        name (Optional[str]): Name for the resulting combined mesh. If None,
            the name assigned by polyUnite is kept.

    Returns:
        str: The combined mesh transform name.

    Raises:
        ValueError: If fewer than 2 meshes are provided or any mesh does not exist.
    """
    if len(meshes) < 2:
        raise ValueError("At least 2 meshes are required for combine_meshes")

    for mesh in meshes:
        if not cmds.objExists(mesh):
            raise ValueError(f"Mesh does not exist: {mesh}")

    result = cmds.polyUnite(meshes, constructionHistory=False, mergeUVSets=True)
    combined = result[0]
    cmds.delete(combined, constructionHistory=True)

    if name is not None:
        combined = cmds.rename(combined, name)

    logger.debug("Combined %d meshes into '%s'", len(meshes), combined)
    return combined


def separate_mesh(mesh: str) -> list[str]:
    """Separate a mesh into its shells (connected components) using polySeparate.

    If the mesh has only one shell, it is returned as-is without modification.
    For multi-shell meshes, pieces are unparented to world level and the
    original (now empty) group transform is deleted.

    Args:
        mesh (str): Mesh transform name.

    Returns:
        list[str]: Separated mesh transform names.
    """
    num_shells = cmds.polyEvaluate(mesh, shell=True)
    if num_shells <= 1:
        return [mesh]

    pieces = cmds.polySeparate(mesh, constructionHistory=False)
    result = [p for p in pieces if cmds.objExists(p)]

    # Unparent pieces from the old group to world level
    for piece in result:
        cmds.parent(piece, world=True)

    # Delete the now-empty original group transform
    if cmds.objExists(mesh) and not cmds.listRelatives(mesh, children=True):
        cmds.delete(mesh)

    logger.debug("Separated '%s' into %d shells", mesh, len(result))
    return result


def validate_shell_shaders(mesh: str) -> None:
    """Validate that each shell in a mesh has a single shader assignment.

    Checks adjacent faces (sharing an edge) for differing shader assignments.
    Adjacent faces are always in the same shell, so a mismatch means a shell
    has multiple shaders, which prevents clean separation by polySeparate.

    Args:
        mesh (str): Mesh transform name.

    Raises:
        ValueError: If any shell contains faces with different shader assignments,
            or if the mesh has no mesh shape.
    """
    import maya.api.OpenMaya as om

    shapes = cmds.listRelatives(mesh, shapes=True, type="mesh") or []
    if not shapes:
        raise ValueError(f"'{mesh}' has no mesh shape")

    sel = om.MSelectionList()
    sel.add(shapes[0])
    dag = sel.getDagPath(0)
    mesh_fn = om.MFnMesh(dag)

    shader_engines, face_shader_indices = mesh_fn.getConnectedShaders(0)
    if len(shader_engines) <= 1:
        return

    edge_it = om.MItMeshEdge(dag)
    while not edge_it.isDone():
        connected_faces = edge_it.getConnectedFaces()
        if len(connected_faces) == 2 and face_shader_indices[connected_faces[0]] != face_shader_indices[connected_faces[1]]:
            raise ValueError(f"Mesh '{mesh}' contains a shell with multiple shader assignments. Each shell must have a single shader for separation.")
        edge_it.next()


def _get_shading_engines(transform: str) -> list[str]:
    """Get shading engines assigned to a mesh transform's shape.

    Args:
        transform (str): Mesh transform name.

    Returns:
        list[str]: Shading engine names. Empty list if no shape or no assignment.
    """
    shapes = cmds.listRelatives(transform, shapes=True, type="mesh") or []
    if not shapes:
        return []
    return cmds.listSets(object=shapes[0], type=1) or []


def combine_meshes_per_shader(meshes: list[str]) -> dict[str, str]:
    """Combine meshes grouped by their shading engine.

    Pipeline:

    1. Validate each mesh via :func:`validate_shell_shaders` — rejects
       meshes whose shells contain face-level multi-shader assignments.
    2. Separate multi-shader meshes into single-shader shells
       via :func:`separate_mesh`.
    3. Group the resulting single-shader meshes by shading engine and
       combine each group via :func:`combine_meshes`.

    Args:
        meshes (list[str]): Mesh transform names.

    Returns:
        dict[str, str]: ``{shading_engine_name: combined_mesh_name}``.

    Raises:
        ValueError: If meshes is empty or any mesh has a shell with
            face-level multi-shader assignments.
    """
    if not meshes:
        raise ValueError("No meshes provided")

    # Step 1 + 2: Validate and separate where needed
    all_pieces: list[str] = []
    for mesh in meshes:
        if not cmds.objExists(mesh):
            logger.warning("Mesh does not exist, skipping: %s", mesh)
            continue

        validate_shell_shaders(mesh)

        sgs = _get_shading_engines(mesh)
        if len(sgs) <= 1:
            all_pieces.append(mesh)
        else:
            pieces = separate_mesh(mesh)
            all_pieces.extend(pieces)

    # Step 3: Group by shader and combine
    shader_groups: dict[str, list[str]] = {}
    for piece in all_pieces:
        if not cmds.objExists(piece):
            continue
        sgs = _get_shading_engines(piece)
        sg = sgs[0] if sgs else "initialShadingGroup"
        shader_groups.setdefault(sg, []).append(piece)

    result: dict[str, str] = {}
    for sg, group_meshes in shader_groups.items():
        if len(group_meshes) == 1:
            result[sg] = group_meshes[0]
        else:
            combined = combine_meshes(group_meshes)
            result[sg] = combined

    logger.debug("Combined meshes per shader: %s", result)
    return result


def shape_parent(sources: list[str], target: str, delete_source_transform: bool = True) -> list[str]:
    """Move shape nodes from source transforms to a target transform.

    Args:
        sources (list[str]): Source transform nodes containing shapes to move.
        target (str): Target transform node to receive the shapes.
        delete_source_transform (bool): If True, delete each source transform
            after moving its shapes (if it becomes empty).

    Returns:
        list[str]: Names of the moved shape nodes.

    Raises:
        ValueError: If target or any source does not exist.
    """
    if not cmds.objExists(target):
        raise ValueError(f"Target does not exist: {target}")

    moved: list[str] = []
    for source in sources:
        if not cmds.objExists(source):
            raise ValueError(f"Source does not exist: {source}")

        shapes = cmds.listRelatives(source, shapes=True, fullPath=True) or []
        if not shapes:
            logger.warning("Source '%s' has no shapes to move", source)
            continue

        for shape in shapes:
            result = cmds.parent(shape, target, shape=True, relative=True)
            moved.extend(result)

        if delete_source_transform:
            remaining_children = cmds.listRelatives(source, children=True)
            if not remaining_children:
                logger.debug("Deleting empty source transform: %s", source)
                cmds.delete(source)

    logger.debug("Moved %d shapes from %d sources to '%s'", len(moved), len(sources), target)
    return moved


__all__ = [
    "duplicate_original_shape",
    "get_original_shape",
    "connect_shapes",
    "check_topology",
    "combine_meshes",
    "validate_shell_shaders",
    "separate_mesh",
    "combine_meshes_per_shader",
    "shape_parent",
]
