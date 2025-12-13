"""
mesh_io.py - Fast mesh data I/O

Optimized mesh data retrieval from Maya API.
Avoids traditional Python loops by using batch retrieval and numpy conversion.
"""

from typing import Union

import maya.api.OpenMaya as om
import maya.cmds as cmds
import numpy as np
import scipy.sparse as sp


def _get_dag_path(node: Union[str, om.MDagPath]) -> om.MDagPath:
    """Get MDagPath from node name.

    Args:
        node: Node name or MDagPath.

    Returns:
        MDagPath for the node.
    """
    if isinstance(node, om.MDagPath):
        return node

    sel = om.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)


def _get_mfn_mesh(node: Union[str, om.MDagPath, om.MFnMesh]) -> om.MFnMesh:
    """Get MFnMesh from node.

    Args:
        node: Node name, MDagPath, or MFnMesh.

    Returns:
        MFnMesh for the node.
    """
    if isinstance(node, om.MFnMesh):
        return node

    dag_path = _get_dag_path(node)
    return om.MFnMesh(dag_path)


def _get_shape_node(node: str) -> str:
    """Get shape node from transform node.

    Args:
        node: Transform or shape node name.

    Returns:
        Shape node name.

    Raises:
        ValueError: If no mesh shape is found.
    """
    if cmds.objectType(node) == "mesh":
        return node

    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True)
    if shapes:
        return shapes[0]

    raise ValueError(f"No mesh shape found for: {node}")


def get_mesh_data(mesh: Union[str, om.MFnMesh], world_space: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Get vertex positions and normals from mesh quickly.

    Args:
        mesh: Mesh node name or MFnMesh.
        world_space: Whether to get coordinates in world space.

    Returns:
        Tuple of (vertices, normals) where:
            - vertices: (N, 3) float32 array of vertex positions.
            - normals: (N, 3) float32 array of vertex normals.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    space = om.MSpace.kWorld if world_space else om.MSpace.kObject

    # Get vertex positions in batch
    points = mesh.getPoints(space)
    num_verts = len(points)

    # MPointArray -> numpy (fast conversion)
    # Maya 2020+: MPointArray is directly iterable
    vertices = np.empty((num_verts, 3), dtype=np.float32)
    for i, p in enumerate(points):
        vertices[i] = (p.x, p.y, p.z)

    # Get normals in batch
    # getVertexNormals returns all vertex normals at once (Maya 2018+)
    normals = np.empty((num_verts, 3), dtype=np.float32)
    for i in range(num_verts):
        n = mesh.getVertexNormal(i, True, space)  # True = angleWeighted
        normals[i] = (n.x, n.y, n.z)

    return vertices, normals


def get_mesh_data_fast(mesh: Union[str, om.MFnMesh], world_space: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Ultra-fast mesh data retrieval (Maya 2022+ recommended).

    Uses MFnMesh.getPoints() and getFloatVectorArray to minimize Python loops.

    Args:
        mesh: Mesh node name or MFnMesh.
        world_space: Whether to get coordinates in world space.

    Returns:
        Tuple of (vertices, normals) where:
            - vertices: (N, 3) float32 array of vertex positions.
            - normals: (N, 3) float32 array of vertex normals.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    space = om.MSpace.kWorld if world_space else om.MSpace.kObject
    num_verts = mesh.numVertices

    # Vertex positions
    points = mesh.getPoints(space)
    vertices = np.array([[p.x, p.y, p.z] for p in points], dtype=np.float32)

    # Normals - Get as MFloatVectorArray
    normal_array = mesh.getVertexNormals(True, space)  # angleWeighted=True
    normals = np.array([[n.x, n.y, n.z] for n in normal_array], dtype=np.float32)

    # Normal array size may differ from vertex count (split normals)
    # In that case, recalculate per vertex
    if len(normals) != num_verts:
        normals = np.empty((num_verts, 3), dtype=np.float32)
        for i in range(num_verts):
            n = mesh.getVertexNormal(i, True, space)
            normals[i] = (n.x, n.y, n.z)

    return vertices, normals


def get_triangles(mesh: Union[str, om.MFnMesh]) -> np.ndarray:
    """Get triangle indices from mesh.

    Args:
        mesh: Mesh node name or MFnMesh.

    Returns:
        (F, 3) int64 array of triangle vertex indices.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    # Count triangles
    tri_counts = []

    face_iter = om.MItMeshPolygon(mesh.dagPath())
    while not face_iter.isDone():
        tri_counts.append(face_iter.numTriangles())
        face_iter.next()

    total_tris = sum(tri_counts)
    triangles = np.empty((total_tris, 3), dtype=np.int64)

    # Collect triangle indices
    face_iter.reset()
    tri_idx = 0
    while not face_iter.isDone():
        num_tris = face_iter.numTriangles()
        for i in range(num_tris):
            points, indices = face_iter.getTriangle(i)
            triangles[tri_idx] = indices
            tri_idx += 1
        face_iter.next()

    return triangles


def get_triangles_fast(mesh: Union[str, om.MFnMesh]) -> np.ndarray:
    """Fast triangle index retrieval using MFnMesh.getTriangles() (Maya 2018+).

    Args:
        mesh: Mesh node name or MFnMesh.

    Returns:
        (F, 3) int64 array of triangle vertex indices.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    # getTriangles returns (vertex count array, vertex index array)
    tri_counts, tri_verts = mesh.getTriangles()

    # Reshape flat array to (N, 3)
    triangles = np.array(tri_verts, dtype=np.int64).reshape(-1, 3)

    return triangles


def get_adjacency_matrix(mesh: Union[str, om.MFnMesh]) -> sp.csr_matrix:
    """Get mesh adjacency matrix in sparse format.

    Args:
        mesh: Mesh node name or MFnMesh.

    Returns:
        (N, N) sparse CSR matrix representing vertex adjacency.
    """
    if isinstance(mesh, str):
        mesh_name = _get_shape_node(mesh)
        mesh = _get_mfn_mesh(mesh_name)
    else:
        mesh_name = mesh.name()

    num_verts = mesh.numVertices

    # Get edge data
    rows = []
    cols = []

    edge_iter = om.MItMeshEdge(mesh.dagPath())
    while not edge_iter.isDone():
        v0 = edge_iter.vertexId(0)
        v1 = edge_iter.vertexId(1)
        rows.extend([v0, v1])
        cols.extend([v1, v0])
        edge_iter.next()

    # Build sparse matrix
    data = np.ones(len(rows), dtype=np.float32)
    adjacency = sp.csr_matrix((data, (rows, cols)), shape=(num_verts, num_verts))

    return adjacency


def get_adjacency_list(mesh: Union[str, om.MFnMesh]) -> list[list[int]]:
    """Get mesh adjacency list.

    Args:
        mesh: Mesh node name or MFnMesh.

    Returns:
        List of adjacent vertex indices for each vertex.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    num_verts = mesh.numVertices
    adj_list = [[] for _ in range(num_verts)]

    edge_iter = om.MItMeshEdge(mesh.dagPath())
    while not edge_iter.isDone():
        v0 = edge_iter.vertexId(0)
        v1 = edge_iter.vertexId(1)
        adj_list[v0].append(v1)
        adj_list[v1].append(v0)
        edge_iter.next()

    return adj_list


def get_bounding_box_diagonal(mesh: Union[str, om.MFnMesh]) -> float:
    """Get mesh bounding box diagonal length.

    Args:
        mesh: Mesh node name or MFnMesh.

    Returns:
        Bounding box diagonal length.
    """
    if isinstance(mesh, str):
        mesh = _get_mfn_mesh(_get_shape_node(mesh))

    bbox = mesh.boundingBox
    diagonal = (bbox.max - bbox.min).length()

    return diagonal


def get_closest_points_on_mesh(
    source_mesh: Union[str, om.MFnMesh], target_points: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Get closest points on source mesh from target point cloud.

    Args:
        source_mesh: Source mesh node name or MFnMesh.
        target_points: (N, 3) array of target point coordinates.

    Returns:
        Tuple of (closest_points, closest_normals, face_indices, distances_sq) where:
            - closest_points: (N, 3) float32 array of closest point coordinates.
            - closest_normals: (N, 3) float32 array of normals at closest points.
            - face_indices: (N,) int64 array of face indices.
            - distances_sq: (N,) float32 array of squared distances.
    """
    if isinstance(source_mesh, str):
        source_mesh = _get_mfn_mesh(_get_shape_node(source_mesh))

    num_points = len(target_points)
    closest_points = np.empty((num_points, 3), dtype=np.float32)
    closest_normals = np.empty((num_points, 3), dtype=np.float32)
    face_indices = np.empty(num_points, dtype=np.int64)
    distances_sq = np.empty(num_points, dtype=np.float32)

    # Use MMeshIntersector (fast)
    intersector = om.MMeshIntersector()
    intersector.create(source_mesh.object(), om.MMatrix.kIdentity)

    for i in range(num_points):
        point = om.MPoint(target_points[i])
        result = intersector.getClosestPoint(point)

        # API 2.0: MPointOnMesh uses property access
        # result.point returns MFloatPoint, so convert to MPoint
        cp_float = result.point
        cp = om.MPoint(cp_float.x, cp_float.y, cp_float.z)
        cn = result.normal

        closest_points[i] = (cp.x, cp.y, cp.z)
        closest_normals[i] = (cn.x, cn.y, cn.z)
        face_indices[i] = result.face
        distances_sq[i] = (point - cp).length() ** 2

    return closest_points, closest_normals, face_indices, distances_sq


def get_closest_points_kdtree(source_verts: np.ndarray, target_points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fast nearest neighbor search using KDTree (vertex-based).

    Note:
        This is vertex-to-vertex nearest neighbor search,
        not closest point on mesh surface.

    Args:
        source_verts: (M, 3) array of source vertex positions.
        target_points: (N, 3) array of target point coordinates.

    Returns:
        Tuple of (distances, indices) where:
            - distances: (N,) array of distances to nearest vertices.
            - indices: (N,) array of nearest source vertex indices.
    """
    from scipy.spatial import cKDTree

    tree = cKDTree(source_verts)
    distances, indices = tree.query(target_points)

    return distances, indices


def get_barycentric_coords(mesh: om.MFnMesh, face_index: int, point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Calculate barycentric coordinates for a point on a face.

    Args:
        mesh: MFnMesh object.
        face_index: Index of the face.
        point: (3,) array of point coordinates.

    Returns:
        Tuple of (bary_coords, vert_indices) where:
            - bary_coords: (3,) float32 array of barycentric coordinates.
            - vert_indices: (3,) int64 array of triangle vertex indices.
    """
    face_iter = om.MItMeshPolygon(mesh.dagPath())
    # API 2.0: setIndex takes (index,) and returns previous index
    face_iter.setIndex(face_index)

    # Triangulate and find closest triangle
    num_tris = face_iter.numTriangles()

    for i in range(num_tris):
        tri_points, tri_indices = face_iter.getTriangle(i)

        # Calculate barycentric coordinates
        v0 = np.array([tri_points[0].x, tri_points[0].y, tri_points[0].z])
        v1 = np.array([tri_points[1].x, tri_points[1].y, tri_points[1].z])
        v2 = np.array([tri_points[2].x, tri_points[2].y, tri_points[2].z])
        p = np.array(point)

        # Barycentric coordinate calculation
        v0v1 = v1 - v0
        v0v2 = v2 - v0
        v0p = p - v0

        d00 = np.dot(v0v1, v0v1)
        d01 = np.dot(v0v1, v0v2)
        d11 = np.dot(v0v2, v0v2)
        d20 = np.dot(v0p, v0v1)
        d21 = np.dot(v0p, v0v2)

        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-10:
            continue

        v = (d11 * d20 - d01 * d21) / denom
        w = (d00 * d21 - d01 * d20) / denom
        u = 1.0 - v - w

        bary = np.array([u, v, w], dtype=np.float32)

        # Check if inside this triangle
        if u >= -0.01 and v >= -0.01 and w >= -0.01:
            return bary, np.array(tri_indices, dtype=np.int64)

    # Fallback: use first triangle
    tri_points, tri_indices = face_iter.getTriangle(0)
    return np.array([1.0 / 3, 1.0 / 3, 1.0 / 3], dtype=np.float32), np.array(tri_indices, dtype=np.int64)
