"""Landmark I/O module — JSON reading and writing."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class LandmarkData:
    """Container for a set of landmark pairs between source and target meshes."""

    source_vertex_indices: list[int] = field(default_factory=list)
    target_vertex_indices: list[int] = field(default_factory=list)
    source_positions: list[list[float]] = field(default_factory=list)
    target_positions: list[list[float]] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

    # Surface mode: triangle index + barycentric coordinates (mutually exclusive with vertex mode)
    source_triangle_indices: list[int] = field(default_factory=list)
    source_barycentric_coords: list[list[float]] = field(default_factory=list)

    @property
    def is_surface_mode(self) -> bool:
        return len(self.source_triangle_indices) > 0

    @property
    def count(self) -> int:
        if self.is_surface_mode:
            return len(self.source_triangle_indices)
        return len(self.source_vertex_indices)

    def validate(self) -> None:
        """Check that all arrays have consistent lengths."""
        if self.is_surface_mode:
            n = len(self.source_triangle_indices)
            if len(self.source_barycentric_coords) != n:
                raise ValueError(f"Mismatched lengths: source_triangle_indices={n}, source_barycentric_coords={len(self.source_barycentric_coords)}")
            for i, bary in enumerate(self.source_barycentric_coords):
                if len(bary) != 3:
                    raise ValueError(f"Barycentric coord {i} has {len(bary)} components, expected 3")
            if self.target_positions and len(self.target_positions) != n:
                raise ValueError("target_positions length mismatch")
            if self.names and len(self.names) != n:
                raise ValueError("names length mismatch")
        else:
            n = len(self.source_vertex_indices)
            if len(self.target_vertex_indices) != n:
                raise ValueError(f"Mismatched lengths: source={n}, target={len(self.target_vertex_indices)}")
            if self.source_positions and len(self.source_positions) != n:
                raise ValueError("source_positions length mismatch")
            if self.target_positions and len(self.target_positions) != n:
                raise ValueError("target_positions length mismatch")
            if self.names and len(self.names) != n:
                raise ValueError("names length mismatch")


def load_landmarks(path: str | Path) -> LandmarkData:
    """Load landmarks from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Landmark file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    lm = LandmarkData(
        source_vertex_indices=data.get("source_vertex_indices", []),
        target_vertex_indices=data.get("target_vertex_indices", []),
        source_positions=data.get("source_positions", []),
        target_positions=data.get("target_positions", []),
        names=data.get("names", []),
        source_triangle_indices=data.get("source_triangle_indices", []),
        source_barycentric_coords=data.get("source_barycentric_coords", []),
    )
    lm.validate()
    return lm


def save_landmarks(landmarks: LandmarkData, path: str | Path) -> Path:
    """Save landmarks to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    landmarks.validate()

    data: dict = {}
    if landmarks.is_surface_mode:
        data["source_triangle_indices"] = landmarks.source_triangle_indices
        data["source_barycentric_coords"] = landmarks.source_barycentric_coords
    else:
        data["source_vertex_indices"] = landmarks.source_vertex_indices
        data["target_vertex_indices"] = landmarks.target_vertex_indices
    if landmarks.source_positions:
        data["source_positions"] = landmarks.source_positions
    if landmarks.target_positions:
        data["target_positions"] = landmarks.target_positions
    if landmarks.names:
        data["names"] = landmarks.names

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return path
