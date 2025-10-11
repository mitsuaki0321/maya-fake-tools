"""
Mesh component conversion operations.
"""

from logging import getLogger

import maya.api.OpenMaya as om

from .lib_mesh import MeshComponent

logger = getLogger(__name__)


class MeshComponentConversion(MeshComponent):
    """Mesh component conversion class."""

    def face_to_vertices(self, face_ids: list[int], flatten: bool = False) -> list[list[int]]:
        """Convert the face ids to vertices.

        Args:
            face_ids (list[int]): The face ids.
            flatten (bool): Whether to flatten the vertices. Default is False.

        Returns:
            list[list[int]]: The vertices.
        """
        num_faces = self._mesh_fn.numPolygons

        vertices = []
        for face_id in face_ids:
            if face_id >= num_faces:
                logger.warning(f"Invalid face id: {face_id}")
                continue

            if flatten:
                vertex_ids = self._mesh_fn.getPolygonVertices(face_id)
                for vertex_id in vertex_ids:
                    if vertex_id not in vertices:
                        vertices.append(vertex_id)
            else:
                vertices.append(list(self._mesh_fn.getPolygonVertices(face_id)))

        return vertices

    def edge_to_vertices(self, edge_ids: list[int], flatten: bool = False) -> list[list[int]]:
        """Convert the edge ids to vertices.

        Args:
            edge_ids (list[int]): The edge ids.

        Returns:
            list[list[int]]: The vertices.
        """
        num_edges = self._mesh_fn.numEdges

        vertices = []
        for edge_id in edge_ids:
            if edge_id >= num_edges:
                logger.warning(f"Invalid edge id: {edge_id}")
                continue

            if flatten:
                vertex_ids = self._mesh_fn.getEdgeVertices(edge_id)
                for vertex_id in vertex_ids:
                    if vertex_id not in vertices:
                        vertices.append(vertex_id)
            else:
                vertices.append(list(self._mesh_fn.getEdgeVertices(edge_id)))

        return vertices

    def vertex_to_faces(self, vertex_ids: list[int], flatten: bool = False) -> list[list[int]]:
        """Convert the vertex ids to faces.

        Args:
            vertex_ids (list[int]): The vertex ids.
            flatten (bool): Whether to flatten the faces. Default is False.

        Returns:
            list[list[int]]: The faces.
        """
        mit_vertex = om.MItMeshVertex(self._dag_path)
        num_vertices = self._mesh_fn.numVertices

        faces = []
        for vertex_id in vertex_ids:
            if vertex_id >= num_vertices:
                logger.warning(f"Invalid vertex id: {vertex_id}")
                continue

            mit_vertex.setIndex(vertex_id)
            face_ids = mit_vertex.getConnectedFaces()
            if flatten:
                for face_id in face_ids:
                    if face_id not in faces:
                        faces.append(face_id)
            else:
                faces.append(list(face_ids))

        return faces
