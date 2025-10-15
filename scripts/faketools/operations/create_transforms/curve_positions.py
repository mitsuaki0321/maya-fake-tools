"""Functions for getting positions from curves."""

from logging import getLogger
from typing import Optional

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ...lib import lib_math, lib_nurbsCurve, lib_nurbsSurface

logger = getLogger(__name__)


def cv_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the cv positions of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            positions = curve_obj.get_cv_positions()
            rotations = []
            if include_rotation:
                # Pass original surface if available
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, positions, **kwargs)

            positions = [[v.x, v.y, v.z] for v in positions]

            result_data.append({"position": positions, "rotation": rotations})

        logger.debug(f"CV positions: {result_data}")

        return result_data

    finally:
        # Clean up temporary curves
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def cv_closest_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the closest cv positions of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            positions = curve_obj.get_cv_positions()
            closest_positions, _ = curve_obj.get_closest_positions(positions)
            rotations = []
            if include_rotation:
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, closest_positions, **kwargs)

            closest_positions = [[v.x, v.y, v.z] for v in closest_positions]
            result_data.append({"position": closest_positions, "rotation": rotations})

        logger.debug(f"Closest CV positions: {result_data}")

        return result_data

    finally:
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def ep_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the ep positions of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            positions, _ = curve_obj.get_edit_positions()
            rotations = []
            if include_rotation:
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, positions, **kwargs)

            positions = [[v.x, v.y, v.z] for v in positions]
            result_data.append({"position": positions, "rotation": rotations})

        logger.debug(f"EP positions: {result_data}")

        return result_data

    finally:
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def length_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the length of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        length (float): The length of the curve. Default is 1.0.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
            positions, _ = curve_positions_obj.get_positions_length(num_divisions=divisions)
            rotations = []
            if include_rotation:
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, positions, **kwargs)

            positions = [[v.x, v.y, v.z] for v in positions]
            result_data.append({"position": positions, "rotation": rotations})

        logger.debug(f"Positions from length: {result_data}")

        return result_data

    finally:
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def param_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the parameter of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
            positions, _ = curve_positions_obj.get_positions_param(num_divisions=divisions)
            rotations = []
            if include_rotation:
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, positions, **kwargs)

            positions = [[v.x, v.y, v.z] for v in positions]
            result_data.append({"position": positions, "rotation": rotations})

        logger.debug(f"Positions from parameter: {result_data}")

        return result_data

    finally:
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def cloud_positions(**kwargs) -> list[dict[str, list[list[float]]]]:
    """Get the positions from the cloud of the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        include_rotation (bool): Whether to include rotation. Default is False.
        divisions (int): The number of divisions. Default is 1.
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        list[{position: list[float], rotation: list[float]}]: The position and rotation.
    """
    curves, surfaces, temp_curves = _get_selected_curves_or_surfaces(**kwargs)
    if not curves:
        logger.warning("No valid nurbsCurve or nurbsSurface selected.")
        return

    include_rotation = kwargs.pop("include_rotation", False)
    divisions = kwargs.pop("divisions", 1)

    try:
        result_data = []
        for i, curve in enumerate(curves):
            curve_obj = lib_nurbsCurve.NurbsCurve(curve)
            curve_positions_obj = lib_nurbsCurve.NurbsCurvePositions(curve_obj)
            positions, _ = curve_positions_obj.get_positions_cloud(num_divisions=divisions)
            rotations = []
            if include_rotation:
                if surfaces:
                    kwargs["original_surface"] = surfaces[i] if i < len(surfaces) else None
                rotations = _get_curve_rotations(curve, positions, **kwargs)

            positions = [[v.x, v.y, v.z] for v in positions]
            result_data.append({"position": positions, "rotation": rotations})

        logger.debug(f"Positions from cloud: {result_data}")

        return result_data

    finally:
        if temp_curves:
            for temp_curve in temp_curves:
                try:
                    temp_transform = cmds.listRelatives(temp_curve, parent=True, path=True)[0]
                    cmds.delete(temp_transform)
                    logger.debug(f"Deleted temp curve: {temp_transform}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp curve: {e}")


def _get_selected_curves() -> list[str]:
    """Get the selected nurbsCurve.

    Returns:
        list[str]: The selected nurbsCurve.
    """
    return cmds.ls(sl=True, dag=True, type="nurbsCurve", ni=True)


def _get_selected_curves_or_surfaces(**kwargs) -> tuple[list[str], Optional[list[str]], Optional[list[str]]]:
    """Get the selected nurbsCurve or nurbsSurface.

    Keyword Args:
        surface_direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        tuple[list[str], list[str] | None, list[str] | None]: The selected curves, original surfaces (if any), and temporary curves (if any).
    """
    curves = cmds.ls(sl=True, dag=True, type="nurbsCurve", ni=True)
    surfaces = cmds.ls(sl=True, dag=True, type="nurbsSurface", ni=True)

    if not curves and not surfaces:
        return [], None, None

    # If only curves selected, return them
    if curves and not surfaces:
        return curves, None, None

    # If surfaces selected, convert to isoparm curves
    surface_direction = kwargs.get("surface_direction", "u")
    temp_curves = []
    for surface in surfaces:
        temp_curve = _convert_surface_to_isoparm_curve(surface, surface_direction)
        if temp_curve:
            temp_curves.append(temp_curve)

    return temp_curves, surfaces, temp_curves


def _convert_surface_to_isoparm_curve(surface: str, direction: str = "u") -> Optional[str]:
    """Convert nurbsSurface to isoparm curve at center.

    Args:
        surface (str): The surface shape name.
        direction (str): The direction of the isoparm curve. Default is 'u'. 'u', 'v'

    Returns:
        str | None: The temporary curve shape name.
    """
    if direction not in ["u", "v"]:
        raise ValueError("Invalid direction. Use 'u' or 'v'.")

    try:
        # Get surface transform
        surface_transform = cmds.listRelatives(surface, parent=True, path=True)[0]

        # Duplicate isoparm curve at center (0.5)
        isoparm = f"{surface_transform}.{direction}[0.5]"
        temp_curve_transform = cmds.duplicateCurve(isoparm, ch=False, rn=False, local=False)[0]

        # Get curve shape
        temp_curve_shape = cmds.listRelatives(temp_curve_transform, shapes=True, path=True)[0]

        logger.debug(f"Created temp isoparm curve: {temp_curve_shape} from {surface}")

        return temp_curve_shape

    except Exception as e:
        logger.error(f"Failed to convert surface to isoparm curve: {e}")
        return None


def _get_curve_rotations(curve: str, positions: list[om.MPoint], **kwargs) -> list[list[float]]:
    """Get the curve rotations.

    Args:
        curve (str): The curve name.
        positions (list[list[float]]): The curve positions.

    Keyword Args:
        aim_vector_method (str): The aim vector method. Default is 'tangent'. 'tangent', 'next_point', 'previous_point'
        up_vector_method (str): The up vector method. Default is 'normal'. 'scene_up', 'normal', 'surface_normal'
        original_surface (str): The original surface shape name (if converted from surface).

    Notes:
        - If the up_vector_method is 'surface_normal' and original_surface is provided,
          the normal from the closest point on the surface will be used.
        - If not found the surface, the up_vector_method will be 'normal'.

    Returns:
        list[list[float]]: The curve rotations.
    """
    aim_vector_method = kwargs.get("aim_vector_method", "tangent")  # 'tangent', 'next_point', 'previous_point'
    up_vector_method = kwargs.get("up_vector_method", "normal")  # 'scene_up', 'normal', 'surface_normal'
    original_surface = kwargs.get("original_surface")

    if aim_vector_method not in ["tangent", "next_point", "previous_point"]:
        raise ValueError("Invalid aim vector method.")

    if up_vector_method not in ["scene_up", "normal", "surface_normal"]:
        raise ValueError("Invalid up vector method.")

    curve_obj = lib_nurbsCurve.NurbsCurve(curve)

    if up_vector_method == "surface_normal":
        surface = None

        # If original_surface is provided (converted from surface), use it
        if original_surface:
            surface = lib_nurbsSurface.NurbsSurface(original_surface)
            iso_param = None
            iso_direction = None
        else:
            # Otherwise, try to find surface from curveFromSurfaceIso connection
            curve_iso = cmds.listConnections(f"{curve}.create", type="curveFromSurfaceIso")
            if not curve_iso:
                logger.warning("No valid curveFromSurfaceIso.")
            else:
                surface_shape = cmds.listConnections(f"{curve_iso[0]}.inputSurface", type="nurbsSurface", shapes=True)

                if not surface_shape:
                    logger.warning("No valid nurbsSurface.")
                else:
                    surface = lib_nurbsSurface.NurbsSurface(surface_shape[0])
                    iso_param = cmds.getAttr(f"{curve_iso[0]}.isoparmValue")
                    iso_direction = cmds.getAttr(f"{curve_iso[0]}.isoparmDirection")

        if not surface:
            logger.warning("No valid nurbsSurface.")
            up_vector_method = "normal"

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
            # If original_surface is provided, get normal from closest point
            if original_surface:
                _, surface_params_list = surface.get_closest_positions([positions[i]])
                up_vector = surface.get_normal(surface_params_list[0])
            else:
                # Otherwise, use isoparm curve parameters
                params = iso_direction == 0 and [param, iso_param] or [iso_param, param]
                up_vector = surface.get_normal(params)

        # Get the rotation
        rotation = lib_math.vector_to_rotation(aim_vector, up_vector, primary_axis="z", secondary_axis="x")
        rotations.append(rotation)

    return rotations
