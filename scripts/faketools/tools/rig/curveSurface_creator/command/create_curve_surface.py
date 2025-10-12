"""CreateCurveSurface class for creating curves and surfaces from nodes."""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

from .....lib import lib_nurbsCurve
from .constants import (
    AXIS_BINORMAL,
    AXIS_NORMAL,
    AXIS_X,
    AXIS_Y,
    AXIS_Z,
    CURVE_DEGREE_CUBIC,
    CURVE_DEGREE_LINEAR,
    MIN_POSITIONS_FOR_CUBIC_CURVE,
    MIN_POSITIONS_FOR_CURVE,
    OBJECT_TYPE_CURVE,
    OBJECT_TYPE_MESH,
    VALID_CURVE_DEGREES,
    VALID_OBJECT_TYPES,
    VALID_SURFACE_AXES,
)

logger = getLogger(__name__)


class CreateCurveSurface:
    """Create curve surface class.

    This class creates a curve and lofted surface and mesh from the specified nodes.
    """

    def __init__(self, nodes: list[str]):
        """Initialize the CreateCurveSurface class.

        Args:
            nodes (list[str]): Target nodes.
        """
        if not nodes:
            raise ValueError("No nodes specified.")

        not_exist_nodes = [node for node in nodes if not cmds.objExists(node)]
        if not_exist_nodes:
            raise ValueError(f"Nodes not found: {not_exist_nodes}")

        not_transform_nodes = [node for node in nodes if "transform" not in cmds.nodeType(node, inherited=True)]
        if not_transform_nodes:
            raise ValueError(f"Invalid node type: {not_transform_nodes}")

        self.nodes = nodes

    def execute(
        self,
        object_type: str = OBJECT_TYPE_CURVE,
        degree: int = CURVE_DEGREE_CUBIC,
        center: bool = False,
        close: bool = False,
        divisions: int = 0,
        surface_width: float = 1.0,
        surface_width_center: float = 0.5,
        surface_axis: str = AXIS_X,
    ) -> str:
        """Create curve surface.

        Args:
            object_type (str): Type of object to create. One of: 'nurbsCurve', 'mesh', 'nurbsSurface'.
            degree (int): Degree of the curve (1 or 3).
            center (bool): Whether to create the curve at the center of the nodes.
            close (bool): Whether to close the curve.
            divisions (int): Number of CVs to insert between given positions.
            surface_width (float): Width of the surface (for mesh/surface only).
            surface_width_center (float): Center point of the surface width, between 0.0 and 1.0.
            surface_axis (str): Axis of the surface. One of: 'x', 'y', 'z', 'normal', 'binormal'.

        Returns:
            str: Created curve or surface transform name.

        Raises:
            ValueError: If parameters are invalid.
        """
        # Validate object type
        if object_type not in VALID_OBJECT_TYPES:
            raise ValueError(f"Invalid object type '{object_type}'. Valid options are: {VALID_OBJECT_TYPES}")

        # Validate degree
        if degree not in VALID_CURVE_DEGREES:
            raise ValueError(f"Invalid degree ({degree}). Valid options are: {VALID_CURVE_DEGREES}")

        # For nurbsCurve, create simple curve
        if object_type == OBJECT_TYPE_CURVE:
            positions = [cmds.xform(node, q=True, ws=True, t=True) for node in self.nodes]
            return self._create_curve(positions, degree=degree, center=center, close=close, divisions=divisions)

        # Validate surface parameters
        if surface_width <= 0:
            raise ValueError(f"Invalid surface width ({surface_width}). Must be greater than 0.")

        if not 0 <= surface_width_center <= 1:
            raise ValueError(f"Invalid surface width center ({surface_width_center}). Must be between 0.0 and 1.0.")

        if surface_axis not in VALID_SURFACE_AXES:
            raise ValueError(f"Invalid surface axis '{surface_axis}'. Valid options are: {VALID_SURFACE_AXES}")

        # Calculate edge positions for surface
        plus_offset = surface_width * surface_width_center
        minus_offset = plus_offset - surface_width

        # For normal/binormal axes, create a base curve for reference
        base_nurbs_curve = None
        if surface_axis in [AXIS_NORMAL, AXIS_BINORMAL]:
            node_positions = [cmds.xform(node, q=True, ws=True, t=True) for node in self.nodes]
            base_curve = self._create_curve(node_positions, degree=CURVE_DEGREE_CUBIC, center=center, close=close, divisions=divisions)
            base_curve_shape = cmds.listRelatives(base_curve, s=True, f=True, ni=True)[0]
            base_nurbs_curve = lib_nurbsCurve.NurbsCurve(base_curve_shape)

        # Calculate positions for both edges of the surface
        plus_positions = []
        minus_positions = []
        for node in self.nodes:
            matrix = om.MMatrix(cmds.xform(node, q=True, ws=True, m=True))
            position = om.MVector(cmds.xform(node, q=True, ws=True, t=True))

            # Calculate offset based on surface axis
            if surface_axis == AXIS_X:
                minus_position = position + om.MVector(minus_offset, 0, 0) * matrix
                plus_position = position + om.MVector(plus_offset, 0, 0) * matrix
            elif surface_axis == AXIS_Y:
                minus_position = position + om.MVector(0, minus_offset, 0) * matrix
                plus_position = position + om.MVector(0, plus_offset, 0) * matrix
            elif surface_axis == AXIS_Z:
                minus_position = position + om.MVector(0, 0, minus_offset) * matrix
                plus_position = position + om.MVector(0, 0, plus_offset) * matrix
            elif surface_axis == AXIS_NORMAL:
                _, param = base_nurbs_curve.get_closest_position(position)
                normal = base_nurbs_curve.get_normal(param).normal()
                minus_position = position + normal * minus_offset
                plus_position = position + normal * plus_offset
            elif surface_axis == AXIS_BINORMAL:
                _, param = base_nurbs_curve.get_closest_position(position)
                normal = base_nurbs_curve.get_normal(param).normal()
                tangent = base_nurbs_curve.get_tangent(param).normal()
                binormal = normal ^ tangent
                minus_position = position + binormal * minus_offset
                plus_position = position + binormal * plus_offset

            minus_positions.append([minus_position.x, minus_position.y, minus_position.z])
            plus_positions.append([plus_position.x, plus_position.y, plus_position.z])

        # Create edge curves
        plus_curve = self._create_curve(plus_positions, degree=degree, center=center, close=close, divisions=divisions)
        minus_curve = self._create_curve(minus_positions, degree=degree, center=center, close=close, divisions=divisions)

        # Loft surface from edge curves
        surface = cmds.loft([plus_curve, minus_curve], ch=False, u=True, d=True)[0]
        cmds.delete(plus_curve, minus_curve)

        # Convert to mesh if requested
        if object_type == OBJECT_TYPE_MESH:
            poly_surface = cmds.nurbsToPoly(surface, f=3, pt=1, ch=False)[0]
            cmds.delete(surface)

            logger.debug(f"Created mesh: {poly_surface}")

            return poly_surface

        logger.debug(f"Created surface: {surface}")

        return surface

    def _create_curve(
        self,
        positions: list[list[float]],
        degree: int = CURVE_DEGREE_CUBIC,
        center: bool = False,
        close: bool = False,
        divisions: int = 0,
    ) -> str:
        """Create curve from positions.

        Args:
            positions (list[list[float]]): Target positions (list of [x, y, z] coordinates).
            degree (int): Degree of the curve (1 or 3).
            center (bool): Whether to create the curve at the center of the nodes.
            close (bool): Whether to close the curve.
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
            if close:
                raise ValueError("Cannot close the curve with only two positions.")

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
        if center or close or divisions:
            curve_shape = cmds.listRelatives(curve, s=True, f=True)[0]
            convert_nurbs_curve = lib_nurbsCurve.ConvertNurbsCurve(curve_shape)

            if close:
                convert_nurbs_curve.close_curve()

            if center and degree == CURVE_DEGREE_CUBIC:
                convert_nurbs_curve.center_curve()

            if divisions:
                convert_nurbs_curve.insert_cvs(divisions)

        logger.debug(f"Created curve: {curve}")

        return curve
