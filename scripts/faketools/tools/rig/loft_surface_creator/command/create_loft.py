"""CreateLoftSurface class for creating lofted surfaces from joint chains."""

from logging import getLogger
from typing import Optional

import maya.cmds as cmds

from .....lib import lib_nurbsCurve
from .constants import (
    CURVE_DEGREE,
    LOFT_WEIGHT_INDEX,
    MIN_CHAINS_FOR_CLOSE,
    MIN_POSITIONS_FOR_CUBIC_CURVE,
    MIN_POSITIONS_FOR_CURVE,
    OUTPUT_MESH,
    OUTPUT_NURBS_SURFACE,
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
    ) -> tuple[str, Optional[str]]:
        """Create lofted surface from joint chains.

        Args:
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

        Returns:
            tuple[str, str | None]: (geometry_name, skin_cluster_name or None if not bound)

        Raises:
            ValueError: If parameters are invalid.
        """
        # Validate parameters
        if output_type not in VALID_OUTPUT_TYPES:
            raise ValueError(f"Invalid output type '{output_type}'. Valid options are: {VALID_OUTPUT_TYPES}")

        if close and len(self.root_joints) < MIN_CHAINS_FOR_CLOSE:
            raise ValueError(f"At least {MIN_CHAINS_FOR_CLOSE} joint chains are required for closed loft.")

        if surface_divisions < 0:
            raise ValueError(f"Invalid surface divisions ({surface_divisions}). Must be >= 0.")

        if is_bind and weight_method not in VALID_WEIGHT_METHODS:
            raise ValueError(f"Invalid weight method '{weight_method}'. Valid options are: {VALID_WEIGHT_METHODS}")

        # Get joint chains from root joints
        self.joint_chains = get_joint_chains_from_roots(self.root_joints, skip)

        # Create curves from joint chains
        curves = self._create_curves_from_chains(
            center=center,
            curve_divisions=curve_divisions,
        )

        # Loft curves into surface
        result = self._loft_curves(
            curves=curves,
            close=close,
            output_type=output_type,
            surface_divisions=surface_divisions,
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
                curve_divisions=curve_divisions,
                is_closed=close,
            )
            skin_cluster = weight_setter.execute(
                method=weight_method,
                smooth_iterations=smooth_iterations,
                parent_influence_ratio=parent_influence_ratio,
                remove_end=remove_end,
                loft_weight_method=loft_weight_method,
            )

        return result, skin_cluster

    def _create_curves_from_chains(
        self,
        center: bool = False,
        curve_divisions: int = 0,
    ) -> list[str]:
        """Create curves from each joint chain.

        Args:
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
                center=center,
                divisions=curve_divisions,
            )
            curves.append(curve)

        logger.debug(f"Created {len(curves)} curves from joint chains")
        return curves

    def _create_curve(
        self,
        positions: list[list[float]],
        center: bool = False,
        divisions: int = 0,
    ) -> str:
        """Create curve from positions.

        This method is adapted from curveSurface_creator's _create_curve().
        Always creates degree 3 (cubic) curves.

        Args:
            positions (list[list[float]]): Target positions (list of [x, y, z] coordinates).
            center (bool): Whether to center cubic curves.
            divisions (int): Number of CVs to insert between given positions.

        Returns:
            str: Created curve transform name.

        Raises:
            ValueError: If parameters are invalid.
        """
        num_positions = len(positions)
        if num_positions < MIN_POSITIONS_FOR_CURVE:
            raise ValueError(f"At least {MIN_POSITIONS_FOR_CURVE} positions are required.")

        # Handle special case: 2 positions - need at least 3 for degree 3
        if num_positions == MIN_POSITIONS_FOR_CURVE:
            raise ValueError(f"At least {MIN_POSITIONS_FOR_CUBIC_CURVE} positions are required for degree 3 curves.")

        # Handle special case: 3 positions - create linear first then rebuild to cubic
        if num_positions == MIN_POSITIONS_FOR_CUBIC_CURVE:
            curve = cmds.curve(d=1, p=positions)
            curve = cmds.rebuildCurve(curve, ch=False, d=CURVE_DEGREE, s=0)[0]
        else:
            # Normal case: 4+ positions
            curve = cmds.curve(d=CURVE_DEGREE, p=positions)

        # Apply curve modifications if needed
        if center or divisions:
            curve_shape = cmds.listRelatives(curve, s=True, f=True)[0]
            convert_nurbs_curve = lib_nurbsCurve.ConvertNurbsCurve(curve_shape)

            if center:
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
    ) -> str:
        """Loft multiple curves into a surface or mesh.

        Args:
            curves (list[str]): List of curve names to loft.
            close (bool): Whether to close the loft loop.
            output_type (str): Type of output ('nurbsSurface' or 'mesh').
            surface_divisions (int): Number of divisions between curves.

        Returns:
            str: Created surface or mesh transform name.
        """
        if len(curves) < 2:
            raise ValueError("At least 2 curves are required for lofting.")

        # Convert surface_divisions to Maya's ss parameter (ss = surface_divisions + 1)
        # surface_divisions=0 means no additional divisions, which is ss=1 in Maya
        maya_ss = surface_divisions + 1

        if output_type == OUTPUT_NURBS_SURFACE:
            # NURBS Surface: use degree 3 for loft direction
            # rsn=True to reverse surface normals (face outward)
            result = cmds.loft(
                curves,
                ch=False,
                u=True,
                c=close,
                ar=True,
                d=CURVE_DEGREE,
                ss=maya_ss,
                rn=False,
                po=0,
                rsn=True,
            )[0]
        else:
            # Mesh: use degree 1 (linear) for loft direction
            # This is required because degree 3 mesh loft has different tessellation behavior
            # rsn=False for mesh (normals face outward without reversal)
            result, loft_node = cmds.loft(
                curves,
                ch=True,
                u=True,
                c=close,
                ar=True,
                d=1,  # Linear for mesh output
                ss=maya_ss,
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

            # For closed mesh, merge first and last row vertices
            if close:
                self._merge_seam_vertices(result)

        # Delete temporary curves
        cmds.delete(curves)

        logger.debug(f"Created lofted {'mesh' if output_type == OUTPUT_MESH else 'surface'}: {result}")
        return result

    def _merge_seam_vertices(self, mesh: str) -> None:
        """Merge first and last row vertices for closed mesh.

        For closed loft, Maya creates duplicate vertices at the seam.
        This method merges them to create a proper closed mesh.

        Args:
            mesh (str): Mesh transform name.
        """
        num_vertices = cmds.polyEvaluate(mesh, vertex=True)

        # Calculate vertices per row (curve direction)
        # This is determined by the curve, not affected by surface_divisions
        # We need to figure out the row count from total vertices
        # num_vertices = num_rows * verts_per_row
        # For closed loft before merge: num_rows = num_chains * surface_divisions + 1

        # Get the actual vertex count per row by checking vertex positions
        # First row vertices are at indices 0, 1, 2, ...
        # We find where the pattern repeats (same X position as vtx[0])
        first_pos = cmds.xform(f"{mesh}.vtx[0]", q=True, ws=True, t=True)

        verts_per_row = 0
        for i in range(1, num_vertices):
            pos = cmds.xform(f"{mesh}.vtx[{i}]", q=True, ws=True, t=True)
            # Check if this vertex is at a different "row" (approximately same position as first)
            dist = ((pos[0] - first_pos[0]) ** 2 + (pos[1] - first_pos[1]) ** 2 + (pos[2] - first_pos[2]) ** 2) ** 0.5
            if dist < 0.0001:
                # Found a vertex at the same position - this is the last row's first vertex
                verts_per_row = i
                break

        if verts_per_row == 0:
            logger.warning("Could not determine vertices per row for seam merge")
            return

        num_rows = num_vertices // verts_per_row
        last_row_start = (num_rows - 1) * verts_per_row

        # Merge each pair of first row and last row vertices
        # Merge from last to first to avoid index shifting issues
        for i in range(verts_per_row - 1, -1, -1):
            first_vtx = f"{mesh}.vtx[{i}]"
            last_vtx = f"{mesh}.vtx[{last_row_start + i}]"
            cmds.polyMergeVertex(first_vtx, last_vtx, d=0.01, am=True, ch=False)

        logger.debug(f"Merged {verts_per_row} seam vertex pairs")


__all__ = ["CreateLoftSurface"]
