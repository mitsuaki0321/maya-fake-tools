"""
NurbsCurve functions.

This module provides the base NurbsCurve class and re-exports specialized classes
for better code organization:
- ConvertNurbsCurve: Curve conversion and modification operations (lib_nurbsCurve_convert.py)
- NurbsCurvePositions: Position calculation operations (lib_nurbsCurve_positions.py)
"""

from collections.abc import Sequence
from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

logger = getLogger(__name__)


class NurbsCurve:
    """NurbsCurve class.

    Attributes:
        curve (str): The curve name.
        dag_path (om.MDagPath): The DAG path of the curve.
        fn (om.MFnNurbsCurve): The function set for the curve.
    """

    def __init__(self, curve: str):
        """Initialize the NurbsCurve class.

        Args:
            curve (str): The curve name.

        Raises:
            ValueError: If the node does not exist or is not a nurbsCurve type.
        """
        if not cmds.objExists(curve):
            raise ValueError(f"Node does not exist: {curve}")

        if cmds.nodeType(curve) != "nurbsCurve":
            raise ValueError(f"Invalid type: {curve}")

        selection_list = om.MSelectionList()
        selection_list.add(curve)

        self.curve = curve
        self.dag_path = selection_list.getDagPath(0)
        self.fn = om.MFnNurbsCurve(self.dag_path)

    @property
    def num_cvs(self) -> int:
        """Get the cv num.

        Returns:
            int: The cv num.
        """
        if self.fn.form != om.MFnNurbsCurve.kPeriodic:
            return self.fn.numCVs
        else:
            return self.fn.numCVs - self.fn.degree

    @property
    def num_spans(self) -> int:
        """Get the span num.

        Returns:
            int: The span num.
        """
        return self.fn.numSpans

    @property
    def form(self) -> str:
        """Get the form.

        Returns:
            str: The form. ('open', 'closed', 'periodic')
        """
        form_map = {
            om.MFnNurbsCurve.kOpen: "open",
            om.MFnNurbsCurve.kClosed: "closed",
            om.MFnNurbsCurve.kPeriodic: "periodic",
        }

        return form_map[self.fn.form]

    @property
    def degree(self) -> int:
        """Get the degree.

        Returns:
            int: The degree.
        """
        return self.fn.degree

    def get_length(self) -> float:
        """Get the length.

        Returns:
            float: The length.
        """
        return self.fn.length()

    def get_cv_position(self, cv_ids: list[int], as_float: bool = False) -> list[om.MPoint] | list[list[float]]:
        """Get the CV positions.

        Args:
            cv_ids (list[int]): The CV IDs.
            as_float (bool): Return as float. Default is False.

        Returns:
            list[om.MPoint] | list[list[float]]: The positions.
        """
        positions = [self.fn.cvPosition(cv_id, om.MSpace.kWorld) for cv_id in cv_ids]
        if as_float:
            return [[pos.x, pos.y, pos.z] for pos in positions]

        return positions

    def get_cv_positions(self, as_float: bool = False) -> list[om.MPoint] | list[list[float]]:
        """Get the CV positions.

        Args:
            as_float (bool): Return as float. Default is False.

        Returns:
            list[om.MPoint] | list[list[float]]: The positions.
        """
        cv_positions = list(self.fn.cvPositions(om.MSpace.kWorld))
        # Keeping the reference to the MPointArray pointer can cause errors in subsequent processing.
        cv_positions = [om.MPoint([pos.x, pos.y, pos.z]) for pos in cv_positions]

        if self.form == "periodic":
            return cv_positions[: -self.fn.degree]

        if as_float:
            return [[pos.x, pos.y, pos.z] for pos in cv_positions]

        return cv_positions

    def get_edit_position(self, edit_ids: list[int], as_float: bool = False) -> tuple[list[om.MPoint] | list[list[float]], list[float]]:
        """Get the edit points.

        Args:
            edit_ids (list[int]): The edit IDs.
            as_float (bool): Return as float. Default is False.

        Returns:
            tuple[list[om.MPoint] | list[list[float]], list[float]]: The positions and parameters.

        Raises:
            ValueError: If edit ID is out of valid range.
        """
        min_param, max_param = self.fn.knotDomain
        param_range = max_param - min_param

        positions = []
        params = []
        for edit_id in edit_ids:
            if edit_id < 0 or edit_id > self.fn.numSpans:
                raise ValueError("Edit ID is out of valid range.")

            param = min_param + edit_id * param_range / self.fn.numSpans
            position = self.fn.getPointAtParam(param, space=om.MSpace.kWorld)

            params.append(param)
            positions.append(position)

        if as_float:
            return [[pos.x, pos.y, pos.z] for pos in positions], params

        return positions, params

    def get_edit_positions(self, as_float: bool = False) -> tuple[list[om.MPoint] | list[list[float]], list[float]]:
        """Get the edit points.

        Args:
            as_float (bool): Return as float. Default is False.

        Returns:
            tuple[list[om.MPoint] | list[list[float]], list[float]]: The positions and parameters.
        """
        min_param, max_param = self.fn.knotDomain
        param_range = max_param - min_param

        positions = []
        params = []
        for i in range(self.fn.numSpans + 1):
            param = min_param + i * param_range / self.fn.numSpans
            position = self.fn.getPointAtParam(param, space=om.MSpace.kWorld)

            params.append(param)
            positions.append(position)

        if as_float:
            return [[pos.x, pos.y, pos.z] for pos in positions], params

        return positions, params

    def get_closest_position(self, reference_position: Sequence[float], as_float: bool = False) -> tuple[om.MPoint | list[float], float]:
        """Get the closest CV position.

        Args:
            reference_position (Sequence[float]): The reference point.
            as_float (bool): Return as float. Default is False.

        Returns:
            tuple[om.MPoint | list[float], float]: The position and parameter.
        """
        closest_position, param = self.fn.closestPoint(om.MPoint(reference_position), space=om.MSpace.kWorld)

        if as_float:
            return [closest_position.x, closest_position.y, closest_position.z], param

        return closest_position, param

    def get_closest_positions(
        self, reference_positions: list[Sequence[float]], as_float: bool = False
    ) -> tuple[list[om.MPoint] | list[list[float]], list[float]]:
        """Get the closest CV positions.

        Args:
            reference_positions (list[Sequence[float]]): The reference points.
            as_float (bool): Return as float. Default is False.

        Returns:
            tuple[list[om.MPoint] | list[list[float]], list[float]]: The positions and parameters.
        """
        positions = []
        params = []
        for reference_position in reference_positions:
            closest_position, param = self.fn.closestPoint(om.MPoint(reference_position), space=om.MSpace.kWorld)
            positions.append(closest_position)
            params.append(param)

        if as_float:
            return [[pos.x, pos.y, pos.z] for pos in positions], params

        return positions, params

    def get_normal(self, param: float) -> om.MVector:
        """Get the normal.

        Args:
            param (float): The parameter.

        Returns:
            om.MVector: The normal.
        """
        return self.fn.normal(param, space=om.MSpace.kWorld)

    def get_tangent(self, param: float) -> om.MVector:
        """Get the tangent.

        Args:
            param (float): The parameter.

        Returns:
            om.MVector: The tangent.
        """
        return self.fn.tangent(param, space=om.MSpace.kWorld)

    def get_normal_and_tangents(self, params: list[float]) -> tuple[list[om.MVector], list[om.MVector]]:
        """Get the normal and tangent.

        Args:
            params (list[float]): The parameters.

        Returns:
            tuple[list[om.MVector], list[om.MVector]]: The normals and tangents.
        """
        normals = []
        tangents = []
        for param in params:
            normal = self.fn.normal(param, space=om.MSpace.kWorld)
            tangent = self.fn.tangent(param, space=om.MSpace.kWorld)
            normals.append(normal)
            tangents.append(tangent)

        return normals, tangents

    def find_cloud_length_from_param(self, start_param: float, target_length: float, **kwargs) -> float:
        """Find the parameter where the chord length from the specified parameter equals the target length.

        Args:
            start_param (float): The starting parameter value.
            target_length (float): The target chord length.

        Keyword Args:
            max_iterations (int): Maximum number of iterations. Default is 50.
            tolerance (float): Tolerance. Default is 1e-4.
            samples (int): Number of initial samples for curve length estimation. Default is 10.

        Raises:
            ValueError: If a parameter corresponding to the target chord length cannot be found.

        Returns:
            float: The parameter value corresponding to the target chord length.
        """
        max_iterations = kwargs.get("max_iterations", 50)
        tolerance = kwargs.get("tolerance", 1e-4)
        samples = kwargs.get("samples", 10)

        min_param, max_param = self.fn.knotDomain

        if not min_param <= start_param < max_param:
            raise ValueError("start_param is out of valid range.")

        start_point = self.fn.getPointAtParam(start_param, space=om.MSpace.kWorld)

        # Early return for very small target lengths
        if target_length < tolerance:
            return start_param

        # Step 1: Calculate initial estimate from curve length
        # Chord length is usually shorter than curve length, so a curve-length-based estimate is a good upper bound
        curve_length_estimate = target_length * 1.2  # Empirical coefficient
        try:
            # Estimate parameter from curve length
            current_length = self.fn.findLengthFromParam(start_param)
            estimated_param = self.fn.findParamFromLength(current_length + curve_length_estimate)

            # If the estimate is out of range, use the maximum value
            if estimated_param > max_param:
                estimated_param = max_param
        except RuntimeError:
            # Fallback: linear estimate
            param_range = max_param - start_param
            estimated_param = min(start_param + param_range * 0.3, max_param)

        # Step 2: Narrow down the range with initial sampling
        # Efficiently identify the range with fewer sample points
        sample_params = []
        sample_distances = []

        # Adaptive sampling interval
        param_step = (estimated_param - start_param) / samples
        current_param = start_param

        for i in range(samples + 1):
            if current_param > max_param:
                current_param = max_param

            sample_params.append(current_param)
            point = self.fn.getPointAtParam(current_param, space=om.MSpace.kWorld)
            distance = start_point.distanceTo(point)
            sample_distances.append(distance)

            # Early exit if the target distance is exceeded
            if distance >= target_length:
                break

            # Adaptively adjust the next sample position
            if i > 0 and distance > 0:
                # Estimate the next step from the rate of distance increase
                distance_rate = (distance - sample_distances[i - 1]) / param_step
                if distance_rate > 0:
                    remaining_distance = target_length - distance
                    next_step = remaining_distance / distance_rate * 0.8  # Safety factor
                    param_step = min(next_step, (max_param - current_param))

            current_param += param_step

        # Step 3: Determine the range for binary search
        left_param = start_param
        right_param = max_param

        for i in range(len(sample_distances)):
            if sample_distances[i] >= target_length:
                if i > 0:
                    left_param = sample_params[i - 1]
                    right_param = sample_params[i]

                    # Improve the initial estimate by linear interpolation
                    if sample_distances[i] > sample_distances[i - 1]:
                        t = (target_length - sample_distances[i - 1]) / (sample_distances[i] - sample_distances[i - 1])
                        estimated_param = left_param + t * (right_param - left_param)
                    else:
                        estimated_param = sample_params[i]
                else:
                    right_param = sample_params[i]
                    estimated_param = sample_params[i]
                break
        else:
            # If the target distance is not reached
            if sample_distances[-1] < target_length * 0.9:
                raise ValueError(
                    f"Cannot find parameter for target chord length {target_length}. Maximum achievable distance: {sample_distances[-1]}"
                )
            # Search in the range up to the maximum parameter
            left_param = sample_params[-2] if len(sample_params) > 1 else start_param
            right_param = max_param
            estimated_param = max_param

        # Step 4: Improved binary search
        # Fast convergence by combining linear interpolation
        best_param = estimated_param
        best_distance = float("inf")

        for iteration in range(max_iterations):
            # Calculate the distance at the current estimate
            point = self.fn.getPointAtParam(estimated_param, space=om.MSpace.kWorld)
            distance = start_point.distanceTo(point)

            # Record the best result
            distance_error = abs(distance - target_length)
            if distance_error < abs(best_distance - target_length):
                best_param = estimated_param
                best_distance = distance

            # Convergence check
            if distance_error < tolerance:
                return estimated_param

            # Update the range
            if distance < target_length:
                left_param = estimated_param
            else:
                right_param = estimated_param

            # Calculate the next estimate
            # Prefer linear interpolation in the early stages, use binary search in the later stages
            if iteration < max_iterations // 2:
                # Estimate by linear interpolation (fast convergence)
                if right_param > left_param:
                    # Calculate distances at both ends
                    if iteration == 0 or iteration % 5 == 0:  # Recalculate every 5 times
                        left_point = self.fn.getPointAtParam(left_param, space=om.MSpace.kWorld)
                        right_point = self.fn.getPointAtParam(right_param, space=om.MSpace.kWorld)
                        left_distance = start_point.distanceTo(left_point)
                        right_distance = start_point.distanceTo(right_point)

                        if right_distance > left_distance:
                            # Linear interpolation
                            t = (target_length - left_distance) / (right_distance - left_distance)
                            t = max(0.1, min(0.9, t))  # Avoid extreme values
                            estimated_param = left_param + t * (right_param - left_param)
                        else:
                            # Fallback: bisection
                            estimated_param = (left_param + right_param) * 0.5
                    else:
                        # Simple adjustment
                        if distance < target_length:
                            estimated_param = estimated_param + (right_param - estimated_param) * 0.6
                        else:
                            estimated_param = left_param + (estimated_param - left_param) * 0.4
                else:
                    break
            else:
                # Binary search (for stability)
                estimated_param = (left_param + right_param) * 0.5

            # Prevent infinite loop
            if right_param - left_param < tolerance * 0.01:
                break

        # Return the best result
        if abs(best_distance - target_length) < tolerance * 10:  # Loose tolerance
            return best_param

        raise ValueError(
            f"Failed to find parameter for target chord length {target_length}. Best distance found: {best_distance} at parameter {best_param}"
        )


# Re-export specialized classes for backward compatibility
# Note: Imports placed here to avoid circular imports
from .lib_nurbsCurve_convert import ConvertNurbsCurve  # noqa: E402
from .lib_nurbsCurve_positions import NurbsCurvePositions  # noqa: E402

__all__ = [
    "NurbsCurve",
    "ConvertNurbsCurve",
    "NurbsCurvePositions",
]
