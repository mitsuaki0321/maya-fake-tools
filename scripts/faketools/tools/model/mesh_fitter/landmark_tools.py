"""Maya landmark placement tools — Protocol-based, Mock-injectable."""

from __future__ import annotations

from pathlib import Path

from .core.algorithms import positions_to_surface_landmarks
from .io.landmark_io import LandmarkData, load_landmarks, save_landmarks
from .mesh_bridge import MayaMeshAPI, OpenMayaMeshAPI, maya_mesh_to_trimesh


class MayaLandmarkPlacer:
    """Place and manage landmark pairs between source and target meshes in Maya.

    Args:
        source_name: Maya mesh name for the source (template).
        target_name: Maya mesh name for the target (scan).
        api: MayaMeshAPI implementation. Defaults to OpenMayaMeshAPI().
    """

    def __init__(
        self,
        source_name: str,
        target_name: str,
        api: MayaMeshAPI | None = None,
    ) -> None:
        self._source_name = source_name
        self._target_name = target_name
        self._api = api if api is not None else OpenMayaMeshAPI()
        self._source_indices: list[int] = []
        self._target_indices: list[int] = []
        self._names: list[str] = []

        # Surface mode state
        self._source_tri_indices: list[int] = []
        self._source_bary_coords: list[list[float]] = []
        self._target_surface_positions: list[list[float]] = []
        self._surface_names: list[str] = []
        self._cached_source_mesh = None

    @property
    def is_surface_mode(self) -> bool:
        return len(self._source_tri_indices) > 0

    @property
    def count(self) -> int:
        if self.is_surface_mode:
            return len(self._source_tri_indices)
        return len(self._source_indices)

    @property
    def names(self) -> list[str]:
        if self.is_surface_mode:
            return list(self._surface_names)
        return list(self._names)

    @property
    def data(self) -> LandmarkData:
        """Build LandmarkData from current pairs, fetching positions from API."""
        if self.is_surface_mode:
            return LandmarkData(
                source_triangle_indices=list(self._source_tri_indices),
                source_barycentric_coords=[list(b) for b in self._source_bary_coords],
                target_positions=[list(p) for p in self._target_surface_positions],
                names=list(self._surface_names),
            )

        src_verts = self._api.get_vertex_positions(self._source_name)
        tgt_verts = self._api.get_vertex_positions(self._target_name)

        src_pos = src_verts[self._source_indices].tolist() if self._source_indices else []
        tgt_pos = tgt_verts[self._target_indices].tolist() if self._target_indices else []

        return LandmarkData(
            source_vertex_indices=list(self._source_indices),
            target_vertex_indices=list(self._target_indices),
            source_positions=src_pos,
            target_positions=tgt_pos,
            names=list(self._names),
        )

    def add_pair(
        self,
        source_idx: int,
        target_idx: int,
        name: str | None = None,
    ) -> None:
        """Add a landmark pair by vertex indices.

        Args:
            source_idx: Vertex index on the source mesh.
            target_idx: Vertex index on the target mesh.
            name: Optional name for this landmark pair.
        """
        if self.is_surface_mode:
            raise ValueError("Cannot add vertex landmarks when surface landmarks exist")
        self._source_indices.append(source_idx)
        self._target_indices.append(target_idx)
        if name is None:
            name = f"lm_{self.count - 1}"
        self._names.append(name)

    def add_surface_pair(
        self,
        source_position: list[float],
        target_position: list[float],
        name: str | None = None,
    ) -> None:
        """Add a surface landmark pair by 3D positions.

        Projects source_position onto the source mesh surface to compute
        triangle index and barycentric coordinates.

        Args:
            source_position: [x, y, z] on or near the source mesh surface.
            target_position: [x, y, z] target position.
            name: Optional name for this landmark pair.
        """
        if self._source_indices:
            raise ValueError("Cannot add surface landmarks when vertex landmarks exist")

        import numpy as np

        # Build/cache the trimesh for projection
        if self._cached_source_mesh is None:
            self._cached_source_mesh = maya_mesh_to_trimesh(self._source_name, api=self._api)

        pos = np.array([source_position], dtype=float)
        tri_ids, bary = positions_to_surface_landmarks(self._cached_source_mesh, pos)

        self._source_tri_indices.append(int(tri_ids[0]))
        self._source_bary_coords.append(bary[0].tolist())
        self._target_surface_positions.append(list(target_position))

        if name is None:
            name = f"lm_{self.count - 1}"
        self._surface_names.append(name)

    def add_from_selection(self, name: str | None = None) -> None:
        """Add a landmark from the current Maya vertex selection.

        Expects exactly one vertex selected. Determines whether the selection
        is on the source or target mesh and records accordingly.

        Call this twice (once per mesh) to complete a pair, or use add_pair()
        for explicit index-based placement.
        """
        mesh_name, indices = self._api.get_selected_vertex_indices()
        if len(indices) != 1:
            raise ValueError(f"Expected 1 vertex selected, got {len(indices)}")

        idx = indices[0]

        if mesh_name == self._source_name:
            # Source vertex — need a target pair later
            self._source_indices.append(idx)
            self._target_indices.append(-1)  # placeholder
            if name is None:
                name = f"lm_{self.count - 1}"
            self._names.append(name)
        elif mesh_name == self._target_name:
            # Target vertex — complete the last incomplete pair
            if self._target_indices and self._target_indices[-1] == -1:
                self._target_indices[-1] = idx
            else:
                raise ValueError("No pending source landmark to pair with. Select a source vertex first, then a target vertex.")
        else:
            raise ValueError(f"Selected mesh '{mesh_name}' is neither source '{self._source_name}' nor target '{self._target_name}'")

    def remove(self, index: int) -> None:
        """Remove a landmark pair by its list index."""
        if self.is_surface_mode:
            self._source_tri_indices.pop(index)
            self._source_bary_coords.pop(index)
            self._target_surface_positions.pop(index)
            self._surface_names.pop(index)
        else:
            self._source_indices.pop(index)
            self._target_indices.pop(index)
            self._names.pop(index)

    def save(self, path: str | Path) -> Path:
        """Save current landmark pairs to JSON."""
        return save_landmarks(self.data, path)

    def load(self, path: str | Path) -> None:
        """Load landmark pairs from JSON, replacing current data."""
        lm = load_landmarks(path)
        if lm.is_surface_mode:
            self._source_tri_indices = lm.source_triangle_indices
            self._source_bary_coords = lm.source_barycentric_coords
            self._target_surface_positions = lm.target_positions
            self._surface_names = lm.names if lm.names else [f"lm_{i}" for i in range(lm.count)]
            # Clear vertex mode state
            self._source_indices = []
            self._target_indices = []
            self._names = []
        else:
            self._source_indices = lm.source_vertex_indices
            self._target_indices = lm.target_vertex_indices
            self._names = lm.names if lm.names else [f"lm_{i}" for i in range(lm.count)]
            # Clear surface mode state
            self._source_tri_indices = []
            self._source_bary_coords = []
            self._target_surface_positions = []
            self._surface_names = []

    def __repr__(self) -> str:
        return f"MayaLandmarkPlacer(source='{self._source_name}', target='{self._target_name}', {self.count} pairs)"
