"""
NurbsCurve and NurbsSurface functions.
"""

from collections.abc import Sequence
from logging import getLogger
import re
from typing import Union

import maya.api.OpenMaya as om
import maya.cmds as cmds

logger = getLogger(__name__)


class NurbsSurface:
    """NurbsSurface class.

    Attributes:
        surface (str): The surface node name.
        dag_path (om.MDagPath): The DAG path of the surface.
        fn (om.MFnNurbsSurface): The function set for the surface.
    """

    def __init__(self, surface: str):
        if not cmds.objExists(surface):
            raise ValueError(f"Node does not exist: {surface}")

        if cmds.nodeType(surface) != "nurbsSurface":
            raise ValueError(f"Invalid type: {surface}")

        selection_list = om.MSelectionList()
        selection_list.add(surface)

        self.surface = surface
        self.dag_path = selection_list.getDagPath(0)
        self.fn = om.MFnNurbsSurface(self.dag_path)

    def get_uv_spans(self) -> tuple[int, int]:
        """Get the UV spans.

        Returns:
            tuple[int, int]: The U and V spans.
        """
        return self.fn.numSpansInU, self.fn.numSpansInV

    def get_uv_range(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Get the UV range.

        Returns:
            tuple[tuple[float, float], tuple[float, float]]: The U and V range.
        """
        return self.fn.knotDomainInU, self.fn.knotDomainInV

    def get_cv_position(self, uv_indices: list[list[int]], as_float: bool = False) -> Union[list[om.MPoint], list[list[float]]]:
        """Get the CV positions.

        Args:
            uv_indices (list[list[int]]): The UV indices.
            as_float (bool): Return the positions as float. Default is False.

        Returns:
            list[om.MPoint] | list[list[float]]: The positions.
        """
        positions = [self.fn.cvPosition(uv_index[0], uv_index[1], om.MSpace.kWorld) for uv_index in uv_indices]
        if as_float:
            return [[p.x, p.y, p.z] for p in positions]

        return positions

    def get_cv_positions(self, as_float: bool = False) -> Union[list[om.MPoint], list[list[float]]]:
        """Get the CV positions.

        Args:
            as_float (bool): Return the positions as float. Default is False.

        Returns:
            Union[list[om.MPoint], list[list[float]]]: The positions.
        """
        positions = list(self.fn.cvPositions(om.MSpace.kWorld))
        if as_float:
            return [[p.x, p.y, p.z] for p in positions]

        return positions

    def get_closest_positions(
        self, reference_positions: list[Sequence[float]], as_float: bool = False
    ) -> tuple[Union[list[om.MPoint], list[list[float]]], list[list[float]]]:  # noqa: E501
        """Get the closest CV positions.

        Args:
            reference_positions (list[Sequence[float]]): The points.
            as_float (bool): Return the positions as float. Default is False.

        Returns:
            tuple[Union[list[om.MPoint], list[list[float]]], list[list[float]]]: The closest positions and parameters.
        """
        positions = []
        params = []
        for reference_position in reference_positions:
            closest_position, param_u, param_v = self.fn.closestPoint(om.MPoint(reference_position), space=om.MSpace.kWorld)

            positions.append(closest_position)
            params.append([param_u, param_v])

        if as_float:
            return [[p.x, p.y, p.z] for p in positions], params

        return positions, params

    def get_normal(self, uv_param: Sequence[float]) -> om.MVector:
        """Get the normal.

        Args:
            uv_param (Sequence[float]): The UV parameter.

        Returns:
            om.MVector: The normal.
        """
        return self.fn.normal(uv_param[0], uv_param[1], om.MSpace.kWorld)

    def get_tangent(self, uv_param: Sequence[float], direction: str = "u") -> om.MVector:
        """Get the tangent.

        Args:
            uv_param (Sequence[float]): The UV parameter.
            direction (str): The direction to get the tangent. Default is 'u'. Options are 'u' and 'v'.

        Returns:
            om.MVector: The tangent.
        """
        if direction not in ["u", "v"]:
            raise ValueError(f"Invalid direction: {direction}")

        return self.fn.tangents(uv_param[0], uv_param[1], om.MSpace.kWorld)[0 if direction == "u" else 1]

    def get_normal_and_tangents(self, uv_params: list[Sequence[float]], direction: str = "u") -> tuple[list[om.MVector], list[om.MVector]]:
        """Get the normal and tangent.

        Args:
            uv_params (list[Sequence[float]]): The UV parameters.
            direction (str): The direction to get the tangent. Default is 'u'. Options are 'u' and 'v'.

        Returns:
            tuple[list[om.MVector], list[om.MVector]]: The normals and tangents.
        """
        if direction not in ["u", "v"]:
            raise ValueError(f"Invalid direction: {direction}")

        direction_index = 0 if direction == "u" else 1

        normals = []
        tangents = []
        for uv_param in uv_params:
            normal = self.fn.normal(uv_param[0], uv_param[1], om.MSpace.kWorld)
            tangent = self.fn.tangents(uv_param[0], uv_param[1], om.MSpace.kWorld)[direction_index]

            normals.append(normal)
            tangents.append(tangent)

        return normals, tangents


def create_curve_on_surface(iso_param: str) -> str:
    """Create curve on the surface.

    Args:
        iso_param (str): The isoparm parameter.

    Returns:
        str: The created curve shape.
    """
    if not iso_param:
        raise ValueError("No isoparm parameters provided.")

    if not cmds.objExists(iso_param):
        raise ValueError(f"Node does not exist: {iso_param}")

    if not cmds.filterExpand(iso_param, sm=45):
        raise ValueError(f"Invalid isoparm parameter: {iso_param}")

    match = re.search(r"\.(u|v)\[(\d+\.?\d*)\]", iso_param)
    if not match:
        raise ValueError(f"Invalid isoparm parameter: {iso_param}")

    direction = match.group(1)
    value = float(match.group(2))
    surface_shape = cmds.ls(iso_param, objectsOnly=True)[0]

    curve_iso = cmds.createNode("curveFromSurfaceIso", n="curveFromSurfaceIso#", ss=True)
    curve_shape = cmds.createNode("nurbsCurve", n="curveShape#", ss=True)

    reverse_direction = "v" if direction == "u" else "u"
    min_range, max_range = cmds.getAttr(f"{surface_shape}.minMaxRange{reverse_direction.capitalize()}")[0]

    cmds.setAttr(f"{curve_iso}.minValue", min_range)
    cmds.setAttr(f"{curve_iso}.maxValue", max_range)
    cmds.setAttr(f"{curve_iso}.isoparmDirection", 1 if direction == "u" else 0)
    cmds.setAttr(f"{curve_iso}.isoparmValue", value)

    cmds.connectAttr(f"{surface_shape}.worldSpace[0]", f"{curve_iso}.inputSurface")
    cmds.connectAttr(f"{curve_iso}.outputCurve", f"{curve_shape}.create")

    cmds.refresh()
    cmds.delete(curve_iso)

    curve = cmds.listRelatives(curve_shape, parent=True)[0]

    logger.debug(f"Create curve on surface: {curve}")

    return curve
