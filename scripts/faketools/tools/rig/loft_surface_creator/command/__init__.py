"""Command layer for loft surface creation."""

from typing import Optional

from .constants import (
    CURVE_DEGREE_CUBIC,
    CURVE_DEGREE_LINEAR,
    OUTPUT_MESH,
    OUTPUT_NURBS_SURFACE,
    VALID_CURVE_DEGREES,
    VALID_OUTPUT_TYPES,
    VALID_WEIGHT_METHODS,
    WEIGHT_METHOD_EASE,
    WEIGHT_METHOD_LINEAR,
    WEIGHT_METHOD_STEP,
)
from .create_loft import CreateLoftSurface
from .helpers import get_joint_chain_from_root, get_joint_chains_from_roots, validate_root_joints
from .weight_setting import LoftWeightSetting


def main(
    root_joints: list[str],
    close: bool = False,
    output_type: str = OUTPUT_NURBS_SURFACE,
    surface_divisions: int = 1,
    degree: int = CURVE_DEGREE_CUBIC,
    center: bool = False,
    curve_divisions: int = 0,
    skip: int = 0,
    is_bind: bool = False,
    weight_method: str = WEIGHT_METHOD_LINEAR,
    smooth_iterations: int = 0,
    parent_influence_ratio: float = 0.0,
    remove_end: bool = False,
) -> tuple[str, Optional[str]]:
    """Create lofted surface from joint chains.

    This is the main entry point for loft surface creation.

    Args:
        root_joints (list[str]): List of root joint names. At least 2 required.
        close (bool): Whether to close the loft loop (connect last chain to first).
        output_type (str): Type of output geometry. One of: 'nurbsSurface', 'mesh'.
        surface_divisions (int): Number of divisions between curves in loft direction.
        degree (int): Degree of the curves (1=linear, 3=cubic).
        center (bool): Whether to center cubic curves.
        curve_divisions (int): Number of CVs to insert between joint positions.
        skip (int): Number of joints to skip in each chain.
        is_bind (bool): Whether to create skin cluster and apply weights.
        weight_method (str): Weight calculation method. One of: 'linear', 'ease', 'step'.
        smooth_iterations (int): Number of weight smoothing iterations.
        parent_influence_ratio (float): Ratio of influence from parent joint (0.0 to 1.0).
        remove_end (bool): For open chains, merge end joint weights to parent.

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
        ...     surface_divisions=3,
        ...     curve_divisions=2,
        ... )
    """
    creator = CreateLoftSurface(root_joints)
    return creator.execute(
        close=close,
        output_type=output_type,
        surface_divisions=surface_divisions,
        degree=degree,
        center=center,
        curve_divisions=curve_divisions,
        skip=skip,
        is_bind=is_bind,
        weight_method=weight_method,
        smooth_iterations=smooth_iterations,
        parent_influence_ratio=parent_influence_ratio,
        remove_end=remove_end,
    )


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
    # Constants - Curve degrees
    "CURVE_DEGREE_LINEAR",
    "CURVE_DEGREE_CUBIC",
    "VALID_CURVE_DEGREES",
    # Constants - Output types
    "OUTPUT_NURBS_SURFACE",
    "OUTPUT_MESH",
    "VALID_OUTPUT_TYPES",
    # Constants - Weight methods
    "WEIGHT_METHOD_LINEAR",
    "WEIGHT_METHOD_EASE",
    "WEIGHT_METHOD_STEP",
    "VALID_WEIGHT_METHODS",
]
