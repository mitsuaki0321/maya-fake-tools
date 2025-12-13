"""
algorithm.py - Core algorithm

Implementation of the two-stage algorithm from
SIGGRAPH Asia 2023 paper "Robust Skin Weights Transfer via Weight Inpainting".

Stage 1: High-confidence vertex matching and transfer
Stage 2: Weight Inpainting (Laplacian-based interpolation)
"""

from logging import getLogger
from typing import Any, Callable, Optional

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as splinalg

from . import laplacian, mesh_io, weight_io

logger = getLogger(__name__)

# =============================================================================
# Stage 1: High-confidence matching
# =============================================================================


def find_matches(
    source_mesh: str,
    target_mesh: str,
    distance_threshold_ratio: float = 0.05,
    angle_threshold_degrees: float = 30.0,
    flip_normals: bool = False,
    use_kdtree: bool = False,
    use_deformed_source: bool = False,
    use_deformed_target: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Find high-confidence matches from source mesh to target mesh (Stage 1).

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.
        distance_threshold_ratio: Distance threshold as ratio of bounding box diagonal.
        angle_threshold_degrees: Maximum normal angle difference in degrees.
        flip_normals: Whether to allow matching with inverted normals.
        use_kdtree: Use KDTree for fast vertex-to-vertex matching (less accurate).
        use_deformed_source: Evaluate source mesh at current deformed state.
        use_deformed_target: Evaluate target mesh at current deformed state.

    Returns:
        Tuple of (matched_mask, matched_weights, closest_data) where:
            - matched_mask: (N,) bool array, True for matched vertices.
            - matched_weights: (N, num_influences) transferred weights for matched vertices.
            - closest_data: Dict containing closest point data used for matching.
    """
    # Get mesh data
    if use_deformed_source:
        from ..features import deform

        source_verts, source_normals = deform.get_deformed_mesh_data(source_mesh)
    else:
        source_verts, source_normals = mesh_io.get_mesh_data(source_mesh)

    if use_deformed_target:
        from ..features import deform

        target_verts, target_normals = deform.get_deformed_mesh_data(target_mesh)
    else:
        target_verts, target_normals = mesh_io.get_mesh_data(target_mesh)

    num_target_verts = len(target_verts)

    # Calculate distance threshold
    bbox_diag = mesh_io.get_bounding_box_diagonal(target_mesh)
    distance_threshold = bbox_diag * distance_threshold_ratio
    distance_threshold_sq = distance_threshold**2

    # Compute closest points
    if use_kdtree:
        # KDTree fast mode (vertex-to-vertex)
        distances, closest_indices = mesh_io.get_closest_points_kdtree(source_verts, target_verts)
        closest_points = source_verts[closest_indices]
        closest_normals = source_normals[closest_indices]
        distances_sq = distances**2
        face_indices = None  # No face info in KDTree mode
    else:
        # Accurate mode (closest point on mesh surface)
        closest_points, closest_normals, face_indices, distances_sq = mesh_io.get_closest_points_on_mesh(source_mesh, target_verts)

    # Check distance condition
    distance_mask = distances_sq <= distance_threshold_sq

    # Check normal angle condition
    # Normalize
    target_normals_normalized = target_normals / (np.linalg.norm(target_normals, axis=1, keepdims=True) + 1e-10)
    closest_normals_normalized = closest_normals / (np.linalg.norm(closest_normals, axis=1, keepdims=True) + 1e-10)

    # Compute angle using dot product
    dot_products = np.einsum("ij,ij->i", target_normals_normalized, closest_normals_normalized)

    if flip_normals:
        # Allow inverted normals (use absolute value of dot product)
        dot_products = np.abs(dot_products)

    # cos(theta) -> theta (degrees)
    dot_products = np.clip(dot_products, -1.0, 1.0)
    angles_rad = np.arccos(dot_products)
    angles_deg = np.degrees(angles_rad)

    # Angle condition
    if flip_normals:
        # When allowing inverted normals, also allow near 180 degrees
        angle_mask = (angles_deg <= angle_threshold_degrees) | (angles_deg >= (180.0 - angle_threshold_degrees))
    else:
        angle_mask = angles_deg <= angle_threshold_degrees

    # Vertices that satisfy both conditions
    matched_mask = distance_mask & angle_mask

    # Get weights for matched vertices
    source_weights, influences = weight_io.get_all_weights(source_mesh)

    matched_weights = np.zeros((num_target_verts, len(influences)), dtype=np.float64)

    if use_kdtree:
        # KDTree mode: Use nearest vertex weights directly
        for i in np.where(matched_mask)[0]:
            matched_weights[i] = source_weights[closest_indices[i]]
    else:
        # Accurate mode: Barycentric interpolation
        source_mesh_fn = mesh_io._get_mfn_mesh(mesh_io._get_shape_node(source_mesh))

        for i in np.where(matched_mask)[0]:
            if face_indices[i] < 0:
                matched_mask[i] = False
                continue

            # Calculate barycentric coordinates
            bary_coords, vert_indices = mesh_io.get_barycentric_coords(source_mesh_fn, int(face_indices[i]), closest_points[i])

            # Interpolate weights
            matched_weights[i] = weight_io.interpolate_weights_barycentric(source_weights, bary_coords, vert_indices)

    closest_data = {
        "points": closest_points,
        "normals": closest_normals,
        "face_indices": face_indices,
        "distances_sq": distances_sq,
    }

    matched_count = np.sum(matched_mask)
    total_count = len(matched_mask)
    logger.debug(f"find_matches: {matched_count}/{total_count} vertices matched (distance_threshold={distance_threshold:.4f})")

    return matched_mask, matched_weights, closest_data


# =============================================================================
# Stage 2: Weight Inpainting
# =============================================================================


def inpaint_weights(
    target_mesh: str,
    matched_mask: np.ndarray,
    matched_weights: np.ndarray,
    use_point_cloud: bool = False,
) -> np.ndarray:
    """Inpaint weights for unmatched vertices using Laplacian interpolation (Stage 2).

    Args:
        target_mesh: Target mesh node name.
        matched_mask: (N,) bool array, True for matched vertices.
        matched_weights: (N, num_influences) weights for matched vertices.
        use_point_cloud: Whether to use Point Cloud Laplacian instead of mesh Laplacian.

    Returns:
        (N, num_influences) array of interpolated weights for all vertices.

    Raises:
        ValueError: If no matched vertices found or Laplacian matrix is invalid.
    """
    # Get mesh data
    target_verts, _ = mesh_io.get_mesh_data(target_mesh)
    target_tris = mesh_io.get_triangles_fast(target_mesh)

    num_influences = matched_weights.shape[1]

    # Indices of matched and unmatched vertices
    matched_indices = np.where(matched_mask)[0]
    unmatched_indices = np.where(~matched_mask)[0]

    if len(unmatched_indices) == 0:
        # All vertices are matched
        return matched_weights.copy()

    if len(matched_indices) == 0:
        # No matched vertices - error
        raise ValueError("No matched vertices found. Cannot perform inpainting.")

    # Compute Laplacian matrix
    L, M = laplacian.compute_laplacian(target_verts, target_tris, use_point_cloud)

    if not laplacian.is_laplacian_valid(L):
        raise ValueError("Invalid Laplacian matrix. Mesh may have issues.")

    # Compute system matrix: Q = -L + L @ M^-1 @ L
    Q = laplacian.compute_system_matrix(L, M)

    # Partition the matrix
    # Q_UU: unknown vertices x unknown vertices
    # Q_UI: unknown vertices x known vertices
    Q_UU = Q[np.ix_(unmatched_indices, unmatched_indices)]
    Q_UI = Q[np.ix_(unmatched_indices, matched_indices)]

    # Known weights
    W_I = matched_weights[matched_indices]

    # Solve for unknown weights: Q_UU @ W_U = -Q_UI @ W_I
    W_U = np.zeros((len(unmatched_indices), num_influences), dtype=np.float64)

    for bone_idx in range(num_influences):
        b = -Q_UI @ W_I[:, bone_idx]
        W_U[:, bone_idx] = splinalg.spsolve(Q_UU.tocsr(), b)

    # Combine results
    inpainted_weights = matched_weights.copy()
    inpainted_weights[unmatched_indices] = W_U

    # Apply constraints
    # 1. Clip each element to [0, 1]
    inpainted_weights = np.clip(inpainted_weights, 0.0, 1.0)

    # 2. Normalize each row to sum to 1
    row_sums = inpainted_weights.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0  # Prevent division by zero
    inpainted_weights = inpainted_weights / row_sums

    logger.debug(f"inpaint_weights: {len(unmatched_indices)} vertices inpainted using {num_influences} influences")

    return inpainted_weights


# =============================================================================
# Smoothing
# =============================================================================


def smooth_weights(
    target_mesh: str,
    weights: np.ndarray,
    matched_mask: np.ndarray,
    num_iterations: int = 10,
    alpha: float = 0.2,
    distance_threshold_ratio: float = 0.05,
) -> np.ndarray:
    """Smooth weights near inpaint boundaries using Laplacian smoothing.

    Args:
        target_mesh: Target mesh node name.
        weights: (N, num_influences) weight array.
        matched_mask: (N,) bool array, True for matched vertices.
        num_iterations: Number of smoothing iterations.
        alpha: Smoothing strength (0-1).
        distance_threshold_ratio: Distance threshold ratio for determining smoothing region.

    Returns:
        (N, num_influences) array of smoothed weights.
    """
    target_verts, _ = mesh_io.get_mesh_data(target_mesh)
    adj_list = mesh_io.get_adjacency_list(target_mesh)
    adj_matrix = mesh_io.get_adjacency_matrix(target_mesh)

    bbox_diag = mesh_io.get_bounding_box_diagonal(target_mesh)
    distance_threshold = bbox_diag * distance_threshold_ratio

    # Identify vertices to smooth
    # Unmatched vertices and their neighbors
    smooth_mask = ~matched_mask.copy()

    # Add adjacent vertices within distance threshold using BFS
    unmatched_indices = np.where(~matched_mask)[0]

    for start_idx in unmatched_indices:
        queue = [start_idx]
        visited = {start_idx}

        while queue:
            current = queue.pop(0)
            for neighbor in adj_list[current]:
                if neighbor not in visited:
                    dist = np.linalg.norm(target_verts[start_idx] - target_verts[neighbor])
                    if dist < distance_threshold:
                        smooth_mask[neighbor] = True
                        visited.add(neighbor)
                        queue.append(neighbor)

    # Build smoothing matrix
    # Reciprocal of degree matrix
    degrees = np.array(adj_matrix.sum(axis=1)).flatten()
    degrees[degrees == 0] = 1.0

    smooth_matrix = sp.diags(1.0 / degrees) @ adj_matrix.astype(np.float64)

    # Apply Laplacian smoothing
    smoothed = weights.copy()

    for _ in range(num_iterations):
        # new_weights = (1 - alpha) * current + alpha * neighbor_average
        neighbor_avg = smooth_matrix @ smoothed
        new_weights = (1 - alpha) * smoothed + alpha * neighbor_avg

        # Update only smoothing target vertices
        smoothed[smooth_mask] = new_weights[smooth_mask]

    # Normalize
    row_sums = smoothed.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    smoothed = smoothed / row_sums

    return smoothed


# =============================================================================
# Integration function
# =============================================================================


def transfer_weights(
    source_mesh: str,
    target_mesh: str,
    distance_threshold_ratio: float = 0.05,
    angle_threshold_degrees: float = 30.0,
    flip_normals: bool = False,
    use_kdtree: bool = False,
    use_point_cloud: bool = False,
    smooth: bool = True,
    smooth_iterations: int = 10,
    smooth_alpha: float = 0.2,
    use_deformed_source: bool = False,
    use_deformed_target: bool = False,
    progress_callback: Optional[Callable[[str, int], None]] = None,
    vertex_indices: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Execute complete weight transfer pipeline.

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.
        distance_threshold_ratio: Distance threshold as ratio of bounding box diagonal.
        angle_threshold_degrees: Maximum normal angle difference in degrees.
        flip_normals: Whether to allow matching with inverted normals.
        use_kdtree: Use KDTree for fast matching (less accurate).
        use_point_cloud: Use Point Cloud Laplacian for inpainting.
        smooth: Whether to apply post-transfer smoothing.
        smooth_iterations: Number of smoothing iterations.
        smooth_alpha: Smoothing strength (0-1).
        use_deformed_source: Evaluate source mesh at current deformed state.
        use_deformed_target: Evaluate target mesh at current deformed state.
        progress_callback: Callback function(message, percent) for progress updates.
        vertex_indices: List of target vertex indices to transfer. None for all vertices.

    Returns:
        Dictionary containing:
            - success: Whether transfer completed successfully.
            - matched_count: Number of matched vertices.
            - unmatched_count: Number of unmatched (inpainted) vertices.
            - total_vertices: Total number of processed vertices.
            - message: Status message.
    """
    result = {
        "success": False,
        "matched_count": 0,
        "unmatched_count": 0,
        "total_vertices": 0,
        "message": "",
    }

    try:
        # Progress display
        if progress_callback:
            progress_callback("Stage 1: Finding matches...", 0)

        # Prepare skinCluster on target
        source_skin = weight_io.get_skincluster(source_mesh)
        influences = weight_io.get_influence_names(source_skin)
        target_skin = weight_io.get_or_create_skincluster(target_mesh, influences)

        # Stage 1: Matching
        matched_mask, matched_weights, closest_data = find_matches(
            source_mesh,
            target_mesh,
            distance_threshold_ratio=distance_threshold_ratio,
            angle_threshold_degrees=angle_threshold_degrees,
            flip_normals=flip_normals,
            use_kdtree=use_kdtree,
            use_deformed_source=use_deformed_source,
            use_deformed_target=use_deformed_target,
        )

        # Filter for partial selection
        if vertex_indices is not None:
            vertex_set = set(vertex_indices)
            # Count only for specified vertices
            matched_count = sum(1 for i in range(len(matched_mask)) if matched_mask[i] and i in vertex_set)
            total_verts = len(vertex_indices)
            unmatched_count = total_verts - matched_count
        else:
            matched_count = np.sum(matched_mask)
            total_verts = len(matched_mask)
            unmatched_count = total_verts - matched_count

        result["matched_count"] = int(matched_count)
        result["unmatched_count"] = int(unmatched_count)
        result["total_vertices"] = int(total_verts)

        if progress_callback:
            progress_callback(f"Stage 1 complete: {matched_count}/{total_verts} matched", 33)

        # Stage 2: Inpainting
        if progress_callback:
            progress_callback("Stage 2: Inpainting weights...", 33)

        inpainted_weights = inpaint_weights(target_mesh, matched_mask, matched_weights, use_point_cloud=use_point_cloud)

        if progress_callback:
            progress_callback("Stage 2 complete", 66)

        # Smoothing
        if smooth:
            if progress_callback:
                progress_callback("Smoothing weights...", 66)

            final_weights = smooth_weights(
                target_mesh,
                inpainted_weights,
                matched_mask,
                num_iterations=smooth_iterations,
                alpha=smooth_alpha,
                distance_threshold_ratio=distance_threshold_ratio,
            )
        else:
            final_weights = inpainted_weights

        # Apply weights
        if progress_callback:
            progress_callback("Applying weights...", 90)

        if vertex_indices is not None:
            # Partial selection: Write only specified vertices
            partial_weights = final_weights[vertex_indices]
            weight_io.set_weights_for_vertices(target_mesh, vertex_indices, partial_weights, target_skin)
        else:
            # All vertices
            weight_io.set_all_weights(target_mesh, final_weights, target_skin)

        if progress_callback:
            progress_callback("Complete!", 100)

        result["success"] = True
        result["message"] = f"Transfer complete: {matched_count}/{total_verts} matched, {unmatched_count} inpainted"

    except Exception as e:
        logger.error(f"Weight transfer failed: {e}")
        result["success"] = False
        result["message"] = str(e)
        raise

    return result


# =============================================================================
# Seam vertex averaging
# =============================================================================


def average_seam_weights(
    meshes: list[str],
    position_tolerance: float = 0.0001,
    include_internal_seams: bool = True,
) -> dict[str, Any]:
    """Average weights for vertices at the same position.

    This is useful for:
    1. Meshes that share seam vertices (e.g., collar and shirt)
    2. Internal seams within a single mesh (e.g., UV seams with split vertices)

    Args:
        meshes: List of mesh node names to process.
        position_tolerance: Maximum distance to consider vertices as coincident.
        include_internal_seams: If True, also average vertices at the same position
            within a single mesh (e.g., UV seam vertices). If False, only average
            across different meshes.

    Returns:
        Dictionary containing:
            - success: Whether averaging completed successfully.
            - seam_groups: Number of seam vertex groups found.
            - vertices_averaged: Total number of vertices that were averaged.
            - message: Status message.
    """
    from maya import cmds

    result = {
        "success": False,
        "seam_groups": 0,
        "vertices_averaged": 0,
        "message": "",
    }

    if len(meshes) < 1:
        result["message"] = "Need at least 1 mesh to average seam weights."
        return result

    if len(meshes) < 2 and not include_internal_seams:
        result["message"] = "Need at least 2 meshes when include_internal_seams is False."
        return result

    try:
        # Collect all vertex positions and their mesh/index info
        all_vertices = []  # List of (mesh_name, vertex_index, position, skincluster)

        for mesh in meshes:
            verts, _ = mesh_io.get_mesh_data(mesh)
            skin = weight_io.get_skincluster(mesh)

            if skin is None:
                result["message"] = f"No skinCluster found on {mesh}"
                return result

            for i, pos in enumerate(verts):
                all_vertices.append((mesh, i, pos, skin))

        # Find coincident vertices using spatial hashing
        # Use a grid-based approach for efficiency
        grid = {}
        grid_size = position_tolerance * 10  # Grid cell size

        for mesh, idx, pos, skin in all_vertices:
            # Compute grid cell
            cell = (
                int(pos[0] / grid_size),
                int(pos[1] / grid_size),
                int(pos[2] / grid_size),
            )
            if cell not in grid:
                grid[cell] = []
            grid[cell].append((mesh, idx, pos, skin))

        # Find seam groups (vertices from different meshes at same position)
        seam_groups = []
        processed = set()

        for cell, _vertices in grid.items():
            # Check vertices in this cell and neighboring cells
            neighbor_cells = [(cell[0] + dx, cell[1] + dy, cell[2] + dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]

            candidates = []
            for nc in neighbor_cells:
                if nc in grid:
                    candidates.extend(grid[nc])

            # Group coincident vertices
            for i, (mesh1, idx1, pos1, skin1) in enumerate(candidates):
                key1 = (mesh1, idx1)
                if key1 in processed:
                    continue

                group = [(mesh1, idx1, skin1)]
                processed.add(key1)

                for mesh2, idx2, pos2, skin2 in candidates[i + 1 :]:
                    key2 = (mesh2, idx2)
                    if key2 in processed:
                        continue

                    # Check if positions match
                    dist = np.linalg.norm(pos1 - pos2)
                    if dist <= position_tolerance:
                        # Check if this is a valid seam vertex
                        if include_internal_seams:
                            # Include all coincident vertices (same or different mesh)
                            # But skip if same mesh and same vertex index
                            if not (mesh2 == mesh1 and idx2 == idx1):
                                group.append((mesh2, idx2, skin2))
                                processed.add(key2)
                        else:
                            # Only include vertices from different meshes
                            if mesh2 != mesh1:
                                group.append((mesh2, idx2, skin2))
                                processed.add(key2)

                # Keep groups with multiple vertices
                if len(group) > 1:
                    seam_groups.append(group)

        if not seam_groups:
            result["success"] = True
            result["message"] = "No seam vertices found between meshes."
            return result

        # Average weights for each seam group
        vertices_averaged = 0

        for group in seam_groups:
            # Collect weights from all vertices in the group
            all_weights = []
            all_influences = set()

            for mesh, idx, skin in group:
                weights, influences = weight_io.get_vertex_weights(mesh, idx, skin)
                all_weights.append((weights, influences))
                all_influences.update(influences)

            # Create a unified influence list
            unified_influences = sorted(all_influences)
            influence_to_idx = {inf: i for i, inf in enumerate(unified_influences)}

            # Accumulate weights
            num_influences = len(unified_influences)
            accumulated = np.zeros(num_influences, dtype=np.float64)
            count = len(group)

            for weights, influences in all_weights:
                for inf, w in zip(influences, weights):
                    accumulated[influence_to_idx[inf]] += w

            # Average
            averaged = accumulated / count

            # Normalize
            total = averaged.sum()
            if total > 0:
                averaged = averaged / total

            # Apply averaged weights to all vertices in the group
            for mesh, idx, skin in group:
                # Get the influences that exist on this skinCluster
                skin_influences = set(cmds.skinCluster(skin, query=True, influence=True) or [])

                # Build weight list for this skinCluster
                weight_values = []
                weight_influences = []

                for inf, w in zip(unified_influences, averaged):
                    if inf in skin_influences and w > 0.0001:
                        weight_values.append(w)
                        weight_influences.append(inf)

                if weight_values:
                    weight_io.set_vertex_weights(mesh, idx, weight_values, weight_influences, skin)

                vertices_averaged += 1

        result["success"] = True
        result["seam_groups"] = len(seam_groups)
        result["vertices_averaged"] = vertices_averaged
        result["message"] = f"Averaged {vertices_averaged} vertices in {len(seam_groups)} seam groups."
        logger.info(result["message"])

    except Exception as e:
        logger.error(f"Seam weight averaging failed: {e}")
        result["success"] = False
        result["message"] = str(e)
        raise

    return result


def get_unmatched_vertices(
    source_mesh: str,
    target_mesh: str,
    distance_threshold_ratio: float = 0.05,
    angle_threshold_degrees: float = 30.0,
    flip_normals: bool = False,
    use_kdtree: bool = False,
    use_deformed_source: bool = False,
    use_deformed_target: bool = False,
) -> tuple[list[int], list[int]]:
    """Get indices of matched and unmatched vertices for preview.

    Args:
        source_mesh: Source mesh node name.
        target_mesh: Target mesh node name.
        distance_threshold_ratio: Distance threshold as ratio of bounding box diagonal.
        angle_threshold_degrees: Maximum normal angle difference in degrees.
        flip_normals: Whether to allow matching with inverted normals.
        use_kdtree: Use KDTree for fast matching (less accurate).
        use_deformed_source: Evaluate source mesh at current deformed state.
        use_deformed_target: Evaluate target mesh at current deformed state.

    Returns:
        Tuple of (matched_indices, unmatched_indices) where each is a list of vertex indices.
    """
    matched_mask, _, _ = find_matches(
        source_mesh,
        target_mesh,
        distance_threshold_ratio=distance_threshold_ratio,
        angle_threshold_degrees=angle_threshold_degrees,
        flip_normals=flip_normals,
        use_kdtree=use_kdtree,
        use_deformed_source=use_deformed_source,
        use_deformed_target=use_deformed_target,
    )

    matched_indices = np.where(matched_mask)[0].tolist()
    unmatched_indices = np.where(~matched_mask)[0].tolist()

    return matched_indices, unmatched_indices
