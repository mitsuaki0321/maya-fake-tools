"""CurveWeightSetting class for applying weights to curves."""

from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_nurbsCurve, lib_skinCluster
from .constants import (
    EASE_IN,
    EASE_INOUT,
    EASE_OUT,
    METHOD_EASE,
    METHOD_LINEAR,
    METHOD_STEP,
    OBJECT_TYPE_CURVE,
    VALID_EASE_TYPES,
    VALID_WEIGHT_METHODS,
)

logger = getLogger(__name__)


class CurveWeightSetting:
    """Curve weight setting class.

    This class applies weights to a nurbsCurve based on influence positions along the curve.
    Weights are calculated according to the curve length relative to influence positions,
    and can optionally be smoothed.
    """

    def __init__(self, curve: str) -> None:
        """Initialize the CurveWeightSetting class.

        Args:
            curve (str): Curve transform name.

        Raises:
            ValueError: If curve is invalid or doesn't have a skinCluster.
        """
        if not curve:
            raise ValueError("No curve specified.")

        if not cmds.objExists(curve):
            raise ValueError(f"Curve not found: {curve}")

        curve_shape = cmds.listRelatives(curve, s=True, f=True, ni=True)
        if not curve_shape:
            raise ValueError(f"No shape found on curve: {curve}")

        if cmds.nodeType(curve_shape[0]) != OBJECT_TYPE_CURVE:
            raise ValueError(f"Invalid node type '{cmds.nodeType(curve_shape[0])}'. Expected '{OBJECT_TYPE_CURVE}'.")

        skin_cluster = lib_skinCluster.get_skinCluster(curve_shape[0])
        if not skin_cluster:
            raise ValueError(f"No skinCluster found on curve: {curve}")

        # Store curve information
        self.curve = curve
        self.nurbs_curve = lib_nurbsCurve.NurbsCurve(curve_shape[0])
        self.cv_positions = self.nurbs_curve.get_cv_positions()
        self.num_cvs = self.nurbs_curve.num_cvs
        self.is_closed = self.nurbs_curve.form != "open"
        self.total_length = self.nurbs_curve.get_length()
        self.skin_cluster = skin_cluster

    def execute(self, method: str = METHOD_LINEAR, smooth_iterations: int = 10) -> None:
        """Calculate and apply weights to the curve.

        Args:
            method (str): Weight calculation method. One of: 'linear', 'ease', 'step'.
            smooth_iterations (int): Number of smoothing iterations.

        Raises:
            ValueError: If method is invalid.
        """
        # Validate method
        if method not in VALID_WEIGHT_METHODS:
            raise ValueError(f"Invalid method '{method}'. Valid options are: {VALID_WEIGHT_METHODS}")

        # Get influences
        infs = cmds.skinCluster(self.skin_cluster, q=True, inf=True)

        # Get CV positions along curve (as length values)
        _, cv_params = self.nurbs_curve.get_closest_positions(self.cv_positions)
        cv_lengths = [self.nurbs_curve.fn.findLengthFromParam(cv_param) for cv_param in cv_params]

        # Get influence positions along curve (as length values)
        inf_positions = [cmds.xform(inf, q=True, ws=True, t=True) for inf in infs]
        _, inf_params = self.nurbs_curve.get_closest_positions(inf_positions)
        inf_lengths = [self.nurbs_curve.fn.findLengthFromParam(inf_param) for inf_param in inf_params]

        # Sort influences by their position along the curve
        sorted_infs, sorted_lengths = zip(*sorted(zip(infs, inf_lengths, strict=False), key=lambda x: x[1]), strict=False)

        # Calculate weights
        cv_weights = self._calculate_weights(cv_lengths, sorted_lengths, method)

        # Apply smoothing if requested
        if smooth_iterations > 0:
            cv_weights = self._smooth_weights(cv_weights, smooth_iterations)

        # Apply weights to curve
        cmds.skinCluster(self.skin_cluster, e=True, normalizeWeights=0)
        for i in range(len(cv_lengths)):
            cmds.skinPercent(self.skin_cluster, f"{self.curve}.cv[{i}]", transformValue=list(zip(sorted_infs, cv_weights[i], strict=False)))
        cmds.skinCluster(self.skin_cluster, e=True, normalizeWeights=1)

        logger.debug(f"Applied weights to curve: {self.curve} using method '{method}'")

    def _calculate_weights(self, cv_lengths: list[float], inf_lengths: list[float], method: str) -> list[list[float]]:
        """Calculate weights for each CV based on influence positions along the curve.

        Args:
            cv_lengths (list[float]): Length values of CVs along the curve.
            inf_lengths (list[float]): Length values of influences along the curve.
            method (str): Weight calculation method ('linear', 'ease', or 'step').

        Returns:
            list[list[float]]: Weights for each CV (one list of weights per CV).

        Raises:
            ValueError: If method is invalid.
        """
        if method not in VALID_WEIGHT_METHODS:
            raise ValueError(f"Invalid method '{method}'. Valid options are: {VALID_WEIGHT_METHODS}")

        cv_weights = []
        num_infs = len(inf_lengths)

        for cv_length in cv_lengths:
            weights = [0.0] * num_infs
            weight_assigned = False

            # Check if CV is between two influences
            for j in range(num_infs - 1):
                # CV exactly at influence position
                if cv_length == inf_lengths[j]:
                    weights[j] = 1.0
                    weight_assigned = True
                    break
                elif cv_length == inf_lengths[j + 1]:
                    weights[j + 1] = 1.0
                    weight_assigned = True
                    break
                # CV between two influences
                elif inf_lengths[j] < cv_length < inf_lengths[j + 1]:
                    # Calculate interpolation factor (0 to 1)
                    t = (cv_length - inf_lengths[j]) / (inf_lengths[j + 1] - inf_lengths[j])

                    # Apply weight calculation method
                    if method == METHOD_LINEAR:
                        weights[j] = 1.0 - t
                        weights[j + 1] = t
                    elif method == METHOD_EASE:
                        eased_t = self._ease_weight(t, ease_type=EASE_INOUT)
                        weights[j] = 1.0 - eased_t
                        weights[j + 1] = eased_t
                    elif method == METHOD_STEP:
                        weights[j] = 1.0

                    weight_assigned = True
                    break

            # Handle out-of-range CVs
            if not weight_assigned:
                if self.is_closed:
                    # For closed curves, interpolate between last and first influence
                    if cv_length > inf_lengths[-1]:
                        numerator = cv_length - inf_lengths[-1]
                    else:
                        numerator = cv_length + self.total_length - inf_lengths[-1]

                    if inf_lengths[0] > inf_lengths[-1]:
                        denominator = inf_lengths[0] - inf_lengths[-1]
                    else:
                        denominator = inf_lengths[0] + self.total_length - inf_lengths[-1]

                    t = numerator / denominator

                    # Apply weight calculation method
                    if method == METHOD_LINEAR:
                        weights[-1] = 1.0 - t
                        weights[0] = t
                    elif method == METHOD_EASE:
                        eased_t = self._ease_weight(t, ease_type=EASE_INOUT)
                        weights[-1] = 1.0 - eased_t
                        weights[0] = eased_t
                    elif method == METHOD_STEP:
                        weights[-1] = 1.0
                else:
                    # For open curves, clamp to nearest influence
                    if cv_length < inf_lengths[0]:
                        weights[0] = 1.0
                    elif cv_length > inf_lengths[-1]:
                        weights[-1] = 1.0

            # Normalize weights
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]

            cv_weights.append(weights)

        logger.debug(f"Calculated {len(cv_weights)} CV weights using method '{method}'")

        return cv_weights

    def _smooth_weights(self, current_weights: list[list[float]], iterations: int = 10) -> list[list[float]]:
        """Smooth weights by blending with neighboring CV weights.

        Uses distance-weighted averaging to blend weights with neighbors.
        For closed curves, the first and last CVs are treated as neighbors.

        Args:
            current_weights (list[list[float]]): Weights before smoothing.
            iterations (int): Number of smoothing iterations.

        Returns:
            list[list[float]]: Smoothed weights.
        """
        # Calculate distances between adjacent CVs
        distances = []
        for i in range(self.num_cvs - 1):
            distances.append(self.cv_positions[i + 1].distanceTo(self.cv_positions[i]))

        num_infs = len(current_weights[0])

        # Build neighbor indices for each CV
        neighbor_indices = []
        for i in range(self.num_cvs):
            if i == 0:
                # First CV
                if self.is_closed:
                    # For closed curves, neighbors are: last, self, next
                    neighbor_indices.append([self.num_cvs - 1, i, i + 1])
                else:
                    # For open curves, first CV has no neighbors (skip smoothing)
                    neighbor_indices.append([])
            elif i == self.num_cvs - 1:
                # Last CV
                if self.is_closed:
                    # For closed curves, neighbors are: prev, self, first
                    neighbor_indices.append([i - 1, i, 0])
                else:
                    # For open curves, last CV has no neighbors (skip smoothing)
                    neighbor_indices.append([])
            else:
                # Interior CVs: prev, self, next
                neighbor_indices.append([i - 1, i, i + 1])

        # Perform smoothing iterations
        smooth_weights = [[0.0] * num_infs for _ in range(self.num_cvs)]
        for _ in range(iterations):
            for i in range(self.num_cvs):
                # Skip smoothing for CVs without neighbors (open curve endpoints)
                if not neighbor_indices[i]:
                    smooth_weights[i] = current_weights[i]
                    continue

                # Collect neighbor weights and distances
                neighbor_weights = []
                neighbor_distances = []

                for index in neighbor_indices[i]:
                    neighbor_weights.append(current_weights[index])
                    # Determine distance to neighbor
                    if index < i:
                        neighbor_distances.append(distances[index])
                    elif index > i:
                        neighbor_distances.append(distances[i])
                    else:
                        # Self (current CV)
                        neighbor_distances.append(1.0)

                # Calculate weighted average (inverse distance weighting)
                total_distance = sum(1.0 / d for d in neighbor_distances)
                weighted_sum = [0.0] * num_infs

                for weight, dist in zip(neighbor_weights, neighbor_distances, strict=False):
                    inv_dist = 1.0 / dist
                    for j in range(num_infs):
                        weighted_sum[j] += weight[j] * inv_dist

                smooth_weights[i] = [w / total_distance for w in weighted_sum]

            # Update current weights for next iteration
            current_weights = [w[:] for w in smooth_weights]

        logger.debug(f"Smoothed weights over {iterations} iterations")

        return smooth_weights

    @staticmethod
    def _ease_weight(t: float, ease_type: str = EASE_IN) -> float:
        """Apply easing function to interpolation value.

        Args:
            t (float): Normalized interpolation value (0.0 to 1.0).
            ease_type (str): Type of easing. One of: 'in', 'out', 'inout'.

        Returns:
            float: Eased interpolation value.

        Raises:
            ValueError: If ease_type is invalid.
        """
        if ease_type == EASE_IN:
            # Quadratic ease-in: slow start, fast end
            return t**2
        elif ease_type == EASE_OUT:
            # Quadratic ease-out: fast start, slow end
            return 1 - (1 - t) ** 2
        elif ease_type == EASE_INOUT:
            # Quadratic ease-in-out: slow start and end, fast middle
            if t < 0.5:
                return 2 * (t**2)
            else:
                return 1 - 2 * ((1 - t) ** 2)

        raise ValueError(f"Invalid ease_type '{ease_type}'. Valid options are: {VALID_EASE_TYPES}")
