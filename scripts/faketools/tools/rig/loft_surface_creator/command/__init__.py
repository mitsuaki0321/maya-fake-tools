"""Command layer for loft surface creation."""

from logging import getLogger
from typing import Optional

import maya.cmds as cmds

from .....lib import lib_math, lib_nurbsCurve, lib_nurbsSurface, lib_skinCluster
from .....operations import convert_weight
from .constants import (
    LOFT_WEIGHT_DISTANCE,
    LOFT_WEIGHT_INDEX,
    LOFT_WEIGHT_PROJECTION,
    OUTPUT_MESH,
    OUTPUT_NURBS_SURFACE,
    VALID_LOFT_WEIGHT_METHODS,
    VALID_OUTPUT_TYPES,
    VALID_WEIGHT_METHODS,
    WEIGHT_METHOD_EASE,
    WEIGHT_METHOD_LINEAR,
    WEIGHT_METHOD_STEP,
)
from .create_loft import CreateLoftSurface
from .helpers import get_joint_chain_from_root, get_joint_chains_from_roots, validate_root_joints
from .weight_setting import LoftWeightSetting

logger = getLogger(__name__)


def main(
    root_joints: list[str],
    close: bool = False,
    output_type: str = OUTPUT_NURBS_SURFACE,
    surface_divisions: int = 0,
    center: bool = False,
    curve_divisions: int = 0,
    skip: int = 0,
    is_bind: bool = False,
    weight_method: str = WEIGHT_METHOD_LINEAR,
    smooth_iterations: int = 0,
    parent_influence_ratio: float = 0.0,
    remove_end: bool = False,
    loft_weight_method: str = LOFT_WEIGHT_INDEX,
    to_skin_cage: bool = False,
    skin_cage_division_levels: int = 1,
) -> tuple[str, Optional[str]]:
    """Create lofted surface from joint chains.

    This is the main entry point for loft surface creation.
    Always uses degree 3 (cubic) curves.

    Args:
        root_joints (list[str]): List of root joint names. At least 2 required.
            For close=True, at least 3 required.
        close (bool): Whether to close the loft loop (connect last chain to first).
        output_type (str): Type of output geometry. One of: 'nurbsSurface', 'mesh'.
        surface_divisions (int): Number of additional divisions between curves in loft direction.
            0 means no additional divisions (default).
        center (bool): Whether to center cubic curves.
        curve_divisions (int): Number of CVs to insert between joint positions.
        skip (int): Number of joints to skip in each chain.
        is_bind (bool): Whether to create skin cluster and apply weights.
        weight_method (str): Weight calculation method. One of: 'linear', 'ease', 'step'.
        smooth_iterations (int): Number of weight smoothing iterations.
        parent_influence_ratio (float): Ratio of influence from parent joint (0.0 to 1.0).
        remove_end (bool): For open chains, merge end joint weights to parent.
        loft_weight_method (str): Loft direction weight distribution method.
            One of: 'index', 'distance', 'projection'.
        to_skin_cage (bool): Whether to convert to skin cage mesh. Only for nurbsSurface with is_bind=True.
        skin_cage_division_levels (int): Number of division levels for the skin cage.

    Returns:
        tuple[str, str | None]: (geometry_name, skin_cluster_name or None if not bound)

    Raises:
        ValueError: If parameters are invalid.

    Example:
        >>> # Basic usage with 2 joint chains
        >>> result, skin = main(["joint_A1", "joint_B1"])

        >>> # Create closed mesh with binding (for skirt)
        >>> result, skin = main(
        ...     ["joint_A1", "joint_B1", "joint_C1", "joint_D1"],
        ...     close=True,
        ...     output_type="mesh",
        ...     is_bind=True,
        ... )

        >>> # Create with more divisions
        >>> result, skin = main(
        ...     ["joint_A1", "joint_B1"],
        ...     surface_divisions=2,  # 2 additional divisions between curves
        ...     curve_divisions=2,    # 2 additional CVs between joints
        ... )

        >>> # Create skin cage from nurbsSurface
        >>> result, skin = main(
        ...     ["joint_A1", "joint_B1"],
        ...     output_type="nurbsSurface",
        ...     is_bind=True,
        ...     to_skin_cage=True,
        ...     skin_cage_division_levels=2,
        ... )
    """
    creator = CreateLoftSurface(root_joints)
    result, skin_cluster = creator.execute(
        close=close,
        output_type=output_type,
        surface_divisions=surface_divisions,
        center=center,
        curve_divisions=curve_divisions,
        skip=skip,
        is_bind=is_bind,
        weight_method=weight_method,
        smooth_iterations=smooth_iterations,
        parent_influence_ratio=parent_influence_ratio,
        remove_end=remove_end,
        loft_weight_method=loft_weight_method,
    )

    # Convert to skin cage if requested
    if to_skin_cage and is_bind and output_type == OUTPUT_NURBS_SURFACE:
        skin_cage, skin_cluster = _to_skin_cage_from_length(result, skin_cage_division_levels)
        cmds.delete(result)
        return skin_cage, skin_cluster

    return result, skin_cluster


def _to_skin_cage_from_length(surface: str, division_levels: int = 1) -> tuple[str, str]:
    """Convert the surface to skin cage.

    Args:
        surface (str): Surface transform name.
        division_levels (int): Number of division levels.

    Returns:
        tuple[str, str]: (skin_cage_name, skin_cluster_name)

    Raises:
        ValueError: If surface is invalid or doesn't have a skinCluster, or division_levels is invalid.
    """
    if not surface:
        raise ValueError("No surface specified.")

    if division_levels < 1:
        raise ValueError(f"Invalid division levels ({division_levels}). Must be at least 1.")

    # Get surface shape
    surface_shape = cmds.listRelatives(surface, s=True, f=True, ni=True)
    if not surface_shape:
        raise ValueError(f"No shape found on surface: {surface}")

    surface_shape = surface_shape[0]
    if cmds.nodeType(surface_shape) != "nurbsSurface":
        raise ValueError(f"Invalid geometry type. Expected nurbsSurface, got: {cmds.nodeType(surface_shape)}")

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
    converter = convert_weight.SkinClusterToMesh(skin_cluster, u_divisions=u_divisions, v_divisions=v_divisions)
    skin_cage = converter.convert()

    # Get skin cluster from skin cage
    skin_cage_shape = cmds.listRelatives(skin_cage, s=True, f=True, ni=True)[0]
    skin_cage_skin_cluster = lib_skinCluster.get_skinCluster(skin_cage_shape)

    # Clean up temporary curves
    cmds.delete(u_curve, v_curve)

    logger.debug(f"Created skin cage: {skin_cage}")

    return skin_cage, skin_cage_skin_cluster


__all__ = [
    # Main function
    "main",
    # Classes
    "CreateLoftSurface",
    "LoftWeightSetting",
    # Helper functions
    "validate_root_joints",
    "get_joint_chain_from_root",
    "get_joint_chains_from_roots",
    # Constants - Output types
    "OUTPUT_NURBS_SURFACE",
    "OUTPUT_MESH",
    "VALID_OUTPUT_TYPES",
    # Constants - Weight methods
    "WEIGHT_METHOD_LINEAR",
    "WEIGHT_METHOD_EASE",
    "WEIGHT_METHOD_STEP",
    "VALID_WEIGHT_METHODS",
    # Constants - Loft weight methods
    "LOFT_WEIGHT_INDEX",
    "LOFT_WEIGHT_DISTANCE",
    "LOFT_WEIGHT_PROJECTION",
    "VALID_LOFT_WEIGHT_METHODS",
]
