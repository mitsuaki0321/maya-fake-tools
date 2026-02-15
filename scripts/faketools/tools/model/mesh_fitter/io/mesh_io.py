"""Mesh I/O module — OBJ/PLY reading and writing via trimesh."""

from __future__ import annotations

from pathlib import Path

import trimesh


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    """Load a mesh from OBJ or PLY file.

    Uses process=False to preserve original vertex ordering and topology.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Mesh file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in (".obj", ".ply"):
        raise ValueError(f"Unsupported mesh format: {suffix} (supported: .obj, .ply)")

    mesh = trimesh.load(str(path), process=False, force="mesh")

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Failed to load as Trimesh: {path}")
    if len(mesh.vertices) == 0:
        raise ValueError(f"Mesh has no vertices: {path}")

    return mesh


def save_mesh(mesh: trimesh.Trimesh, path: str | Path) -> Path:
    """Save a mesh to OBJ or PLY file.

    Returns the resolved output path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    if suffix not in (".obj", ".ply"):
        raise ValueError(f"Unsupported mesh format: {suffix} (supported: .obj, .ply)")

    mesh.export(str(path))
    return path


def mesh_info(mesh: trimesh.Trimesh) -> dict:
    """Return basic mesh statistics."""
    return {
        "n_vertices": len(mesh.vertices),
        "n_faces": len(mesh.faces),
        "bounds_min": mesh.vertices.min(axis=0).tolist(),
        "bounds_max": mesh.vertices.max(axis=0).tolist(),
        "is_watertight": mesh.is_watertight,
    }
