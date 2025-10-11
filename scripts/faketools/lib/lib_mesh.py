"""
Mesh functions.

This module provides the base MeshComponent class and re-exports specialized mesh classes
for better code organization:
- MeshVertex: Vertex operations (lib_mesh_vertex.py)
- MeshFace: Face operations (lib_mesh_face.py)
- MeshEdge: Edge operations (lib_mesh_edge.py)
- MeshPoint: Point operations (lib_mesh_point.py)
- MeshComponentConversion: Component conversion operations (lib_mesh_conversion.py)
"""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

logger = getLogger(__name__)


class MeshComponent:
    """Mesh component base class."""

    def __init__(self, mesh: str):
        """Initialize the Mesh class.

        Args:
            mesh (str): The mesh name.
        """
        if not cmds.objExists(mesh):
            raise ValueError(f"Mesh does not exist: {mesh}")

        if not cmds.objectType(mesh) == "mesh":
            raise ValueError(f"Not a mesh: {mesh}")

        selection_list = om.MSelectionList()
        selection_list.add(mesh)

        self._mesh_name = mesh
        self._dag_path = selection_list.getDagPath(0)
        self._mesh_fn = om.MFnMesh(self._dag_path)

    def get_mesh_name(self) -> str:
        """Get the mesh name.

        Returns:
            str: The mesh name.
        """
        return self._mesh_name

    def get_dag_path(self) -> om.MDagPath:
        """Get the DAG path.

        Returns:
            om.MDagPath: The DAG path.
        """
        return self._dag_path

    def get_mesh_fn(self) -> om.MFnMesh:
        """Get the mesh function set.

        Returns:
            om.MFnMesh: The mesh function set.
        """
        return self._mesh_fn

    def get_components_indices(self, components: list[str], component_type: str) -> list[int]:
        """Get the component indices.

        Args:
            components (list[str]): The component names
            component_type (str): The component type.

        Returns:
            list[int]: The component indices.
        """
        selection_list = om.MSelectionList()
        for component in components:
            selection_list.add(component)

        if selection_list.length() == 0:
            raise ValueError("No components found.")

        if selection_list.length() > 1:
            raise ValueError("Multiple components found.")

        component_path, component_obj = selection_list.getComponent(0)
        if component_obj.isNull():
            raise ValueError("Invalid component object.")

        component_type_str = {"face": "kMeshPolygonComponent", "edge": "kMeshEdgeComponent", "vertex": "kMeshVertComponent"}

        if component_obj.apiTypeStr != component_type_str[component_type]:
            raise ValueError(f"Invalid component type: {component_obj.apiTypeStr}")

        if component_path != self._dag_path:
            raise ValueError("Component does not belong to the mesh")

        component_indices = om.MFnSingleIndexedComponent(component_obj).getElements()

        return list(component_indices)

    def get_components_from_indices(self, indices: list[int], component_type: str) -> list[str]:
        """Get the component names from the indices.

        Args:
            indices (list[int]): The component indices.
            component_type (str): The component type.

        Returns:
            list[str]: The component names.
        """
        if component_type not in ["face", "edge", "vertex"]:
            raise ValueError(f"Invalid component type: {component_type}")

        mesh_transform = cmds.listRelatives(self._mesh_name, parent=True, path=True)[0]

        if component_type == "face":
            num_faces = self._mesh_fn.numPolygons
            if min(indices) < 0 or max(indices) >= num_faces:
                raise ValueError("Face index out of range.")

            return [f"{mesh_transform}.f[{index}]" for index in indices]

        elif component_type == "edge":
            num_edges = self._mesh_fn.numEdges
            if min(indices) < 0 or max(indices) >= num_edges:
                raise ValueError("Edge index out of range.")

            return [f"{mesh_transform}.e[{index}]" for index in indices]

        elif component_type == "vertex":
            num_vertices = self._mesh_fn.numVertices
            if min(indices) < 0 or max(indices) >= num_vertices:
                raise ValueError("Vertex index out of range.")

            return [f"{mesh_transform}.vtx[{index}]" for index in indices]


def is_same_topology(mesh_a: str, mesh_b: str) -> bool:
    """Check if two meshes have the same topology.

    Args:
        mesh_a (str): The first mesh.
        mesh_b (str): The second mesh.

    Returns:
        bool: True if the meshes have the same topology.
    """
    mesh_fn_a = MeshComponent(mesh_a).get_mesh_fn()
    mesh_fn_b = MeshComponent(mesh_b).get_mesh_fn()

    if mesh_fn_a.numVertices != mesh_fn_b.numVertices:
        logger.debug(f"Vertex count is different: {mesh_a}, {mesh_b}")
        return False

    if mesh_fn_a.numEdges != mesh_fn_b.numEdges:
        logger.debug(f"Edge count is different: {mesh_a}, {mesh_b}")
        return False

    if mesh_fn_a.numPolygons != mesh_fn_b.numPolygons:
        logger.debug(f"Face count is different: {mesh_a}, {mesh_b}")
        return False

    for i in range(mesh_fn_a.numPolygons):
        vertices_a = list(mesh_fn_a.getPolygonVertices(i))
        vertices_b = list(mesh_fn_b.getPolygonVertices(i))

        if vertices_a != vertices_b:
            logger.debug(f"The vertices that make up the face are different: {mesh_a}, {mesh_b} ({i})")
            return False

    return True


# Re-export specialized mesh classes for backward compatibility
# Note: Imports placed here to avoid circular imports
from .lib_mesh_conversion import MeshComponentConversion  # noqa: E402
from .lib_mesh_edge import MeshEdge  # noqa: E402
from .lib_mesh_face import MeshFace  # noqa: E402
from .lib_mesh_point import MeshPoint  # noqa: E402
from .lib_mesh_vertex import MeshVertex  # noqa: E402

__all__ = [
    "MeshComponent",
    "MeshVertex",
    "MeshFace",
    "MeshEdge",
    "MeshPoint",
    "MeshComponentConversion",
    "is_same_topology",
]
