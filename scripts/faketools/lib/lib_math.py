"""
Math functions.
"""

from collections.abc import Sequence
from logging import getLogger
import math

import maya.api.OpenMaya as om

logger = getLogger(__name__)


# Utilities


def round_up(value: float, *, decimal_places: int = 0) -> float:
    """Round up the value.

    Args:
        value (float): The value to round up.
        decimal_places (int): The number of decimal places. Default is 0.

    Returns:
        float: The rounded up value.
    """
    factor = 10**decimal_places
    return math.ceil(value * factor) / factor


def round_down(value: float, *, decimal_places: int = 0) -> float:
    """Round down the value.

    Args:
        value (float): The value to round down.
        decimal_places (int): The number of decimal places. Default is 0.

    Returns:
        float: The rounded down value.
    """
    factor = 10**decimal_places
    return math.floor(value * factor) / factor


# Distance


def get_distance(point_a: Sequence[float], point_b: Sequence[float]) -> float:
    """Get the distance between two points.

    Args:
        point_a (Sequence[float]): The first point.
        point_b (Sequence[float]): The second point.

    Returns:
        float: The distance.
    """
    # Using Maya's MVector for distance calculation
    vec_a = om.MVector(point_a)
    vec_b = om.MVector(point_b)
    distance = (vec_a - vec_b).length()

    logger.debug(f"Distance: {distance}")

    return distance


def inner_divide(point_a: Sequence[float], point_b: Sequence[float], *, spans: int = 1) -> list[list[float]]:
    """Divide the line segment.

    Args:
        point_a (Sequence[float]): The first point.
        point_b (Sequence[float]): The second point.
        spans (int): The number of spans. Default is 1.

    Returns:
        list[list[float]]: The divided points.
    """
    # Create linspace equivalent using Python built-in
    divided_points = []
    for i in range(spans + 1):
        t = i / spans if spans > 0 else 0
        point = [a + t * (b - a) for a, b in zip(point_a, point_b)]
        divided_points.append(point)

    logger.debug(f"Inner divided points: {divided_points}")

    return divided_points


# Object Position


def get_bounding_box(points: list[list[float]]) -> tuple[list[float], list[float]]:
    """Get the bounding box from a list of 3D points.

    Args:
        points (list[list[float]]): List of 3D points.

    Returns:
        tuple[list[float], list[float]]: Minimum point and maximum point of the bounding box.
    """
    if not points:
        return [], []

    # Calculate min and max for each dimension using zip (more efficient)
    transposed = zip(*points)
    min_point = [min(coords) for coords in transposed]
    transposed = zip(*points)
    max_point = [max(coords) for coords in transposed]

    logger.debug(f"Bounding box: {min_point}, {max_point}")

    return min_point, max_point


def get_bounding_box_center(points: list[list[float]]) -> list[float]:
    """Get the center point of the bounding box from a list of 3D points.

    Args:
        points (list[list[float]]): List of 3D points.

    Returns:
        list[float]: Coordinates of the center point.
    """
    min_point, max_point = get_bounding_box(points)
    center_point = [(min_val + max_val) / 2 for min_val, max_val in zip(min_point, max_point)]

    logger.debug(f"Bounding box center: {center_point}")

    return center_point


def get_centroid(points: list[list[float]]) -> list[float]:
    """Get the centroid coordinates of a set of 3D points.

    Args:
        points (list[list[float]]): List of 3D points.

    Returns:
        list[float]: Coordinates of the centroid.
    """
    if not points:
        return []

    # Calculate mean for each dimension
    num_points = len(points)
    num_dims = len(points[0])
    centroid = [sum(p[i] for p in points) / num_points for i in range(num_dims)]

    logger.debug(f"Centroid: {centroid}")

    return centroid


# Vector


def get_vector(point_a: Sequence[float], point_b: Sequence[float]) -> list[float]:
    """Get the vector from point A to point B.

    Args:
        point_a (Sequence[float]): The first point.
        point_b (Sequence[float]): The second point.

    Returns:
        list[float]: The vector.
    """
    vector = [(b - a) for a, b in zip(point_a, point_b)]

    logger.debug(f"Vector: {vector}")

    return vector


def get_vector_angle(vector_a: Sequence[float], vector_b: Sequence[float], as_degrees: bool = False) -> float:
    """Get the angle between two vectors.

    Args:
        vector_a (Sequence[float]): The first vector.
        vector_b (Sequence[float]): The second vector.
        as_degrees (bool): Return the angle in degrees. Default is False (radians).

    Returns:
        float: The angle in degrees or radians.
    """
    vector_a = om.MVector(vector_a).normal()
    vector_b = om.MVector(vector_b).normal()

    angle = vector_a.angle(vector_b)
    if as_degrees:
        angle = math.degrees(angle)

    logger.debug(f"Angle: {angle}")

    return angle


def vector_orthogonalize(vector_a: Sequence[float], vector_b: Sequence[float]) -> om.MVector:
    """Orthogonalize vector B to vector A.

    Args:
        vector_a (Sequence[float]): The first vector.
        vector_b (Sequence[float]): The second vector.

    Returns:
        om.MVector: The orthogonalized vector.
    """
    vector_a_normalized = om.MVector(vector_a).normal()
    vector_b = om.MVector(vector_b)

    vector_ortho = (vector_b - (vector_a_normalized * vector_b) * vector_a_normalized).normal()

    return vector_ortho


# Rotation


def multiply_rotation(rotations: list[Sequence[float]]) -> list[float]:
    """Multiply rotations.

    Args:
        rotations (list[Sequence[float]]): List of euler rotations.

    Returns:
        list[float]: The multiplied rotation.
    """
    quat_rotation = om.MQuaternion()
    for rotation in rotations:
        quat_rotation *= om.MEulerRotation([math.radians(value) for value in rotation]).asQuaternion()

    quat_rotation.normalizeIt()
    euler_rotation = quat_rotation.asEulerRotation()
    euler_rotation_degree = [math.degrees(euler_rotation.x), math.degrees(euler_rotation.y), math.degrees(euler_rotation.z)]

    logger.debug(f"Multiplied rotation: {euler_rotation_degree}")

    return euler_rotation_degree


def invert_rotation(rotation: Sequence[float]) -> list[float]:
    """Invert the rotation.

    Args:
        rotation (Sequence[float]): The euler rotation.

    Returns:
        list[float]: The inverted rotation.
    """
    quat_rotation = om.MEulerRotation([math.radians(value) for value in rotation]).asQuaternion()
    quat_rotation.invertIt()

    euler_rotation = quat_rotation.asEulerRotation()
    euler_rotation_degree = [math.degrees(euler_rotation.x), math.degrees(euler_rotation.y), math.degrees(euler_rotation.z)]

    logger.debug(f"Inverted rotation: {euler_rotation_degree}")

    return euler_rotation_degree


def vector_to_rotation(
    primary_vec: Sequence[float], secondary_vec: Sequence[float], primary_axis: str = "x", secondary_axis: str = "y"
) -> list[float]:
    """Get the rotation from vector A to vector B.

    Args:
        primary_vec (Sequence[float]): The primary vector.
        secondary_vec (Sequence[float]): The secondary vector.
        primary_axis (str): The axis to align the primary vector ('x', 'y', 'z').
        secondary_axis (str): The axis to align the secondary vector ('x', 'y', 'z').

    Returns:
        list[float]: The rotation in degrees.

    Raises:
        ValueError: If primary_axis and secondary_axis are the same or invalid.
    """
    # Validate axis
    if primary_axis == secondary_axis:
        raise ValueError("Primary axis and secondary axis cannot be the same.")
    if primary_axis not in ["x", "y", "z"] or secondary_axis not in ["x", "y", "z"]:
        raise ValueError("Invalid axis.")

    # Normalize vectors
    primary_vec = om.MVector(primary_vec).normal()
    secondary_vec = vector_orthogonalize(primary_vec, secondary_vec)
    third_vec = primary_vec ^ secondary_vec

    # Get rotation
    matrix = om.MMatrix(
        [
            primary_vec.x,
            primary_vec.y,
            primary_vec.z,
            0,
            secondary_vec.x,
            secondary_vec.y,
            secondary_vec.z,
            0,
            third_vec.x,
            third_vec.y,
            third_vec.z,
            0,
            0,
            0,
            0,
            1,
        ]
    )

    offset_matrices = {
        ("x", "y"): om.MMatrix(),
        ("x", "z"): om.MMatrix([1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1]),
        ("y", "x"): om.MMatrix([0, 1, 0, 0, 1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1]),
        ("y", "z"): om.MMatrix([0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1]),
        ("z", "x"): om.MMatrix([0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1]),
        ("z", "y"): om.MMatrix([0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1]),
    }

    matrix = offset_matrices[(primary_axis, secondary_axis)] * matrix
    transform = om.MTransformationMatrix(matrix)
    euler_rotation = transform.rotation()

    result_rotation = [math.degrees(euler_rotation.x), math.degrees(euler_rotation.y), math.degrees(euler_rotation.z)]

    logger.debug(f"Vector to rotation: {result_rotation}")

    return result_rotation


def get_average_rotation(rotations: list[Sequence[float]]) -> list[float]:
    """Get the average rotation from a list of rotations.

    Args:
        rotations (list[Sequence[float]]): List of rotations.

    Returns:
        list[float]: The average rotation.
    """
    if len(rotations) == 1:
        return rotations[0]

    quats = [om.MEulerRotation(rotation).asQuaternion() for rotation in rotations]
    log_sum = om.MVector([0.0, 0.0, 0.0])
    for quat in quats:
        quat_log = quat.log()
        log_sum += om.MVector([quat_log.x, quat_log.y, quat_log.z])

    avg_log = log_sum / len(quats)
    avg_quat = om.MQuaternion(avg_log.x, avg_log.y, avg_log.z, 0).exp()
    avg_quat.normalize()

    avg_euler = avg_quat.asEulerRotation()
    avg_euler_degree = [math.degrees(avg_euler.x), math.degrees(avg_euler.y), math.degrees(avg_euler.z)]

    logger.debug(f"Average rotation: {avg_euler_degree}")

    return avg_euler_degree
