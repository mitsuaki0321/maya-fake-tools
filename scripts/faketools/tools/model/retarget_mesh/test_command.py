"""Retarget mesh to another mesh test command."""

import logging

import maya.cmds as cmds
import numpy as np
from scipy.spatial import KDTree

from ....lib import lib_retarget
from ....lib.lib_mesh_vertex import MeshVertex

logger = logging.getLogger(__name__)


def save_mesh_data(src_mesh: str, dst_meshes: list[str], trg_meshes: list[str], file_path: str) -> None:
    """Save mesh vertex data to a JSON file for testing.

    Args:
        src_mesh (str): The source mesh for deformation.
        dst_meshes (list[str]): The target meshes for deformation.
        trg_meshes (list[str]): The meshes to be deformed.
        file_path (str): The file path to save the data.

    Raises:
        ValueError: If required meshes are not specified or don't exist.
    """
    import json

    if not src_mesh or not dst_meshes or not trg_meshes:
        raise ValueError("Required meshes are not specified.")

    if not cmds.objExists(src_mesh):
        raise ValueError(f"Source mesh does not exist: {src_mesh}.")

    not_exists_dst_meshes = [mesh for mesh in dst_meshes if not cmds.objExists(mesh)]
    if not_exists_dst_meshes:
        raise ValueError(f"Destination meshes do not exist: {not_exists_dst_meshes}.")

    not_exists_trg_meshes = [mesh for mesh in trg_meshes if not cmds.objExists(mesh)]
    if not_exists_trg_meshes:
        raise ValueError(f"Target meshes do not exist: {not_exists_trg_meshes}.")

    # Collect mesh data
    data = {
        "src_mesh": {"name": src_mesh, "vertices": MeshVertex(src_mesh).get_vertex_positions(as_float=True)},
        "dst_meshes": [{"name": mesh, "vertices": MeshVertex(mesh).get_vertex_positions(as_float=True)} for mesh in dst_meshes],
        "trg_meshes": [{"name": mesh, "vertices": MeshVertex(mesh).get_vertex_positions(as_float=True)} for mesh in trg_meshes],
    }

    # Save to file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Mesh data saved to: {file_path}")


def load_mesh_data(file_path: str) -> dict:
    """Load mesh vertex data from a JSON file.

    Args:
        file_path (str): The file path to load the data from.

    Returns:
        dict: The mesh data containing src_mesh, dst_meshes, and trg_meshes.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file format is invalid.
    """
    import json
    import os

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path) as f:
        data = json.load(f)

    # Validate data structure
    required_keys = ["src_mesh", "dst_meshes", "trg_meshes"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Invalid file format: missing '{key}'")

    logger.info(f"Mesh data loaded from: {file_path}")
    return data


def test_retarget_from_file(file_path: str, *, max_vertices: int = 1000, radius_multiplier: float = 1.0) -> dict:
    """Test retarget_mesh using data from a file without Maya scene.

    This function simulates the retarget_mesh operation using saved vertex data,
    allowing testing without actual Maya meshes.

    Args:
        file_path (str): The file path to load the test data from.
        max_vertices (int): The maximum number of vertices to use when referencing trg_mesh.
        radius_multiplier (float): The radius multiplier when selecting vertices.

    Returns:
        dict: Test results containing computed vertex positions for each target mesh.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the data format is invalid or topology doesn't match.
    """
    # Load data
    data = load_mesh_data(file_path)

    src_vertices = np.array(data["src_mesh"]["vertices"], dtype=np.float32)
    src_kd_tree = KDTree(src_vertices)

    if len(src_vertices) < 4:
        raise ValueError(f"The source mesh must have at least 4 vertices: {data['src_mesh']['name']}.")

    results = {}

    # Process each target mesh
    for trg_mesh_data in data["trg_meshes"]:
        trg_name = trg_mesh_data["name"]
        trg_vertices = np.array(trg_mesh_data["vertices"], dtype=np.float32)
        num_trg_vertices = len(trg_vertices)

        logger.info(f"Processing target mesh: {trg_name} ({num_trg_vertices} vertices)")

        # Determine clustering strategy
        if num_trg_vertices > max_vertices:
            # Simple k-means clustering simulation for testing
            num_clusters = int(num_trg_vertices / max_vertices)
            cluster_size = num_trg_vertices // num_clusters
            trg_index_list = [list(range(i * cluster_size, min((i + 1) * cluster_size, num_trg_vertices))) for i in range(num_clusters)]
        else:
            trg_index_list = [list(range(num_trg_vertices))]

        # Compute source indices for each cluster with adaptive radius
        src_index_list = []
        min_src_vertices = 10  # Minimum source vertices for reliable RBF deformation
        for cluster_idx, trg_indices in enumerate(trg_index_list):
            trg_cluster_points = trg_vertices[trg_indices]
            distances, _ = src_kd_tree.query(trg_cluster_points)
            base_distance = np.max(distances)
            current_multiplier = radius_multiplier
            iteration = 0
            max_iterations = 10

            while iteration < max_iterations:
                search_radius = base_distance * current_multiplier

                # Find all source vertices within radius
                src_indices_set = set()
                for trg_point in trg_cluster_points:
                    nearby_indices = src_kd_tree.query_ball_point(trg_point, search_radius)
                    src_indices_set.update(nearby_indices)

                src_indices = sorted(list(src_indices_set))

                # Check if we have enough source vertices
                if len(src_indices) >= min_src_vertices:
                    if iteration > 0:
                        logger.info(
                            f"Cluster {cluster_idx}: Found {len(src_indices)} source vertices "
                            f"after {iteration} iterations (radius: {search_radius:.4f})"
                        )
                    break

                # Not enough vertices, increase radius
                if iteration == 0:
                    logger.debug(
                        f"Cluster {cluster_idx}: Only found {len(src_indices)} source vertices (need {min_src_vertices}), increasing radius..."
                    )
                current_multiplier *= 1.5
                iteration += 1

            # Fallback if no vertices found
            if not src_indices:
                logger.warning(f"Cluster {cluster_idx}: No source vertices found, using nearest vertex as fallback")
                _, nearest_idx = src_kd_tree.query(trg_cluster_points[0])
                src_indices = [int(nearest_idx)]

            src_index_list.append(src_indices)

        # Process each destination mesh
        trg_results = []
        for dst_mesh_data in data["dst_meshes"]:
            dst_name = dst_mesh_data["name"]
            dst_vertices = np.array(dst_mesh_data["vertices"], dtype=np.float32)

            # Validate topology
            if len(dst_vertices) != len(src_vertices):
                raise ValueError(f"The topology of the source and destination meshes must be the same: {data['src_mesh']['name']} -> {dst_name}.")

            logger.info(f"  Processing destination mesh: {dst_name}")

            # Initialize result vertices with original positions
            result_vertices = trg_vertices.copy()

            # Apply RBF deformation for each cluster
            for trg_indices, src_indices in zip(trg_index_list, src_index_list):
                rbf_deform = lib_retarget.RBFDeform(src_vertices[src_indices])
                weight_x, weight_y, weight_z = rbf_deform.compute_weights(dst_vertices[src_indices])
                computed_points = rbf_deform.compute_points(trg_vertices[trg_indices], weight_x, weight_y, weight_z)

                # Update result vertices
                for i, idx in enumerate(trg_indices):
                    result_vertices[idx] = computed_points[i]

            trg_results.append({"dst_name": dst_name, "vertices": result_vertices.tolist()})

        results[trg_name] = trg_results

    logger.info(f"Test completed for {len(data['trg_meshes'])} target meshes")

    return results
