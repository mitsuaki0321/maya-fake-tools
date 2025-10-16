"""OffsetCurveToSurface command for creating surfaces from curves."""

from logging import getLogger
from typing import Optional

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ....lib import lib_nurbsCurve
from ....lib.lib_nurbsSurface import NurbsSurface

logger = getLogger(__name__)

# Axis type constants
AXIS_VECTOR = "vector"
AXIS_NORMAL = "normal"
AXIS_BINORMAL = "binormal"
AXIS_MESH_NORMAL = "meshNormal"
AXIS_MESH_BINORMAL = "meshBinormal"
AXIS_SURFACE_NORMAL = "surfaceNormal"
AXIS_SURFACE_BINORMAL = "surfaceBinormal"

VALID_AXIS_TYPES = [
    AXIS_VECTOR,
    AXIS_NORMAL,
    AXIS_BINORMAL,
    AXIS_MESH_NORMAL,
    AXIS_MESH_BINORMAL,
    AXIS_SURFACE_NORMAL,
    AXIS_SURFACE_BINORMAL,
]


class OffsetCurveToSurface:
    """Create NURBS surface by offsetting curve in specified direction.

    This class creates a lofted surface from a curve by offsetting its CV positions
    in a specified direction (vector, normal, binormal, mesh/surface normal/binormal).
    """

    def __init__(self, curve_shape: str):
        """Initialize the OffsetCurveToSurface class.

        Args:
            curve_shape (str): NURBS curve shape node name.

        Raises:
            ValueError: If curve_shape is invalid or not a nurbsCurve.
        """
        if not cmds.objExists(curve_shape):
            raise ValueError(f"Curve shape not found: {curve_shape}")

        if cmds.nodeType(curve_shape) != "nurbsCurve":
            raise ValueError(f"Node is not a nurbsCurve: {curve_shape}")

        self.curve_shape = curve_shape
        self.nurbs_curve = lib_nurbsCurve.NurbsCurve(curve_shape)

    def execute(
        self,
        axis_type: str = AXIS_VECTOR,
        surface_width: float = 1.0,
        surface_width_center: float = 0.5,
        vector: Optional[list[float]] = None,
        reference_object: Optional[str] = None,
        divisions: int = 0,
    ) -> str:
        """Create offset surface from curve.

        Args:
            axis_type (str): Offset direction type. One of: 'vector', 'normal', 'binormal',
                'meshNormal', 'meshBinormal', 'surfaceNormal', 'surfaceBinormal'.
            surface_width (float): Width of the surface.
            surface_width_center (float): Center point of the surface width, between 0.0 and 1.0.
            vector (list[float] | None): Direction vector [x, y, z] for 'vector' axis type.
            reference_object (str | None): Reference surface/mesh for normal/binormal calculation.
                Required for meshNormal, meshBinormal, surfaceNormal, surfaceBinormal axes.
            divisions (int): Number of CVs to insert between existing CVs (0 = no insertion).

        Returns:
            str: Created surface transform name.

        Raises:
            ValueError: If parameters are invalid.
        """
        # Validate axis type
        if axis_type not in VALID_AXIS_TYPES:
            raise ValueError(f"Invalid axis type '{axis_type}'. Valid options are: {VALID_AXIS_TYPES}")

        # Validate surface parameters
        if surface_width <= 0:
            raise ValueError(f"Invalid surface width ({surface_width}). Must be greater than 0.")

        if not 0 <= surface_width_center <= 1:
            raise ValueError(f"Invalid surface width center ({surface_width_center}). Must be between 0.0 and 1.0.")

        # Validate vector for vector axis type
        if axis_type == AXIS_VECTOR:
            if vector is None or len(vector) != 3:
                raise ValueError("Vector [x, y, z] is required for 'vector' axis type.")
            if all(v == 0 for v in vector):
                raise ValueError("Vector cannot be zero vector.")

        # Validate reference object for mesh/surface axes
        if axis_type in [AXIS_MESH_NORMAL, AXIS_MESH_BINORMAL, AXIS_SURFACE_NORMAL, AXIS_SURFACE_BINORMAL]:
            if reference_object is None:
                raise ValueError(f"reference_object is required for '{axis_type}' axis type.")
            if not cmds.objExists(reference_object):
                raise ValueError(f"Reference object not found: {reference_object}")

            # Validate reference object type
            if axis_type in [AXIS_MESH_NORMAL, AXIS_MESH_BINORMAL] and cmds.nodeType(reference_object) != "mesh":
                raise ValueError(f"Reference object must be a mesh for '{axis_type}': {reference_object}")
            elif axis_type in [AXIS_SURFACE_NORMAL, AXIS_SURFACE_BINORMAL] and cmds.nodeType(reference_object) != "nurbsSurface":
                raise ValueError(f"Reference object must be a nurbsSurface for '{axis_type}': {reference_object}")

        # Calculate edge positions for surface
        plus_offset = surface_width * surface_width_center
        minus_offset = plus_offset - surface_width

        # Get CV positions from curve
        cv_positions = self.nurbs_curve.get_cv_positions(as_float=True)

        # Calculate offset positions
        plus_positions = []
        minus_positions = []

        for cv_index, cv_position in enumerate(cv_positions):
            position = om.MVector(cv_position)

            # Calculate offset direction based on axis type
            if axis_type == AXIS_VECTOR:
                offset_direction = om.MVector(vector).normal()
            elif axis_type == AXIS_NORMAL:
                offset_direction = self._get_normal_direction(cv_index, position)
            elif axis_type == AXIS_BINORMAL:
                offset_direction = self._get_binormal_direction(cv_index, position)
            elif axis_type == AXIS_MESH_NORMAL:
                offset_direction = self._get_mesh_normal_direction(position, reference_object)
            elif axis_type == AXIS_MESH_BINORMAL:
                offset_direction = self._get_mesh_binormal_direction(position, cv_index, reference_object)
            elif axis_type == AXIS_SURFACE_NORMAL:
                offset_direction = self._get_surface_normal_direction(position, reference_object)
            elif axis_type == AXIS_SURFACE_BINORMAL:
                offset_direction = self._get_surface_binormal_direction(position, cv_index, reference_object)
            else:
                raise ValueError(f"Unsupported axis type: {axis_type}")

            # Calculate offset positions
            minus_pos = position + offset_direction * minus_offset
            plus_pos = position + offset_direction * plus_offset

            minus_positions.append([minus_pos.x, minus_pos.y, minus_pos.z])
            plus_positions.append([plus_pos.x, plus_pos.y, plus_pos.z])

        # Get curve degree from original curve
        degree = cmds.getAttr(f"{self.curve_shape}.degree")

        # Create edge curves
        plus_curve = self._create_curve(plus_positions, degree=degree, divisions=divisions)
        minus_curve = self._create_curve(minus_positions, degree=degree, divisions=divisions)

        # Loft surface from edge curves
        surface = cmds.loft([plus_curve, minus_curve], ch=False, u=True, d=True)[0]
        cmds.delete(plus_curve, minus_curve)

        logger.debug(f"Created surface: {surface}")

        return surface

    def _create_curve(self, positions: list[list[float]], degree: int, divisions: int = 0) -> str:
        """Create curve from positions.

        Args:
            positions (list[list[float]]): CV positions (list of [x, y, z] coordinates).
            degree (int): Degree of the curve.
            divisions (int): Number of CVs to insert between given positions.

        Returns:
            str: Created curve transform name.
        """
        # Create curve
        curve = cmds.curve(d=degree, p=positions)

        # Insert CVs if divisions > 0
        if divisions > 0:
            curve_shape = cmds.listRelatives(curve, s=True, f=True)[0]
            lib_nurbsCurve.ConvertNurbsCurve(curve_shape).insert_cvs(divisions)

        return curve

    def _get_normal_direction(self, cv_index: int, position: om.MVector) -> om.MVector:
        """Get normal direction at CV position.

        Args:
            cv_index (int): CV index.
            position (om.MVector): CV position.

        Returns:
            om.MVector: Normal direction (normalized).
        """
        # Get closest parameter on curve
        _, param = self.nurbs_curve.get_closest_position(position)

        # Get normal at parameter
        normal = self.nurbs_curve.get_normal(param).normal()
        return normal

    def _get_binormal_direction(self, cv_index: int, position: om.MVector) -> om.MVector:
        """Get binormal direction at CV position.

        Args:
            cv_index (int): CV index.
            position (om.MVector): CV position.

        Returns:
            om.MVector: Binormal direction (normalized).
        """
        # Get closest parameter on curve
        _, param = self.nurbs_curve.get_closest_position(position)

        # Get normal and tangent at parameter
        normal = self.nurbs_curve.get_normal(param).normal()
        tangent = self.nurbs_curve.get_tangent(param).normal()

        # Calculate binormal (cross product)
        binormal = normal ^ tangent
        return binormal.normal()

    def _get_mesh_normal_direction(self, position: om.MVector, reference_mesh: str) -> om.MVector:
        """Get mesh normal direction at closest point.

        Args:
            position (om.MVector): Query position.
            reference_mesh (str): Reference mesh shape node.

        Returns:
            om.MVector: Normal direction (normalized).
        """
        # Get closest point on mesh with normal
        mesh_intersector = om.MMeshIntersector()
        selection_list = om.MSelectionList()
        selection_list.add(reference_mesh)
        dag_path = selection_list.getDagPath(0)
        matrix = dag_path.inclusiveMatrix()
        inverse_matrix = dag_path.inclusiveMatrixInverse()
        mesh_intersector.create(dag_path.node(), matrix)

        # Transform to local space
        local_position = inverse_matrix * om.MPoint(position)
        point_on_mesh = mesh_intersector.getClosestPoint(local_position, 1000.0)

        if point_on_mesh is None:
            raise ValueError(f"No closest point found on mesh: {reference_mesh}")

        # Transform normal to world space
        normal = om.MVector(point_on_mesh.normal) * matrix
        return normal.normal()

    def _get_mesh_binormal_direction(self, position: om.MVector, cv_index: int, reference_mesh: str) -> om.MVector:
        """Get mesh binormal direction at closest point.

        Args:
            position (om.MVector): Query position.
            cv_index (int): CV index.
            reference_mesh (str): Reference mesh shape node.

        Returns:
            om.MVector: Binormal direction (normalized).
        """
        # Get normal at closest point
        normal = self._get_mesh_normal_direction(position, reference_mesh)

        # Get tangent direction from curve
        _, param = self.nurbs_curve.get_closest_position(position)
        tangent = self.nurbs_curve.get_tangent(param).normal()

        # Calculate binormal
        binormal = (normal ^ tangent).normal()
        return binormal

    def _get_surface_normal_direction(self, position: om.MVector, reference_surface: str) -> om.MVector:
        """Get surface normal direction at closest point.

        Args:
            position (om.MVector): Query position.
            reference_surface (str): Reference surface shape node.

        Returns:
            om.MVector: Normal direction (normalized).
        """
        nurbs_surface = NurbsSurface(reference_surface)

        # Get closest position and UV parameter
        _, uv_params = nurbs_surface.get_closest_positions([[position.x, position.y, position.z]])
        uv_param = uv_params[0]

        # Get normal at the closest point
        normal = nurbs_surface.get_normal(uv_param).normal()
        return normal

    def _get_surface_binormal_direction(self, position: om.MVector, cv_index: int, reference_surface: str) -> om.MVector:
        """Get surface binormal direction at closest point.

        Args:
            position (om.MVector): Query position.
            cv_index (int): CV index.
            reference_surface (str): Reference surface shape node.

        Returns:
            om.MVector: Binormal direction (normalized).
        """
        # Get normal at closest point
        normal = self._get_surface_normal_direction(position, reference_surface)

        # Get tangent direction from curve
        _, param = self.nurbs_curve.get_closest_position(position)
        tangent = self.nurbs_curve.get_tangent(param).normal()

        # Calculate binormal
        binormal = (normal ^ tangent).normal()
        return binormal
