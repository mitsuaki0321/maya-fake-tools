"""
NurbsCurve positions calculation functions.
"""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

from .lib_nurbsCurve import NurbsCurve

logger = getLogger(__name__)


class NurbsCurvePositions:
    """NurbsCurvePositions class.

    Attributes:
        curve (NurbsCurve): The NurbsCurve object.
    """

    def __init__(self, curve: NurbsCurve):
        """Initialize the NurbsCurvePositions class.

        Args:
            curve (NurbsCurve): The NurbsCurve object.
        """
        self.curve = curve

    def get_positions_length(self, num_divisions: int = 10) -> tuple[list[om.MPoint], list[float]]:
        """Get the positions by length.

        Args:
            num_divisions (int): The number of divisions. Default is 10.

        Returns:
            tuple[list[om.MPoint], list[float]]: The positions and parameters.
        """
        space = om.MSpace.kWorld
        length = self.curve.fn.length()

        num_points = num_divisions
        if self.curve.form == "open":
            num_points += 1

        positions = []
        params = []
        for i in range(num_points):
            param_length = length * i / num_divisions
            param = self.curve.fn.findParamFromLength(param_length)

            positions.append(self.curve.fn.getPointAtParam(param, space=space))
            params.append(param)

        return positions, params

    def get_positions_param(self, num_divisions: int = 10) -> tuple[list[om.MPoint], list[float]]:
        """Get the positions by parameter.

        Args:
            num_divisions (int): The number of divisions. Default is 10.

        Returns:
            tuple[list[om.MPoint], list[float]]: The positions and parameters.
        """
        space = om.MSpace.kWorld

        min_param, max_param = self.curve.fn.knotDomain
        param_range = max_param - min_param

        num_points = num_divisions
        if self.curve.form == "open":
            num_points += 1

        positions = []
        params = []
        for i in range(num_points):
            param = min_param + param_range * i / num_divisions
            position = self.curve.fn.getPointAtParam(param, space=space)
            positions.append(position)
            params.append(param)

        return positions, params

    def get_positions_cloud(self, num_divisions: int = 10, **kwargs) -> tuple[list[om.MPoint], list[float]]:
        """Get the positions by chord length.

        Args:
            num_divisions (int): The number of divisions. Default is 10.

        Keyword Args:
            max_iterations (int): Maximum number of iterations. Default is 500.
            tolerance (float): Tolerance. Default is 1e-5.
            add_length (float): The length to add. Default is 0.1.

        Returns:
            tuple[list[om.MPoint], list[float]]: The positions and parameters.

        Raises:
            ValueError: If the curve is not open.
        """
        if self.curve.form != "open":
            raise ValueError("Unsupported operation. The curve must be open.")

        max_iterations = kwargs.get("max_iterations", 500)
        tolerance = kwargs.get("tolerance", 1e-5)
        step_size = kwargs.get("add_length", 0.1)

        min_param, max_param = self.curve.fn.knotDomain

        end_point = self.curve.fn.getPointAtParam(max_param, space=om.MSpace.kWorld)

        dist_to = end_point.distanceTo

        length = 0.01
        count = 0

        while count < max_iterations:
            state = False

            params = []
            tmp_param = min_param
            for _ in range(num_divisions - 1):
                try:
                    param = self.curve.find_cloud_length_from_param(tmp_param, length, local=om.MSpace.kWorld)
                except ValueError as e:
                    raise ValueError("Parameter corresponding to the target chord length not found.") from e
                if param is not None:
                    params.append(param)
                    tmp_param = param
                else:
                    length -= step_size
                    step_size *= 0.1
                    state = True
                    break

            if state:
                continue

            end_length = dist_to(self.curve.fn.getPointAtParam(params[-1], space=om.MSpace.kWorld))
            if abs(end_length - length) < tolerance:
                break

            if end_length > length:
                length += step_size
            else:
                length -= step_size
                step_size *= 0.1

            count += 1

        logger.debug(f"Loop count: {count} of {max_iterations}")

        if count == max_iterations:
            cmds.warning("Max iterations reached.")

        params.insert(0, min_param)
        params.append(max_param)

        positions = [self.curve.fn.getPointAtParam(param, space=om.MSpace.kWorld) for param in params]

        return positions, params
