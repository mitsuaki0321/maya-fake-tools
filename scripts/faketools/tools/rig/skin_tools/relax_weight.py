"""
Relax skin weights using various methods.
"""

from itertools import chain
from logging import getLogger
import math

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ....lib import lib_mesh, lib_skinCluster

logger = getLogger(__name__)


class SmoothSkinWeights:
    """Smooth skin weights using various methods."""

    def __init__(self, skinCluster: str, vertices: list[str]):
        """Initialize the BaseSkinWeights class.

        Args:
            skinCluster (str): The name of the skinCluster node.
            vertices (list[str]): The list of mesh vertices to be processed.
        """
        # Check the skinCluster node
        if not skinCluster:
            raise ValueError("No skinCluster node specified")

        if not cmds.objExists(skinCluster):
            raise RuntimeError(f"Node does not exist: {skinCluster}")

        if cmds.nodeType(skinCluster) != "skinCluster":
            raise RuntimeError(f"Node is not a skinCluster: {skinCluster}")

        self.skinCluster = skinCluster
        self.infs = cmds.skinCluster(skinCluster, q=True, inf=True)
        self.num_infs = len(self.infs)
        self.vertices = vertices

        # Check the vertices
        if not lib_skinCluster.is_bound_to_skinCluster(skinCluster, vertices):
            raise RuntimeError(f"Vertices are not bound to the skinCluster: {vertices}")

        # Mesh vertex
        shp = cmds.ls(vertices, objectsOnly=True)[0]
        if cmds.nodeType(shp) != "mesh":
            raise RuntimeError(f"Node is not a mesh: {shp}")

        self.mesh = shp
        self.mesh_vertex = lib_mesh.MeshVertex(shp)
        self.indices = self.mesh_vertex.get_vertex_indices(vertices)
        self.num_indices = len(self.indices)

    def calculate_weights(self, *args, **kwargs) -> None:
        """Calculate the weights for the smoothing operation."""
        raise NotImplementedError

    def smooth(self, *args, **kwargs) -> None:
        """Execute the smoothing operation."""
        only_unlock_infs = kwargs.pop("only_unlock_influences", False)
        blend_weights = kwargs.pop("blend_weights", 1.0)
        if blend_weights <= 0 or blend_weights > 1:
            raise ValueError("The blend_weights must be in the range [0, 1]")

        if only_unlock_infs:
            unlocked_infs = lib_skinCluster.get_lock_influences(self.skinCluster, lock=False)
            if not unlocked_infs:
                raise RuntimeError("No unlocked influences found")

            unlocked_infs_status = [inf in unlocked_infs for inf in self.infs]

        if only_unlock_infs or blend_weights < 1:
            before_weights = lib_skinCluster.get_skin_weights(self.skinCluster, self.vertices)

        calc_weights = self.calculate_weights(*args, **kwargs)

        if only_unlock_infs:
            for i in range(self.num_indices):
                unlock_before_weights = []
                unlock_new_weights = []
                for j in range(self.num_infs):
                    if unlocked_infs_status[j]:
                        unlock_before_weights.append(before_weights[i][j])
                        unlock_new_weights.append(calc_weights[i][j])

                unlock_before_weights_total = sum(unlock_before_weights)
                unlock_new_weights_total = sum(unlock_new_weights)

                if unlock_before_weights_total < 1e-5 or unlock_new_weights_total < 1e-5:
                    calc_weights[i] = before_weights[i]
                else:
                    if unlock_before_weights_total < unlock_new_weights_total:
                        for j in range(self.num_infs):
                            if unlocked_infs_status[j]:
                                calc_weights[i][j] = unlock_before_weights_total * calc_weights[i][j] / unlock_new_weights_total
                            else:
                                calc_weights[i][j] = before_weights[i][j]

                    else:
                        unlock_dif_weights_total = unlock_before_weights_total - unlock_new_weights_total

                        for j in range(self.num_infs):
                            if unlocked_infs_status[j]:
                                calc_weights[i][j] = (
                                    unlock_dif_weights_total * (before_weights[i][j] / unlock_before_weights_total) + calc_weights[i][j]
                                )  # noqa
                            else:
                                calc_weights[i][j] = before_weights[i][j]

        if blend_weights < 1:
            for i in range(self.num_indices):
                for j in range(self.num_infs):
                    calc_weights[i][j] = blend_weights * calc_weights[i][j] + (1 - blend_weights) * before_weights[i][j]

        lib_skinCluster.set_skin_weights(self.skinCluster, calc_weights, self.vertices)

    def _get_indices_weights(self, skinCluster: str, indices: list[int]) -> dict[int, list[float]]:
        """Get the vertex indices and weights from the skinCluster.

        Args:
            skinCluster (str): The name of the skinCluster node.
            indices (list[int]): The list of vertex indices.

        Returns:
            dict[int, list[float]]: The vertex indices and their weights.
        """
        vertex_indices = self.mesh_vertex.get_vertex_components(indices)
        weights = lib_skinCluster.get_skin_weights(skinCluster, vertex_indices)

        return {i: w for i, w in zip(indices, weights, strict=False)}

    def _get_indices_positions(self, indices: list[int]) -> dict[int, om.MPoint]:
        """Get the vertex indices and their positions.

        Args:
            indices (list[int]): The list of vertex indices.

        Returns:
            dict[int, om.MPoint]: The vertex indices and their positions.
        """
        positions = self.mesh_vertex.get_vertex_positions(indices)
        return {i: p for i, p in zip(indices, positions, strict=False)}


class LaplacianSkinWeights(SmoothSkinWeights):
    """Smooth skin weights using Laplacian smoothing."""

    def calculate_weights(self, iterations: int = 1) -> None:
        """Calculate the Laplacian weights for the skin weights.

        Args:
            iterations (int): The number of iterations to perform.
        """
        neighbor_indices_list = self.mesh_vertex.get_connected_vertices(self.indices)
        all_indices = list(set(chain.from_iterable(neighbor_indices_list)) | set(self.indices))

        all_indices_weights = self._get_indices_weights(self.skinCluster, all_indices)

        smoothed_weights = [0.0] * self.num_indices
        for _ in range(iterations):
            for i in range(self.num_indices):
                neighbor_weights = [all_indices_weights[neighbor_index] for neighbor_index in neighbor_indices_list[i]]
                smoothed_weights[i] = [sum(w) / len(neighbor_weights) for w in zip(*neighbor_weights, strict=False)]

            if iterations > 1:
                for i, index in enumerate(self.indices):
                    all_indices_weights[index] = smoothed_weights[i]

        logger.debug(f"Smoothed skin weights using Laplacian method: {self.vertices}")

        return smoothed_weights


class RBFSkinWeights(SmoothSkinWeights):
    """Smooth skin weights using Radial Basis Functions (RBF)."""

    @staticmethod
    def gaussian_weight(distance, **kwargs):
        sigma = kwargs.get("sigma", 1.0)
        return math.exp(-(distance**2) / (2 * sigma**2))

    @staticmethod
    def linear_weight(distance):
        return max(1 - distance, 0)

    @staticmethod
    def inverse_distance_weight(distance, **kwargs):
        power = kwargs.get("power", 2)
        if distance == 0:
            return float("inf")  # Handle the case where distance is zero (e.g., self-weight)
        return 1 / (distance**power)

    def get_weight_function(self, weight_type: str):
        """Get the weight function based on the weight type.

        Args:
            weight_type (str): The type of weight function to use ("gaussian", "linear", "inverse_distance").

        Returns:
            function: The weight function.
        """
        weight_function_map = {
            "gaussian": self.gaussian_weight,
            "linear": self.linear_weight,
            "inverse_distance": self.inverse_distance_weight,
        }

        if weight_type not in weight_function_map:
            raise ValueError(f"Unknown weight type: {weight_type}")

        return weight_function_map[weight_type]

    def calculate_weights(self, iterations: int = 1, weight_type: str = "gaussian", options: dict | None = None) -> None:
        """Calculate the weights for the RBF smoothing operation.

        Args:
            iterations (int): The number of iterations to perform.
            weight_type (str): The type of weight function to use ("gaussian", "linear", "inverse_distance").
            options (dict): Additional options for the weight function.
        """
        # Get the weight function based on the weight type
        weight_function = self.get_weight_function(weight_type)
        weight_options = options or {}

        # Get the neighbor indices and all indices
        neighbor_indices_list = self.mesh_vertex.get_connected_vertices(self.indices)
        all_indices = list(set(chain.from_iterable(neighbor_indices_list)) | set(self.indices))

        # Precompute weights
        weights = []
        weight_sums = []

        positions = self._get_indices_positions(all_indices)

        for i, index in enumerate(self.indices):
            vertex_distances = []
            vertex_weights = []
            weight_sum = 0.0
            for neighbor_index in neighbor_indices_list[i]:
                distance = positions[index].distanceTo(positions[neighbor_index])
                weight = weight_function(distance, **weight_options)
                vertex_distances.append(distance)
                vertex_weights.append(weight)
                weight_sum += weight

            weights.append(vertex_weights)
            weight_sums.append(weight_sum)

        # Get all indices weights
        all_indices_weights = self._get_indices_weights(self.skinCluster, all_indices)

        smoothed_weights = [0.0] * self.num_indices
        for _ in range(iterations):
            for i in range(self.num_indices):
                neighbor_weights = []
                weight_sum = weight_sums[i]

                for j, neighbor_index in enumerate(neighbor_indices_list[i]):
                    neighbor_weights.append((weights[i][j], all_indices_weights[neighbor_index]))

                # Calculate weighted average
                if weight_sum > 0:
                    smoothed_weights[i] = [sum(w * nw[j] for w, nw in neighbor_weights) / weight_sum for j in range(self.num_infs)]

            # Update all_weights with smoothed values only if iterations > 1
            if iterations > 1:
                for i, index in enumerate(self.indices):
                    all_indices_weights[index] = smoothed_weights[i]

        logger.debug(f"Skin weights smoothed using {weight_type} method: {self.vertices}")

        return smoothed_weights


class BiharmonicSkinWeights(SmoothSkinWeights):
    """Smooth skin weights using Biharmonic smoothing."""

    def calculate_weights(self, iterations: int = 1, first_order_weight: float = 0.75, second_order_weight: float = 0.25) -> None:
        """Calculate the weights for the Biharmonic smoothing operation.

        Args:
            iterations (int): The number of iterations to perform.
            first_order_weight (float): The weight for the first-order neighbors.
            second_order_weight (float): The weight for the second-order neighbors.
        """
        # Ensure the weights sum to 1
        if not math.isclose(first_order_weight + second_order_weight, 1.0, rel_tol=1e-5):
            raise ValueError("The sum of first_order_weight and second_order_weight must be 1.")

        neighbor_indices_list = self.mesh_vertex.get_connected_vertices(self.indices)
        second_neighbor_indices_list = []
        for index, neighbor_indices in zip(self.indices, neighbor_indices_list, strict=False):
            second_indices = self.mesh_vertex.get_connected_vertices(neighbor_indices)
            second_indices = set(chain.from_iterable(second_indices))
            if index in second_indices:
                second_indices.remove(index)

            second_neighbor_indices_list.append(list(second_indices))

        self.all_indices = list(
            set(chain.from_iterable(neighbor_indices_list)) | set(chain.from_iterable(second_neighbor_indices_list)) | set(self.indices)
        )

        indices_weights = self._get_indices_weights(self.skinCluster, self.all_indices)

        smoothed_weights = [0.0] * self.num_indices
        for _ in range(iterations):
            for i in range(self.num_indices):
                # Calculate biharmonic weights using neighbors' weights for a smoother result
                neighbor_weights = [indices_weights[neighbor_index] for neighbor_index in neighbor_indices_list[i]]
                second_neighbor_weights = [indices_weights[second_neighbor_index] for second_neighbor_index in second_neighbor_indices_list[i]]

                avg_first_order = [sum(w) / len(neighbor_weights) for w in zip(*neighbor_weights, strict=False)]
                avg_second_order = [sum(w) / len(second_neighbor_weights) for w in zip(*second_neighbor_weights, strict=False)]

                smoothed_weights[i] = [
                    first_order_weight * avg_first_order[j] + second_order_weight * avg_second_order[j] for j in range(len(avg_first_order))
                ]

            if iterations > 1:
                for i, index in enumerate(self.indices):
                    indices_weights[index] = smoothed_weights[i]

        logger.debug(f"Skin weights smoothed using Biharmonic method: {self.vertices}")

        return smoothed_weights


class RelaxSkinWeights(SmoothSkinWeights):
    """Smooth skin weights using Relax Operator smoothing."""

    def calculate_weights(self, iterations: int = 1, relaxation_factor: float = 0.5) -> None:
        """Calculate the weights for the Relax Operator smoothing operation.

        Args:
            iterations (int): The number of iterations to perform.
            relaxation_factor (float): The factor controlling the relaxation strength (0 < relaxation_factor < 1).
        """
        if not (0 < relaxation_factor <= 1):
            raise ValueError("The relaxation factor must be in the range (0, 1).")

        neighbor_indices_list = self.mesh_vertex.get_connected_vertices(self.indices)
        all_indices = list(set(chain.from_iterable(neighbor_indices_list)) | set(self.indices))

        all_indices_weights = self._get_indices_weights(self.skinCluster, all_indices)

        smoothed_weights = [0.0] * self.num_indices
        for _ in range(iterations):
            for i in range(self.num_indices):
                neighbor_weights = [all_indices_weights[j] for j in neighbor_indices_list[i]]
                avg_weight = [sum(w) / len(neighbor_weights) for w in zip(*neighbor_weights, strict=False)]

                # Relax the weight towards the average of its neighbors
                smoothed_weights[i] = [
                    (1 - relaxation_factor) * all_indices_weights[self.indices[i]][j] + relaxation_factor * avg_weight[j]
                    for j in range(len(all_indices_weights[self.indices[i]]))
                ]

            # Update all_weights with smoothed values only if iterations > 1
            if iterations > 1:
                for i, index in enumerate(self.indices):
                    all_indices_weights[index] = smoothed_weights[i]

        logger.debug(f"Skin weights smoothed using Relax Operator method: {self.vertices}")

        return smoothed_weights
