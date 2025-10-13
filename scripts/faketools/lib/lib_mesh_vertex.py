"""
Mesh vertex operations.
"""

from logging import getLogger

import maya.api.OpenMaya as om

from .lib_mesh import MeshComponent

logger = getLogger(__name__)


class MeshVertex(MeshComponent):
    """Mesh vertex class."""

    def get_vertex_positions(self, vtx_indices: list[int] | None = None, as_float: bool = False) -> list[om.MPoint] | list[list[float]]:
        """Get the vertex positions.

        Args:
            vtx_indices (Optional[list[int]], optional): The vertex indices. Defaults to None. If None, get all vertex positions.
            as_float (bool, optional): Whether to return the positions as float. Defaults to False.

        Returns:
            Union[list[om.MPoint], list[list[float]]]: The vertex positions.
        """
        if vtx_indices is None:
            positions = [om.MPoint([p.x, p.y, p.z]) for p in self._mesh_fn.getPoints(om.MSpace.kWorld)]
        else:
            num_vertices = self._mesh_fn.numVertices
            for index in vtx_indices:
                if index >= num_vertices:
                    raise ValueError(f"Vertex index out of range: {index}")

            positions = [self._mesh_fn.getPoint(index, om.MSpace.kWorld) for index in vtx_indices]
            positions = [om.MPoint([p.x, p.y, p.z]) for p in positions]

        if not as_float:
            return positions

        return [[p.x, p.y, p.z] for p in positions]

    def get_vertex_normals(self, vtx_indices: list[int] | None = None) -> list[om.MVector]:
        """Get the vertex normals.

        Args:
            vtx_indices (Optional[list[int]], optional): The vertex indices. Defaults to None. If None, get all vertex normals.

        Returns:
            list[om.MVector]: The vertex normals.
        """
        if vtx_indices is None:
            normals = self._mesh_fn.getVertexNormals(False, om.MSpace.kWorld)
        else:
            num_vertices = self._mesh_fn.numVertices
            for index in vtx_indices:
                if index >= num_vertices:
                    raise ValueError(f"Vertex index out of range: {index}")

            normals = [self._mesh_fn.getVertexNormal(index, om.MSpace.kWorld) for index in vtx_indices]

        return normals

    def get_vertex_tangents(self, vtx_indices: list[int] | None = None) -> list[om.MVector]:
        """Get the vertex tangents from the connected faces average.

        Args:
            vtx_indices (Optional[list[int]], optional): The vertex indices. Defaults to None. If None, get all vertex tangents.

        Returns:
            list[om.MVector]: The vertex tangents.
        """
        mit_vertex = om.MItMeshVertex(self._dag_path)
        num_vertices = self._mesh_fn.numVertices

        if vtx_indices is None:
            vtx_indices = range(num_vertices)

        result_tangents = []
        for index in vtx_indices:
            if index >= num_vertices:
                raise ValueError(f"Vertex index out of range: {index}")

            mit_vertex.setIndex(index)
            connected_face_ids = mit_vertex.getConnectedFaces()
            tangent = om.MVector(0.0, 0.0, 0.0)

            for face_id in connected_face_ids:
                try:
                    tangent += self._mesh_fn.getFaceVertexTangent(face_id, index, space=om.MSpace.kWorld)
                except RuntimeError:
                    logger.warning(f"Failed to get tangent for vertex: {index}")

            if len(connected_face_ids) > 1:
                tangent /= len(connected_face_ids)

            tangent.normalize()
            result_tangents.append(tangent)

        return result_tangents

    def get_vertex_binormals(self, vtx_indices: list[int] | None = None) -> list[om.MVector]:
        """Get the vertex binormals from the connected faces average.

        Args:
            vtx_indices (Optional[list[int]], optional): The vertex indices. Defaults to None. If None, get all vertex binormals.

        Returns:
            list[om.MVector]: The vertex binormals.
        """
        mit_vertex = om.MItMeshVertex(self._dag_path)
        num_vertices = self._mesh_fn.numVertices

        if vtx_indices is None:
            vtx_indices = range(num_vertices)

        result_binormals = []
        for index in vtx_indices:
            if index >= num_vertices:
                raise ValueError(f"Vertex index out of range: {index}")

            mit_vertex.setIndex(index)
            connected_face_ids = mit_vertex.getConnectedFaces()
            binormal = om.MVector(0.0, 0.0, 0.0)

            for face_id in connected_face_ids:
                try:
                    binormal += self._mesh_fn.getFaceVertexBinormal(face_id, index, om.MSpace.kWorld)
                except RuntimeError:
                    logger.warning(f"Failed to get binormal for vertex: {index}")

            if len(connected_face_ids) > 1:
                binormal /= len(connected_face_ids)

            binormal.normalize()
            result_binormals.append(binormal)

        return result_binormals

    def get_vertex_shells(self) -> list[list[int]]:
        """Get the vertex shells.

        Returns:
            list[list[int]]: The vertex shells.
        """
        num_shells, shell_ids = self._mesh_fn.getMeshShellsIds(om.MFn.kMeshVertComponent)

        shells = [[] for _ in range(num_shells)]
        for vertex_id, shell_id in enumerate(shell_ids):
            shells[shell_id].append(vertex_id)

        return shells

    def get_connected_vertices(self, vtx_indices: list[int]) -> list[list[int]]:
        """Get the connected vertices.

        Args:
            vtx_indices (list[int]): The vertex indices.

        Returns:
            list[list[int]]: The connected vertices.
        """
        mit_vertex = om.MItMeshVertex(self._dag_path)
        num_vertices = self._mesh_fn.numVertices

        connected_vertices = []
        for index in vtx_indices:
            if index >= num_vertices:
                raise ValueError(f"Vertex index out of range: {index}")

            mit_vertex.setIndex(index)
            connected_vertices.append(list(mit_vertex.getConnectedVertices()))

        return connected_vertices

    def get_vertex_indices(self, components) -> list[int]:
        """Get the component indices.

        Args:
            components (list[str]): The component names.

        Returns:
            list[int]: The component indices.
        """
        return self.get_components_indices(components, "vertex")

    def get_vertex_components(self, indices: list[int]) -> list[str]:
        """Get the component names from the indices.

        Args:
            indices (list[int]): The component indices.

        Returns:
            list[str]: The component names.
        """
        return self.get_components_from_indices(indices, "vertex")

    def set_vertex_positions(self, positions: list[tuple[float, float, float]] | list[om.MPoint], vtx_indices: list[int] | None = None) -> None:
        """Set the vertex positions.

        Args:
            positions (list[tuple[float, float, float]] | list[om.MPoint]): The vertex positions.
            vtx_indices (list[int] | None): The vertex indices. If None, set all vertex positions.

        Raises:
            ValueError: If the number of positions doesn't match the number of indices, or if indices are out of range.
        """
        # Convert positions to MPointArray
        point_array = om.MPointArray()
        for pos in positions:
            if isinstance(pos, om.MPoint):
                point_array.append(pos)
            else:
                point_array.append(om.MPoint(pos[0], pos[1], pos[2]))

        if vtx_indices is None:
            # Set all vertex positions
            if len(positions) != self._mesh_fn.numVertices:
                raise ValueError(f"Number of positions ({len(positions)}) doesn't match number of vertices ({self._mesh_fn.numVertices})")
            self._mesh_fn.setPoints(point_array, om.MSpace.kWorld)
        else:
            # Set specific vertex positions
            if len(positions) != len(vtx_indices):
                raise ValueError(f"Number of positions ({len(positions)}) doesn't match number of indices ({len(vtx_indices)})")

            num_vertices = self._mesh_fn.numVertices
            for index in vtx_indices:
                if index >= num_vertices:
                    raise ValueError(f"Vertex index out of range: {index}")

            # Get current points
            current_points = self._mesh_fn.getPoints(om.MSpace.kWorld)

            # Update specified vertices
            for i, index in enumerate(vtx_indices):
                current_points[index] = point_array[i]

            # Set all points back
            self._mesh_fn.setPoints(current_points, om.MSpace.kWorld)

    def num_vertices(self) -> int:
        """Get the number of vertices.

        Returns:
            int: The number of vertices.
        """
        return self._mesh_fn.numVertices
