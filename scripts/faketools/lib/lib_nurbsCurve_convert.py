"""
NurbsCurve conversion and modification functions.
"""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

from .lib_nurbsCurve import NurbsCurve

logger = getLogger(__name__)


class ConvertNurbsCurve:
    """ConvertNurbsCurve class.

    Attributes:
        curve (str): The curve name.
        nurbs_curve (NurbsCurve): The NurbsCurve object.
    """

    def __init__(self, curve: str):
        """Initialize the ConvertNurbsCurve class.

        Args:
            curve (str): The curve name.
        """
        self.curve = curve
        self.nurbs_curve = NurbsCurve(curve)

    def close_curve(self):
        """Close the curve."""
        cmds.closeCurve(self.curve, ch=False, ps=0, rpo=True)

    def insert_cvs(self, divisions: int = 1):
        """Insert CVs.

        Args:
            divisions (int): The number of divisions. Default is 1.

        Raises:
            ValueError: If divisions is less than 1.
        """
        if divisions < 1:
            raise ValueError("Divisions must be 1 or more.")

        positions = self.nurbs_curve.get_cv_positions()
        degree = self.nurbs_curve.degree
        form_open = self.nurbs_curve.form == "open"
        num_cvs = self.nurbs_curve.num_cvs

        new_positions = []

        # Special case for 2 CVs
        if self.nurbs_curve.num_cvs == 2:
            for j in range(divisions):
                new_positions.append(positions[0] + (positions[1] - positions[0]) * (j + 1) / (divisions + 1))
            new_positions.append(positions[1])

        def _calculate_new_positions(
            nurbs_curve: NurbsCurve, target_positions: list[om.MPoint], target_lengths: list[float], open_form: bool = False
        ) -> list[om.MPoint]:
            """Calculate new positions.

            Args:
                nurbs_curve (NurbsCurve): The NurbsCurve object.
                target_positions (list[om.MPoint]): The target positions.
                target_lengths (list[float]): The target lengths.
                open_form (bool): Whether the form is open. Default is False.

            Returns:
                list[om.MPoint]: The new positions.
            """
            total_length = nurbs_curve.get_length()

            result_positions = []
            for i in range(num_cvs - 1 if open_form else num_cvs):
                result_positions.append(target_positions[i])

                if target_lengths[(i + 1) % num_cvs] > target_lengths[i]:
                    length_diff = target_lengths[(i + 1) % num_cvs] - target_lengths[i]
                else:
                    length_diff = total_length - target_lengths[i] + target_lengths[(i + 1) % num_cvs]

                for j in range(divisions):
                    target_length = target_lengths[i] + length_diff * (j + 1) / (divisions + 1)
                    if target_length > total_length:
                        target_length -= total_length
                    target_param = nurbs_curve.fn.findParamFromLength(target_length)
                    target_position = nurbs_curve.fn.getPointAtParam(target_param, space=om.MSpace.kWorld)

                    result_positions.append(target_position)

            if open_form:
                result_positions.append(target_positions[-1])

            return result_positions

        # Degree 1
        if degree == 1:
            fit_curve = cmds.fitBspline(self.curve, ch=0, tol=0.01)[0]
            fit_curve_shp = cmds.listRelatives(fit_curve, s=True)[0]
            fit_nurbs_curve = NurbsCurve(fit_curve_shp)

            closest_positions, params = fit_nurbs_curve.get_closest_positions(positions)
            lengths = [fit_nurbs_curve.fn.findLengthFromParam(param) for param in params]

            new_positions = _calculate_new_positions(fit_nurbs_curve, closest_positions, lengths, form_open)

            cmds.delete(fit_curve)

        # Degree 3
        elif degree == 3:
            closest_positions, params = self.nurbs_curve.get_closest_positions(positions)
            lengths = [self.nurbs_curve.fn.findLengthFromParam(param) for param in params]

            new_positions = _calculate_new_positions(self.nurbs_curve, closest_positions, lengths, form_open)
        else:
            cmds.error("Degree is not 1 or 3. Unsupported operation.")

        new_positions = [[position.x, position.y, position.z] for position in new_positions]
        inserted_curve = cmds.listRelatives(cmds.curve(d=degree, p=new_positions), s=True)[0]

        if not form_open:
            cmds.closeCurve(inserted_curve, ch=False, ps=0, rpo=True)

        self._transfer_shape(inserted_curve)

        if degree == 3:
            self.center_curve()

    def center_curve(self, iterations: int = 100):
        """Adjust the curve to pass through the center of the CVs.

        Args:
            iterations (int): Number of iterations. Default is 100.
        """
        if self.nurbs_curve.degree != 3:
            logger.debug("Degree is not 3. Cannot center the curve.")
            return

        cv_indices = range(self.nurbs_curve.num_cvs)
        source_positions = self.nurbs_curve.get_cv_positions()

        source_positions = source_positions[:]

        if self.nurbs_curve.form == "open":
            source_positions = source_positions[1:-1]
            cv_indices = cv_indices[1:-1]

        count = 0
        while count < iterations:
            for cv_index, source_position in zip(cv_indices, source_positions, strict=False):
                closest_position, _ = self.nurbs_curve.get_closest_position(source_position)
                goal_position = source_position - closest_position
                cmds.xform(f"{self.curve}.cv[{cv_index}]", t=goal_position, ws=True, r=True)

            if all([self.nurbs_curve.fn.isPointOnCurve(source_position, space=om.MSpace.kWorld) for source_position in source_positions]):
                break

            count += 1

        if count == iterations:
            cmds.warning("Failed to center the curve.")

        logger.debug(f"Loop count: {count} of {iterations}")

    def to_fit_BSpline(self):
        """Convert to BSpline."""
        fit_curve = cmds.fitBspline(self.curve, ch=0, tol=0.01)[0]
        fit_curve_shp = cmds.listRelatives(fit_curve, s=True)[0]

        self._transfer_shape(fit_curve_shp)

    def set_degree(self, degree: int):
        """Set the degree.

        Args:
            degree (int): The degree.

        Raises:
            ValueError: If degree is not 1 or 3.
        """
        if degree not in (1, 3):
            raise ValueError("Degree must be 1 or 3.")

        if degree == self.nurbs_curve.degree:
            logger.debug(f"Degree is already {degree}.")
            return

        if degree == 3 and self.nurbs_curve.num_cvs < 4:
            cmds.error("Degree is 3. The number of CVs must be 4 or more.")

        cmds.rebuildCurve(
            self.curve,
            constructionHistory=False,
            replaceOriginal=True,
            end=1,
            keepRange=0,
            keepControlPoints=True,
            keepEndPoints=False,
            keepTangents=False,
            degree=1,
        )

    def _transfer_shape(self, source_curve: str):
        """Transfer the shape, after delete the source curve.

        Args:
            source_curve (str): The source curve shape.

        Raises:
            ValueError: If source_curve is not a nurbsCurve type.
        """
        if cmds.nodeType(source_curve) != "nurbsCurve":
            raise ValueError("Invalid type.")

        source_nurbs_curve = NurbsCurve(source_curve)
        source_positions = source_nurbs_curve.get_cv_positions()

        curve_transform = cmds.listRelatives(self.curve, p=True)[0]
        curve_matrix = cmds.xform(curve_transform, q=True, ws=True, m=True)

        if not om.MMatrix(curve_matrix).isEquivalent(om.MMatrix.kIdentity, 1e-5):
            source_curve_transform = cmds.listRelatives(source_curve, p=True)[0]
            cmds.xform(source_curve_transform, ws=True, m=curve_matrix)
            for i, position in enumerate(source_positions):
                cmds.xform(f"{source_curve}.cv[{i}]", t=[position.x, position.y, position.z], ws=True)

        input_curve_plug = f"{self.curve}.create"
        original_curve = cmds.geometryAttrInfo(f"{self.curve}.create", originalGeometry=True)
        if original_curve:
            input_curve_plug = original_curve[0].split(".")[0] + ".create"

        cmds.connectAttr(f"{source_curve}.local", input_curve_plug, f=True)
        cmds.refresh()
        source_curve_transform = cmds.listRelatives(source_curve, p=True)[0]
        cmds.delete(source_curve_transform)
