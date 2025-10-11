"""Bounding Box functions."""

from abc import ABC, abstractmethod
from logging import getLogger

import maya.api.OpenMaya as om
import numpy as np
from scipy.spatial import ConvexHull

logger = getLogger(__name__)


class BoundingBox(ABC):
    """Abstract base class for bounding boxes."""

    def __init__(self, points: list[list[float]] | np.ndarray):
        """Initialize the BoundingBox with a list of points.

        Args:
            points (Union[list[list[float]], np.ndarray]): The list of points. Each point must be a 3-element list or numpy array.
        """
        if not isinstance(points, list | np.ndarray):
            raise ValueError("Points must be a list or numpy array.")

        if isinstance(points, list):
            points = np.array(points)

        if not all(isinstance(pt, list | np.ndarray) and len(pt) == 3 for pt in points):
            raise ValueError("Points must be a list of 3-element lists or numpy arrays.")

        self._points = points

    @property
    @abstractmethod
    def center(self) -> np.ndarray:
        """Get the center of the bounding box.

        Returns:
            np.ndarray: The center of the bounding box.
        """
        pass

    @property
    @abstractmethod
    def scale(self) -> np.ndarray:
        """Get the scale of the bounding box.

        Returns:
            np.ndarray: The scale of the bounding box.
        """
        pass

    @property
    @abstractmethod
    def rotation(self) -> np.ndarray:
        """Get the rotation of the bounding box.

        Returns:
            np.ndarray: The rotation of the bounding box.
        """
        pass

    @property
    @abstractmethod
    def volume(self) -> float:
        """Get the volume of the bounding box.

        Returns:
            float: The volume of the bounding box.
        """
        pass

    @property
    @abstractmethod
    def rotation_matrix(self) -> np.ndarray:
        """Get the rotation matrix of the bounding box.

        Returns:
            np.ndarray: The rotation matrix of the bounding box.
        """
        pass

    def _rotation_matrix_to_euler_angles(self, R):
        """Convert the rotation matrix to Euler angles.

        Args:
            R (np.ndarray): The rotation matrix.

        Returns:
            np.ndarray: The Euler angles.
        """
        transform_matrix = om.MMatrix(
            [
                R[0, 0],
                R[0, 1],
                R[0, 2],
                0,
                R[1, 0],
                R[1, 1],
                R[1, 2],
                0,
                R[2, 0],
                R[2, 1],
                R[2, 2],
                0,
                0.0,
                0.0,
                0.0,
                1.0,
            ]
        )
        transform_matrix = om.MTransformationMatrix(transform_matrix)
        euler_rotation = transform_matrix.rotation()

        return np.degrees([euler_rotation.x, euler_rotation.y, euler_rotation.z])


class WorldBoundingBox(BoundingBox):
    """Class representing a bounding box in world coordinates."""

    @property
    def center(self) -> np.ndarray:
        """Get the center of the bounding box.

        Returns:
            np.ndarray: The center of the bounding box.
        """
        min_pt = np.min(self._points, axis=0)
        max_pt = np.max(self._points, axis=0)
        return (min_pt + max_pt) / 2

    @property
    def scale(self) -> np.ndarray:
        """Get the scale of the bounding box.

        Returns:
            np.ndarray: The scale of the bounding box.
        """
        return np.ptp(self._points, axis=0)

    @property
    def rotation(self) -> np.ndarray:
        """Get the rotation of the bounding box.

        Returns:
            np.ndarray: The rotation of the bounding box.
        """
        return np.zeros(3)

    @property
    def volume(self) -> float:
        """Get the volume of the bounding box.

        Returns:
            float: The volume of the bounding box.
        """
        return np.prod(self.scale)

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Get the rotation matrix of the bounding box.

        Returns:
            np.ndarray: The rotation matrix of the bounding box.
        """
        return np.eye(3)


class MinimumBoundingBox(BoundingBox):
    """Class representing the bounding box with the minimum volume."""

    def __init__(self, points: list[list[float]] | np.ndarray):
        """Initialize the MinimumBoundingBox with a list of points.

        Args:
            points (Union[list[list[float]], np.ndarray]): The list of points.
        """
        super().__init__(points)

        self._volume, self._R, self._min_pt, self._max_pt = self._compute_minimum_bounding_box()

    def _compute_minimum_bounding_box(self):
        """Compute the minimum bounding box.

        Returns:
            tuple[float, np.ndarray, np.ndarray, np.ndarray]: The volume, rotation matrix, min point, and max point.
        """
        hull = ConvexHull(self._points)
        best_volume = np.inf
        best_R = None
        best_min = None
        best_max = None

        for simplex in hull.simplices:
            face_pts = self._points[simplex]
            v1 = face_pts[1] - face_pts[0]
            v2 = face_pts[2] - face_pts[0]
            normal = np.cross(v1, v2)
            norm = np.linalg.norm(normal)
            if norm < 1e-8:
                continue
            normal = normal / norm

            u = v1 - np.dot(v1, normal) * normal
            u_norm = np.linalg.norm(u)
            if u_norm < 1e-8:
                continue
            u = u / u_norm
            v = np.cross(normal, u)

            R = np.vstack([u, v, normal])

            rot_points = np.dot(self._points, R.T)
            min_pt = np.min(rot_points, axis=0)
            max_pt = np.max(rot_points, axis=0)
            extents = max_pt - min_pt
            volume = np.prod(extents)

            if volume < best_volume:
                best_volume = volume
                best_R = R
                best_min = min_pt
                best_max = max_pt

        return best_volume, best_R, best_min, best_max

    @property
    def center(self) -> np.ndarray:
        """Get the center of the bounding box.

        Returns:
            np.ndarray: The center of the bounding box.
        """
        local_center = (self._min_pt + self._max_pt) / 2
        return np.dot(local_center, self._R)

    @property
    def scale(self) -> np.ndarray:
        """Get the scale of the bounding box.

        Returns:
            np.ndarray: The scale of the bounding box.
        """
        return self._max_pt - self._min_pt

    @property
    def rotation(self) -> np.ndarray:
        """Get the rotation of the bounding box.

        Returns:
            np.ndarray: The rotation of the bounding box.
        """
        return self._rotation_matrix_to_euler_angles(self._R)

    @property
    def volume(self) -> float:
        """Get the volume of the bounding box.

        Returns:
            float: The volume of the bounding box.
        """
        return self._volume

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Get the rotation matrix of the bounding box.

        Returns:
            np.ndarray: The rotation matrix of the bounding box.
        """
        return self._R


class AxisAlignedBoundingBox(BoundingBox):
    """Class representing a bounding box with the minimum volume around an arbitrary axis."""

    def __init__(
        self,
        points: list[list[float]] | np.ndarray,
        axis_direction: list[float] | np.ndarray = (0, 1, 0),
        axis: str = "y",
        theta_samples: int = 360,
    ):
        """Initialize the AxisAlignedBoundingBox with a list of points.

        Args:
            points (Union[list[list[float]], np.ndarray]): The list of points.
            axis_direction (Union[list[float], np.ndarray]): The direction vector of the fixed axis.
            axis (str): The axis in the local coordinate system to which the fixed axis is assigned.
                        One of "x", "y", or "z". Default is "z" (i.e., axis_direction is assigned to the local Z axis).
            theta_sampling (int): The number of divisions to evaluate θ (0 to 2π). Default is 360.
        """
        super().__init__(points)
        self._axis_origin = (np.min(self._points, axis=0) + np.max(self._points, axis=0)) / 2.0
        self._axis = np.array(axis_direction, dtype=float)
        self._axis = self._axis / np.linalg.norm(self._axis)
        self._axis_spec = axis.lower()
        if self._axis_spec not in ("x", "y", "z"):
            raise ValueError("axis must be one of 'x', 'y', or 'z'")
        self._theta_samples = theta_samples

        (
            self._volume,
            self._R,
            self._min_pt,
            self._max_pt,
            self._translation,
            self._center_local,
            self._fixed_index,
        ) = self._compute_minimum_bounding_box_on_axis()

    def _compute_minimum_bounding_box_on_axis(self):
        """Compute the minimum bounding box with the specified fixed axis (self._axis_direction)
        placed as the fixed axis in the local coordinate system, specified by _axis_spec.
        Perform a grid search over θ (0 to 2π) to find the bounding box with the minimum volume.
        The origin of the axis is the centroid of the point cloud (self._axis_origin).

        Returns:
            tuple containing:
                - minimum volume (float)
                - rotation matrix R (3*3 numpy.ndarray) (each row is a local axis)
                - local min point (numpy.ndarray)
                - local max point (numpy.ndarray)
                - optimal world translation T (numpy.ndarray)
                - local center (numpy.ndarray)
                - fixed_index (int): The index of the fixed axis in the local coordinate system (0: x, 1: y, 2: z)
        """
        best_volume = np.inf
        best_R = None
        best_min = None
        best_max = None
        best_translation = None
        best_center_local = None

        fixed_index = {"x": 0, "y": 1, "z": 2}[self._axis_spec]

        ref = np.array([1, 0, 0], dtype=float)
        if np.allclose(np.abs(np.dot(ref, self._axis)), 1.0, atol=1e-6):
            ref = np.array([0, 1, 0], dtype=float)

        u0 = ref - np.dot(ref, self._axis) * self._axis
        u0 = u0 / np.linalg.norm(u0)
        v0 = np.cross(self._axis, u0)

        desired_center = self._axis_origin

        for i in range(self._theta_samples):
            theta = 2 * np.pi * i / self._theta_samples
            u = np.cos(theta) * u0 + np.sin(theta) * v0
            v = np.cross(self._axis, u)

            if self._axis_spec == "x":
                R_candidate = np.vstack([self._axis, u, v])
            elif self._axis_spec == "y":
                R_candidate = np.vstack([u, self._axis, v])
            else:
                R_candidate = np.vstack([u, v, self._axis])

            rotated = np.dot(self._points, R_candidate.T)
            min_local = np.min(rotated, axis=0)
            max_local = np.max(rotated, axis=0)
            volume_candidate = np.prod(max_local - min_local)

            center_local = (min_local + max_local) / 2.0
            T_candidate = desired_center - center_local[fixed_index] * self._axis

            if volume_candidate < best_volume:
                best_volume = volume_candidate
                best_R = R_candidate
                best_min = min_local
                best_max = max_local
                best_translation = T_candidate
                best_center_local = center_local

        return (
            best_volume,
            best_R,
            best_min,
            best_max,
            best_translation,
            best_center_local,
            fixed_index,
        )

    @property
    def center(self) -> np.ndarray:
        """
        Get the center of the bounding box.

        Returns:
            np.ndarray: The center of the bounding box.
        """
        return self._translation + self._center_local[self._fixed_index] * self._axis

    @property
    def scale(self) -> np.ndarray:
        """
        Get the scale of the bounding box.

        Returns:
            np.ndarray: The scale of the bounding box.
        """
        return self._max_pt - self._min_pt

    @property
    def rotation(self) -> np.ndarray:
        """
        Get the rotation of the bounding box.

        Returns:
            np.ndarray: The rotation of the bounding box.
        """
        return self._rotation_matrix_to_euler_angles(self._R)

    @property
    def volume(self) -> float:
        """
        Get the volume of the bounding box.

        Returns:
            float: The volume of the bounding box.
        """
        return self._volume

    @property
    def rotation_matrix(self) -> np.ndarray:
        """
        Get the rotation matrix of the bounding box.

        Returns:
            np.ndarray: The rotation matrix of the bounding box.
        """
        return self._R
