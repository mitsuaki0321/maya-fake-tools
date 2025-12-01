"""LoftWeightSetting class for applying weights to lofted surfaces."""

from logging import getLogger
from math import sqrt

import maya.cmds as cmds

from .constants import (
    VALID_WEIGHT_METHODS,
    WEIGHT_METHOD_EASE,
    WEIGHT_METHOD_LINEAR,
    WEIGHT_METHOD_STEP,
)

logger = getLogger(__name__)


class LoftWeightSetting:
    """Loft weight setting class.

    This class applies weights to a lofted surface (NURBS or mesh) based on joint chain positions.
    Weights are calculated using curve length-based approach (like CurveWeightSetting).

    Two-step process:
    1. Calculate weights for CVs/vertices at chain positions using curve length-based approach
    2. Interpolate weights for intermediate CVs/vertices between chain positions
    """

    def __init__(
        self,
        geometry: str,
        joint_chains: list[list[str]],
        num_chains: int,
        surface_divisions: int,
        curve_divisions: int = 0,
        is_closed: bool = False,
    ) -> None:
        """Initialize the LoftWeightSetting class.

        Args:
            geometry (str): Surface or mesh transform name.
            joint_chains (list[list[str]]): List of joint chains used for lofting.
            num_chains (int): Number of joint chains (curves) used in lofting.
            surface_divisions (int): Number of additional divisions between curves in loft direction.
                0 means no additional divisions.
            curve_divisions (int): Number of CVs inserted between joint positions.
            is_closed (bool): Whether the loft is closed (cylinder shape).

        Raises:
            ValueError: If geometry is invalid or joint_chains is empty.
        """
        if not geometry:
            raise ValueError("No geometry specified.")

        if not cmds.objExists(geometry):
            raise ValueError(f"Geometry not found: {geometry}")

        if not joint_chains:
            raise ValueError("No joint chains specified.")

        if len(joint_chains) < 2:
            raise ValueError("At least 2 joint chains are required.")

        self.geometry = geometry
        self.joint_chains = joint_chains
        self.num_chains = num_chains
        self.surface_divisions = surface_divisions
        self.curve_divisions = curve_divisions
        self.is_closed = is_closed

        # Determine geometry type
        shape = cmds.listRelatives(geometry, s=True, f=True, ni=True)
        if not shape:
            raise ValueError(f"No shape found on geometry: {geometry}")

        self.shape = shape[0]
        self.shape_type = cmds.nodeType(self.shape)

        # Collect all influences from all chains
        self.all_influences = self._collect_influences()

        # Get CV/vertex count info
        self._analyze_geometry()

        # Pre-calculate joint lengths for each chain
        self._calculate_joint_lengths()

    def _collect_influences(self) -> list[str]:
        """Collect all unique joints from all chains as influences.

        Returns:
            list[str]: List of all unique joint names.
        """
        influences = []
        for chain in self.joint_chains:
            for joint in chain:
                if joint not in influences:
                    influences.append(joint)
        return influences

    def _analyze_geometry(self) -> None:
        """Analyze geometry to get CV/vertex layout information."""
        if self.shape_type == "nurbsSurface":
            # Get NURBS surface CV counts
            spans_u = cmds.getAttr(f"{self.shape}.spansU")
            spans_v = cmds.getAttr(f"{self.shape}.spansV")
            self.degree_u = cmds.getAttr(f"{self.shape}.degreeU")
            self.degree_v = cmds.getAttr(f"{self.shape}.degreeV")
            form_u = cmds.getAttr(f"{self.shape}.formU")  # 0=open, 1=closed, 2=periodic
            form_v = cmds.getAttr(f"{self.shape}.formV")

            if form_u == 2:  # periodic
                self.num_cvs_u = spans_u
            else:
                self.num_cvs_u = spans_u + self.degree_u

            if form_v == 2:  # periodic
                self.num_cvs_v = spans_v
            else:
                self.num_cvs_v = spans_v + self.degree_v

            self.total_cvs = self.num_cvs_u * self.num_cvs_v

            logger.debug(f"NURBS Surface: {self.num_cvs_u} x {self.num_cvs_v} CVs (degree U={self.degree_u}, V={self.degree_v})")

        elif self.shape_type == "mesh":
            # Get mesh vertex count
            self.num_vertices = cmds.polyEvaluate(self.geometry, vertex=True)

            # Calculate expected layout based on loft parameters
            chain_length = len(self.joint_chains[0])
            # curve_divisions adds intermediate vertices between each joint
            # Formula: chain_length + (chain_length - 1) * curve_divisions
            self.num_verts_along_curve = chain_length + (chain_length - 1) * self.curve_divisions
            self.num_verts_loft_direction = self._calculate_loft_verts()

            logger.debug(f"Mesh: {self.num_vertices} vertices, expected {self.num_verts_along_curve} x {self.num_verts_loft_direction}")

        else:
            raise ValueError(f"Unsupported geometry type: {self.shape_type}")

    def _calculate_loft_verts(self) -> int:
        """Calculate number of vertices in loft direction for mesh.

        Returns:
            int: Number of vertices in loft direction.
        """
        # surface_divisions=0 means no additional divisions
        # Maya's ss = surface_divisions + 1
        if self.is_closed:
            # For closed loft, seam vertices are merged
            # Formula: num_chains * (surface_divisions + 1)
            return self.num_chains * (self.surface_divisions + 1)
        else:
            return self.num_chains + (self.num_chains - 1) * self.surface_divisions

    def _calculate_joint_lengths(self) -> None:
        """Pre-calculate cumulative lengths for each joint chain.

        This creates a list of length values for each joint in each chain,
        similar to how CurveWeightSetting calculates lengths along a curve.
        """
        self.chain_joint_lengths: list[list[float]] = []
        self.chain_total_lengths: list[float] = []

        for chain in self.joint_chains:
            lengths = [0.0]  # First joint is at length 0
            cumulative_length = 0.0

            for i in range(1, len(chain)):
                # Get positions of consecutive joints
                pos1 = cmds.xform(chain[i - 1], q=True, ws=True, t=True)
                pos2 = cmds.xform(chain[i], q=True, ws=True, t=True)

                # Calculate distance
                dist = sqrt((pos2[0] - pos1[0]) ** 2 + (pos2[1] - pos1[1]) ** 2 + (pos2[2] - pos1[2]) ** 2)
                cumulative_length += dist
                lengths.append(cumulative_length)

            self.chain_joint_lengths.append(lengths)
            self.chain_total_lengths.append(cumulative_length)

        logger.debug(f"Calculated joint lengths for {len(self.joint_chains)} chains")

    def execute(
        self,
        method: str = WEIGHT_METHOD_LINEAR,
        smooth_iterations: int = 0,
        parent_influence_ratio: float = 0.0,
        remove_end: bool = False,
    ) -> str:
        """Create skin cluster and apply weights to the geometry.

        Args:
            method (str): Weight calculation method. One of: 'linear', 'ease', 'step'.
            smooth_iterations (int): Number of smoothing iterations.
            parent_influence_ratio (float): Ratio of influence from parent joint (0.0 to 1.0).
            remove_end (bool): For open chains, merge end joint weights to parent.

        Returns:
            str: Created skin cluster name.

        Raises:
            ValueError: If method is invalid.
        """
        if method not in VALID_WEIGHT_METHODS:
            raise ValueError(f"Invalid method '{method}'. Valid options are: {VALID_WEIGHT_METHODS}")

        # Validate parent_influence_ratio
        if not 0.0 <= parent_influence_ratio <= 1.0:
            raise ValueError(f"Invalid parent_influence_ratio '{parent_influence_ratio}'. Must be between 0.0 and 1.0.")

        # Create skin cluster with all influences
        skin_cluster = cmds.skinCluster(
            self.all_influences,
            self.geometry,
            toSelectedBones=True,
            bindMethod=0,
            normalizeWeights=1,
            weightDistribution=0,
        )[0]

        logger.info(f"Created skin cluster: {skin_cluster}")

        # Calculate and apply weights
        self._apply_weights(skin_cluster, method, smooth_iterations, parent_influence_ratio, remove_end)

        logger.info(f"Applied weights to {self.geometry}")

        return skin_cluster

    def _apply_weights(
        self, skin_cluster: str, method: str, smooth_iterations: int, parent_influence_ratio: float, remove_end: bool
    ) -> None:
        """Apply weights to geometry.

        Args:
            skin_cluster (str): Skin cluster name.
            method (str): Weight calculation method.
            smooth_iterations (int): Number of smoothing iterations.
            parent_influence_ratio (float): Ratio of influence from parent joint.
            remove_end (bool): Whether to merge end joint weights to parent.
        """
        # Step 1: Calculate weights for each chain position (curve direction)
        chain_position_weights = self._calculate_chain_position_weights(method, parent_influence_ratio, remove_end)

        # Step 2: Apply smoothing to chain position weights (curve direction only)
        if smooth_iterations > 0:
            chain_position_weights = self._smooth_chain_weights(chain_position_weights, smooth_iterations)

        # Step 3: Apply weights to all CVs/vertices (interpolate in loft direction)
        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=0)

        if self.shape_type == "nurbsSurface":
            self._apply_nurbs_weights(skin_cluster, chain_position_weights)
        else:
            self._apply_mesh_weights(skin_cluster, chain_position_weights)

        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=1)

    def _calculate_chain_position_weights(self, method: str, parent_influence_ratio: float, remove_end: bool) -> list[list[list[float]]]:
        """Calculate weights for each CV/vertex at chain positions.

        This uses the curve length-based approach from CurveWeightSetting.

        Args:
            method (str): Weight calculation method.
            parent_influence_ratio (float): Ratio of influence from parent joint.
            remove_end (bool): Whether to merge end joint weights to parent.

        Returns:
            list[list[list[float]]]: Weights for each chain, each CV position.
                Shape: [num_chains][num_cvs_in_curve_direction][num_influences]
        """
        all_chain_weights = []

        for chain_index in range(self.num_chains):
            chain = self.joint_chains[chain_index]
            joint_lengths = self.chain_joint_lengths[chain_index]
            total_length = self.chain_total_lengths[chain_index]

            # Get number of CVs/vertices in curve direction
            if self.shape_type == "nurbsSurface":
                num_cvs_curve = self.num_cvs_u
            else:
                num_cvs_curve = self.num_verts_along_curve

            # Calculate CV positions along the chain (as length values)
            cv_lengths = self._calculate_cv_lengths(num_cvs_curve, total_length)

            # Calculate weights for each CV
            chain_weights = self._calculate_weights_for_chain(cv_lengths, joint_lengths, chain, method, parent_influence_ratio)

            # Merge end influence weights if requested
            if remove_end and not self.is_closed:
                chain_weights = self._merge_end_influence_weights(chain_weights, chain)

            all_chain_weights.append(chain_weights)

        return all_chain_weights

    def _calculate_cv_lengths(self, num_cvs: int, total_length: float) -> list[float]:
        """Calculate length values for CVs evenly distributed along the chain.

        Args:
            num_cvs (int): Number of CVs in curve direction.
            total_length (float): Total length of the joint chain.

        Returns:
            list[float]: Length values for each CV.
        """
        if num_cvs <= 1:
            return [0.0]

        return [total_length * i / (num_cvs - 1) for i in range(num_cvs)]

    def _calculate_weights_for_chain(
        self,
        cv_lengths: list[float],
        joint_lengths: list[float],
        chain: list[str],
        method: str,
        parent_influence_ratio: float,
    ) -> list[list[float]]:
        """Calculate weights for CVs in a single chain.

        This implements the same algorithm as CurveWeightSetting._calculate_weights.

        Args:
            cv_lengths (list[float]): Length values of CVs along the chain.
            joint_lengths (list[float]): Length values of joints along the chain.
            chain (list[str]): Joint names in the chain.
            method (str): Weight calculation method.
            parent_influence_ratio (float): Ratio of influence from parent joint.

        Returns:
            list[list[float]]: Weights for each CV.
        """
        num_influences = len(self.all_influences)
        num_joints = len(chain)
        cv_weights = []

        for cv_length in cv_lengths:
            weights = [0.0] * num_influences
            primary_influence_indices = []

            # Find which joint segment this CV falls in
            weight_assigned = False
            for j in range(num_joints - 1):
                joint_length_a = joint_lengths[j]
                joint_length_b = joint_lengths[j + 1]

                # CV exactly at joint position
                if cv_length == joint_length_a:
                    inf_index = self.all_influences.index(chain[j])
                    weights[inf_index] = 1.0
                    primary_influence_indices.append(inf_index)
                    weight_assigned = True
                    break
                elif cv_length == joint_length_b:
                    inf_index = self.all_influences.index(chain[j + 1])
                    weights[inf_index] = 1.0
                    primary_influence_indices.append(inf_index)
                    weight_assigned = True
                    break
                # CV between two joints
                elif joint_length_a < cv_length < joint_length_b:
                    t = (cv_length - joint_length_a) / (joint_length_b - joint_length_a)
                    weight_a, weight_b = self._interpolate_weight(t, method)

                    inf_index_a = self.all_influences.index(chain[j])
                    inf_index_b = self.all_influences.index(chain[j + 1])

                    weights[inf_index_a] = weight_a
                    weights[inf_index_b] = weight_b
                    primary_influence_indices.extend([inf_index_a, inf_index_b])
                    weight_assigned = True
                    break

            # Handle out-of-range CVs
            if not weight_assigned:
                if cv_length <= joint_lengths[0]:
                    # Before first joint
                    inf_index = self.all_influences.index(chain[0])
                    weights[inf_index] = 1.0
                    primary_influence_indices.append(inf_index)
                elif cv_length >= joint_lengths[-1]:
                    # After last joint
                    inf_index = self.all_influences.index(chain[-1])
                    weights[inf_index] = 1.0
                    primary_influence_indices.append(inf_index)

            # Apply parent influence
            if parent_influence_ratio > 0.0:
                for inf_index in primary_influence_indices:
                    weights = self._apply_parent_influence(weights, inf_index, parent_influence_ratio, chain)

            # Normalize weights
            weights = self._normalize_weights(weights)
            cv_weights.append(weights)

        return cv_weights

    def _apply_nurbs_weights(self, skin_cluster: str, chain_position_weights: list[list[list[float]]]) -> None:
        """Apply weights to NURBS surface CVs.

        Args:
            skin_cluster (str): Skin cluster name.
            chain_position_weights (list): Pre-calculated weights for each chain position.
        """
        # Get chain position indices in V direction
        chain_v_indices = self._get_chain_v_indices_nurbs()

        for cv_u in range(self.num_cvs_u):  # curve direction
            for cv_v in range(self.num_cvs_v):  # loft direction
                cv_name = f"{self.geometry}.cv[{cv_u}][{cv_v}]"

                # Determine weights for this CV
                weights = self._get_weights_for_loft_position(cv_u, cv_v, chain_v_indices, chain_position_weights, is_nurbs=True)

                # Apply weights
                transform_values = list(zip(self.all_influences, weights))
                cmds.skinPercent(skin_cluster, cv_name, transformValue=transform_values)

    def _apply_mesh_weights(self, skin_cluster: str, chain_position_weights: list[list[list[float]]]) -> None:
        """Apply weights to mesh vertices.

        Args:
            skin_cluster (str): Skin cluster name.
            chain_position_weights (list): Pre-calculated weights for each chain position.
        """
        # Get chain position indices in loft direction (row indices)
        chain_row_indices = self._get_chain_row_indices_mesh()

        for vtx_index in range(self.num_vertices):
            vtx_name = f"{self.geometry}.vtx[{vtx_index}]"

            # Convert to grid position
            row = vtx_index // self.num_verts_along_curve  # loft direction
            col = vtx_index % self.num_verts_along_curve  # curve direction

            # Determine weights for this vertex
            weights = self._get_weights_for_loft_position(col, row, chain_row_indices, chain_position_weights, is_nurbs=False)

            # Apply weights
            transform_values = list(zip(self.all_influences, weights))
            cmds.skinPercent(skin_cluster, vtx_name, transformValue=transform_values)

    def _get_chain_v_indices_nurbs(self) -> list[int]:
        """Get V indices that correspond to chain positions for NURBS surface.

        Returns:
            list[int]: V indices for each chain position.
        """
        # surface_divisions=0 means no additional divisions
        # Maya's ss = surface_divisions + 1
        maya_ss = self.surface_divisions + 1

        if self.is_closed:
            # For closed NURBS (periodic), CV indices follow a specific pattern:
            # - First chain (A) is always at v=1 (offset by 1)
            # - Subsequent chains are spaced by maya_ss (surface_divisions + 1)
            # Example (3 chains, surface_divisions=1, maya_ss=2, num_cvs_v=6):
            #   chain 0 -> v=1, chain 1 -> v=3, chain 2 -> v=5
            return [(1 + chain_idx * maya_ss) % self.num_cvs_v for chain_idx in range(self.num_chains)]
        else:
            # For open NURBS, chains are at evenly spaced V positions
            if self.num_chains == 1:
                return [0]
            step = (self.num_cvs_v - 1) / (self.num_chains - 1)
            return [int(round(i * step)) for i in range(self.num_chains)]

    def _get_chain_row_indices_mesh(self) -> list[int]:
        """Get row indices that correspond to chain positions for mesh.

        Returns:
            list[int]: Row indices for each chain position.
        """
        # surface_divisions=0 means no additional divisions
        # Maya's ss = surface_divisions + 1
        maya_ss = self.surface_divisions + 1

        if self.is_closed:
            # For closed mesh (after seam merge):
            # Chains are evenly spaced with maya_ss (surface_divisions + 1) between each
            # Chain 0 at row 0, chain 1 at row maya_ss, etc.
            return [i * maya_ss for i in range(self.num_chains)]
        else:
            # For open mesh, chains are at evenly spaced row positions
            if self.num_chains == 1:
                return [0]
            step = (self.num_verts_loft_direction - 1) / (self.num_chains - 1)
            return [int(round(i * step)) for i in range(self.num_chains)]

    def _get_weights_for_loft_position(
        self,
        curve_pos: int,
        loft_pos: int,
        chain_indices: list[int],
        chain_position_weights: list[list[list[float]]],
        is_nurbs: bool,
    ) -> list[float]:
        """Get weights for a CV/vertex at a specific loft position.

        If the position is at a chain, returns the pre-calculated weights.
        If between chains, interpolates between adjacent chain weights.

        Args:
            curve_pos (int): Position in curve direction (CV index or column).
            loft_pos (int): Position in loft direction (CV index or row).
            chain_indices (list[int]): Loft indices that correspond to chain positions.
            chain_position_weights (list): Pre-calculated weights for each chain.
            is_nurbs (bool): Whether this is for NURBS surface.

        Returns:
            list[float]: Interpolated weights.
        """
        num_influences = len(self.all_influences)

        # Check if this position is exactly at a chain
        for chain_idx, chain_loft_idx in enumerate(chain_indices):
            if loft_pos == chain_loft_idx:
                return chain_position_weights[chain_idx][curve_pos]

        # Find which two chains this position is between
        chain_a_idx, chain_b_idx, t = self._find_adjacent_chains(loft_pos, chain_indices, is_nurbs)

        # Get weights from both chains
        weights_a = chain_position_weights[chain_a_idx][curve_pos]
        weights_b = chain_position_weights[chain_b_idx][curve_pos]

        # Interpolate weights
        interpolated = [0.0] * num_influences
        for i in range(num_influences):
            interpolated[i] = weights_a[i] * (1.0 - t) + weights_b[i] * t

        return self._normalize_weights(interpolated)

    def _find_adjacent_chains(self, loft_pos: int, chain_indices: list[int], is_nurbs: bool) -> tuple[int, int, float]:
        """Find the two chains adjacent to a loft position and interpolation factor.

        Args:
            loft_pos (int): Position in loft direction.
            chain_indices (list[int]): Loft indices that correspond to chain positions.
            is_nurbs (bool): Whether this is for NURBS surface.

        Returns:
            tuple[int, int, float]: (chain_a_index, chain_b_index, interpolation_factor)
        """
        # Sort chain indices with their original chain index
        sorted_chains = sorted(enumerate(chain_indices), key=lambda x: x[1])

        # Find which segment the loft position falls in
        for i in range(len(sorted_chains) - 1):
            chain_a_idx, loft_a = sorted_chains[i]
            chain_b_idx, loft_b = sorted_chains[i + 1]

            if loft_a <= loft_pos <= loft_b:
                if loft_b == loft_a:
                    t = 0.0
                else:
                    t = (loft_pos - loft_a) / (loft_b - loft_a)
                return chain_a_idx, chain_b_idx, t

        # Handle closed loft - interpolate between last and first chain
        if self.is_closed:
            last_chain_idx, last_loft = sorted_chains[-1]
            first_chain_idx, first_loft = sorted_chains[0]

            if is_nurbs:
                total_range = self.num_cvs_v
            else:
                total_range = self.num_verts_loft_direction

            if loft_pos > last_loft:
                # Between last chain and wrap-around
                wrap_distance = total_range - last_loft + first_loft
                t = (loft_pos - last_loft) / wrap_distance if wrap_distance > 0 else 0.0
                return last_chain_idx, first_chain_idx, t
            elif loft_pos < first_loft:
                # Before first chain (wrapped from end)
                wrap_distance = total_range - last_loft + first_loft
                t = (total_range - last_loft + loft_pos) / wrap_distance if wrap_distance > 0 else 0.0
                return last_chain_idx, first_chain_idx, t

        # Fallback: clamp to nearest chain
        if loft_pos <= sorted_chains[0][1]:
            return sorted_chains[0][0], sorted_chains[0][0], 0.0
        else:
            return sorted_chains[-1][0], sorted_chains[-1][0], 0.0

    def _merge_end_influence_weights(self, cv_weights: list[list[float]], chain: list[str]) -> list[list[float]]:
        """Merge end influence weights to parent influence for open chains.

        Args:
            cv_weights (list[list[float]]): CV weights before merging.
            chain (list[str]): Joint chain.

        Returns:
            list[list[float]]: CV weights after merging.
        """
        if len(chain) < 2:
            return cv_weights

        end_joint = chain[-1]
        parent_joint = chain[-2]

        end_idx = self.all_influences.index(end_joint)
        parent_idx = self.all_influences.index(parent_joint)

        merged_weights = []
        for weights in cv_weights:
            new_weights = weights[:]
            new_weights[parent_idx] += new_weights[end_idx]
            new_weights[end_idx] = 0.0
            merged_weights.append(self._normalize_weights(new_weights))

        return merged_weights

    def _apply_parent_influence(self, weights: list[float], primary_inf_index: int, parent_ratio: float, chain: list[str]) -> list[float]:
        """Apply parent influence to weights.

        Args:
            weights (list[float]): Current weights.
            primary_inf_index (int): Index of the primary influence.
            parent_ratio (float): Ratio of influence from parent.
            chain (list[str]): Joint chain.

        Returns:
            list[float]: Modified weights.
        """
        if parent_ratio <= 0.0:
            return weights

        # Find the joint in the chain
        primary_joint = self.all_influences[primary_inf_index]
        if primary_joint not in chain:
            return weights

        joint_idx_in_chain = chain.index(primary_joint)
        if joint_idx_in_chain == 0:
            # First joint has no parent
            return weights

        parent_joint = chain[joint_idx_in_chain - 1]
        parent_inf_index = self.all_influences.index(parent_joint)

        # Redistribute weight
        primary_weight = weights[primary_inf_index]
        weights[primary_inf_index] = primary_weight * (1.0 - parent_ratio)
        weights[parent_inf_index] += primary_weight * parent_ratio

        return weights

    @staticmethod
    def _interpolate_weight(t: float, method: str) -> tuple[float, float]:
        """Calculate interpolated weights.

        Args:
            t (float): Interpolation factor (0.0 to 1.0).
            method (str): Weight calculation method.

        Returns:
            tuple[float, float]: (weight_for_first, weight_for_second)
        """
        if method == WEIGHT_METHOD_LINEAR:
            return (1.0 - t, t)
        elif method == WEIGHT_METHOD_EASE:
            # Quadratic ease-in-out
            if t < 0.5:
                eased_t = 2 * (t**2)
            else:
                eased_t = 1 - 2 * ((1 - t) ** 2)
            return (1.0 - eased_t, eased_t)
        elif method == WEIGHT_METHOD_STEP:
            # Step function - 100% to nearest
            return (1.0, 0.0)
        else:
            return (1.0 - t, t)

    @staticmethod
    def _normalize_weights(weights: list[float]) -> list[float]:
        """Normalize weights to sum to 1.0.

        Args:
            weights (list[float]): Weights to normalize.

        Returns:
            list[float]: Normalized weights.
        """
        total = sum(weights)
        if total > 0:
            return [w / total for w in weights]
        return weights

    def _smooth_chain_weights(
        self, chain_position_weights: list[list[list[float]]], iterations: int
    ) -> list[list[list[float]]]:
        """Smooth weights in curve direction only for each chain.

        Uses distance-weighted averaging to blend weights with neighbors,
        similar to CurveWeightSetting._smooth_weights.
        Only smooths in curve direction (along joints), not in loft direction (between chains).

        Args:
            chain_position_weights (list): Weights for each chain, each CV position.
                Shape: [num_chains][num_cvs_in_curve_direction][num_influences]
            iterations (int): Number of smoothing iterations.

        Returns:
            list: Smoothed weights with same shape as input.
        """
        num_influences = len(self.all_influences)
        smoothed_weights = []

        for chain_idx, chain_weights in enumerate(chain_position_weights):
            num_cvs = len(chain_weights)

            # Get total length for this chain (for distance calculation)
            total_length = self.chain_total_lengths[chain_idx]

            # Calculate CV length positions
            cv_lengths = self._calculate_cv_lengths(num_cvs, total_length)

            # Calculate distances between adjacent CVs
            distances = []
            for i in range(num_cvs - 1):
                distances.append(cv_lengths[i + 1] - cv_lengths[i])

            # Perform smoothing iterations
            current_weights = [w[:] for w in chain_weights]

            for _ in range(iterations):
                new_weights = [w[:] for w in current_weights]

                for i in range(num_cvs):
                    # Skip endpoints (no smoothing for first and last CV)
                    if i == 0 or i == num_cvs - 1:
                        continue

                    # Get neighbors: prev, self, next
                    neighbor_indices = [i - 1, i, i + 1]
                    neighbor_distances = [distances[i - 1], 1.0, distances[i]]

                    # Calculate distance-weighted average
                    total_inv_dist = sum(1.0 / d for d in neighbor_distances)
                    weighted_sum = [0.0] * num_influences

                    for idx, dist in zip(neighbor_indices, neighbor_distances):
                        inv_dist = 1.0 / dist
                        for j in range(num_influences):
                            weighted_sum[j] += current_weights[idx][j] * inv_dist

                    new_weights[i] = [w / total_inv_dist for w in weighted_sum]

                current_weights = new_weights

            smoothed_weights.append(current_weights)

        logger.debug(f"Smoothed chain weights {iterations} times (curve direction only)")
        return smoothed_weights


__all__ = ["LoftWeightSetting"]
