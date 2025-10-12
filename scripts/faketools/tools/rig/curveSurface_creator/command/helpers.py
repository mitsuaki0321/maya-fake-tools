"""Helper functions for curve surface creation."""

from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_math, lib_mesh, lib_nurbsCurve, lib_nurbsSurface
from .constants import CURVE_DEGREE_LINEAR, OBJECT_TYPE_CURVE, OBJECT_TYPE_SURFACE

logger = getLogger(__name__)


def validate_geometry(geometry: str, node_types: list[str] | None = None) -> str:
    """Validate geometry and return its shape node.

    Args:
        geometry (str): Geometry transform name.
        node_types (list[str] | None): List of valid node types. Defaults to ['nurbsCurve'].

    Returns:
        str: Shape node name.

    Raises:
        ValueError: If geometry is invalid, doesn't exist, or has wrong type.
    """
    if node_types is None:
        node_types = [OBJECT_TYPE_CURVE]

    if not geometry:
        raise ValueError("No geometry specified.")

    if not cmds.objExists(geometry):
        raise ValueError(f"Geometry does not exist: {geometry}")

    shape = cmds.listRelatives(geometry, s=True, f=True, ni=True)
    if not shape:
        raise ValueError(f"No shape node found on geometry: {geometry}")

    shape_type = cmds.nodeType(shape[0])
    if shape_type not in node_types:
        raise ValueError(f"Invalid geometry type '{shape_type}'. Expected one of: {node_types}")

    return shape[0]


def create_curve_from_vertices(target_vertices: list[str]) -> str:
    """Create a curve from mesh vertices by expanding selection iteratively.

    Creates a curve that follows the center of expanding vertex selections,
    useful for creating curves along mesh topology.

    Args:
        target_vertices (list[str]): List of mesh vertices (e.g., ['pCube1.vtx[0]', ...]).

    Returns:
        str: Name of the created curve.

    Raises:
        ValueError: If vertices are invalid or all vertices are selected.
    """
    if not target_vertices or not isinstance(target_vertices, list):
        raise ValueError("No vertices specified. Please provide a list of vertices.")

    # Validate that selection contains vertices
    if not cmds.filterExpand(target_vertices, sm=31):
        raise ValueError("No vertices found in selection. Please select mesh vertices.")

    # Get mesh and vertex information
    mesh = cmds.ls(target_vertices, objectsOnly=True)[0]
    mesh_vertex = lib_mesh.MeshVertex(mesh)
    num_vertices = mesh_vertex.num_vertices()
    all_positions = mesh_vertex.get_vertex_positions(as_float=True)

    # Flatten vertex list
    target_vertices = cmds.ls(target_vertices, fl=True)
    if len(target_vertices) == num_vertices:
        raise ValueError("All vertices are selected. Please select a subset of vertices.")

    # Get initial vertex indices and center position
    vertex_indices = mesh_vertex.get_vertex_indices(target_vertices)
    positions = [all_positions[i] for i in vertex_indices]
    center_position = lib_math.get_bounding_box_center(positions)

    # Expand selection iteratively and collect center positions
    mesh_conversion = lib_mesh.MeshComponentConversion(mesh)
    result_positions = [center_position]

    while True:
        # Expand to connected faces, then to their vertices
        face_indices = mesh_conversion.vertex_to_faces(vertex_indices, flatten=True)
        expanded_indices = mesh_conversion.face_to_vertices(face_indices, flatten=True)

        # Get newly added vertices
        new_indices = list(set(expanded_indices) - set(vertex_indices))
        center_position = lib_math.get_bounding_box_center([all_positions[i] for i in new_indices])
        result_positions.append(center_position)

        # Stop if we've covered the entire mesh
        if len(expanded_indices) >= num_vertices:
            break

        vertex_indices = expanded_indices

    # Create curve from collected positions
    curve = cmds.curve(d=CURVE_DEGREE_LINEAR, p=result_positions)

    # Rename curve based on mesh name
    mesh_transform = cmds.listRelatives(mesh, p=True)[0]
    renamed_curve = cmds.rename(curve, f"{mesh_transform}_centerCurve")

    logger.debug(f"Created curve from {len(target_vertices)} vertices: {renamed_curve}")

    return renamed_curve


def move_cv_positions(target_cv: str) -> None:
    """Rotate CV positions on a closed curve to start from the specified CV.

    Args:
        target_cv (str): Target CV to become the first CV (e.g., 'curve1.cv[5]').

    Raises:
        ValueError: If CV is invalid or curve is not closed.
    """
    if not target_cv:
        raise ValueError("No CV specified.")

    # Validate that selection contains CVs
    if not cmds.filterExpand(target_cv, sm=28):
        raise ValueError("No CVs found in selection. Please select a curve CV.")

    # Get curve and validate it's closed
    curve_shape = cmds.ls(target_cv, objectsOnly=True)[0]
    nurbs_curve = lib_nurbsCurve.NurbsCurve(curve_shape)
    if nurbs_curve.form == "open":
        raise ValueError("Open curves are not supported. Only closed curves can have their CVs rotated.")

    # Get all CV positions
    cv_positions = nurbs_curve.get_cv_positions(as_float=True)

    # Get all CVs and target CV
    cvs = cmds.ls(f"{curve_shape}.cv[*]", fl=True)
    target_cv = cmds.ls(target_cv, fl=True)[0]

    # Rotate CV positions so target CV becomes first
    target_cv_index = cvs.index(target_cv)
    move_positions = cv_positions[target_cv_index:] + cv_positions[:target_cv_index]

    # Apply rotated positions
    for cv, move_position in zip(cvs, move_positions, strict=False):
        cmds.xform(cv, ws=True, t=move_position)

    logger.debug(f"Rotated CV positions starting from: {target_cv}")


def create_curve_on_surface(surface: str, surface_axis: str = "u") -> str:
    """Create a curve at the center of a NURBS surface along the specified axis.

    Args:
        surface (str): NURBS surface shape name.
        surface_axis (str): Axis along which to create the curve ('u' or 'v').

    Returns:
        str: Name of the created curve transform.

    Raises:
        ValueError: If surface is invalid or axis is invalid.
    """
    if not surface:
        raise ValueError("No surface specified.")

    if not cmds.objExists(surface):
        raise ValueError(f"Surface does not exist: {surface}")

    if cmds.nodeType(surface) != OBJECT_TYPE_SURFACE:
        raise ValueError(f"Invalid node type '{cmds.nodeType(surface)}'. Expected '{OBJECT_TYPE_SURFACE}'.")

    if surface_axis not in ["u", "v"]:
        raise ValueError(f"Invalid surface axis '{surface_axis}'. Valid options are: ['u', 'v']")

    # Get surface parameter range
    nurbs_surface = lib_nurbsSurface.NurbsSurface(surface)
    u_range, v_range = nurbs_surface.get_uv_range()

    # Calculate center parameter
    if surface_axis == "u":
        center_param = (v_range[0] + v_range[1]) / 2.0
        iso_axis = "v"
    else:
        center_param = (u_range[0] + u_range[1]) / 2.0
        iso_axis = "u"

    # Create curve from surface isoparm
    nodes = cmds.duplicateCurve(
        f"{surface}.{iso_axis}[{center_param}]",
        ch=True,
        rn=False,
        local=False,
        n=f"{surface}_centerCurve",
    )

    # Rename history node
    cmds.rename(nodes[1], f"{surface}_curveFromSurfaceIso")

    logger.debug(f"Created curve on surface at {iso_axis}={center_param}: {nodes[0]}")

    return nodes[0]
