"""Functions for getting positions from curves."""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ...lib import lib_math, lib_nurbsCurve, lib_nurbsSurface

logger = getLogger(__name__)


def cv_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the cv positions of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        positions = curve_obj.get_cv_positions()
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, positions, **kwargs)

        positions = [[v.x, v.y, v.z] for v in positions]

        result_data.append({"position": positions, "rotation": rotations})

    logger.debug(f"CV positions: {result_data}")

    return result_data


def cv_closest_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the closest cv positions of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        positions = curve_obj.get_cv_positions()
        closest_positions, _ = curve_obj.get_closest_positions(positions)
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, closest_positions, **kwargs)

        closest_positions = [[v.x, v.y, v.z] for v in closest_positions]
        result_data.append({"position": closest_positions, "rotation": rotations})

    logger.debug(f"Closest CV positions: {result_data}")

    return result_data


def ep_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the ep positions of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        positions, _ = curve_obj.get_edit_positions()
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, positions, **kwargs)

        positions = [[v.x, v.y, v.z] for v in positions]
        result_data.append({"position": positions, "rotation": rotations})

    logger.debug(f"EP positions: {result_data}")

    return result_data


def length_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the length of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        length (float): The length of the curve. Default is 1.0.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
        positions, _ = curve_positions_obj.get_positions_length(num_divisions=divisions)
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, positions, **kwargs)

        positions = [[v.x, v.y, v.z] for v in positions]
        result_data.append({"position": positions, "rotation": rotations})

    logger.debug(f"Positions from length: {result_data}")

    return result_data


def param_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the parameter of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
        positions, _ = curve_positions_obj.get_positions_param(num_divisions=divisions)
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, positions, **kwargs)

        positions = [[v.x, v.y, v.z] for v in positions]
        result_data.append({"position": positions, "rotation": rotations})

    logger.debug(f"Positions from parameter: {result_data}")

    return result_data


def cloud_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the cloud of the selected nurbsCurve.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves = _get_selected_curves()
    if not curves:
        logger.warning("No valid nurbsCurve selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    result_data = []
    for curve in curves:
        curve_obj = lib_nurbsCurve.NurbsCurve(curve)
        curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
        positions, _ = curve_positions_obj.get_positions_cloud(num_divisions=divisions)
        rotations = []
        if include_rotation:
            rotations = _get_curve_rotations(curve, positions, **kwargs)

        positions = [[v.x, v.y, v.z] for v in positions]
        result_data.append({"position": positions, "rotation": rotations})

    logger.debug(f"Positions from cloud: {result_data}")

    return result_data


def _get_selected_curves() -> list[str]:
    """Get the selected nurbsCurve.

    Returns:
        list[str]: The selected nurbsCurve.
    """
    return cmds.ls(sl=True, dag=True, type="nurbsCurve", ni=True)


def _get_curve_rotations(curve: str, positions: list[om.MPoint], **kwargs) -> list[list[float]]:
    """Get the curve rotations.

    Args:
        curve (str): The curve name.
        positions (list[list[float]]): The curve positions.

    Keyword Args:
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'

    Notes:
        - If the up_vector_method is 'surface_normal', the curve must be on the surface.
        - If not found the surface, the up_vector_method will be 'normal'.

    Returns:
        list[list[float]]: The curve rotations.
    """
    aim_vector_method = kwargs.get("aim_vector_method", "tangent")  # 'tangent', 'next_point', 'previous_point'
    up_vector_method = kwargs.get("up_vector_method", "normal")  # 'scene_up', 'normal', 'surface_normal'

    if aim_vector_method not in ["tangent", "next_point", "previous_point"]:
        raise ValueError("Invalid aim vector method.")

    if up_vector_method not in ["scene_up", "normal", "surface_normal"]:
        raise ValueError("Invalid up vector method.")

    curve_obj = lib_nurbsCurve.NurbsCurve(curve)

    if up_vector_method == "surface_normal":
        surface = None
        curve_iso = cmds.listConnections(f"{curve}.create", type="curveFromSurfaceIso")
        if not curve_iso:
            logger.warning("No valid curveFromSurfaceIso.")
        else:
            surface = cmds.listConnections(f"{curve_iso[0]}.inputSurface", type="nurbsSurface", shapes=True)

        if not surface:
            logger.warning("No valid nurbsSurface.")
            up_vector_method = "normal"
        else:
            surface = lib_nurbsSurface.NurbsSurface(surface[0])
            iso_param = cmds.getAttr(f"{curve_iso[0]}.isoparmValue")
            iso_direction = cmds.getAttr(f"{curve_iso[0]}.isoparmDirection")

    num_positions = len(positions)

    rotations = []
    for i in range(num_positions):
        _, param = curve_obj.get_closest_position(positions[i])

        # Get the aim vector
        if aim_vector_method == "tangent":
            aim_vector = curve_obj.get_tangent(param)
        elif aim_vector_method == "next_point":
            aim_vector = positions[i] - positions[i - 1] if i == num_positions - 1 else positions[i + 1] - positions[i]
        elif aim_vector_method == "previous_point":
            aim_vector = positions[i + 1] - positions[i] if i == 0 else positions[i] - positions[i - 1]

        # Get the up vector
        if up_vector_method == "scene_up":
            up_vector = [0.0, 1.0, 0.0]
        elif up_vector_method == "normal":
            up_vector = curve_obj.get_normal(param)
        elif up_vector_method == "surface_normal":
            params = iso_direction == 0 and [param, iso_param] or [iso_param, param]
            up_vector = surface.get_normal(params)

        # Get the rotation
        rotation = lib_math.vector_to_rotation(aim_vector, up_vector, primary_axis="z", secondary_axis="x")
        rotations.append(rotation)

    return rotations
