"""Preprocessing module — rigid alignment and scale normalization."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
import trimesh


def compute_scale(mesh: trimesh.Trimesh) -> float:
    """Compute the bounding box diagonal length as a scale measure."""
    extent = mesh.vertices.max(axis=0) - mesh.vertices.min(axis=0)
    return float(np.linalg.norm(extent))


def normalize_scale(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
) -> tuple[trimesh.Trimesh, float]:
    """Scale source to match target's bounding box diagonal.

    Returns:
        (scaled_source, scale_factor)
    """
    s_scale = compute_scale(source)
    t_scale = compute_scale(target)

    if s_scale < 1e-10:
        raise ValueError("Source mesh has zero extent")

    factor = t_scale / s_scale
    scaled = source.copy()
    scaled.vertices = source.vertices * factor

    return scaled, factor


def align_centroids(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Translate source so its centroid matches target's centroid."""
    src_centroid = source.vertices.mean(axis=0)
    tgt_centroid = target.vertices.mean(axis=0)

    aligned = source.copy()
    aligned.vertices = source.vertices + (tgt_centroid - src_centroid)
    return aligned


def procrustes_align(
    source_points: np.ndarray,
    target_points: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Compute optimal rigid transform (rotation + translation + uniform scale).

    Uses SVD-based Procrustes analysis.

    Args:
        source_points: (N, 3) source landmark positions.
        target_points: (N, 3) target landmark positions.

    Returns:
        (rotation_3x3, translation_3, scale_factor)
    """
    src_centroid = source_points.mean(axis=0)
    tgt_centroid = target_points.mean(axis=0)

    src_centered = source_points - src_centroid
    tgt_centered = target_points - tgt_centroid

    # Optimal scale
    src_norm = np.linalg.norm(src_centered)
    tgt_norm = np.linalg.norm(tgt_centered)
    scale = tgt_norm / src_norm if src_norm > 1e-10 else 1.0

    # SVD for rotation
    H = src_centered.T @ tgt_centered
    U, S, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    sign_matrix = np.diag([1, 1, np.sign(d)])
    R = Vt.T @ sign_matrix @ U.T

    t = tgt_centroid - scale * (R @ src_centroid)

    return R, t, scale


def rigid_align_landmarks(
    source: trimesh.Trimesh,
    source_landmarks: np.ndarray,
    target_landmarks: np.ndarray,
) -> trimesh.Trimesh:
    """Align source mesh to target using landmark-based Procrustes.

    Args:
        source: Source mesh to transform.
        source_landmarks: (N, 3) positions on source.
        target_landmarks: (N, 3) positions on target.

    Returns:
        Transformed copy of source mesh.
    """
    R, t, scale = procrustes_align(source_landmarks, target_landmarks)

    aligned = source.copy()
    aligned.vertices = (scale * (R @ source.vertices.T).T) + t
    return aligned


def rigid_align_icp(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
    max_iterations: int = 50,
    tolerance: float = 1e-6,
) -> trimesh.Trimesh:
    """Align source to target using point-to-point ICP.

    Simple ICP implementation using nearest-neighbor correspondences.
    """
    src_pts = source.vertices.copy()

    for _iteration in range(max_iterations):
        # Find nearest neighbors
        tree = cKDTree(target.vertices)
        _, indices = tree.query(src_pts)
        tgt_pts = target.vertices[indices]

        # Solve for rigid transform (no scale)
        src_centroid = src_pts.mean(axis=0)
        tgt_centroid = tgt_pts.mean(axis=0)

        src_centered = src_pts - src_centroid
        tgt_centered = tgt_pts - tgt_centroid

        H = src_centered.T @ tgt_centered
        U, S, Vt = np.linalg.svd(H)
        d = np.linalg.det(Vt.T @ U.T)
        R = Vt.T @ np.diag([1, 1, np.sign(d)]) @ U.T

        t = tgt_centroid - R @ src_centroid

        # Apply transform
        new_pts = (R @ src_pts.T).T + t

        # Check convergence
        delta = np.linalg.norm(new_pts - src_pts)
        src_pts = new_pts

        if delta < tolerance:
            break

    aligned = source.copy()
    aligned.vertices = src_pts
    return aligned


def auto_align(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
    source_landmarks: np.ndarray | None = None,
    target_landmarks: np.ndarray | None = None,
) -> trimesh.Trimesh:
    """Automatically align source to target.

    Strategy:
    1. If landmarks provided: Procrustes alignment
    2. Otherwise: centroid alignment + scale normalization + ICP
    """
    if source_landmarks is not None and target_landmarks is not None:
        return rigid_align_landmarks(source, source_landmarks, target_landmarks)

    # Scale normalization
    aligned, _ = normalize_scale(source, target)
    # Centroid alignment
    aligned = align_centroids(aligned, target)
    # ICP refinement
    aligned = rigid_align_icp(aligned, target)
    return aligned
