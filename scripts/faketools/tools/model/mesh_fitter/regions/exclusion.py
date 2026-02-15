"""Exclusion region module — vertex masks and geodesic flood fill."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.csgraph import shortest_path
import trimesh


def create_vertex_mask(
    mesh: trimesh.Trimesh,
    exclude_indices: list[int] | None = None,
    include_indices: list[int] | None = None,
) -> np.ndarray:
    """Create a boolean mask for vertices.

    Args:
        mesh: The mesh.
        exclude_indices: Vertices to exclude (mask=False).
        include_indices: Vertices to include (mask=True). If provided,
            all other vertices are excluded.

    Returns:
        Boolean array of shape (n_vertices,). True = included.
    """
    n = len(mesh.vertices)

    if include_indices is not None:
        mask = np.zeros(n, dtype=bool)
        mask[include_indices] = True
    else:
        mask = np.ones(n, dtype=bool)

    if exclude_indices is not None:
        mask[exclude_indices] = False

    return mask


def geodesic_flood_fill(
    mesh: trimesh.Trimesh,
    seed_indices: list[int],
    max_distance: float,
) -> np.ndarray:
    """Find all vertices within geodesic distance from seed vertices.

    Uses edge-weighted graph shortest paths.

    Args:
        mesh: Input mesh.
        seed_indices: Starting vertex indices.
        max_distance: Maximum geodesic distance.

    Returns:
        Boolean mask — True for vertices within range.
    """
    graph = _build_edge_graph(mesh)

    # Compute shortest paths from all seeds
    dist_matrix = shortest_path(
        graph,
        method="D",
        directed=False,
        indices=seed_indices,
    )

    # Minimum distance from any seed
    min_dists = dist_matrix.min(axis=0)

    return min_dists <= max_distance


def exclusion_mask_from_seeds(
    mesh: trimesh.Trimesh,
    seed_indices: list[int],
    radius: float,
) -> np.ndarray:
    """Create an exclusion mask: vertices near seeds are excluded.

    Args:
        mesh: Input mesh.
        seed_indices: Center vertices of exclusion zones.
        radius: Geodesic radius of exclusion.

    Returns:
        Boolean mask — True for included (non-excluded) vertices.
    """
    flood = geodesic_flood_fill(mesh, seed_indices, radius)
    return ~flood


def apply_mask_to_fitting(
    source: trimesh.Trimesh,
    mask: np.ndarray,
) -> np.ndarray:
    """Convert vertex mask to per-vertex weight array for fitting.

    Excluded vertices get weight 0, included vertices get weight 1.
    This can be used with nricp_amberg's W parameter.
    """
    weights = np.zeros(len(source.vertices))
    weights[mask] = 1.0
    return weights


def save_mask(mask: np.ndarray, path: str | Path) -> Path:
    """Save a vertex mask to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "excluded_indices": np.where(~mask)[0].tolist(),
        "n_vertices": len(mask),
        "n_excluded": int((~mask).sum()),
        "n_included": int(mask.sum()),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_mask(path: str | Path, n_vertices: int) -> np.ndarray:
    """Load a vertex mask from a JSON file."""
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    mask = np.ones(n_vertices, dtype=bool)
    mask[data["excluded_indices"]] = False
    return mask


def _build_edge_graph(mesh: trimesh.Trimesh) -> lil_matrix:
    """Build sparse edge-weight graph from mesh faces."""
    n = len(mesh.vertices)
    graph = lil_matrix((n, n))

    for face in mesh.faces:
        for i in range(3):
            v0, v1 = face[i], face[(i + 1) % 3]
            dist = np.linalg.norm(mesh.vertices[v0] - mesh.vertices[v1])
            if graph[v0, v1] == 0 or dist < graph[v0, v1]:
                graph[v0, v1] = dist
                graph[v1, v0] = dist

    return graph.tocsr()
