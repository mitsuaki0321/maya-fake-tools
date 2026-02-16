"""Algorithm wrapper for Non-Rigid ICP (nricp_amberg)."""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
import math

import numpy as np
import trimesh
from trimesh.registration import nricp_amberg

logger = getLogger(__name__)

# Predefined stiffness schedules
# Each step: [stiffness(alpha), landmark_weight, normal_weight, max_iterations]
SCHEDULES: dict[str, list[list[float]]] = {
    "standard": [
        [0.1, 0, 0.5, 15],
        [0.05, 0, 0.5, 15],
        [0.02, 0, 0.5, 10],
        [0.01, 0, 0.0, 10],
        [0.005, 0, 0.0, 10],
    ],
    "strong": [
        [0.05, 50, 0.5, 10],
        [0.03, 20, 0.5, 10],
        [0.02, 10, 0.5, 10],
        [0.01, 5, 0.5, 10],
        [0.005, 2, 0.0, 10],
        [0.002, 0, 0.0, 10],
    ],
    "gentle": [
        [0.1, 0, 0.5, 15],
        [0.05, 0, 0.5, 15],
        [0.03, 0, 0.5, 10],
        [0.02, 0, 0.5, 10],
        [0.01, 0, 0.0, 10],
        [0.005, 0, 0.0, 10],
        [0.002, 0, 0.0, 10],
    ],
    "landmark": [
        [0.1, 50, 0.5, 3],
        [0.05, 20, 0.5, 3],
        [0.03, 10, 0.5, 5],
        [0.02, 5, 0.5, 5],
        [0.01, 2, 0.0, 5],
        [0.005, 1, 0.0, 5],
        [0.002, 0, 0.0, 5],
    ],
}


def generate_schedule(
    initial_stiffness: float = 0.10,
    landmark_strength: float = 1.0,
    num_steps: int = 5,
    has_landmarks: bool = False,
) -> list[list[float]]:
    """Generate a custom stiffness schedule.

    Args:
        initial_stiffness: Starting stiffness value (decays to 0.002).
        landmark_strength: Multiplier for landmark weights (0.0–1.0).
        num_steps: Number of schedule steps (>= 2).
        has_landmarks: Whether landmarks are present.

    Returns:
        List of steps [stiffness, landmark_weight, normal_weight, max_iterations].
    """
    num_steps = max(2, num_steps)
    final_stiffness = 0.002
    steps: list[list[float]] = []

    for i in range(num_steps):
        # Stiffness: exponential decay from initial_stiffness to 0.002
        t = i / max(num_steps - 1, 1)
        stiffness = initial_stiffness * (final_stiffness / initial_stiffness) ** t

        # Landmark weight: linear decay, final step = 0
        if has_landmarks and i < num_steps - 1:
            lm_weight = 50.0 * landmark_strength * (1 - i / max(num_steps - 1, 1))
        else:
            lm_weight = 0.0

        # Normal weight: first 60% of steps use 0.5, rest use 0.0
        cutoff = math.ceil(num_steps * 0.6)
        normal_weight = 0.5 if i < cutoff else 0.0

        # Max iterations: with landmarks → fewer per step; without → more
        if has_landmarks:
            max_iter = 3.0 if i < 2 else 5.0
        else:
            max_iter = 15.0 if i < 2 else 10.0

        steps.append([stiffness, lm_weight, normal_weight, max_iter])

    return steps


@dataclass
class FittingParams:
    """Parameters for nricp_amberg fitting."""

    schedule: str | list[list[float]] = "standard"
    source_landmarks: list[int] | None = None
    target_positions: np.ndarray | None = None
    use_faces: bool = True  # Whether to use face normals for correspondence
    eps: float = 1e-4  # Convergence threshold

    # Surface landmarks: triangle index + barycentric coordinates
    source_landmark_triangles: np.ndarray | None = None  # (n,) int
    source_landmark_barycentrics: np.ndarray | None = None  # (n, 3) float

    def get_steps(self) -> list[list[float]]:
        if isinstance(self.schedule, str):
            if self.schedule not in SCHEDULES:
                raise ValueError(f"Unknown schedule '{self.schedule}'. Available: {list(SCHEDULES.keys())}")
            return SCHEDULES[self.schedule]
        return self.schedule

    @property
    def is_surface_landmarks(self) -> bool:
        return self.source_landmark_triangles is not None and len(self.source_landmark_triangles) > 0

    @property
    def has_landmarks(self) -> bool:
        return self.is_surface_landmarks or (
            self.source_landmarks is not None and self.target_positions is not None and len(self.source_landmarks) > 0
        )


def surface_landmarks_to_positions(
    mesh: trimesh.Trimesh,
    triangle_indices: np.ndarray,
    barycentric_coords: np.ndarray,
) -> np.ndarray:
    """Convert surface landmarks (triangle + barycentric) to 3D positions.

    Args:
        mesh: The mesh the landmarks are defined on.
        triangle_indices: (n,) int array of triangle face indices.
        barycentric_coords: (n, 3) float array of barycentric coordinates.

    Returns:
        (n, 3) array of 3D positions.
    """
    tri_ids = np.asarray(triangle_indices, dtype=int)
    bary = np.asarray(barycentric_coords, dtype=float)
    # (n, 3, 3): for each landmark, the 3 vertices of its triangle
    tri_verts = mesh.vertices[mesh.faces[tri_ids]]
    # einsum: for each landmark n, sum bary[n,k] * tri_verts[n,k,d] over k
    return np.einsum("nk,nkd->nd", bary, tri_verts)


def positions_to_surface_landmarks(
    mesh: trimesh.Trimesh,
    positions: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert 3D positions to surface landmarks (triangle + barycentric).

    Projects each position onto the closest point on the mesh surface.

    Args:
        mesh: The mesh to project onto.
        positions: (n, 3) array of 3D positions.

    Returns:
        (triangle_indices, barycentric_coords) — (n,) int and (n, 3) float arrays.
    """
    closest, _, tri_ids = trimesh.proximity.closest_point(mesh, positions)
    tri_verts = mesh.vertices[mesh.faces[tri_ids]]  # (n, 3, 3)
    bary = trimesh.triangles.points_to_barycentric(tri_verts, closest)
    return np.asarray(tri_ids, dtype=int), np.asarray(bary, dtype=float)


def _merge_duplicate_vertices(
    mesh: trimesh.Trimesh,
) -> tuple[trimesh.Trimesh, np.ndarray | None]:
    """Merge duplicate (coincident) vertices to avoid singular matrices in NRICP.

    Returns:
        (clean_mesh, inverse): clean_mesh has unique vertices only.
            inverse[i] gives the clean-mesh index for original vertex i.
            Returns (mesh, None) if no duplicates found.
    """
    _, unique_idx, inverse = np.unique(
        np.round(mesh.vertices, decimals=10),
        axis=0,
        return_index=True,
        return_inverse=True,
    )
    if len(unique_idx) == len(mesh.vertices):
        return mesh, None

    clean_verts = mesh.vertices[unique_idx]
    clean_faces = inverse[mesh.faces]

    # Remove degenerate faces where merging collapsed two vertices into one
    non_degen = (clean_faces[:, 0] != clean_faces[:, 1]) & (clean_faces[:, 1] != clean_faces[:, 2]) & (clean_faces[:, 0] != clean_faces[:, 2])
    clean_faces = clean_faces[non_degen]

    clean_mesh = trimesh.Trimesh(vertices=clean_verts, faces=clean_faces, process=False)
    return clean_mesh, inverse


def fit_mesh(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
    params: FittingParams | None = None,
) -> trimesh.Trimesh:
    """Run nricp_amberg to fit source mesh to target.

    Args:
        source: Template mesh to deform (topology preserved).
        target: Target mesh/scan to fit towards.
        params: Fitting parameters. Uses defaults if None.

    Returns:
        New Trimesh with deformed vertices and original source topology.
    """
    if params is None:
        params = FittingParams()

    # Merge duplicate vertices to prevent singular matrix errors.
    # NRICP computes 1/edge_length, so zero-length edges (from coincident
    # vertices) cause division by zero and a singular linear system.
    clean_source, inverse = _merge_duplicate_vertices(source)
    if inverse is not None:
        n_merged = len(source.vertices) - len(clean_source.vertices)
        logger.info("Merged %d duplicate vertices for fitting", n_merged)

    steps = params.get_steps()

    # Inject landmark weights into steps if landmarks provided
    if params.has_landmarks:
        steps = _inject_landmark_weights(steps)

    kwargs: dict = {
        "steps": steps,
        "eps": params.eps,
        "use_faces": params.use_faces,
    }

    if params.has_landmarks:
        if params.is_surface_landmarks:
            tri_ids = params.source_landmark_triangles
            bary = params.source_landmark_barycentrics
            if inverse is not None:
                # Re-project after vertex merge: positions -> new surface landmarks
                positions = surface_landmarks_to_positions(source, tri_ids, bary)
                tri_ids, bary = positions_to_surface_landmarks(clean_source, positions)
            kwargs["source_landmarks"] = (np.asarray(tri_ids), np.asarray(bary))
        else:
            # Vertex index path
            landmarks = params.source_landmarks
            if inverse is not None:
                landmarks = [int(inverse[i]) for i in landmarks]
            kwargs["source_landmarks"] = landmarks
        kwargs["target_positions"] = np.asarray(params.target_positions)

    result_verts = nricp_amberg(clean_source, target, **kwargs)

    # If vertices were merged, expand result back to original vertex count
    if inverse is not None:
        result_verts = result_verts[inverse]

    return trimesh.Trimesh(
        vertices=result_verts,
        faces=source.faces.copy(),
        process=False,
    )


def _inject_landmark_weights(steps: list[list[float]]) -> list[list[float]]:
    """If landmark weight columns are all zero, inject decreasing weights."""
    has_weights = any(step[1] > 0 for step in steps)
    if has_weights:
        return steps

    n = len(steps)
    new_steps = []
    for i, step in enumerate(steps):
        weight = max(50 * (1 - i / max(n - 1, 1)), 1) if i < n - 1 else 0
        new_steps.append([step[0], weight, step[2], step[3]])
    return new_steps
