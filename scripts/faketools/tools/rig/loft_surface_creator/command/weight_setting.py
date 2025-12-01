"""LoftWeightSetting class for applying weights to lofted surfaces."""

from logging import getLogger

import maya.cmds as cmds

from .constants import (
    VALID_WEIGHT_METHODS,
    WEIGHT_METHOD_LINEAR,
)

logger = getLogger(__name__)


class LoftWeightSetting:
    """Loft weight setting class.

    This class applies weights to a lofted surface (NURBS or mesh) based on joint chain positions.
    Weights are calculated in two directions:
    - Along curve direction: based on joint positions within each chain
    - Loft direction: based on interpolation between adjacent chains
    """

    def __init__(
        self,
        geometry: str,
        joint_chains: list[list[str]],
        num_chains: int,
        surface_divisions: int,
        is_closed: bool = False,
    ) -> None:
        """Initialize the LoftWeightSetting class.

        Args:
            geometry (str): Surface or mesh transform name.
            joint_chains (list[list[str]]): List of joint chains used for lofting.
            num_chains (int): Number of joint chains (curves) used in lofting.
            surface_divisions (int): Number of divisions between curves in loft direction.
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
            # spansU/V + degreeU/V = numCVsU/V (for non-periodic)
            spans_u = cmds.getAttr(f"{self.shape}.spansU")
            spans_v = cmds.getAttr(f"{self.shape}.spansV")
            degree_u = cmds.getAttr(f"{self.shape}.degreeU")
            degree_v = cmds.getAttr(f"{self.shape}.degreeV")
            form_u = cmds.getAttr(f"{self.shape}.formU")  # 0=open, 1=closed, 2=periodic

            if form_u == 2:  # periodic
                self.num_cvs_u = spans_u
            else:
                self.num_cvs_u = spans_u + degree_u

            self.num_cvs_v = spans_v + degree_v
            self.total_cvs = self.num_cvs_u * self.num_cvs_v

            logger.debug(f"NURBS Surface: {self.num_cvs_u} x {self.num_cvs_v} CVs")

        elif self.shape_type == "mesh":
            # Get mesh vertex count
            self.num_vertices = cmds.polyEvaluate(self.geometry, vertex=True)

            # Calculate expected layout based on loft parameters
            # For mesh from loft: vertices are arranged in a grid
            chain_length = len(self.joint_chains[0])  # Assume all chains have same length
            self.num_verts_along_curve = chain_length
            self.num_verts_loft_direction = self._calculate_loft_verts()

            logger.debug(f"Mesh: {self.num_vertices} vertices, expected {self.num_verts_along_curve} x {self.num_verts_loft_direction}")

        else:
            raise ValueError(f"Unsupported geometry type: {self.shape_type}")

    def _calculate_loft_verts(self) -> int:
        """Calculate number of vertices in loft direction for mesh.

        Returns:
            int: Number of vertices in loft direction.
        """
        # For mesh output with format=3 (CV positions):
        # Each chain creates 1 vertex row
        # Between chains, surface_divisions creates additional rows
        if self.is_closed:
            return self.num_chains * self.surface_divisions
        else:
            return self.num_chains + (self.num_chains - 1) * (self.surface_divisions - 1)

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

        # Create skin cluster with all influences
        skin_cluster = cmds.skinCluster(
            self.all_influences,
            self.geometry,
            toSelectedBones=True,
            bindMethod=0,  # Closest distance
            normalizeWeights=1,
            weightDistribution=0,  # Distance
        )[0]

        logger.info(f"Created skin cluster: {skin_cluster}")

        # Calculate and apply weights based on geometry type
        if self.shape_type == "nurbsSurface":
            self._apply_nurbs_weights(skin_cluster, method)
        else:
            self._apply_mesh_weights(skin_cluster, method)

        # Apply smoothing if requested
        if smooth_iterations > 0:
            self._smooth_weights(skin_cluster, smooth_iterations)

        logger.info(f"Applied weights to {self.geometry}")

        return skin_cluster

    def _apply_nurbs_weights(self, skin_cluster: str, method: str) -> None:
        """Apply weights to NURBS surface CVs.

        Args:
            skin_cluster (str): Skin cluster name.
            method (str): Weight calculation method.
        """
        # Disable normalization during weight setting
        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=0)

        for u in range(self.num_cvs_u):
            for v in range(self.num_cvs_v):
                cv_name = f"{self.geometry}.cv[{u}][{v}]"

                # Calculate weights for this CV
                weights = self._calculate_cv_weights(u, v, method)

                # Apply weights
                transform_values = list(zip(self.all_influences, weights))
                cmds.skinPercent(skin_cluster, cv_name, transformValue=transform_values)

        # Re-enable normalization
        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=1)

    def _apply_mesh_weights(self, skin_cluster: str, method: str) -> None:
        """Apply weights to mesh vertices.

        Args:
            skin_cluster (str): Skin cluster name.
            method (str): Weight calculation method.
        """
        # Disable normalization during weight setting
        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=0)

        for vtx_index in range(self.num_vertices):
            vtx_name = f"{self.geometry}.vtx[{vtx_index}]"

            # Convert vertex index to grid position
            u, v = self._vertex_index_to_uv(vtx_index)

            # Calculate weights for this vertex
            weights = self._calculate_cv_weights(u, v, method)

            # Apply weights
            transform_values = list(zip(self.all_influences, weights))
            cmds.skinPercent(skin_cluster, vtx_name, transformValue=transform_values)

        # Re-enable normalization
        cmds.skinCluster(skin_cluster, e=True, normalizeWeights=1)

    def _vertex_index_to_uv(self, vtx_index: int) -> tuple[int, int]:
        """Convert mesh vertex index to UV grid position.

        Args:
            vtx_index (int): Vertex index.

        Returns:
            tuple[int, int]: (u, v) grid position.
        """
        # Mesh vertices from loft are arranged row by row
        # u = loft direction (between chains)
        # v = along curve direction (along chain)
        u = vtx_index // self.num_verts_along_curve
        v = vtx_index % self.num_verts_along_curve
        return u, v

    def _calculate_cv_weights(self, u: int, v: int, method: str) -> list[float]:
        """Calculate weights for a CV/vertex at grid position (u, v).

        Args:
            u (int): Position in loft direction (which chain).
            v (int): Position along curve direction (which joint in chain).
            method (str): Weight calculation method.

        Returns:
            list[float]: Weights for each influence.
        """
        num_influences = len(self.all_influences)
        weights = [0.0] * num_influences

        # Determine which chain(s) this CV belongs to based on u position
        chain_index, loft_t = self._get_chain_info_from_u(u)

        # Get the joint chains involved
        chain_a_index = chain_index
        chain_b_index = (chain_index + 1) % self.num_chains if self.is_closed else min(chain_index + 1, self.num_chains - 1)

        chain_a = self.joint_chains[chain_a_index]
        chain_b = self.joint_chains[chain_b_index]

        # Calculate along-curve weights for each chain
        joint_index, curve_t = self._get_joint_info_from_v(v, len(chain_a))

        # Get the joints involved in along-curve interpolation
        joint_a1 = chain_a[joint_index]
        joint_a2 = chain_a[min(joint_index + 1, len(chain_a) - 1)]
        joint_b1 = chain_b[joint_index]
        joint_b2 = chain_b[min(joint_index + 1, len(chain_b) - 1)]

        # Calculate along-curve weights (same for both chains)
        curve_weight_1, curve_weight_2 = self._interpolate_weight(curve_t, method)

        # Calculate loft direction weights
        loft_weight_a, loft_weight_b = self._interpolate_weight(loft_t, method)

        # Combine weights
        # Final weight = loft_weight * curve_weight
        if loft_t == 0.0:
            # Exactly on chain A
            weights[self.all_influences.index(joint_a1)] = curve_weight_1
            weights[self.all_influences.index(joint_a2)] = curve_weight_2
        elif loft_t == 1.0 or (chain_a_index == chain_b_index):
            # Exactly on chain B (or same chain if not interpolating)
            weights[self.all_influences.index(joint_b1)] = curve_weight_1
            weights[self.all_influences.index(joint_b2)] = curve_weight_2
        else:
            # Between chains - combine both
            weights[self.all_influences.index(joint_a1)] += loft_weight_a * curve_weight_1
            weights[self.all_influences.index(joint_a2)] += loft_weight_a * curve_weight_2
            weights[self.all_influences.index(joint_b1)] += loft_weight_b * curve_weight_1
            weights[self.all_influences.index(joint_b2)] += loft_weight_b * curve_weight_2

        # Normalize weights
        weights = self._normalize_weights(weights)

        return weights

    def _get_chain_info_from_u(self, u: int) -> tuple[int, float]:
        """Get chain index and interpolation factor from u position.

        Args:
            u (int): Position in loft direction.

        Returns:
            tuple[int, float]: (chain_index, interpolation_factor 0.0-1.0)
        """
        if self.shape_type == "nurbsSurface":
            # For NURBS surface, u directly maps to chain positions
            # u=0 -> chain 0, u=num_cvs_u-1 -> last chain (or wraps if closed)
            total_spans = self.num_chains if self.is_closed else self.num_chains - 1
            if total_spans == 0:
                return 0, 0.0

            # Calculate which segment and position within segment
            segment_size = self.num_cvs_u / total_spans if self.is_closed else (self.num_cvs_u - 1) / total_spans
            if segment_size == 0:
                return 0, 0.0

            chain_index = int(u / segment_size)
            if chain_index >= total_spans:
                chain_index = total_spans - 1

            position_in_segment = (u / segment_size) - chain_index
            return chain_index, position_in_segment

        else:
            # For mesh, similar calculation
            total_spans = self.num_chains if self.is_closed else self.num_chains - 1
            if total_spans == 0:
                return 0, 0.0

            verts_per_span = self.num_verts_loft_direction / total_spans
            if verts_per_span == 0:
                return 0, 0.0

            chain_index = int(u / verts_per_span)
            if chain_index >= total_spans:
                chain_index = total_spans - 1

            position_in_segment = (u / verts_per_span) - chain_index
            return chain_index, min(position_in_segment, 1.0)

    def _get_joint_info_from_v(self, v: int, chain_length: int) -> tuple[int, float]:
        """Get joint index and interpolation factor from v position.

        Args:
            v (int): Position along curve direction.
            chain_length (int): Number of joints in the chain.

        Returns:
            tuple[int, float]: (joint_index, interpolation_factor 0.0-1.0)
        """
        if self.shape_type == "nurbsSurface":
            # For NURBS, v maps to joint positions
            total_joints = chain_length - 1  # Number of segments between joints
            if total_joints <= 0:
                return 0, 0.0

            segment_size = (self.num_cvs_v - 1) / total_joints
            if segment_size == 0:
                return 0, 0.0

            joint_index = int(v / segment_size)
            if joint_index >= total_joints:
                joint_index = total_joints - 1

            position_in_segment = (v / segment_size) - joint_index
            return joint_index, min(position_in_segment, 1.0)

        else:
            # For mesh
            total_joints = chain_length - 1
            if total_joints <= 0:
                return 0, 0.0

            segment_size = (self.num_verts_along_curve - 1) / total_joints if self.num_verts_along_curve > 1 else 1
            if segment_size == 0:
                return 0, 0.0

            joint_index = int(v / segment_size)
            if joint_index >= total_joints:
                joint_index = total_joints - 1

            position_in_segment = (v / segment_size) - joint_index
            return joint_index, min(position_in_segment, 1.0)

    @staticmethod
    def _interpolate_weight(t: float, method: str) -> tuple[float, float]:
        """Calculate interpolated weights.

        Args:
            t (float): Interpolation factor (0.0 to 1.0).
            method (str): Weight calculation method.

        Returns:
            tuple[float, float]: (weight_1, weight_2)
        """
        if method == WEIGHT_METHOD_LINEAR:
            return (1.0 - t, t)
        else:
            # For now, default to linear for all methods
            # Can add ease/step later
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

    def _smooth_weights(self, skin_cluster: str, iterations: int) -> None:
        """Apply weight smoothing.

        Args:
            skin_cluster (str): Skin cluster name.
            iterations (int): Number of smoothing iterations.
        """
        # Use Maya's built-in smooth weights for simplicity
        if self.shape_type == "mesh":
            cmds.select(f"{self.geometry}.vtx[*]")
            for _ in range(iterations):
                cmds.skinCluster(skin_cluster, e=True, smoothWeights=0.5)
            cmds.select(cl=True)

        logger.debug(f"Smoothed weights {iterations} times")


__all__ = ["LoftWeightSetting"]
