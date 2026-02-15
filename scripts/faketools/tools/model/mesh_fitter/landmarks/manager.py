"""Landmark manager — create, edit, save/load, and mirror landmark pairs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import trimesh

from ..core.algorithms import surface_landmarks_to_positions
from ..io.landmark_io import LandmarkData, load_landmarks, save_landmarks


class LandmarkManager:
    """Manages landmark pairs between source and target meshes."""

    def __init__(
        self,
        source_mesh: trimesh.Trimesh | None = None,
        target_mesh: trimesh.Trimesh | None = None,
    ):
        self.source_mesh = source_mesh
        self.target_mesh = target_mesh
        self._data = LandmarkData()

    @property
    def count(self) -> int:
        return self._data.count

    @property
    def data(self) -> LandmarkData:
        return self._data

    @property
    def source_indices(self) -> list[int]:
        return self._data.source_vertex_indices

    @property
    def target_indices(self) -> list[int]:
        return self._data.target_vertex_indices

    def add(
        self,
        source_vertex_idx: int,
        target_vertex_idx: int,
        name: str | None = None,
    ) -> None:
        """Add a landmark pair by vertex indices."""
        self._data.source_vertex_indices.append(source_vertex_idx)
        self._data.target_vertex_indices.append(target_vertex_idx)

        if self.source_mesh is not None:
            pos = self.source_mesh.vertices[source_vertex_idx].tolist()
            self._data.source_positions.append(pos)
        if self.target_mesh is not None:
            pos = self.target_mesh.vertices[target_vertex_idx].tolist()
            self._data.target_positions.append(pos)

        if name is None:
            name = f"lm_{self.count - 1}"
        self._data.names.append(name)

    def remove(self, index: int) -> None:
        """Remove a landmark pair by its list index."""
        if self._data.is_surface_mode:
            for lst in [
                self._data.source_triangle_indices,
                self._data.source_barycentric_coords,
                self._data.target_positions,
                self._data.names,
            ]:
                if index < len(lst):
                    lst.pop(index)
        else:
            for lst in [
                self._data.source_vertex_indices,
                self._data.target_vertex_indices,
                self._data.source_positions,
                self._data.target_positions,
                self._data.names,
            ]:
                if index < len(lst):
                    lst.pop(index)

    def get_source_positions(self) -> np.ndarray:
        """Get source landmark 3D positions from mesh vertices."""
        if self._data.is_surface_mode:
            if self.source_mesh is not None:
                return surface_landmarks_to_positions(
                    self.source_mesh,
                    np.array(self._data.source_triangle_indices),
                    np.array(self._data.source_barycentric_coords),
                )
            return np.array(self._data.source_positions)
        if self.source_mesh is None:
            return np.array(self._data.source_positions)
        return self.source_mesh.vertices[self._data.source_vertex_indices]

    def get_target_positions(self) -> np.ndarray:
        """Get target landmark 3D positions from mesh vertices."""
        if self.target_mesh is None:
            return np.array(self._data.target_positions)
        return self.target_mesh.vertices[self._data.target_vertex_indices]

    def mirror_x(self, mesh: trimesh.Trimesh, vertex_indices: list[int]) -> list[int]:
        """Find mirrored vertices across the YZ plane (X=0).

        For each vertex, reflects its position across X=0 and finds the
        nearest vertex on the mesh.

        Returns:
            List of mirrored vertex indices.
        """
        positions = mesh.vertices[vertex_indices]
        mirrored_pos = positions.copy()
        mirrored_pos[:, 0] *= -1

        tree = cKDTree(mesh.vertices)
        _, mirrored_indices = tree.query(mirrored_pos)
        return mirrored_indices.tolist()

    def add_mirrored_pairs(self, mirror_axis: int = 0) -> int:
        """Mirror all existing landmarks across the given axis.

        Requires both source_mesh and target_mesh to be set.

        Returns:
            Number of new landmarks added.
        """
        if self.source_mesh is None or self.target_mesh is None:
            raise ValueError("Both source and target meshes are required for mirroring")

        n_existing = self.count
        src_indices = list(self._data.source_vertex_indices)
        tgt_indices = list(self._data.target_vertex_indices)

        src_mirrored = self._mirror_indices(self.source_mesh, src_indices, mirror_axis)
        tgt_mirrored = self._mirror_indices(self.target_mesh, tgt_indices, mirror_axis)

        added = 0
        for i in range(n_existing):
            src_m = src_mirrored[i]
            tgt_m = tgt_mirrored[i]
            # Skip if mirrored vertex is the same as original (on axis)
            if src_m == src_indices[i]:
                continue
            # Skip if already exists
            if src_m in self._data.source_vertex_indices:
                continue
            name = self._data.names[i] + "_mirror" if self._data.names else None
            self.add(src_m, tgt_m, name=name)
            added += 1
        return added

    def _mirror_indices(self, mesh: trimesh.Trimesh, indices: list[int], axis: int) -> list[int]:
        positions = mesh.vertices[indices].copy()
        positions[:, axis] *= -1
        tree = cKDTree(mesh.vertices)
        _, mirrored = tree.query(positions)
        return mirrored.tolist()

    def save(self, path: str | Path) -> Path:
        """Save landmarks to JSON."""
        return save_landmarks(self._data, path)

    def load(self, path: str | Path) -> None:
        """Load landmarks from JSON."""
        self._data = load_landmarks(path)

    def __repr__(self) -> str:
        return f"LandmarkManager({self.count} landmarks)"
