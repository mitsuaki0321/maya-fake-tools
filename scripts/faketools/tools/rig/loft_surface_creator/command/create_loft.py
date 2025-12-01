"""CreateLoftSurface class for creating lofted surfaces from joint chains."""

from logging import getLogger
from typing import Optional

import maya.cmds as cmds

from .....lib import lib_nurbsCurve
from .constants import (
    CURVE_DEGREE_CUBIC,
    CURVE_DEGREE_LINEAR,
    MIN_POSITIONS_FOR_CUBIC_CURVE,
    MIN_POSITIONS_FOR_CURVE,
    OUTPUT_MESH,
    OUTPUT_NURBS_SURFACE,
    VALID_CURVE_DEGREES,
    VALID_OUTPUT_TYPES,
    VALID_WEIGHT_METHODS,
    WEIGHT_METHOD_LINEAR,
)
from .helpers import get_joint_chains_from_roots, validate_root_joints
from .weight_setting import LoftWeightSetting

logger = getLogger(__name__)


class CreateLoftSurface:
    """Create lofted surface from multiple joint chains.

    This class creates curves from joint chains and lofts them into a surface or mesh.
    Used for creating weight transfer sources for skirts, belts, etc.
    """

    def __init__(self, root_joints: list[str]):
        """Initialize the CreateLoftSurface class.

        Args:
            root_joints (list[str]): List of root joint names. At least 2 required.

        Raises:
            ValueError: If root_joints is invalid.
        """
        validate_root_joints(root_joints)
        self.root_joints = root_joints
        self.joint_chains: list[list[str]] = []

    def execute(
        self,
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

        Args:
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
        """
        # Validate parameters
        if output_type not in VALID_OUTPUT_TYPES:
            raise ValueError(f"Invalid output type '{output_type}'. Valid options are: {VALID_OUTPUT_TYPES}")

        if degree not in VALID_CURVE_DEGREES:
            raise ValueError(f"Invalid degree ({degree}). Valid options are: {VALID_CURVE_DEGREES}")

        if surface_divisions < 1:
            raise ValueError(f"Invalid surface divisions ({surface_divisions}). Must be >= 1.")

        if is_bind and weight_method not in VALID_WEIGHT_METHODS:
            raise ValueError(f"Invalid weight method '{weight_method}'. Valid options are: {VALID_WEIGHT_METHODS}")

        # Get joint chains from root joints
        self.joint_chains = get_joint_chains_from_roots(self.root_joints, skip)

        # Create curves from joint chains
        curves = self._create_curves_from_chains(
            degree=degree,
            center=center,
            curve_divisions=curve_divisions,
        )

        # Loft curves into surface
        result = self._loft_curves(
            curves=curves,
            close=close,
            output_type=output_type,
            surface_divisions=surface_divisions,
            degree=degree,
        )

        logger.info(f"Created lofted surface: {result}")

        # Apply skin weights if requested
        skin_cluster = None
        if is_bind:
            weight_setter = LoftWeightSetting(
                geometry=result,
                joint_chains=self.joint_chains,
                num_chains=len(self.root_joints),
                surface_divisions=surface_divisions,
                is_closed=close,
            )
            skin_cluster = weight_setter.execute(
                method=weight_method,
                smooth_iterations=smooth_iterations,
                parent_influence_ratio=parent_influence_ratio,
                remove_end=remove_end,
            )

        return result, skin_cluster

    def _create_curves_from_chains(
        self,
        degree: int = CURVE_DEGREE_CUBIC,
        center: bool = False,
        curve_divisions: int = 0,
    ) -> list[str]:
        """Create curves from each joint chain.

        Args:
            degree (int): Degree of the curves.
            center (bool): Whether to center cubic curves.
            curve_divisions (int): Number of CVs to insert between joint positions.

        Returns:
            list[str]: List of created curve transform names.
        """
        curves = []

        for chain in self.joint_chains:
            # Get world positions of joints
            positions = [cmds.xform(joint, q=True, ws=True, t=True) for joint in chain]

            # Create curve from positions
            curve = self._create_curve(
                positions=positions,
                degree=degree,
                center=center,
                divisions=curve_divisions,
            )
            curves.append(curve)

        logger.debug(f"Created {len(curves)} curves from joint chains")
        return curves

    def _create_curve(
        self,
        positions: list[list[float]],
        degree: int = CURVE_DEGREE_CUBIC,
        center: bool = False,
        divisions: int = 0,
    ) -> str:
        """Create curve from positions.

        This method is adapted from curveSurface_creator's _create_curve().

        Args:
            positions (list[list[float]]): Target positions (list of [x, y, z] coordinates).
            degree (int): Degree of the curve (1 or 3).
            center (bool): Whether to center cubic curves.
            divisions (int): Number of CVs to insert between given positions.

        Returns:
            str: Created curve transform name.

        Raises:
            ValueError: If parameters are invalid.
        """
        if degree not in VALID_CURVE_DEGREES:
            raise ValueError(f"Invalid degree ({degree}). Valid options are: {VALID_CURVE_DEGREES}")

        num_positions = len(positions)
        if num_positions < MIN_POSITIONS_FOR_CURVE:
            raise ValueError(f"At least {MIN_POSITIONS_FOR_CURVE} positions are required.")

        # Handle special case: 2 positions
        if num_positions == MIN_POSITIONS_FOR_CURVE:
            if degree == CURVE_DEGREE_CUBIC:
                logger.warning("Degree 3 curve requires at least 3 positions. Creating degree 1 curve instead.")

            curve = cmds.curve(d=CURVE_DEGREE_LINEAR, p=positions)
            if divisions:
                curve_shape = cmds.listRelatives(curve, s=True, f=True)[0]
                lib_nurbsCurve.ConvertNurbsCurve(curve_shape).insert_cvs(divisions)

            logger.debug(f"Created curve: {curve}")
            return curve

        # Handle special case: 3 positions with cubic degree
        if num_positions == MIN_POSITIONS_FOR_CUBIC_CURVE:
            curve = cmds.curve(d=CURVE_DEGREE_LINEAR, p=positions)
            if degree == CURVE_DEGREE_CUBIC:
                curve = cmds.rebuildCurve(curve, ch=False, d=CURVE_DEGREE_CUBIC, s=0)[0]
        else:
            # Normal case: 4+ positions
            curve = cmds.curve(d=degree, p=positions)

        # Apply curve modifications if needed
        if center or divisions:
            curve_shape = cmds.listRelatives(curve, s=True, f=True)[0]
            convert_nurbs_curve = lib_nurbsCurve.ConvertNurbsCurve(curve_shape)

            if center and degree == CURVE_DEGREE_CUBIC:
                convert_nurbs_curve.center_curve()

            if divisions:
                convert_nurbs_curve.insert_cvs(divisions)

        logger.debug(f"Created curve: {curve}")
        return curve

    def _loft_curves(
        self,
        curves: list[str],
        close: bool,
        output_type: str,
        surface_divisions: int,
        degree: int,
    ) -> str:
        """Loft multiple curves into a surface or mesh.

        Args:
            curves (list[str]): List of curve names to loft.
            close (bool): Whether to close the loft loop.
            output_type (str): Type of output ('nurbsSurface' or 'mesh').
            surface_divisions (int): Number of divisions between curves.
            degree (int): Degree of the loft (1=linear, 3=cubic).

        Returns:
            str: Created surface or mesh transform name.
        """
        if len(curves) < 2:
            raise ValueError("At least 2 curves are required for lofting.")

        # Determine loft degree based on curve degree
        loft_degree = degree if output_type == OUTPUT_NURBS_SURFACE else CURVE_DEGREE_LINEAR

        if output_type == OUTPUT_NURBS_SURFACE:
            # NURBS Surface: no construction history needed
            # rsn=True to reverse surface normals (face outward)
            result = cmds.loft(
                curves,
                ch=False,
                u=True,
                c=close,
                ar=True,
                d=loft_degree,
                ss=surface_divisions,
                rn=False,
                po=0,
                rsn=True,
            )[0]
        else:
            # Mesh: need construction history to configure nurbsTessellate node
            # rsn=False for mesh (normals face outward without reversal)
            result, loft_node = cmds.loft(
                curves,
                ch=True,
                u=True,
                c=close,
                ar=True,
                d=loft_degree,
                ss=surface_divisions,
                rn=False,
                po=1,
                rsn=False,
            )

            # Find and configure the nurbsTessellate node
            # Node graph: loft -> nurbsTessellate -> mesh
            tessellate_nodes = cmds.listConnections(loft_node, type="nurbsTessellate")
            if tessellate_nodes:
                tessellate_node = tessellate_nodes[0]
                # format=3: tessellate at CV positions
                # polygonType=1: quads
                cmds.setAttr(f"{tessellate_node}.format", 3)
                cmds.setAttr(f"{tessellate_node}.polygonType", 1)

            # Delete construction history
            cmds.delete(result, ch=True)

        # Delete temporary curves
        cmds.delete(curves)

        logger.debug(f"Created lofted {'mesh' if output_type == OUTPUT_MESH else 'surface'}: {result}")
        return result


__all__ = ["CreateLoftSurface"]
