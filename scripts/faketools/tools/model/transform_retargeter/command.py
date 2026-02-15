"""Retarget transform positions command."""

from __future__ import annotations

import logging
import os
import pickle

import maya.cmds as cmds

from ....lib import lib_retarget
from .hierarchy import TransformHierarchy
from .position_methods import DefaultPosition, MeshBaryPosition, MeshRBFPosition

logger = logging.getLogger(__name__)


def export_transform_position(output_directory: str, file_name: str, method: str = "barycentric", **kwargs) -> None:
    """Export the transform positions to a file for GUI.

    Notes:
        - Exports the positions and rotations of the selected nodes.
        - The names of the selected nodes must be unique within the selection.

    Args:
        output_directory (str): The output file directory.
        file_name (str): The output file name.
        method (str): The method to use for exporting the positions. Default is 'barycentric'.
                      Options are 'default', 'barycentric', 'rbf'.

    Keyword Args:
        rbf_radius (float): The RBF radius multiplier. Default is 1.5.

    Raises:
        ValueError: If output parameters are invalid, no nodes selected, or invalid method.
    """
    # Validate output file path
    if not output_directory:
        raise ValueError("Output file directory not provided.")

    if not file_name:
        raise ValueError("Output file name not provided.")

    if not os.path.exists(output_directory):
        raise ValueError(f"Output file directory not found: {output_directory}")

    output_file_path = os.path.join(output_directory, f"{file_name}.pkl")

    # Validate selection
    sel_nodes = cmds.ls(sl=True)

    if not sel_nodes:
        raise ValueError("No nodes selected.")

    if method not in ["default", "barycentric", "rbf"]:
        raise ValueError("Please specify a valid method. Options are: default, barycentric, rbf")

    if method == "default":
        not_transform_nodes = [node for node in sel_nodes if "transform" not in cmds.nodeType(node, inherited=True)]
        if not_transform_nodes:
            raise ValueError(f"Selected nodes are not transform nodes: {not_transform_nodes}")
        transforms = sel_nodes
    else:
        if len(sel_nodes) < 2:
            raise ValueError("Please select at least two nodes. One mesh and one or more transform nodes.")

        not_transform_nodes = [node for node in sel_nodes if "transform" not in cmds.nodeType(node, inherited=True)]
        if not_transform_nodes:
            raise ValueError(f"Selected nodes are not transform nodes: {not_transform_nodes}")

        target_mesh_transform = sel_nodes[0]
        transforms = sel_nodes[1:]

        target_mesh = cmds.listRelatives(target_mesh_transform, s=True, ni=True, type="mesh")
        if not target_mesh:
            raise ValueError(f"No mesh found in the first selected node: {target_mesh_transform}")

        target_mesh = target_mesh[0]

    # Check unique names in the selection
    local_names = [transform.split("|")[-1] for transform in transforms]
    not_unique_names = [name for name in local_names if local_names.count(name) > 1]
    if not_unique_names:
        raise ValueError(f"Selected nodes have non-unique names in selection: {not_unique_names}")

    # Get the positions and rotations
    positions = [cmds.xform(transform, q=True, ws=True, t=True) for transform in transforms]
    rotations = [cmds.xform(transform, q=True, ws=True, ro=True) for transform in transforms]

    if method == "default":
        method_instance = DefaultPosition()
        position_data = method_instance.export_data(positions, rotations=rotations)
    else:
        if method == "barycentric":
            method_instance = MeshBaryPosition(target_mesh)
            position_data = method_instance.export_data(positions, rotations=rotations)
        elif method == "rbf":
            rbf_radius = kwargs.get("rbf_radius", 1.5)
            logger.info(f"Using RBF with radius: {rbf_radius}")
            method_instance = MeshRBFPosition(target_mesh)
            index_query_method = lib_retarget.NearestRadiusIndexQuery(radius_multiplier=rbf_radius)
            position_data = method_instance.export_data(positions, rotations=rotations, method_instance=index_query_method)

    # Get the hierarchy data
    transform_hierarchy = TransformHierarchy()
    for transform in transforms:
        transform_hierarchy.register_node(transform)

    export_data = {
        "method": method,
        "transforms": local_names,
        "position_data": position_data,
        "hierarchy_data": transform_hierarchy.get_hierarchy_data(),
    }

    # Write the data to a file
    with open(output_file_path, "wb") as f:
        pickle.dump(export_data, f)

    logger.debug(f"Exported transform positions: {output_file_path}")


def load_transform_position_data(input_file_path: str) -> dict:
    """Get the transform position data from a file.

    Args:
        input_file_path (str): The input file path.

    Returns:
        dict: The transform position data.

    Raises:
        ValueError: If input file is invalid or missing required data.
    """
    # Validate input file path
    if not input_file_path:
        raise ValueError("Input file path not provided.")

    if not os.path.exists(input_file_path):
        raise ValueError(f"Input file path not found: {input_file_path}")

    # Read the data
    with open(input_file_path, "rb") as f:
        input_data = pickle.load(f)

    # Validate input data
    if "method" not in input_data:
        raise ValueError("Invalid input data. Missing method.")

    if "transforms" not in input_data:
        raise ValueError("Invalid input data. Missing transforms.")

    if "position_data" not in input_data:
        raise ValueError("Invalid input data. Missing position data.")

    return input_data


def _create_transform_node(name: str, object_type: str = "transform", size: float = 1.0) -> str:
    """Create a new transform node.

    Args:
        name (str): The transform name.
        object_type (str): The creation object type. Default is 'transform'.
                          Options are 'transform', 'locator', 'joint'.
        size (float): The creation node size. Default is 1.0.

    Returns:
        str: The new transform node name.

    Raises:
        ValueError: If invalid creation node type.
    """
    if object_type == "transform":
        new_transform = cmds.createNode("transform", name=name, ss=True)
    elif object_type == "locator":
        new_transform = cmds.spaceLocator(name=name)[0]
        cmds.setAttr(f"{new_transform}.localScale", size, size, size)
    elif object_type == "joint":
        new_transform = cmds.createNode("joint", name=name, ss=True)
        cmds.setAttr(f"{new_transform}.radius", size)
    else:
        raise ValueError(f"Invalid creation node type: {object_type}")

    return new_transform


def import_transform_position(input_file_path: str, create_new: bool = False, is_rotation: bool = True, **kwargs) -> list[str]:
    """Import the transform positions from a file.

    Notes:
        - If the create_new flag is True, a new transform node is created and the data is set to that node.
        - If the create_new flag is False, the data is set to the selected node. The selected node must have a unique name in the scene.

    Args:
        input_file_path (str): The input file path.
        create_new (bool): Create new transform nodes. Default is False.
        is_rotation (bool): Import rotations. Default is True.

    Keyword Args:
        restore_hierarchy (bool): Restore the hierarchy only if create_new is True. Default is False.
        creation_object_type (str): The creation object type. Default is 'transform'.
                                    Options are 'transform', 'locator', 'joint'.
        creation_object_size (float): The creation object size. Default is 1.0.

    Returns:
        list[str]: The new transform nodes if create_new is True. Otherwise, the updated transform nodes.

    Raises:
        ValueError: If input data is invalid, missing nodes, or nodes are not unique.
    """
    restore_hierarchy = kwargs.get("restore_hierarchy", False)
    creation_object_type = kwargs.get("creation_object_type", "transform")  # 'transform', 'locator', 'joint'
    creation_object_size = kwargs.get("creation_object_size", 1.0)

    # Read the data
    input_data = load_transform_position_data(input_file_path)

    method = input_data["method"]
    target_transforms = input_data["transforms"]
    position_data = input_data["position_data"]
    hierarchy_data = input_data["hierarchy_data"]

    # Get the target mesh
    if method in ["barycentric", "rbf"]:
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            raise ValueError("No mesh transform selected.")

        target_mesh_transform = sel_nodes[0]
        target_mesh = cmds.listRelatives(target_mesh_transform, s=True, ni=True, type="mesh")
        if not target_mesh:
            raise ValueError(f"No mesh transform selected.: {target_mesh_transform}")

        target_mesh = target_mesh[0]

    # Check the target transforms
    if not create_new:
        not_exists_nodes = [node for node in target_transforms if not cmds.objExists(node)]
        if not_exists_nodes:
            raise ValueError(f"Target transform node do not exist: {not_exists_nodes}")

        not_transform_nodes = [node for node in target_transforms if "transform" not in cmds.nodeType(node, inherited=True)]
        if not_transform_nodes:
            raise ValueError(f"Target transforms are not transform nodes: {not_transform_nodes}")

        not_unique_nodes = [transform for transform in target_transforms if len(cmds.ls(transform)) > 1]
        if not_unique_nodes:
            raise ValueError(f"Target transform nodes are not unique: {not_unique_nodes}")

    # Get the positions and rotations
    if method == "default":
        method_instance = DefaultPosition()
        result_positions, result_rotations = method_instance.import_data(position_data)
    else:
        if method == "barycentric":
            method_instance = MeshBaryPosition(target_mesh)
        elif method == "rbf":
            method_instance = MeshRBFPosition(target_mesh)

        result_positions, result_rotations = method_instance.import_data(position_data)

    # Set the data to the transforms
    if create_new:
        new_transforms = []
        for i, transform in enumerate(target_transforms):
            new_transform = _create_transform_node(f"{transform}_position#", creation_object_type, creation_object_size)
            cmds.xform(new_transform, ws=True, t=result_positions[i])
            if is_rotation:
                cmds.xform(new_transform, ws=True, ro=result_rotations[i])
            new_transforms.append(new_transform)

        logger.debug(f"Created new transform nodes: {new_transforms}")

        if restore_hierarchy:
            transform_hierarchy = TransformHierarchy.set_hierarchy_data(hierarchy_data)
            for target_transform, new_transform in zip(target_transforms, new_transforms):
                register_parent = transform_hierarchy.get_registered_parent(target_transform)
                if not register_parent:
                    continue

                parent_transform = new_transforms[target_transforms.index(register_parent)]
                cmds.parent(new_transform, parent_transform)
                logger.info(f"Parenting {new_transform} to {parent_transform}")

            logger.debug(f"Restored transform hierarchy: {new_transforms}")

        return new_transforms
    else:
        depth_dict = {}
        for transform in target_transforms:
            depth = len(cmds.ls(transform, long=True)[0].split("|")) - 1
            depth_dict[transform] = depth
        reorder_transforms = sorted(target_transforms, key=lambda x: depth_dict[x])

        for transform in reorder_transforms:
            index = target_transforms.index(transform)
            cmds.xform(transform, ws=True, t=result_positions[index])
            if is_rotation:
                cmds.xform(transform, ws=True, ro=result_rotations[index])

        logger.debug(f"Set transform positions: {reorder_transforms}")

        return reorder_transforms


__all__ = ["export_transform_position", "load_transform_position_data", "import_transform_position"]
