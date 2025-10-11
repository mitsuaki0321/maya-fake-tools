"""
Retargeting functions.
"""

from logging import getLogger

import numpy as np
from scipy.linalg import pinv
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

logger = getLogger(__name__)


class RBFDeform:
    """RBF Deformation class.

    This class is used to deform points using Radial Basis Functions (RBF).
    It uses src_points (before deformation) and trg_points (after deformation) to deform deform_points.

    """

    def __init__(self, src_points: np.ndarray, data_type: type = np.float32):
        """Initialize the RBFDeform class.

        Args:
            src_points (np.ndarray): The source points.
            data_type (type): The data type, default is np.float32.
        """
        self._src_points = src_points
        self._data_type = data_type

    def compute_weights(self, trg_points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute the RBF weights for the target points.

        Args:
            trg_points (np.ndarray): The target points.

        Returns:
            tuple[np.ndarray, np.ndarray, np.ndarray]: The weights for x, y, and z.
        """
        mat_cc = np.insert(self._src_points, 3, 1.0, axis=1)

        mat_cct = mat_cc.transpose()
        A = mat_cct[..., :, np.newaxis]
        B = mat_cct[..., np.newaxis, :]
        mat_k = np.sqrt(((A - B) ** 2).sum(axis=0))

        mat_a = np.c_[mat_k, mat_cc]
        mat_a = np.r_[mat_a, np.c_[mat_cct, np.zeros([4, 4])]]  # base matrix

        trg_x, trg_y, trg_z = np.asarray(trg_points, dtype=self._data_type).T
        trg_x = np.append(trg_x, [0.0, 0.0, 0.0, 0.0])
        trg_y = np.append(trg_y, [0.0, 0.0, 0.0, 0.0])
        trg_z = np.append(trg_z, [0.0, 0.0, 0.0, 0.0])

        weights_x = self._solve_weight(mat_a, trg_x)
        weights_y = self._solve_weight(mat_a, trg_y)
        weights_z = self._solve_weight(mat_a, trg_z)

        return weights_x, weights_y, weights_z

    def compute_points(
        self, deform_points: np.ndarray, weight_x: np.ndarray, weight_y: np.ndarray, weight_z: np.ndarray
    ) -> list[tuple[float, float, float]]:
        """Generate final positions by applying the RBF weights to the source and target points.

        Args:
            deform_points (np.ndarray): The deform points.
            weight_x (np.ndarray): Weights for x-axis.
            weight_y (np.ndarray): Weights for y-axis.
            weight_z (np.ndarray): Weights for z-axis.

        Returns:
            list[tuple[float, float, float]]: The transformed (x, y, z) positions.
        """
        num_out = len(self._src_points)

        mat_p = np.insert(deform_points, 3, 1.0, axis=1)

        out_x = np.dot(mat_p, weight_x[num_out:])
        out_y = np.dot(mat_p, weight_y[num_out:])
        out_z = np.dot(mat_p, weight_z[num_out:])

        AB = cdist(deform_points, self._src_points, "euclidean")

        out_x = np.dot(AB, weight_x[:num_out]) + out_x
        out_y = np.dot(AB, weight_y[:num_out]) + out_y
        out_z = np.dot(AB, weight_z[:num_out]) + out_z

        return [(float(px), float(py), float(pz)) for px, py, pz in zip(out_x, out_y, out_z, strict=False)]

    def _solve_weight(self, base_matrix: np.ndarray, trg_points: np.ndarray) -> np.ndarray:
        """Solve the system of linear equations for the RBF. Uses a sparse solver and falls back to pinv if necessary.

        Args:
            base_matrix (np.ndarray): The RBF base matrix.
            trg_points (np.ndarray): The extended target array for one axis.

        Returns:
            np.ndarray: The resulting weight array.
        """
        if not isinstance(base_matrix, csr_matrix):
            base_matrix = csr_matrix(base_matrix)
        try:
            return spsolve(base_matrix, trg_points)
        except np.linalg.LinAlgError:
            logger.warning("Singular matrix detected. Using pinv instead.")
            return np.dot(pinv(base_matrix), trg_points)


class IndexQueryMethod:
    """Index query method base class."""

    def get_indices(self, mesh_points: np.ndarray, positions: np.ndarray) -> list[list[int]]:
        """Get vertex indices for each position.

        Args:
            mesh_points (np.ndarray): The mesh points array.
            positions (np.ndarray): The query positions array.

        Returns:
            list[list[int]]: The vertex indices for each position.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Method not implemented.")


class DistanceIndexQuery(IndexQueryMethod):
    """Distance index query class.

    This class is used to get the specified number of closest vertices to each specified position.
    """

    def __init__(self, num_vertices=10):
        """Initialize the DistanceIndexQuery class.

        Args:
            num_vertices (int): The number of vertices to return.
        """
        self.__num_vertices = num_vertices

    def get_indices(self, mesh_points: np.ndarray, positions: np.ndarray) -> list[list[int]]:
        """Get the closest vertices to each specified position.

        Args:
            mesh_points (np.ndarray): The mesh points array.
            positions (np.ndarray): The query positions array.

        Returns:
            list[list[int]]: The closest vertex indices for each position.
        """
        # Ensure inputs are numpy arrays
        mesh_points = np.asarray(mesh_points)
        positions = np.asarray(positions)

        # Use KDTree for efficient nearest neighbor queries
        kd_tree = cKDTree(mesh_points)
        _, indices = kd_tree.query(positions, k=self.__num_vertices)

        # Convert to list of lists (handle single position case)
        if positions.ndim == 1 or len(positions) == 1:
            return [indices.tolist()]
        return [idx.tolist() for idx in indices]


class RadiusIndexQuery(IndexQueryMethod):
    """Radius index query class.

    This class is used to get the vertices within the specified radius for each specified position.
    """

    def __init__(self, radius: float = 1.0):
        """Initialize the RadiusIndexQuery class.

        Args:
            radius (float): The radius.
        """
        self._radius = radius

    def get_indices(self, mesh_points: np.ndarray, positions: np.ndarray) -> list[list[int]]:
        """Get the vertices within the radius for each position.

        Args:
            mesh_points (np.ndarray): The target mesh points array.
            positions (np.ndarray): The radius center positions array.

        Returns:
            list[list[int]]: The vertex indices within the radius for each position.
        """
        # Ensure inputs are numpy arrays
        mesh_points = np.asarray(mesh_points)
        positions = np.asarray(positions)

        # Build KDTree once
        kd_tree = cKDTree(mesh_points)

        # Query all positions (query_ball_point doesn't support batch queries directly)
        return [kd_tree.query_ball_point(position, self._radius) for position in positions]


class NearestRadiusIndexQuery(IndexQueryMethod):
    """Nearest radius index query class.

    This class is used to get the vertices within the radius for each specified position,
    where the radius is determined by the distance to the nearest vertex.
    """

    def __init__(self, radius_multiplier: float = 1.5):
        """Initialize the NearestRadiusIndexQuery class.

        Args:
            radius_multiplier (float): The radius multiplier.
        """
        self._radius_multiplier = radius_multiplier

    def get_indices(self, mesh_points: np.ndarray, positions: np.ndarray) -> list[list[int]]:
        """Get the vertices within the radius for each position.

        Args:
            mesh_points (np.ndarray): The target mesh points array.
            positions (np.ndarray): The radius center positions array.

        Returns:
            list[list[int]]: The vertex indices within the radius for each position.
        """
        # Ensure inputs are numpy arrays
        mesh_points = np.asarray(mesh_points)
        positions = np.asarray(positions)

        # Build KDTree once
        kd_tree = cKDTree(mesh_points)

        # Query all positions with adaptive radius
        result_indices = []
        for position in positions:
            # Find nearest vertex distance
            dist, _ = kd_tree.query(position)
            # Calculate effective radius
            effective_radius = self._radius_multiplier * dist
            # Query vertices within effective radius
            indices = kd_tree.query_ball_point(position, effective_radius)
            result_indices.append(indices)

        return result_indices
