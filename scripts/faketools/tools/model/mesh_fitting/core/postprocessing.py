"""Postprocessing module — smoothing and progressive snap."""

from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.spatial import cKDTree
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

    Args:
        fitted: Fitted mesh to snap.
        target: Target mesh to snap towards.
        snap_fraction: How far to move towards target (0=no move, 1=snap fully).
        distance_threshold: Only snap vertices within this distance. None = all.

    Returns:
        Snapped mesh copy.
    """
    result = fitted.copy()
    tree = cKDTree(target.vertices)
    distances, indices = tree.query(fitted.vertices)

    target_positions = target.vertices[indices]
    displacement = target_positions - fitted.vertices

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
    smooth_between: bool = True,
) -> trimesh.Trimesh:
    """Progressive snap in multiple stages with optional smoothing.

    Args:
        fitted: Fitted mesh.
        target: Target mesh.
        stages: List of snap fractions per stage. Default: [0.3, 0.5, 0.7].
        smooth_between: Apply Taubin smoothing between stages.
    """
    if stages is None:
        stages = [0.3, 0.5, 0.7]

    result = fitted.copy()
    for fraction in stages:
        result = progressive_snap(result, target, snap_fraction=fraction)
        if smooth_between:
            result = taubin_smooth(result, iterations=2)

    return result


def _build_adjacency_sparse(mesh: trimesh.Trimesh):
    """Build row-normalised adjacency matrix (CSR) from faces.

    Returns a sparse matrix L where ``L @ vertices`` gives the neighbour-
    centroid for every vertex (isolated vertices map to themselves).
    """
    faces = mesh.faces
    n_verts = len(mesh.vertices)

    # Build all directed edge pairs from triangular faces
    # Each triangle (a, b, c) contributes edges: a->b, b->a, b->c, c->b, a->c, c->a
    i0, i1, i2 = faces[:, 0], faces[:, 1], faces[:, 2]
    rows = np.concatenate([i0, i1, i1, i2, i0, i2])
    cols = np.concatenate([i1, i0, i2, i1, i2, i0])
    data = np.ones(len(rows), dtype=np.float64)

    adj = coo_matrix((data, (rows, cols)), shape=(n_verts, n_verts)).tocsr()
    # Collapse duplicate edges to binary adjacency
    adj.data[:] = 1.0

    # Row-normalise: each row sums to 1 (neighbour average)
    degree = np.asarray(adj.sum(axis=1)).ravel()

    # Inject self-loops for isolated vertices so L @ v = v
    isolated = degree == 0
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
