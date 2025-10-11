"""
Mesh point operations (closest point, intersection).
"""

from logging import getLogger

import maya.api.OpenMaya as om

from .lib_mesh import MeshComponent

logger = getLogger(__name__)


class MeshPoint(MeshComponent):
    """Mesh point class."""

    def get_closest_points(
        self, reference_points: list[list[float]], max_distance: float = 100.0, as_float: bool = False
    ) -> list[om.MPoint] | list[list[float]]:
        """Get the closest point on the mesh.

        Args:
            reference_points (list[list[float]]): List of reference points.
            max_distance (float): The maximum distance. Default is 100.0.
            as_float (bool): Whether to return the points as float. Default is False.

        Returns:
            Union[list[om.MPoint], list[list[float]]]: The closest points.
        """
        mesh_intersector = om.MMeshIntersector()
        matrix = self._dag_path.inclusiveMatrix()
        inverse_matrix = self._dag_path.inclusiveMatrixInverse()
        mesh_intersector.create(self._dag_path.node(), matrix)

        result_positions = []
        for reference_point in reference_points:
            reference_point = inverse_matrix * om.MPoint(reference_point)
            point_on_mesh = mesh_intersector.getClosestPoint(reference_point, max_distance)

            if point_on_mesh is None:
                logger.warning(f"No intersection found for point: {reference_point}")
                continue

            closest_point = om.MPoint(point_on_mesh.point) * matrix
            result_positions.append(closest_point)

        if as_float:
            return [[p.x, p.y, p.z] for p in result_positions]

        return result_positions

    def get_intersect_point(self, start_point: list[float], end_point: list[float], **kwargs) -> tuple | None:
        """Get the intersection point on the mesh.

        Args:
            start_point (list[float]): The start point.
            end_point (list[float]): The end point.

        Keyword Args:
            max_param (float): 	Specifies the maximum radius within which hits will be considered. Default is 1000.
            test_both_directions (bool): Specifies that hits in the negative rayDirection should also be considered. Default is False.

        Returns:
            tuple: The intersection data.(hitPoint, hitRayParam, hitFace, hitTriangle, hitBary1, hitBay2)
        """
        max_param = kwargs.get("max_param", 1000)
        test_both_directions = kwargs.get("test_both_directions", False)

        start_point = om.MFloatPoint(start_point)
        end_point = om.MFloatPoint(end_point)
        ray_direction = end_point - start_point

        hit_data = self._mesh_fn.closestIntersection(start_point, ray_direction, om.MSpace.kWorld, max_param, test_both_directions)

        if hit_data is None:
            logger.warning(f"No intersection found for points: {start_point}, {end_point}, {self._mesh_name}")
            return None

        return hit_data
