"""Command layer for curve surface creation.

This module provides the main API for creating curve surfaces from nodes.
"""

from logging import getLogger
from typing import Optional

import maya.cmds as cmds

from .....lib import lib_math, lib_nurbsCurve, lib_nurbsSurface, lib_selection, lib_skinCluster
from .....operations import convert_weight
from .constants import OBJECT_TYPE_CURVE, OBJECT_TYPE_MESH, OBJECT_TYPE_SURFACE
from .create_curve_surface import CreateCurveSurface
from .curve_weight_setting import CurveWeightSetting
from .helpers import create_curve_from_vertices, create_curve_on_surface, move_cv_positions, validate_geometry

logger = getLogger(__name__)


def main(
    select_type: str = "selected",
    object_type: str = "nurbsCurve",
    is_bind: bool = False,
    to_skin_cage: bool = False,
    skin_cage_division_levels: int = 1,
    select_options: Optional[dict] = None,
    create_options: Optional[dict] = None,
    bind_options: Optional[dict] = None,
) -> list[str]:
    """Create and bind curve surface.

    Args:
        select_type (str): If "selected", get the selected nodes. If "hierarchy", get the hierarchy of the selected nodes.
        object_type (str): Type of object to create. 'nurbsCurve' or 'mesh' or 'nurbsSurface'.
        is_bind (bool): Whether to bind the created geometry.
        to_skin_cage (bool): Whether to bind to the skin cage. Only nurbsSurface is supported.
        skin_cage_division_levels (int): Number of division levels for the skin cage.
        select_options (dict | None): Options for selecting nodes.
        create_options (dict | None): Options for creating curve surface.
        bind_options (dict | None): Options for binding curve surface.

    Returns:
        list[str]: Created surface or curves.
    """
    if select_options is None:
        select_options = {}
    if create_options is None:
        create_options = {}
    if bind_options is None:
        bind_options = {}

    sel_nodes = _get_selected_nodes(select_type, **select_options)

    result_objs = []
    for nodes in sel_nodes:
        create_curve_surface = CreateCurveSurface(nodes)
        obj = create_curve_surface.execute(object_type=object_type, **create_options)

        if not is_bind:
            result_objs.append(obj)
            continue

        if object_type == OBJECT_TYPE_CURVE:
            _bind_curve_surface(nodes, obj)
            CurveWeightSetting(obj).execute(**bind_options)
            result_objs.append(obj)
        else:
            bind_curve = create_curve_surface.execute(object_type=OBJECT_TYPE_CURVE, **create_options)
            _bind_curve_surface(nodes, bind_curve)
            CurveWeightSetting(bind_curve).execute(**bind_options)

            # Get influences from bind_curve after weight setting (may have removed end influence)
            bind_curve_shape = validate_geometry(bind_curve, [OBJECT_TYPE_CURVE])
            bind_curve_skin = lib_skinCluster.get_skinCluster(bind_curve_shape)
            bind_curve_infs = set(cmds.skinCluster(bind_curve_skin, q=True, inf=True))

            _bind_curve_surface(nodes, obj)
            _transfer_curve_weights(bind_curve, obj)

            # Remove influences from obj that are not in bind_curve (e.g., removed end influence)
            obj_shape = validate_geometry(obj, [OBJECT_TYPE_SURFACE, OBJECT_TYPE_MESH])
            obj_skin_cluster = lib_skinCluster.get_skinCluster(obj_shape)
            obj_infs = cmds.skinCluster(obj_skin_cluster, q=True, inf=True)
            for inf in obj_infs:
                if inf not in bind_curve_infs:
                    cmds.skinCluster(obj_skin_cluster, e=True, removeInfluence=inf)
                    logger.debug(f"Removed influence from {obj}: {inf}")

            cmds.delete(bind_curve)

            if object_type == OBJECT_TYPE_SURFACE and to_skin_cage:
                skin_cage = _to_skin_cage_from_length(obj, skin_cage_division_levels)
                cmds.delete(obj)

                result_objs.append(skin_cage)
            else:
                result_objs.append(obj)

    return result_objs


def _get_selected_nodes(select_type: str, *, skip: int = 0, reverse: bool = False) -> list[list[str]]:
    """Get selected nodes or hierarchy nodes.

    Args:
        select_type (str): If "selected", get the selected nodes. If "hierarchy", get the hierarchy of the selected nodes.
        skip (int): Value to skip selected nodes.
        reverse (bool): Whether to get the selected nodes in reverse order.

    Returns:
        list[list[str]]: Selected nodes.

    Raises:
        ValueError: If no transform nodes are selected, hierarchies are overlapping, or skip value is invalid.
    """
    sel_nodes = cmds.ls(sl=True, type="transform", l=True)
    if not sel_nodes:
        raise ValueError("No transform nodes selected. Please select at least one transform node.")

    node_list = []
    if select_type == "selected":
        node_list = [sel_nodes]
    elif select_type == "hierarchy":
        # Check for overlapping hierarchies
        overlapping = []
        for i, node_i in enumerate(sel_nodes):
            for j, node_j in enumerate(sel_nodes):
                if i != j and node_i.startswith(node_j):
                    overlapping.append(node_i)
                    break

        if overlapping:
            overlapping_short = cmds.ls(overlapping)
            raise ValueError(f"Invalid hierarchy. Hierarchies are overlapping: {overlapping_short}")

        for node in sel_nodes:
            node_list.append(lib_selection.get_hierarchy([node], include_shape=False))

    if reverse:
        node_list = [list(reversed(nodes)) for nodes in node_list]

    if skip:
        skip_step = skip + 1
        if not all(skip_step < len(nodes) for nodes in node_list):
            raise ValueError(f"Invalid skip value ({skip}). Skip value is too large for the selected nodes.")

        for i in range(len(node_list)):
            skip_nodes = node_list[i][::skip_step]
            # Add the last node if not already included
            if len(node_list[i]) % skip_step != 0:
                skip_nodes.append(node_list[i][-1])

            node_list[i] = skip_nodes

    logger.debug(f"Selected nodes: {node_list}")

    return node_list


def _bind_curve_surface(infs: list[str], obj: str) -> str:
    """Bind the influence nodes to the curve or surface or mesh.

    Args:
        infs (list[str]): Influence nodes.
        obj (str): Bind target geometry.

    Returns:
        str: SkinCluster node name.

    Raises:
        ValueError: If influences or geometry are invalid or not found.
    """
    if not infs:
        raise ValueError("No influences specified. Please provide at least one influence.")

    if not obj:
        raise ValueError("No geometry specified. Please provide a geometry to bind.")

    # Validate influences exist
    missing_infs = [inf for inf in infs if not cmds.objExists(inf)]
    if missing_infs:
        raise ValueError(f"Influences not found: {missing_infs}")

    # Validate influences are joints
    invalid_infs = [inf for inf in infs if cmds.nodeType(inf) != "joint"]
    if invalid_infs:
        raise ValueError(f"Invalid influence type (must be joints): {invalid_infs}")

    # Validate and get geometry shape
    shape = validate_geometry(obj, [OBJECT_TYPE_CURVE, OBJECT_TYPE_MESH, OBJECT_TYPE_SURFACE])

    # Create skinCluster
    skin_cluster = cmds.skinCluster(infs, shape, tsb=True)[0]

    logger.debug(f"Created skinCluster: {infs} -> {obj}")

    return skin_cluster


def _transfer_curve_weights(curve: str, surface: str) -> None:
    """Transfer curve weights to the lofted surface or mesh.

    Args:
        curve (str): Curve transform name.
        surface (str): Target surface transform name.

    Raises:
        ValueError: If curve or surface are invalid or don't have skinClusters.
    """
    if not curve:
        raise ValueError("No curve specified.")

    if not surface:
        raise ValueError("No target surface specified.")

    # Validate curve and get shape
    curve_shape = validate_geometry(curve, [OBJECT_TYPE_CURVE])

    # Get curve skinCluster
    curve_skin_cluster = lib_skinCluster.get_skinCluster(curve_shape)
    if not curve_skin_cluster:
        raise ValueError(f"No skinCluster found on curve: {curve}")

    # Validate surface and get shape
    surface_shape = validate_geometry(surface, [OBJECT_TYPE_SURFACE, OBJECT_TYPE_MESH])

    # Get surface skinCluster
    surface_skin_cluster = lib_skinCluster.get_skinCluster(surface_shape)
    if not surface_skin_cluster:
        raise ValueError(f"No skinCluster found on surface: {surface}")

    # Get weights and influences from curve
    surface_type = cmds.nodeType(surface_shape)
    weights = lib_skinCluster.get_skin_weights(curve_skin_cluster, all_components=True)
    infs = cmds.skinCluster(curve_skin_cluster, q=True, inf=True)
    num_cvs = len(weights)

    # Transfer weights to surface
    for i, weight in enumerate(weights):
        if surface_type == OBJECT_TYPE_SURFACE:
            # NurbsSurface has two rows of CVs (U direction)
            cmds.skinPercent(surface_skin_cluster, f"{surface}.cv[0][{i}]", transformValue=list(zip(infs, weight)))
            cmds.skinPercent(surface_skin_cluster, f"{surface}.cv[1][{i}]", transformValue=list(zip(infs, weight)))
        elif surface_type == OBJECT_TYPE_MESH:
            # Mesh has vertices on both edges
            cmds.skinPercent(surface_skin_cluster, f"{surface}.vtx[{i}]", transformValue=list(zip(infs, weight)))
            cmds.skinPercent(surface_skin_cluster, f"{surface}.vtx[{num_cvs + i}]", transformValue=list(zip(infs, weight)))

    logger.debug(f"Transfer weights: {curve} -> {surface}")


def _to_skin_cage_from_length(surface: str, division_levels: int = 1) -> str:
    """Convert the surface to skin cage.

    Args:
        surface (str): Surface transform name.
        division_levels (int): Number of division levels.

    Returns:
        str: Skin cage name.

    Raises:
        ValueError: If surface is invalid or doesn't have a skinCluster, or division_levels is invalid.
    """
    if not surface:
        raise ValueError("No surface specified.")

    if division_levels < 1:
        raise ValueError(f"Invalid division levels ({division_levels}). Must be at least 1.")

    # Validate surface and get shape
    surface_shape = validate_geometry(surface, [OBJECT_TYPE_SURFACE])

    # Get skinCluster
    skin_cluster = lib_skinCluster.get_skinCluster(surface_shape)
    if not skin_cluster:
        raise ValueError(f"No skinCluster found on surface: {surface}")

    # Get surface parameters
    nurbs_surface = lib_nurbsSurface.NurbsSurface(surface_shape)
    u_range, v_range = nurbs_surface.get_uv_range()
    u_span, v_span = nurbs_surface.get_uv_spans()

    # Calculate center parameters
    u_center = (u_range[1] - u_range[0]) / 2.0
    v_center = (v_range[1] - v_range[0]) / 2.0

    # Create curves at center of surface
    u_curve = lib_nurbsSurface.create_curve_on_surface(f"{surface}.v[{v_center}]")
    v_curve = lib_nurbsSurface.create_curve_on_surface(f"{surface}.u[{u_center}]")

    # Get curve lengths
    u_curve_shape = cmds.listRelatives(u_curve, s=True, f=True, ni=True)[0]
    u_curve_length = lib_nurbsCurve.NurbsCurve(u_curve_shape).get_length()

    v_curve_shape = cmds.listRelatives(v_curve, s=True, f=True, ni=True)[0]
    v_curve_length = lib_nurbsCurve.NurbsCurve(v_curve_shape).get_length()

    # Calculate divisions based on curve length and spans
    u_divisions = int(lib_math.round_up(u_curve_length) / ((2 + u_span) / 4)) * division_levels
    v_divisions = int(lib_math.round_up(v_curve_length) / ((2 + v_span) / 4)) * division_levels

    # Convert to mesh
    skin_cage = convert_weight.SkinClusterToMesh(skin_cluster, u_divisions=u_divisions, v_divisions=v_divisions).convert()

    # Clean up temporary curves
    cmds.delete(u_curve, v_curve)

    logger.debug(f"Created skin cage: {skin_cage}")

    return skin_cage


# Public API exports
__all__ = [
    "main",
    "CreateCurveSurface",
    "CurveWeightSetting",
    "create_curve_from_vertices",
    "create_curve_on_surface",
    "move_cv_positions",
]
