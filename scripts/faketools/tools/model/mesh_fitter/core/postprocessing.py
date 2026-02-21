"""Postprocessing module — smoothing and progressive snap."""

from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, diags
import trimesh


def laplacian_smooth(
    mesh: trimesh.Trimesh,
    iterations: int = 3,
    lamb: float = 0.5,
) -> trimesh.Trimesh:
    """Apply Laplacian smoothing while preserving topology.

    Args:
        mesh: Input mesh.
        iterations: Number of smoothing passes.
        lamb: Smoothing factor (0-1). Higher = more smoothing.

    Returns:
        Smoothed mesh copy.
    """
    result = mesh.copy()
    vertices = result.vertices.copy()
    L = _build_adjacency_sparse(mesh)

    for _ in range(iterations):
        vertices = _laplacian_step_sparse(vertices, L, lamb)

    result.vertices = vertices
    return result


def taubin_smooth(
    mesh: trimesh.Trimesh,
    iterations: int = 5,
    lamb: float = 0.5,
    mu: float = -0.53,
) -> trimesh.Trimesh:
    """Apply Taubin smoothing (shrinkage-resistant).

    Alternates positive and negative Laplacian steps to avoid shrinkage.
    """
    result = mesh.copy()
    vertices = result.vertices.copy()
    L = _build_adjacency_sparse(mesh)

    for _ in range(iterations):
        # Forward step (smoothing)
        vertices = _laplacian_step_sparse(vertices, L, lamb)
        # Backward step (inflation)
        vertices = _laplacian_step_sparse(vertices, L, mu)

    result.vertices = vertices
    return result


def progressive_snap(
    fitted: trimesh.Trimesh,
    target: trimesh.Trimesh,
    snap_fraction: float = 0.5,
    distance_threshold: float | None = None,
) -> trimesh.Trimesh:
    """Move fitted vertices towards nearest target surface points.

    Projects each fitted vertex to the closest point on the target **surface**
    (not just the nearest vertex), then moves by *snap_fraction* of the
    displacement.

    Args:
        fitted: Fitted mesh to snap.
        target: Target mesh to snap towards.
        snap_fraction: How far to move towards target (0=no move, 1=snap fully).
        distance_threshold: Only snap vertices within this distance. None = all.

    Returns:
        Snapped mesh copy.
    """
    result = fitted.copy()
    closest_points, distances, _ = trimesh.proximity.closest_point(target, fitted.vertices)
    displacement = closest_points - fitted.vertices

    if distance_threshold is not None:
        mask = distances < distance_threshold
        snapped = fitted.vertices.copy()
        snapped[mask] += snap_fraction * displacement[mask]
    else:
        snapped = fitted.vertices + snap_fraction * displacement

    result.vertices = snapped
    return result


def multi_stage_snap(
    fitted: trimesh.Trimesh,
    target: trimesh.Trimesh,
    stages: list[float] | None = None,
) -> trimesh.Trimesh:
    """Progressive snap in multiple stages.

    Each stage projects fitted vertices onto the target surface and moves
    them by the given fraction.

    Args:
        fitted: Fitted mesh.
        target: Target mesh.
        stages: List of snap fractions per stage. Default: [1.0].
    """
    if stages is None:
        stages = [1.0]

    result = fitted.copy()
    for fraction in stages:
        result = progressive_snap(result, target, snap_fraction=fraction)

    return result


def _build_adjacency_sparse(mesh: trimesh.Trimesh):
    """Build row-normalised cotangent-weighted adjacency matrix (CSR).

    Uses cotangent weights so that diagonal edges introduced by fan
    triangulation of quads receive near-zero weight, preserving the
    original quad-like neighbourhood structure during smoothing.

    Returns a sparse matrix L where ``L @ vertices`` gives the weighted
    neighbour-centroid for every vertex (isolated vertices map to
    themselves).
    """
    vertices = mesh.vertices
    faces = mesh.faces
    n_verts = len(vertices)

    i0, i1, i2 = faces[:, 0], faces[:, 1], faces[:, 2]
    v0, v1, v2 = vertices[i0], vertices[i1], vertices[i2]

    # Edge vectors
    e01 = v1 - v0
    e02 = v2 - v0
    e12 = v2 - v1

    # Cotangent at vertex 0 -> weights edge v1-v2
    cross0 = np.linalg.norm(np.cross(e01, e02), axis=1)
    cot0 = np.sum(e01 * e02, axis=1) / (cross0 + 1e-10)

    # Cotangent at vertex 1 -> weights edge v0-v2
    cross1 = np.linalg.norm(np.cross(-e01, e12), axis=1)
    cot1 = np.sum(-e01 * e12, axis=1) / (cross1 + 1e-10)

    # Cotangent at vertex 2 -> weights edge v0-v1
    e20 = -e02
    e21 = -e12
    cross2 = np.linalg.norm(np.cross(e20, e21), axis=1)
    cot2 = np.sum(e20 * e21, axis=1) / (cross2 + 1e-10)

    # Clamp to [0, 10] — negative values come from obtuse angles
    cot0 = np.clip(cot0, 0.0, 10.0)
    cot1 = np.clip(cot1, 0.0, 10.0)
    cot2 = np.clip(cot2, 0.0, 10.0)

    # cot_at_v0 weights edge v1-v2, cot_at_v1 weights edge v0-v2, etc.
    rows = np.concatenate([i1, i2, i0, i2, i0, i1])
    cols = np.concatenate([i2, i1, i2, i0, i1, i0])
    weights = np.concatenate([cot0, cot0, cot1, cot1, cot2, cot2])

    adj = coo_matrix((weights, (rows, cols)), shape=(n_verts, n_verts)).tocsr()

    # Row-normalise: each row sums to 1 (weighted neighbour average)
    degree = np.asarray(adj.sum(axis=1)).ravel()

    # Inject self-loops for isolated vertices so L @ v = v
    isolated = degree < 1e-10
    if isolated.any():
        iso_idx = np.where(isolated)[0]
        iso_coo = coo_matrix(
            (np.ones(len(iso_idx)), (iso_idx, iso_idx)),
            shape=(n_verts, n_verts),
        )
        adj = (adj + iso_coo).tocsr()
        degree[isolated] = 1.0

    L = diags(1.0 / degree) @ adj
    return L


def _laplacian_step_sparse(
    vertices: np.ndarray,
    L,
    factor: float,
) -> np.ndarray:
    """Single Laplacian smoothing step using sparse matrix multiply."""
    centroids = L @ vertices
    return vertices + factor * (centroids - vertices)
