"""Position calculation methods for retarget transforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import math

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np

from ....lib import lib_retarget

logger = logging.getLogger(__name__)


class PositionBase(ABC):
    """Position base class."""

    @abstractmethod
    def export_data(self, positions: list[list[float]], **kwargs) -> dict:
        """Export the positions.

        Args:
            positions (list[list[float]]): The positions.

        Returns:
            dict: The exported data.
        """
        raise NotImplementedError("Method not implemented.")

    @abstractmethod
    def import_data(self, data: dict) -> list[list[float]]:
        """Import the data.

        Args:
            data (dict): The data.

        Returns:
            list[list[float]]: The imported positions.
        """
        raise NotImplementedError("Method not implemented.")


class DefaultPosition(PositionBase):
    """Default positions import/export class.

    A class that simply returns the input positions and rotations as they are.
    """

    def export_data(self, positions: list[list[float]], **kwargs) -> dict:
        """Export the positions.

        Args:
            positions (list[list[float]]): The positions.

        Keyword Args:
            rotations (list[list[float]]): The euler rotations. Default is [].

        Returns:
            dict: The exported data.
        """
        rotations = kwargs.get("rotations", [])
        return {"positions": positions, "rotations": rotations}

    def import_data(self, data: dict) -> tuple[list[list[float]], list[list[float]]]:
        """Import the data.

        Args:
            data (dict): exported data.

        Returns:
            tuple[list[list[float]], list[list[float]]]: The imported positions and rotations.
        """
        if "positions" not in data:
            raise ValueError("Missing positions data.")

        positions = data["positions"]
        rotations = data.get("rotations", [])
        if rotations and len(rotations) != len(positions):
            raise ValueError("Rotations and positions length mismatch.")

        return positions, rotations


class MeshPosition(PositionBase):
    """Mesh positions import/export base class."""

    def __init__(self, mesh: str):
        """Initialize the MeshPositions class.

        Args:
            mesh (str): The mesh name.
        """
        if not cmds.objExists(mesh):
            raise ValueError(f"Mesh does not exist: {mesh}")

        if cmds.objectType(mesh) != "mesh":
            raise ValueError(f"Not a mesh: {mesh}")

        selection_list = om.MSelectionList()
        selection_list.add(mesh)

        self.mesh = mesh
        self.dag_path = selection_list.getDagPath(0)
        self.mesh_fn = om.MFnMesh(self.dag_path)


class MeshBaryPosition(MeshPosition):
    """Mesh positions import/export class using barycentric coordinates."""

    def __init__(self, target_mesh: str):
        """Initialize the MeshPositions class.

        Args:
            target_mesh (str): The mesh name.
        """
        super().__init__(target_mesh)

        self.mit_polygon = om.MItMeshPolygon(self.dag_path)

        # Unify calculations in object space
        self.mesh_intersector = om.MMeshIntersector()
        self.mesh_intersector.create(self.dag_path.node(), om.MMatrix())

    def export_data(self, positions: list[list[float]], **kwargs) -> dict:
        """Export the positions to barycentric coordinates.

        Args:
            positions (list[list[float]]): The positions.

        Keyword Args:
            rotations (list[list[float]]): The euler rotations. Default is [].
            max_distance (float): The maximum distance. Default is 100.0.

        Returns:
            dict: The barycentric coordinates.
        """
        rotations = kwargs.get("rotations", [])
        if rotations and len(rotations) != len(positions):
            raise ValueError("Rotations and positions length mismatch.")

        mesh_inverse_matrix = self.dag_path.inclusiveMatrixInverse()

        data = {}
        data["num_vertices"] = self.mesh_fn.numVertices

        weight_data = []
        for i, position in enumerate(positions):
            # Get the position data
            position = om.MPoint(position) * mesh_inverse_matrix

            point_on_mesh = self.mesh_intersector.getClosestPoint(position)
            u, v = point_on_mesh.barycentricCoords
            bary_data = {"weight": [u, v, 1.0 - u - v]}

            self.mit_polygon.setIndex(point_on_mesh.face)
            points, indices = self.mit_polygon.getTriangle(point_on_mesh.triangle, space=om.MSpace.kObject)
            bary_data["indices"] = list(indices)

            normal = om.MVector(point_on_mesh.normal)
            tangent = points[0] - points[1]
            rot_matrix = self._get_rotation_matrix(normal, tangent)
            closest_to_pos_vector = position - om.MPoint(point_on_mesh.point)
            if closest_to_pos_vector.length() < 1e-10:
                bary_data["position"] = [0.0, 0.0, 0.0]
            else:
                rot_matrix_inv_pos = closest_to_pos_vector * rot_matrix.inverse()
                bary_data["position"] = [rot_matrix_inv_pos.x, rot_matrix_inv_pos.y, rot_matrix_inv_pos.z]

            # Get the rotation data
            if rotations:
                rotation = [math.radians(rot) for rot in rotations[i]]
                quat = om.MEulerRotation(rotation, om.MEulerRotation.kXYZ).asQuaternion()
                point_quat = om.MTransformationMatrix(rot_matrix).rotation(True)
                diff_quat = (quat * point_quat.inverse()).normal()
                bary_data["rotation"] = [diff_quat.x, diff_quat.y, diff_quat.z, diff_quat.w]

            weight_data.append(bary_data)

        data["weights"] = weight_data

        return data

    def import_data(self, data: dict) -> tuple[list[list[float]], list[list[float]]]:
        """Import the barycentric coordinates.

        Args:
            data (dict): The barycentric coordinates.

        Returns:
            tuple[list[list[float]], list[list[float]]]: The positions and rotations.
        """
        mesh_matrix = self.dag_path.inclusiveMatrix()

        restored_positions = []
        restored_rotations = []

        weights = data.get("weights", [])

        for bary_data in weights:
            # Calculate the restored position
            points = [self.mesh_fn.getPoint(i) for i in bary_data["indices"]]
            weight = bary_data["weight"]
            restored_position = points[0] * weight[0]
            restored_position += points[1] * weight[1]
            restored_position += points[2] * weight[2]

            # Adjust position using the stored offset and rotation matrix
            offset_vector = om.MVector(bary_data["position"])
            point_on_mesh = self.mesh_intersector.getClosestPoint(restored_position)
            normal = om.MVector(point_on_mesh.normal)
            tangent = points[0] - points[1]
            rot_matrix = self._get_rotation_matrix(normal, tangent)
            restored_position += offset_vector * rot_matrix
            restored_position *= mesh_matrix

            restored_positions.append([restored_position.x, restored_position.y, restored_position.z])

            # Restore rotation if present
            rotation_data = bary_data.get("rotation")
            if rotation_data:
                rotation_quat = om.MQuaternion(rotation_data[0], rotation_data[1], rotation_data[2], rotation_data[3])
                rotation_quat = rotation_quat * om.MTransformationMatrix(rot_matrix).rotation(True)
                euler_rotation = rotation_quat.asEulerRotation()
                restored_rotations.append([math.degrees(euler_rotation.x), math.degrees(euler_rotation.y), math.degrees(euler_rotation.z)])
            else:
                logger.debug("No rotation data found.")
                restored_rotations.append([0.0, 0.0, 0.0])

        return restored_positions, restored_rotations

    def _get_rotation_matrix(self, vector_a: om.MVector, vector_b: om.MVector) -> om.MMatrix:
        """Get the rotation matrix.

        Args:
            vector_a (om.MVector): The first vector.
            vector_b (om.MVector): The second vector.

        Returns:
            om.MMatrix: The rotation matrix.
        """
        vector_a.normalize()
        vector_b.normalize()
        vector_b = (vector_b - (vector_a * vector_b) * vector_a).normal()
        cross_product_vector = vector_a ^ vector_b

        matrix = om.MMatrix(
            [
                vector_a.x,
                vector_a.y,
                vector_a.z,
                0.0,
                vector_b.x,
                vector_b.y,
                vector_b.z,
                0.0,
                cross_product_vector.x,
                cross_product_vector.y,
                cross_product_vector.z,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ]
        )

        return matrix


class MeshRBFPosition(MeshPosition):
    """Mesh positions import/export class using RBF."""

    _data_type = np.float32

    def export_data(self, positions: list[list[float]], method_instance: lib_retarget.IndexQueryMethod, **kwargs) -> dict:
        """Export the positions to RBF-like interpolation.

        Args:
            positions (list[list[float]]): The positions.
            method_instance (IndexQueryMethod): The index query method instance.

        Keyword Args:
            rotations (list[list[float]]): The euler rotations. Default is [].

        Returns:
            dict: The RBF-like interpolation.

        Raises:
            ValueError: If the mesh has less than 4 vertices or invalid method instance.
        """
        if self.mesh_fn.numVertices < 4:
            raise ValueError("Mesh must have at least 4 vertices.")

        if method_instance is None:
            raise ValueError("Index query method instance not provided.")

        if not isinstance(method_instance, lib_retarget.IndexQueryMethod):
            raise ValueError("Invalid index query method instance.")

        rotations = kwargs.get("rotations", [])
        rotation_positions = []
        if rotations:
            if len(rotations) != len(positions):
                raise ValueError("Rotations and positions length mismatch.")

            for position, rotation in zip(positions, rotations, strict=False):
                quat = om.MEulerRotation([math.radians(rot) for rot in rotation], om.MEulerRotation.kXYZ).asQuaternion()
                quat_mat = quat.asMatrix()
                x_vector = om.MVector(om.MVector.kXaxisVector) * quat_mat
                y_vector = om.MVector(om.MVector.kYaxisVector) * quat_mat

                x_hit_distance = self._intersect_length(position, x_vector)
                y_hit_distance = self._intersect_length(position, y_vector)

                if x_hit_distance == 0.0 and y_hit_distance == 0.0:
                    vector_length = 1.0
                else:
                    vector_length = min(x_hit_distance, y_hit_distance)

                x_point = om.MPoint(position) + x_vector * vector_length
                y_point = om.MPoint(position) + y_vector * vector_length

                rotation_positions.append([[x_point.x, x_point.y, x_point.z], [y_point.x, y_point.y, y_point.z]])

        vtx_positions = self._get_vtx_positions()
        indices = method_instance.get_indices(vtx_positions, positions)

        # Add vertices if the number of elements in indices is less than 4
        index_counts = [len(index) for index in indices]
        if not all([count >= 4 for count in index_counts]):
            distance_index_query = lib_retarget.DistanceIndexQuery(num_vertices=4)
            distance_indices = distance_index_query.get_indices(vtx_positions, positions)
            for i, count in enumerate(index_counts):
                if count < 4:
                    indices[i] = distance_indices[i]

        logger.debug(f"Exporting RBF-like interpolation with positions: {len(positions)}")

        return {"positions": positions, "vtx_positions": vtx_positions, "target_indices": indices, "rotation_positions": rotation_positions}

    def import_data(self, data: dict) -> tuple[list[list[float]], list[list[float]]]:
        """Import the RBF-like interpolation.

        Args:
            data (dict): The RBF-like interpolation.

        Returns:
            tuple[list[list[float]], list[list[float]]]: The positions and rotations.

        Raises:
            ValueError: If missing required data or length mismatch.
        """
        if "vtx_positions" not in data:
            raise ValueError("Missing vertex positions data.")

        trg_positions = data["positions"]
        trg_indices_list = data["target_indices"]
        src_positions_list = np.asarray(data["vtx_positions"])
        dst_positions_list = np.asarray(self._get_vtx_positions())

        trg_rotations_positions = data.get("rotation_positions", [])

        if len(src_positions_list) != len(dst_positions_list):
            raise ValueError(f"Source and destination positions length mismatch: src {len(src_positions_list)} != dest {len(dst_positions_list)}")

        computed_position_list = []
        computed_rotation_list = []
        for i in range(len(trg_positions)):
            src_positions = np.asarray(src_positions_list[trg_indices_list[i]])
            dst_positions = np.asarray(dst_positions_list[trg_indices_list[i]])

            if trg_rotations_positions:
                compute_positions = [trg_positions[i]] + trg_rotations_positions[i]
            else:
                compute_positions = [trg_positions[i]]
            compute_positions = np.asarray(compute_positions)

            rbf_deform = lib_retarget.RBFDeform(src_positions, data_type=self._data_type)
            weight_point_x, weight_point_y, weight_point_z = rbf_deform.compute_weights(dst_positions)
            computed_positions = rbf_deform.compute_points(compute_positions, weight_point_x, weight_point_y, weight_point_z)

            logger.debug(f"Computed positions: {computed_positions}")

            computed_position_list.append(computed_positions[0])

            if trg_rotations_positions:
                computed_rotation = self._vector_to_rotation(computed_positions[0], computed_positions[1], computed_positions[2])
                computed_rotation_list.append(computed_rotation)

        logger.debug(f"Imported RBF-like interpolation with positions: {len(trg_positions)}")

        return computed_position_list, computed_rotation_list

    def _get_vtx_positions(self) -> list[list[float]]:
        """Get the mesh positions.

        Returns:
            list[list[float]]: The mesh positions.
        """
        return [[point.x, point.y, point.z] for point in self.mesh_fn.getPoints(om.MSpace.kWorld)]

    def _vector_to_rotation(self, origin_point: list[float], x_point: list[float], y_point: list[float]) -> list[float]:
        """Convert the vectors to a euler rotation.

        Args:
            origin_point (list[float]): The origin point.
            x_point (list[float]): The x axis point.
            y_point (list[float]): The y axis point.

        Returns:
            list[float]: The euler rotation.
        """
        x_vector = om.MPoint(x_point) - om.MPoint(origin_point)
        y_vector = om.MPoint(y_point) - om.MPoint(origin_point)
        x_vector.normalize()
        y_vector.normalize()

        vector_ortho = (y_vector - (x_vector * y_vector) * x_vector).normal()

        z_vector = x_vector ^ vector_ortho

        matrix = om.MMatrix(
            [
                x_vector.x,
                x_vector.y,
                x_vector.z,
                0.0,
                y_vector.x,
                y_vector.y,
                y_vector.z,
                0.0,
                z_vector.x,
                z_vector.y,
                z_vector.z,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ]
        )

        rotation = om.MTransformationMatrix(matrix).rotation(asQuaternion=False)
        return [math.degrees(rot) for rot in rotation]

    def _intersect_length(self, origin_point: om.MPoint, direction_vector: om.MVector) -> float:
        """Get the intersection length.

        Args:
            origin_point (om.MPoint): The origin point.
            direction_vector (om.MVector): The direction vector.

        Returns:
            float: The intersection length.
        """
        ray_origin = om.MFloatPoint(origin_point)
        ray_direction = om.MFloatVector(direction_vector)

        hit_data = self.mesh_fn.closestIntersection(ray_origin, ray_direction, om.MSpace.kWorld, 100, False)

        if hit_data is None:
            return 0.0

        return hit_data[1]  # hitRayParam ( Parametric distance to the hit point along the ray. )


__all__ = ["PositionBase", "DefaultPosition", "MeshPosition", "MeshBaryPosition", "MeshRBFPosition"]
