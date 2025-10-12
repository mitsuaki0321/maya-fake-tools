"""Functions for getting positions from objects and components."""

from logging import getLogger

import maya.cmds as cmds

from ...lib import lib_math
from .position_helpers import get_selected_positions

logger = getLogger(__name__)


def bounding_box_center(**kwargs) -> list[dict[str, list[float]]]:
    """Get the bounding box center of the selected object.

    Keyword Args:
        **kwargs: Additional arguments (ignored for this function).

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    positions = get_selected_positions()
    if not positions:
        logger.warning("No valid object selected.")
        return

    center_position = lib_math.get_bounding_box_center(positions[0])

    logger.debug(f"Bounding box center: {center_position}")

    return [{"position": [center_position], "rotation": []}]


def gravity_center(**kwargs) -> list[dict[str, list[float]]]:
    """Get the centroid of the selected object.

    Keyword Args:
        **kwargs: Additional arguments (ignored for this function).

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    positions = get_selected_positions()
    if not positions:
        logger.warning("No valid object selected.")
        return

    gravity_center_position = lib_math.get_centroid(positions[0])

    logger.debug(f"Gravity center: {gravity_center_position}")

    return [{"position": [gravity_center_position], "rotation": []}]


def each_positions(**kwargs) -> list[dict[str, list[float]]]:
    """Get the each position of the selected object.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    include_rotation = kwargs.get("include_rotation", False)
    tangent_from_component = kwargs.get("tangent_from_component", False)

    positions = get_selected_positions(include_rotation=include_rotation, tangent_from_component=tangent_from_component)
    if not positions:
        logger.warning("No valid object selected.")
        return

    logger.debug(f"Each positions: {positions}")

    return [{"position": positions[0], "rotation": positions[1]}]


def closest_position(**kwargs) -> list[dict[str, list[float]]]:
    """Get the closest point on the selected nurbs surface or curve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    include_rotation = kwargs.get("include_rotation", False)
    tangent_from_component = kwargs.get("tangent_from_component", False)

    positions = get_selected_positions(
        only_component=True, include_rotation=include_rotation, closest_position=True, tangent_from_component=tangent_from_component
    )
    if not positions:
        logger.warning("No valid object selected.")
        return

    logger.debug(f"Closest positions: {positions}")

    return [{"position": positions[0], "rotation": positions[1]}]


def inner_divide(**kwargs) -> list[dict[str, list[float]]]:
    """Get the inner divided points of the selected object.

    Keyword Args:
        divisions (int): The number of divisions. Default is 1.
        include_rotation (bool): Whether to include rotation. Default is False.

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    transforms = cmds.ls(sl=True, type="transform")
    if not transforms:
        logger.warning("No valid object selected.")
        return

    if len(transforms) < 2:
        logger.warning("Select two or more objects.")
        return

    divisions = kwargs.get("divisions", 1)

    if divisions < 1:
        logger.warning("Invalid divisions.")
        return

    include_rotation = kwargs.get("include_rotation", False)

    reference_positions = [cmds.xform(transform, q=True, ws=True, t=True) for transform in transforms]
    if include_rotation:
        reference_rotations = [cmds.xform(transform, q=True, ws=True, ro=True) for transform in transforms]

    num_transforms = len(transforms)

    result_positions = []
    result_rotations = []
    for i in range(num_transforms - 1):
        positions = lib_math.inner_divide(reference_positions[i], reference_positions[i + 1], spans=divisions)
        if i != (num_transforms - 2):
            positions.pop(-1)
        result_positions.extend(positions)

        if include_rotation:
            if i != (num_transforms - 2):
                result_rotations.extend([reference_rotations[i]] * divisions)
            else:
                result_rotations.extend([reference_rotations[i]] * (divisions + 1))

    logger.debug(f"Inner divided points: {result_positions}")

    return [{"position": result_positions, "rotation": result_rotations}]
