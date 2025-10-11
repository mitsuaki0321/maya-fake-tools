"""
Mesh edge operations.
"""

from logging import getLogger

import maya.api.OpenMaya as om

from .lib_mesh import MeshComponent

logger = getLogger(__name__)


class MeshEdge(MeshComponent):
    """Mesh edge class."""

    def get_edge_position(self, edge_ids: list[int]) -> list[om.MPoint]:
        """Get the edge center position.

        Args:
            edge_ids (list[int]): The edge ids.

        Returns:
            list[om.MPoint]: The edge positions.
        """
        num_edges = self._mesh_fn.numEdges

        mit_edge = om.MItMeshEdge(self._dag_path)

        points = []
        for edge_id in edge_ids:
            if edge_id >= num_edges:
                logger.warning(f"Invalid edge id: {edge_id}")
                continue

            mit_edge.setIndex(edge_id)
            points.append(mit_edge.center(om.MSpace.kWorld))

        return points

    def get_edge_normal(self, edge_ids: list[int]) -> list[om.MVector]:
        """Get the edge normal.

        Args:
            edge_ids (list[int]): The edge ids.

        Returns:
            list[om.MVector]: The edge normals.
        """
        num_edges = self._mesh_fn.numEdges

        normals = []
        for edge_id in edge_ids:
            if edge_id >= num_edges:
                continue

            edge_vertices = self._mesh_fn.getEdgeVertices(edge_id)
            vertex_normals = [self._mesh_fn.getVertexNormal(vertex_id, om.MSpace.kWorld) for vertex_id in edge_vertices]
            edge_normal = (vertex_normals[0] + vertex_normals[1]) / 2.0

            normals.append(edge_normal)

        return normals

    def get_edge_tangent(self, edge_ids: list[int]) -> list[om.MVector]:
        """Get the edge tangent.

        Args:
            edge_ids (list[int]): The edge ids.

        Returns:
            list[om.MVector]: The edge tangents.
        """
        num_edges = self._mesh_fn.numEdges

        mit_vertex = om.MItMeshVertex(self._dag_path)

        def _get_vertex_tangents(edge_vertices: list[int]) -> list[om.MVector]:
            """Get the vertex tangents."""
            result_tangents = []
            for index in edge_vertices:
                mit_vertex.setIndex(index)
                connected_face_ids = mit_vertex.getConnectedFaces()
                tangent = om.MVector(0.0, 0.0, 0.0)

                for face_id in connected_face_ids:
                    try:
                        tangent += self._mesh_fn.getFaceVertexTangent(face_id, index, om.MSpace.kWorld)
                    except RuntimeError:
                        logger.warning(f"Failed to get tangent for vertex: {index}")

                if len(connected_face_ids) > 1:
                    tangent /= len(connected_face_ids)

                tangent.normalize()
                result_tangents.append(tangent)

            return result_tangents

        tangents = []
        for edge_id in edge_ids:
            if edge_id >= num_edges:
                continue

            edge_vertices = self._mesh_fn.getEdgeVertices(edge_id)
            vertex_tangents = _get_vertex_tangents(edge_vertices)
            edge_tangent = (vertex_tangents[0] + vertex_tangents[1]) / 2.0

            tangents.append(edge_tangent)

        return tangents

    def get_edge_vector(self, edge_ids: list[int], normalize: bool = False) -> list[om.MVector]:
        """Get the vector between the two vertices that make up the edge.

        Args:
            edge_ids (list[int]): The edge ids.
            normalize (bool): Whether to normalize the vector. Default is False.

        Returns:
            list[om.MVector]: The edge vectors.
        """
        num_edges = self._mesh_fn.numEdges

        vectors = []
        for edge_id in edge_ids:
            if edge_id >= num_edges:
                continue

            edge_vertices = self._mesh_fn.getEdgeVertices(edge_id)
            vector = self._mesh_fn.getPoint(edge_vertices[1], om.MSpace.kWorld) - self._mesh_fn.getPoint(edge_vertices[0], om.MSpace.kWorld)

            if normalize:
                vector.normalize()

            vectors.append(vector)

        return vectors

    def get_edge_indices(self, components) -> list[int]:
        """Get the component indices.

        Args:
            components (list[str]): The component names.

        Returns:
            list[int]: The component indices.
        """
        return self.get_components_indices(components, "edge")

    def get_edge_components(self, indices: list[int]) -> list[str]:
        """Get the component names from the indices.

        Args:
            indices (list[int]): The component indices.

        Returns:
            list[str]: The component names.
        """
        return self.get_components_from_indices(indices, "edge")

    def num_edges(self) -> int:
        """Get the number of edges.

        Returns:
            int: The number of edges.
        """
        return self._mesh_fn.numEdges
