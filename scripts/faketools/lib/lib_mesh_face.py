"""
Mesh face operations.
"""

from logging import getLogger

import maya.api.OpenMaya as om

from .lib_mesh import MeshComponent

logger = getLogger(__name__)


class MeshFace(MeshComponent):
    """Mesh face class."""

    def get_face_position(self, face_ids: list[int]) -> list[om.MPoint]:
        """Get the face center position.

        Args:
            face_ids (list[int]): The face ids.

        Returns:
            list[om.MPoint]: The face positions.
        """
        num_faces = self._mesh_fn.numPolygons

        mit_poly = om.MItMeshPolygon(self._dag_path)

        points = []
        for face_id in face_ids:
            if face_id >= num_faces:
                logger.warning(f"Face id is invalid: {face_id}")
                continue

            mit_poly.setIndex(face_id)
            points.append(mit_poly.center(om.MSpace.kWorld))

        return points

    def get_face_normal(self, face_ids: list[int]) -> list[om.MVector]:
        """Get the face normal.

        Args:
            face_ids (list[int]): The face ids.

        Returns:
            list[om.MVector]: The face normals.
        """
        num_faces = self._mesh_fn.numPolygons

        normals = []
        for face_id in face_ids:
            if face_id >= num_faces:
                logger.warning(f"Invalid face id: {face_id}")
                continue

            normal = self._mesh_fn.getPolygonNormal(face_id, om.MSpace.kWorld)
            normals.append(normal)

        return normals

    def get_face_tangent(self, face_ids: list[int]) -> list[om.MVector]:
        """Get the face tangent.

        Args:
            face_ids (list[int]): The face ids.

        Returns:
            list[om.MVector]: The face tangents.
        """
        num_faces = self._mesh_fn.numPolygons

        mit_poly = om.MItMeshPolygon(self._dag_path)

        tangents = []
        for face_id in face_ids:
            if face_id >= num_faces:
                logger.warning(f"Invalid face id: {face_id}")
                continue

            mit_poly.setIndex(face_id)
            vertex_ids = mit_poly.getVertices()

            tangent = om.MVector(0.0, 0.0, 0.0)
            for vertex_id in vertex_ids:
                try:
                    tangent += self._mesh_fn.getFaceVertexTangent(face_id, vertex_id, om.MSpace.kWorld)
                except RuntimeError:
                    logger.warning(f"Failed to get tangent for face: {face_id}")

            tangent /= len(vertex_ids)
            tangent.normalize()

            tangents.append(tangent)

        return tangents

    def get_face_indices(self, components) -> list[int]:
        """Get the component indices.

        Args:
            components (list[str]): The component names.

        Returns:
            list[int]: The component indices.
        """
        return self.get_components_indices(components, "face")

    def get_face_components(self, indices: list[int]) -> list[str]:
        """Get the component names from the indices.

        Args:
            indices (list[int]): The component indices.

        Returns:
            list[str]: The component names.
        """
        return self.get_components_from_indices(indices, "face")

    def num_faces(self) -> int:
        """Get the number of faces.

        Returns:
            int: The number of faces.
        """
        return self._mesh_fn.numPolygons
