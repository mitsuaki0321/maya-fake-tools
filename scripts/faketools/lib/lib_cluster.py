"""
Mesh vertex clustering functions.

All clustering algorithms are implemented using numpy only (no sklearn dependency).
"""

from abc import ABC, abstractmethod
from logging import getLogger
import random

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np

logger = getLogger(__name__)


class Clustering(ABC):
    """Clustering class for mesh vertices."""

    def __init__(self, mesh: str):
        """Initialize the Cluster with a target mesh.

        Args:
            mesh (str): The target mesh.
        """
        if not mesh:
            raise ValueError("Mesh is not specified.")

        if not isinstance(mesh, str):
            raise ValueError("Mesh must be a string.")

        if not cmds.objExists(mesh):
            raise ValueError(f"Mesh does not exist: {mesh}")

        if "mesh" not in cmds.nodeType(mesh, inherited=True):
            raise ValueError(f"Node is not a mesh: {mesh}")

        self.mesh = mesh

        sel_list = om.MSelectionList()
        sel_list.add(mesh)
        self.dag_path = sel_list.getDagPath(0)
        self.mesh_fn = om.MFnMesh(self.dag_path)

    @abstractmethod
    def get_clusters(self, *args, **kwargs) -> list[list[int]]:
        """Get the clusters of vertices.

        Returns:
            list[list[int]]: The list of cluster vertex indices.
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.mesh})"

    def __str__(self):
        return f"{self.__class__.__name__}({self.mesh})"


class SplitAxisClustering(Clustering):
    """Split axis clustering for mesh vertices."""

    def get_clusters(self, split_num: int, axis: str = "x") -> list[list[int]]:
        """Get the clusters of vertices by splitting the mesh along an axis.

        Args:
            split_num (int): The number of splits.
            axis (str, optional): The axis to split. Defaults to 'x'.

        Returns:
            list[list[int]]: The list of vertex indices for each cluster.
        """
        if axis not in ["x", "y", "z"]:
            raise ValueError(f"Invalid axis: {axis}")

        if split_num < 2:
            raise ValueError(f"Invalid split number: {split_num}")

        # Get axis index
        axis_idx = {"x": 0, "y": 1, "z": 2}[axis]

        # Convert MPointArray to numpy array efficiently
        points = self.mesh_fn.getPoints(om.MSpace.kWorld)
        positions = np.array([[p.x, p.y, p.z] for p in points])

        # Sort indices by axis values
        axis_values = positions[:, axis_idx]
        indices_sorted = np.argsort(axis_values)

        # Split into clusters
        split_array = np.array_split(indices_sorted, split_num)

        logger.debug(f"Split {len(positions)} vertices into {split_num} clusters along the {axis} axis.")

        return [cluster.tolist() for cluster in split_array]


class KMeansClustering(Clustering):
    """K-means clustering for mesh vertices (numpy-only implementation)."""

    def get_clusters(self, n_clusters: int, max_iter: int = 100, tol: float = 1e-4) -> list[list[int]]:
        """Apply K-means clustering to classify vertices.

        Features:
            - Calculate the centroid (mean) of each cluster and classify the vertices closest to that position into the cluster.
            - The number of clusters must be specified.
            - Classify all vertices into clusters.
            - Implemented using numpy only (no sklearn dependency).

        Args:
            n_clusters (int): The number of clusters.
            max_iter (int, optional): Maximum number of iterations. Defaults to 100.
            tol (float, optional): Convergence tolerance. Defaults to 1e-4.

        Returns:
            list[list[int]]: The list of vertex indices for each cluster.
        """
        if n_clusters < 1:
            raise ValueError("n_clusters must be greater than 0.")

        # Convert MPointArray to numpy array efficiently
        points = self.mesh_fn.getPoints(om.MSpace.kWorld)
        vertex_positions = np.array([[p.x, p.y, p.z] for p in points])

        # K-means implementation using numpy only
        np.random.seed(42)
        indices = np.random.choice(len(vertex_positions), n_clusters, replace=False)
        centroids = vertex_positions[indices].copy()

        for iteration in range(max_iter):
            # Assign points to nearest centroid
            distances = np.sqrt(((vertex_positions[:, np.newaxis] - centroids) ** 2).sum(axis=2))
            labels = np.argmin(distances, axis=1)

            # Update centroids
            new_centroids = np.array([vertex_positions[labels == i].mean(axis=0) if np.any(labels == i) else centroids[i] for i in range(n_clusters)])

            # Check convergence
            if np.allclose(centroids, new_centroids, atol=tol):
                logger.debug(f"K-means converged after {iteration + 1} iterations.")
                break

            centroids = new_centroids

        # Group vertex indices by cluster
        clusters = [np.where(labels == i)[0].tolist() for i in range(n_clusters)]

        logger.debug(f"Clustered {len(vertex_positions)} vertices into {n_clusters} clusters.")

        return clusters


class DBSCANClustering(Clustering):
    """DBSCAN clustering for mesh vertices (numpy-only implementation)."""

    def get_clusters(self, eps: float = 0.5, min_samples: int = 5) -> list[list[int]]:
        """Classify vertices using DBSCAN clustering and create a list for each cluster.

        Features:
            - Create clusters based on the distance defined by eps.
            - A cluster is formed by points with at least min_samples.
            - Not all vertices are classified into clusters (noise points are excluded).
            - Implemented using numpy only (no sklearn dependency).

        Args:
            eps (float): The maximum distance between points to be considered as a cluster (clustering range).
            min_samples (int): The minimum number of points to be considered as a cluster.

        Returns:
            list[list[int]]: The list of vertices for each cluster (noise points excluded).
        """
        # Convert MPointArray to numpy array efficiently
        points = self.mesh_fn.getPoints(om.MSpace.kWorld)
        vertex_positions = np.array([[p.x, p.y, p.z] for p in points])

        # DBSCAN implementation using numpy only
        n_points = len(vertex_positions)
        labels = np.full(n_points, -1, dtype=int)  # -1 = unvisited/noise
        cluster_id = 0

        # Compute distance matrix
        distances = np.sqrt(((vertex_positions[:, np.newaxis] - vertex_positions) ** 2).sum(axis=2))

        for i in range(n_points):
            if labels[i] != -1:  # Already processed
                continue

            # Find neighbors within eps
            neighbors = np.where(distances[i] <= eps)[0]

            if len(neighbors) < min_samples:
                continue  # Mark as noise (stays -1)

            # Start new cluster
            labels[i] = cluster_id
            seed_set = set(neighbors) - {i}

            while seed_set:
                current = seed_set.pop()

                if labels[current] == -1:  # Noise point becomes border point
                    labels[current] = cluster_id

                if labels[current] != -1:  # Already processed
                    continue

                labels[current] = cluster_id

                # Find current point's neighbors
                current_neighbors = np.where(distances[current] <= eps)[0]

                if len(current_neighbors) >= min_samples:
                    seed_set.update(current_neighbors)

            cluster_id += 1

        # Get unique labels (excluding noise label -1)
        unique_labels = np.unique(labels)
        unique_labels = unique_labels[unique_labels != -1]

        # Group vertex indices by cluster
        clusters = [np.where(labels == label)[0].tolist() for label in unique_labels]

        logger.debug(f"Clustered {len(vertex_positions)} vertices into {len(unique_labels)} clusters.")

        return clusters


def cluster_vertex_colors(obj: str, cluster_indices: list[list[int]]) -> None:
    """Cluster the vertices and assign a color to each cluster.

    Args:
        obj (str): The target object.
        cluster_indices (list[list[int]]): The list of vertex indices for each cluster.
    """
    if not cmds.objExists(obj):
        raise ValueError(f"Object does not exist: {obj}")

    for cluster in cluster_indices:
        cluster_color = [random.uniform(0, 1) for _ in range(3)]

        vertices = [f"{obj}.vtx[{i}]" for i in cluster]
        cmds.polyColorPerVertex(vertices, rgb=cluster_color)

        logger.debug(f"Assigned color to cluster: {vertices}")
