"""Helper functions for getting positions from Maya selections."""

from logging import getLogger
import math

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ...lib import lib_math, lib_nurbsCurve, lib_nurbsSurface
from ...lib.lib_componentfilter import ComponentFilter
from ...lib.lib_mesh import MeshComponentConversion, MeshEdge, MeshFace, MeshVertex

logger = getLogger(__name__)


def get_selected_positions(
    *,
    only_component: bool = False,
    flatten_components: bool = False,
    include_rotation: bool = False,
    closest_position: bool = False,
    tangent_from_component: bool = False,
) -> tuple[list[list[float]], list[list[float]]] | None:
    """Get the selected object's position and rotation.

    Args:
        only_component (bool): Whether to get the component only. Default is False.
        include_rotation (bool): Whether to include rotation. Default is False.
        flatten_components (bool): Whether to flatten the mesh components. Default is False.
        closest_position (bool): Whether to get the closest position the nurbsSurface or curve. Default is False.
        tangent_from_component (bool): Whether to get the tangent from the component. Default is False.

    Returns:
        Optional[tuple[list[list[float]], list[list[float]]]: The position and rotation.
    """
    sel_transforms = cmds.ls(sl=True, type="transform")
    sel_components = cmds.filterExpand(sm=[28, 30, 31, 32, 34, 46])  # Added 46 for lattice points

    if not sel_transforms and not sel_components:
        logger.warning("No valid object selected.")
        return

    result_positions = []
    result_rotations = []

    # Get the dagNode position and rotation
    if sel_transforms and not only_component:
        transform_positions, transform_rotations = _get_transform_positions(sel_transforms, include_rotation)
        result_positions.extend(transform_positions)
        result_rotations.extend(transform_rotations)

    # Get the component position and rotation
    if sel_components:
        component_positions, component_rotations = _get_component_positions(
            sel_components, include_rotation, closest_position, tangent_from_component, flatten_components
        )
        result_positions.extend(component_positions)
        result_rotations.extend(component_rotations)

    if not result_positions and not result_rotations:
        logger.warning("No valid position and rotation data.")
        return

    return result_positions, result_rotations


def _get_transform_positions(transforms: list[str], include_rotation: bool) -> tuple[list[list[float]], list[list[float]]]:
    """Get positions and rotations from transform nodes.

    Args:
        transforms (list[str]): Transform node names.
        include_rotation (bool): Whether to include rotation.

    Returns:
        tuple[list[list[float]], list[list[float]]]: Positions and rotations.
    """
    logger.debug(f"Dag nodes: {transforms}")

    positions = []
    rotations = []

    if include_rotation:
        for transform in transforms:
            positions.append(cmds.xform(transform, q=True, ws=True, t=True))
            rotations.append(cmds.xform(transform, q=True, ws=True, ro=True))
    else:
        positions = [cmds.xform(transform, q=True, ws=True, t=True) for transform in transforms]

    logger.debug(f"Transform positions: {positions}")
    logger.debug(f"Transform rotations: {rotations}")

    return positions, rotations


def _get_component_positions(
    components: list[str], include_rotation: bool, closest_position: bool, tangent_from_component: bool, flatten_components: bool
) -> tuple[list[list[float]], list[list[float]]]:
    """Get positions and rotations from components.

    Args:
        components (list[str]): Component names.
        include_rotation (bool): Whether to include rotation.
        closest_position (bool): Whether to get closest position.
        tangent_from_component (bool): Whether to get tangent from component.
        flatten_components (bool): Whether to flatten mesh components.

    Returns:
        tuple[list[list[float]], list[list[float]]]: Positions and rotations.
    """
    logger.debug(f"Component data: {components}")

    component_positions = []
    component_rotations = []

    components_filter = ComponentFilter(components)

    # Process mesh components
    mesh_positions, mesh_rotations = _get_mesh_positions(components_filter, include_rotation, tangent_from_component, flatten_components)
    component_positions.extend(mesh_positions)
    component_rotations.extend(mesh_rotations)

    # Process curve components
    curve_positions, curve_rotations = _get_curve_positions(components_filter, include_rotation, closest_position)
    component_positions.extend(curve_positions)
    component_rotations.extend(curve_rotations)

    # Process surface components
    surface_positions, surface_rotations = _get_surface_positions(components_filter, include_rotation, closest_position)
    component_positions.extend(surface_positions)
    component_rotations.extend(surface_rotations)

    # Process lattice components
    lattice_positions = _get_lattice_positions(components_filter)
    component_positions.extend(lattice_positions)

    # Convert MPoint to list
    component_positions = [[v.x, v.y, v.z] for v in component_positions]

    logger.debug(f"Bound positions: {component_positions}")
    logger.debug(f"Bound rotations: {component_rotations}")

    return component_positions, component_rotations


def _get_mesh_positions(
    components_filter: ComponentFilter, include_rotation: bool, tangent_from_component: bool, flatten_components: bool
) -> tuple[list[om.MPoint], list[list[float]]]:
    """Get positions and rotations from mesh components.

    Args:
        components_filter (ComponentFilter): Filtered components.
        include_rotation (bool): Whether to include rotation.
        tangent_from_component (bool): Whether to get tangent from component.
        flatten_components (bool): Whether to flatten components.

    Returns:
        tuple[list[MPoint], list[list[float]]]: Positions and rotations.
    """
    positions = []
    rotations = []

    vertex_components = components_filter.get_vertices()
    edge_components = components_filter.get_edges()
    face_components = components_filter.get_faces()

    # Flatten the mesh components
    if flatten_components and (face_components or edge_components):
        vertex_components = _flatten_mesh_components(vertex_components, edge_components, face_components)

    # Vertex
    for shape, indices in vertex_components.items():
        mesh_vertex = MeshVertex(shape)
        vertex_positions = mesh_vertex.get_vertex_positions(indices)
        positions.extend(vertex_positions)

        if include_rotation:
            normals = mesh_vertex.get_vertex_normals(indices)
            tangents = mesh_vertex.get_vertex_tangents(indices)

            if not tangent_from_component:
                rotations.extend(
                    [
                        lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
                        for normal, tangent in zip(normals, tangents, strict=False)
                    ]
                )
            else:
                vertex_rotations = _get_vertex_rotations_from_topology(mesh_vertex, vertex_positions, normals, tangents, indices)
                rotations.extend(vertex_rotations)

    # Edge
    for shape, indices in edge_components.items():
        mesh_edge = MeshEdge(shape)
        positions.extend(mesh_edge.get_edge_position(indices))

        if include_rotation:
            edge_rotations = _get_edge_rotations(mesh_edge, indices, tangent_from_component)
            rotations.extend(edge_rotations)

    # Face
    for shape, indices in face_components.items():
        mesh_face = MeshFace(shape)
        positions.extend(mesh_face.get_face_position(indices))

        if include_rotation:
            normals = mesh_face.get_face_normal(indices)
            tangents = mesh_face.get_face_tangent(indices)
            rotations.extend(
                [
                    lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
                    for normal, tangent in zip(normals, tangents, strict=False)
                ]
            )

    return positions, rotations


def _flatten_mesh_components(vertex_components: dict, edge_components: dict, face_components: dict) -> dict:
    """Flatten mesh components to vertices.

    Args:
        vertex_components (dict): Vertex components.
        edge_components (dict): Edge components.
        face_components (dict): Face components.

    Returns:
        dict: Flattened vertex components.
    """
    result = vertex_components.copy()

    for shape, indices in face_components.items():
        mesh_conversion = MeshComponentConversion(shape)
        converted_indices = mesh_conversion.face_to_vertices(indices, flatten=True)
        if shape in result:
            result[shape] = list(set(converted_indices + result[shape]))
        else:
            result[shape] = converted_indices

    for shape, indices in edge_components.items():
        mesh_conversion = MeshComponentConversion(shape)
        converted_indices = mesh_conversion.edge_to_vertices(indices, flatten=True)
        if shape in result:
            result[shape] = list(set(converted_indices + result[shape]))
        else:
            result[shape] = converted_indices

    return result


def _get_vertex_rotations_from_topology(
    mesh_vertex: MeshVertex, positions: list[om.MPoint], normals: list[om.MVector], tangents: list[om.MVector], indices: list[int]
) -> list[list[float]]:
    """Get vertex rotations based on topology.

    Args:
        mesh_vertex (MeshVertex): Mesh vertex object.
        positions (list[MPoint]): Vertex positions.
        normals (list[MVector]): Vertex normals.
        tangents (list[MVector]): Vertex tangents.
        indices (list[int]): Vertex indices.

    Returns:
        list[list[float]]: Vertex rotations.
    """
    rotations = []
    connected_vertices_list = mesh_vertex.get_connected_vertices(indices)

    for position, normal, tangent, connected_vertices in zip(positions, normals, tangents, connected_vertices_list, strict=False):
        connected_positions = mesh_vertex.get_vertex_positions(connected_vertices)

        angle = math.pi
        result_tangent = tangent

        # If the number of connected vertices is even,
        # select the one with the smallest angle between the vectors of the opposite vertices
        num_connected = len(connected_vertices)
        if num_connected % 2 == 0:
            half_num_connected = num_connected // 2
            for i in range(half_num_connected):
                vector_tangent = connected_positions[i] - connected_positions[i + half_num_connected]
                if vector_tangent * tangent < 0:
                    vector_tangent *= -1.0
                vector_angle = tangent.angle(vector_tangent)
                if vector_angle < angle:
                    angle = vector_angle
                    result_tangent = vector_tangent
        else:
            # If the number of connected vertices is odd, select the one with the smallest angle to the vertex vector
            for connected_position in connected_positions:
                vector_tangent = connected_position - position
                vector_angle = tangent.angle(vector_tangent)
                if vector_angle < angle:
                    angle = vector_angle
                    result_tangent = vector_tangent

        rotations.append(lib_math.vector_to_rotation(normal, result_tangent, primary_axis="z", secondary_axis="x"))

    return rotations


def _get_edge_rotations(mesh_edge: MeshEdge, indices: list[int], tangent_from_component: bool) -> list[list[float]]:
    """Get edge rotations.

    Args:
        mesh_edge (MeshEdge): Mesh edge object.
        indices (list[int]): Edge indices.
        tangent_from_component (bool): Whether to get tangent from component.

    Returns:
        list[list[float]]: Edge rotations.
    """
    normals = mesh_edge.get_edge_normal(indices)
    tangents = mesh_edge.get_edge_tangent(indices)

    if not tangent_from_component:
        return [
            lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
            for normal, tangent in zip(normals, tangents, strict=False)
        ]

    # Get the vector of the vertices that make up the edge, which is closest to the current tangent
    vertex_vectors = mesh_edge.get_edge_vector(indices, normalize=True)
    rotations = []

    for normal, tangent, vertex_vector in zip(normals, tangents, vertex_vectors, strict=False):
        tangent = lib_math.vector_orthogonalize(normal, tangent)
        binormal = normal ^ tangent

        result_tangent = None
        angle = math.pi
        tangent_axis = "x"

        for axis_vector, axis in zip([tangent, binormal], ["x", "y"], strict=False):
            dot_product = axis_vector * vertex_vector
            candidate_vector = dot_product > 0 and vertex_vector or vertex_vector * -1.0

            vector_angle = axis_vector.angle(candidate_vector)
            if vector_angle < angle:
                angle = vector_angle
                result_tangent = candidate_vector
                tangent_axis = axis

        rotations.append(lib_math.vector_to_rotation(normal, result_tangent, primary_axis="z", secondary_axis=tangent_axis))

    return rotations


def _get_curve_positions(
    components_filter: ComponentFilter, include_rotation: bool, closest_position: bool
) -> tuple[list[om.MPoint], list[list[float]]]:
    """Get positions and rotations from curve components.

    Args:
        components_filter (ComponentFilter): Filtered components.
        include_rotation (bool): Whether to include rotation.
        closest_position (bool): Whether to get closest position.

    Returns:
        tuple[list[MPoint], list[list[float]]]: Positions and rotations.
    """
    positions = []
    rotations = []

    curve_cv_components = components_filter.get_curve_cvs()
    curve_ep_components = components_filter.get_curve_eps()

    # CV
    for shape, indices in curve_cv_components.items():
        curve = lib_nurbsCurve.NurbsCurve(shape)
        cv_positions = curve.get_cv_position(indices)

        if include_rotation or closest_position:
            closest_positions, params = curve.get_closest_positions(cv_positions)
            if closest_position:
                positions.extend(closest_positions)
            else:
                positions.extend(cv_positions)
        else:
            positions.extend(cv_positions)

        if include_rotation:
            normals, tangents = curve.get_normal_and_tangents(params)
            rotations.extend(
                [
                    lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
                    for normal, tangent in zip(normals, tangents, strict=False)
                ]
            )

    # EP
    for shape, indices in curve_ep_components.items():
        curve = lib_nurbsCurve.NurbsCurve(shape)
        ep_positions, params = curve.get_edit_position(indices)
        positions.extend(ep_positions)

        if include_rotation:
            normals, tangents = curve.get_normal_and_tangents(params)
            rotations.extend(
                [
                    lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
                    for normal, tangent in zip(normals, tangents, strict=False)
                ]
            )

    return positions, rotations


def _get_surface_positions(
    components_filter: ComponentFilter, include_rotation: bool, closest_position: bool
) -> tuple[list[om.MPoint], list[list[float]]]:
    """Get positions and rotations from surface components.

    Args:
        components_filter (ComponentFilter): Filtered components.
        include_rotation (bool): Whether to include rotation.
        closest_position (bool): Whether to get closest position.

    Returns:
        tuple[list[MPoint], list[list[float]]]: Positions and rotations.
    """
    positions = []
    rotations = []

    surface_cv_components = components_filter.get_surface_cvs()

    for shape, indices in surface_cv_components.items():
        surface = lib_nurbsSurface.NurbsSurface(shape)
        cv_positions = surface.get_cv_position(indices)

        if include_rotation or closest_position:
            closest_positions, params = surface.get_closest_positions(cv_positions)
            if closest_position:
                positions.extend(closest_positions)
            else:
                positions.extend(cv_positions)
        else:
            positions.extend(cv_positions)

        if include_rotation:
            normals, tangents = surface.get_normal_and_tangents(params)
            rotations.extend(
                [
                    lib_math.vector_to_rotation(normal, tangent, primary_axis="z", secondary_axis="x")
                    for normal, tangent in zip(normals, tangents, strict=False)
                ]
            )

    return positions, rotations


def _get_lattice_positions(components_filter: ComponentFilter) -> list[om.MPoint]:
    """Get positions from lattice components.

    Args:
        components_filter (ComponentFilter): Filtered components.

    Returns:
        list[MPoint]: Lattice point positions.
    """
    positions = []

    lattice_components = components_filter.get_lattice_points()

    for shape, indices in lattice_components.items():
        # Get lattice point positions using xform
        lattice_transform = cmds.listRelatives(shape, parent=True, path=True)[0]
        for index in indices:
            s, t, u = index  # Lattice points have 3D indices
            point_name = f"{lattice_transform}.pt[{s}][{t}][{u}]"
            position = cmds.xform(point_name, query=True, worldSpace=True, translation=True)
            positions.append(om.MPoint(position[0], position[1], position[2]))

    return positions
