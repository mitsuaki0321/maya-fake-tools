"""Maya mesh bridge — Protocol-based abstraction for Maya mesh operations.

Uses Protocol + dependency injection so tests can use MockMayaMeshAPI
without any Maya installation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import trimesh


@runtime_checkable
class MayaMeshAPI(Protocol):
    """Protocol for Maya mesh operations. Implement for real Maya or mocks."""

    def get_vertex_positions(self, mesh_name: str) -> np.ndarray:
        """Return (N, 3) float64 array of vertex positions."""
        ...

    def get_face_vertex_indices(self, mesh_name: str) -> np.ndarray:
        """Return (M, K) int array of face-vertex indices (triangles or quads)."""
        ...

    def set_vertex_positions(self, mesh_name: str, positions: np.ndarray) -> None:
        """Set vertex positions on the named mesh."""
        ...

    def get_selected_vertex_indices(self) -> tuple[str, list[int]]:
        """Return (mesh_name, [vertex_indices]) from current Maya selection."""
        ...

    def get_world_matrix(self, mesh_name: str) -> np.ndarray:
        """Return (4, 4) world transformation matrix."""
        ...

    def get_closest_point_on_mesh(self, mesh_name: str, point: list[float]) -> list[float]:
        """Return closest point on mesh surface in object space."""
        ...


class OpenMayaMeshAPI:
    """Real Maya implementation using maya.api.OpenMaya (lazy import)."""

    def get_vertex_positions(self, mesh_name: str) -> np.ndarray:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MSelectionList()
        sel.add(mesh_name)
        dag = sel.getDagPath(0)
        fn_mesh = om2.MFnMesh(dag)
        points = fn_mesh.getPoints(om2.MSpace.kObject)
        return np.array([[p.x, p.y, p.z] for p in points], dtype=np.float64)

    def get_face_vertex_indices(self, mesh_name: str) -> np.ndarray:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MSelectionList()
        sel.add(mesh_name)
        dag = sel.getDagPath(0)
        fn_mesh = om2.MFnMesh(dag)

        face_counts, face_vertices = fn_mesh.getVertices()
        faces = []
        idx = 0
        for count in face_counts:
            faces.append([face_vertices[idx + j] for j in range(count)])
            idx += count
        # Pad to uniform width (max verts per face)
        max_k = max(len(f) for f in faces)
        padded = [f + [-1] * (max_k - len(f)) for f in faces]
        return np.array(padded, dtype=np.int64)

    def set_vertex_positions(self, mesh_name: str, positions: np.ndarray) -> None:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MSelectionList()
        sel.add(mesh_name)
        dag = sel.getDagPath(0)
        fn_mesh = om2.MFnMesh(dag)

        points = om2.MPointArray()
        for pos in positions:
            points.append(om2.MPoint(float(pos[0]), float(pos[1]), float(pos[2])))
        fn_mesh.setPoints(points, om2.MSpace.kObject)

    def get_selected_vertex_indices(self) -> tuple[str, list[int]]:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MGlobal.getActiveSelectionList()
        if sel.length() == 0:
            raise RuntimeError("Nothing selected")

        dag, component = sel.getComponent(0)

        # Vertex selection returns the shape node; go up to the transform
        # so the name matches scene_ops.list_meshes() (full DAG path).
        if dag.node().apiType() == om2.MFn.kMesh:
            dag.pop()
        mesh_name = dag.fullPathName()

        if component.isNull():
            raise RuntimeError("No vertex component selected")

        fn_comp = om2.MFnSingleIndexedComponent(component)
        indices = list(fn_comp.getElements())
        return mesh_name, indices

    def get_world_matrix(self, mesh_name: str) -> np.ndarray:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MSelectionList()
        sel.add(mesh_name)
        dag = sel.getDagPath(0)
        matrix = dag.inclusiveMatrix()
        return np.array(
            [matrix.getElement(i, j) for i in range(4) for j in range(4)],
            dtype=np.float64,
        ).reshape(4, 4)

    def get_closest_point_on_mesh(self, mesh_name: str, point: list[float]) -> list[float]:
        from maya.api import OpenMaya as om2  # type: ignore[import]

        sel = om2.MSelectionList()
        sel.add(mesh_name)
        dag = sel.getDagPath(0)
        intersector = om2.MMeshIntersector()
        intersector.create(dag.node(), om2.MMatrix())  # object space
        result = intersector.getClosestPoint(om2.MPoint(point))
        p = result.point
        return [p.x, p.y, p.z]


class MockMayaMeshAPI:
    """Mock implementation for testing without Maya.

    Register meshes with add_mesh() before use.
    """

    def __init__(self) -> None:
        self._meshes: dict[str, dict] = {}
        self._selection: tuple[str, list[int]] | None = None

    def add_mesh(
        self,
        name: str,
        vertices: np.ndarray,
        faces: np.ndarray,
        world_matrix: np.ndarray | None = None,
    ) -> None:
        """Register a mesh for mock operations."""
        self._meshes[name] = {
            "vertices": np.array(vertices, dtype=np.float64),
            "faces": np.array(faces, dtype=np.int64),
            "world_matrix": np.array(world_matrix, dtype=np.float64) if world_matrix is not None else np.eye(4, dtype=np.float64),
        }

    def set_selection(self, mesh_name: str, vertex_indices: list[int]) -> None:
        """Set the mock vertex selection."""
        self._selection = (mesh_name, vertex_indices)

    def get_vertex_positions(self, mesh_name: str) -> np.ndarray:
        if mesh_name not in self._meshes:
            raise RuntimeError(f"Mesh '{mesh_name}' not found")
        return self._meshes[mesh_name]["vertices"].copy()

    def get_face_vertex_indices(self, mesh_name: str) -> np.ndarray:
        if mesh_name not in self._meshes:
            raise RuntimeError(f"Mesh '{mesh_name}' not found")
        return self._meshes[mesh_name]["faces"].copy()

    def set_vertex_positions(self, mesh_name: str, positions: np.ndarray) -> None:
        if mesh_name not in self._meshes:
            raise RuntimeError(f"Mesh '{mesh_name}' not found")
        self._meshes[mesh_name]["vertices"] = np.array(positions, dtype=np.float64)

    def get_selected_vertex_indices(self) -> tuple[str, list[int]]:
        if self._selection is None:
            raise RuntimeError("Nothing selected")
        return self._selection

    def get_world_matrix(self, mesh_name: str) -> np.ndarray:
        if mesh_name not in self._meshes:
            raise RuntimeError(f"Mesh '{mesh_name}' not found")
        return self._meshes[mesh_name]["world_matrix"].copy()

    def get_closest_point_on_mesh(self, mesh_name: str, point: list[float]) -> list[float]:
        if mesh_name not in self._meshes:
            raise RuntimeError(f"Mesh '{mesh_name}' not found")
        mesh_data = self._meshes[mesh_name]
        mesh = trimesh.Trimesh(
            vertices=mesh_data["vertices"],
            faces=mesh_data["faces"],
            process=False,
        )
        closest, _, _ = trimesh.proximity.closest_point(mesh, np.array([point]))
        return closest[0].tolist()


def _triangulate_faces(faces: np.ndarray) -> np.ndarray:
    """Convert quad (or n-gon) faces to triangles via fan triangulation.

    Args:
        faces: (M, K) array where K >= 3. Entries of -1 indicate padding.

    Returns:
        (T, 3) array of triangle faces.
    """
    triangles = []
    for face in faces:
        # Remove padding (-1 values)
        verts = face[face >= 0]
        n = len(verts)
        if n < 3:
            continue
        # Fan triangulation from vertex 0
        for i in range(1, n - 1):
            triangles.append([verts[0], verts[i], verts[i + 1]])
    return np.array(triangles, dtype=np.int64)


def maya_mesh_to_trimesh(
    mesh_name: str,
    api: MayaMeshAPI | None = None,
    face_indices: list[int] | None = None,
) -> trimesh.Trimesh:
    """Convert a Maya mesh to a trimesh.Trimesh.

    Args:
        mesh_name: Name of the Maya mesh shape or transform.
        api: MayaMeshAPI implementation. Defaults to OpenMayaMeshAPI().
        face_indices: Optional list of Maya face indices to extract as a submesh.
            When provided, only the specified faces are included and unreferenced
            vertices are removed.

    Returns:
        trimesh.Trimesh with triangulated faces.
    """
    if api is None:
        api = OpenMayaMeshAPI()

    vertices = api.get_vertex_positions(mesh_name)
    raw_faces = api.get_face_vertex_indices(mesh_name)

    if face_indices is not None:
        # Extract only the selected faces, then triangulate
        faces = raw_faces[face_indices]
        faces = _triangulate_faces(faces)
        # Remove unreferenced vertices and remap indices
        used = np.unique(faces)
        remap = np.full(len(vertices), -1, dtype=np.int64)
        remap[used] = np.arange(len(used))
        vertices = vertices[used]
        faces = remap[faces]
    else:
        # Full mesh path
        if raw_faces.shape[1] > 3:
            faces = _triangulate_faces(raw_faces)
        elif raw_faces.shape[1] == 3:
            # Already triangles, remove any -1 padding rows
            valid = np.all(raw_faces >= 0, axis=1)
            faces = raw_faces[valid]
        else:
            faces = raw_faces

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def trimesh_to_maya_mesh(
    mesh: trimesh.Trimesh,
    mesh_name: str,
    api: MayaMeshAPI | None = None,
) -> None:
    """Write trimesh vertex positions back to an existing Maya mesh.

    Only updates vertex positions — topology must already match.

    Args:
        mesh: Source trimesh with updated vertex positions.
        mesh_name: Name of the target Maya mesh.
        api: MayaMeshAPI implementation. Defaults to OpenMayaMeshAPI().
    """
    if api is None:
        api = OpenMayaMeshAPI()

    api.set_vertex_positions(mesh_name, mesh.vertices)
