"""Convert MLdeleteUnused to python."""

import maya.cmds as cmds


def _get_render_nodes() -> list[str]:
    """Get all rendering nodes in the scene.

    Returns:
        list[str]: List of rendering nodes.
    """
    render_nodes = []

    # Collect each type of node
    node_classifications = ["texture", "utility", "math", "imageplane", "shader"]

    for classification in node_classifications:
        try:
            node_types = cmds.listNodeTypes(classification)
            if node_types:
                for node_type in node_types:
                    nodes = cmds.ls(type=node_type, long=True)
                    if nodes:
                        render_nodes.extend(nodes)
        except Exception:
            pass

    # Include Mental Ray nodes if present
    try:
        mr_nodes = cmds.lsThroughFilter("DefaultMrNodesFilter")
        if mr_nodes:
            render_nodes.extend(mr_nodes)
    except Exception:
        pass

    return list(set(render_nodes))  # Remove duplicates


def _is_shading_group_unused(shading_group) -> bool:
    """Determine if a shading group is unused."""
    if not cmds.objExists(shading_group):
        return False

    # Default shading groups are not subject to deletion
    default_groups = ["initialShadingGroup", "initialParticleSE", "defaultLightSet", "defaultObjectSet"]
    if shading_group in default_groups:
        return False

    try:
        # Check if the set is renderable
        if not cmds.sets(shading_group, q=True, renderable=True):
            return False

        # Check members
        members = cmds.sets(shading_group, q=True) or []

        # Check connections to render layers
        layers = cmds.listConnections(shading_group, type="renderLayer") or []

        # Check connections to material templates
        material_templates = cmds.listConnections(shading_group, type="materialTemplate") or []

        # Check connections to shapes
        shapes = cmds.listConnections(shading_group, type="shape", p=True, d=True, s=False) or []

        # If there are no members or connections
        if not members and not layers and not material_templates and not shapes:
            return True

        # Check if a shader is connected
        shader_attrs = [".surfaceShader", ".volumeShader", ".displacementShader"]
        has_shader = False

        for attr in shader_attrs:
            connections = cmds.listConnections(shading_group + attr) or []
            if connections:
                has_shader = True
                break

        # If no shader is connected, it is unused
        if not has_shader:
            return True

    except Exception:
        pass

    return False


def _is_material_unused(material) -> bool:
    """Determine if a material (shader) is unused."""
    if not cmds.objExists(material):
        return False

    # Default materials are not subject to deletion
    default_materials = cmds.ls(defaultNodes=True, materials=True) or []
    if material in default_materials:
        return False

    try:
        # Check output connections
        connections = cmds.listConnections(material, c=True, s=False, shapes=True) or []

        if not connections:
            return True

        # Process connections in pairs (plug, destination)
        for i in range(0, len(connections), 2):
            plug = connections[i]

            # If there is a connection other than the message attribute, it is in use
            if not plug.endswith(".message"):
                return False

            # If there is a connection to a shading group even via message attribute, it is in use
            se_connections = cmds.listConnections(plug, type="shadingEngine") or []
            if se_connections:
                return False

        return True

    except Exception:
        pass

    return False


def _is_texture_utility_unused(node) -> bool:
    """Determine if a texture/utility node is unused."""
    if not cmds.objExists(node):
        return False

    try:
        node_type = cmds.nodeType(node)

        # Special handling for heightField
        if node_type == "heightField":
            input_connections = cmds.listConnections(node, c=True, s=True, shapes=True) or []
            if input_connections:
                return False

        # Special handling for imagePlane
        if node_type == "imagePlane":
            try:
                locked_to_camera = cmds.getAttr(node + ".lockedToCamera")
                if not locked_to_camera:  # Free image planes are not subject to deletion
                    return False
            except Exception:
                pass

        # Check output connections
        connections = cmds.listConnections(node, c=True, s=False, shapes=True) or []

        if not connections:
            return True

        # Process connections in pairs
        for i in range(0, len(connections), 2):
            plug = connections[i]
            dest = connections[i + 1]

            # If there is a connection other than the message attribute, it is in use
            if not plug.endswith(".message"):
                return False

            # If the destination node type is among specific types, it is in use
            dest_type = cmds.nodeType(dest)

            # Node types considered as used
            used_types = ["shadingEngine", "imagePlane", "arrayMapper", "directionalLight", "spotLight", "pointLight", "areaLight", "transform"]

            if dest_type in used_types:
                return False

            # Also check for connections to cameras
            if cmds.objectType(dest, isa="camera"):
                return False

            # Also check for connections to shaders
            try:
                if (
                    cmds.isClassified(dest, "shader/surface")
                    or cmds.isClassified(dest, "shader/volume")
                    or cmds.isClassified(dest, "shader/displacement")
                ):
                    return False
            except Exception:
                pass

        return True

    except Exception:
        pass

    return False


def _get_non_used_pair_blend() -> list[str]:
    """Get all pairBlend nodes in the scene.

    Notes:
        - If there are no input connections, the node is considered unused.
        - If there are no inputs and the node is connected to a blendWeighted node, and that blendWeighted node is not connected to any other nodes, it is considered unused.

    Returns:
        list[str]: List of unused pairBlend nodes.
    """
    pair_blend_nodes = cmds.ls(type="pairBlend", long=True) or []
    if not pair_blend_nodes:
        return []

    non_used_pair_blends = []
    for pb in pair_blend_nodes:
        if not cmds.objExists(pb):
            continue

        inputs = cmds.listConnections(pb, s=True, d=False) or []
        if not inputs:
            non_used_pair_blends.append(pb)
            continue

        is_non_used = True
        for input_node in inputs:
            input_inputs = cmds.listConnections(input_node, s=True, d=False) or []
            if cmds.nodeType(input_node) != "blendWeighted":
                is_non_used = False
                continue

            if len(input_inputs) > 1:
                is_non_used = False

        if is_non_used:
            non_used_pair_blends.append(pb)

    return non_used_pair_blends


def _unused_groupId_nodes() -> list[str]:
    """Get all groupId nodes in the scene.

    Notes:
        - If there are no input or output connections, the node is considered unused.

    Returns:
        list[str]: List of unused groupId nodes.
    """
    group_id_nodes = cmds.ls(type="groupId", long=True) or []
    if not group_id_nodes:
        return []

    non_used_group_ids = []
    for gid in group_id_nodes:
        if not cmds.objExists(gid):
            continue

        if not cmds.listConnections(gid, s=True, d=True):
            non_used_group_ids.append(gid)

    return non_used_group_ids


def find_unused_nodes() -> list[str]:
    """Detect all unused nodes and return them as a list.

    Returns:
        list[str]: List of unused nodes.
    """
    unused_nodes = []

    # 1. Detect unused shading groups
    all_sets = cmds.ls(sets=True) or []
    for sg in all_sets:
        if _is_shading_group_unused(sg):
            unused_nodes.append(sg)

    # 2. Detect unused materials)
    all_materials = cmds.ls(materials=True, long=True) or []
    for mat in all_materials:
        if _is_material_unused(mat):
            unused_nodes.append(mat)

    # 3. Detect unused texture/utility nodes
    render_nodes = _get_render_nodes()

    # Exclude materials already checked
    nodes_to_check = [n for n in render_nodes if n not in all_materials]

    # Iteratively check (considering dependencies)
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        found_unused = False

        remaining_nodes = []
        for node in nodes_to_check:
            if cmds.objExists(node):
                if _is_texture_utility_unused(node):
                    unused_nodes.append(node)
                    found_unused = True
                else:
                    remaining_nodes.append(node)

        nodes_to_check = remaining_nodes

        # If no new unused nodes are found, exit
        if not found_unused:
            break

    # 4. Other unused nodes (e.g., pairBlend, groupId)
    non_used_pair_blends = _get_non_used_pair_blend() or []
    unused_nodes.extend(non_used_pair_blends)

    non_used_group_ids = _unused_groupId_nodes() or []
    unused_nodes.extend(non_used_group_ids)

    return unused_nodes
