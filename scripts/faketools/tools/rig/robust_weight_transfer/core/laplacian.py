"""
laplacian.py - Laplacian matrix computation

Wrapper for robust_laplacian library with
manual implementation fallback.
"""

from logging import getLogger

import numpy as np
import scipy.sparse as sp

logger = getLogger(__name__)

# Try to import robust_laplacian
_HAS_ROBUST_LAPLACIAN = False
try:
    import robust_laplacian

    _HAS_ROBUST_LAPLACIAN = True
    logger.debug("robust_laplacian library is available")
except ImportError:
    logger.debug("robust_laplacian library not available, using manual implementation")


def compute_laplacian(vertices: np.ndarray, triangles: np.ndarray, use_point_cloud: bool = False) -> tuple[sp.csr_matrix, sp.dia_matrix]:
    """Compute Laplacian matrix and mass matrix.

    Args:
        vertices: (N, 3) array of vertex coordinates.
        triangles: (F, 3) array of triangle vertex indices.
        use_point_cloud: Whether to use Point Cloud Laplacian instead of mesh Laplacian.

    Returns:
        Tuple of (L, M) where:
            - L: (N, N) sparse CSR Laplacian matrix.
            - M: (N, N) sparse diagonal mass matrix.
    """
    if _HAS_ROBUST_LAPLACIAN:
        return _compute_laplacian_robust(vertices, triangles, use_point_cloud)
    else:
        return _compute_laplacian_manual(vertices, triangles)


def _compute_laplacian_robust(vertices: np.ndarray, triangles: np.ndarray, use_point_cloud: bool = False) -> tuple[sp.csr_matrix, sp.dia_matrix]:
    """Compute Laplacian using robust_laplacian library (fast).

    Args:
        vertices: (N, 3) array of vertex coordinates.
        triangles: (F, 3) array of triangle vertex indices.
        use_point_cloud: Whether to use Point Cloud Laplacian.

    Returns:
        Tuple of (L, M) where:
            - L: (N, N) sparse CSR Laplacian matrix.
            - M: (N, N) sparse diagonal mass matrix.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int64)

    if use_point_cloud:
        L, M = robust_laplacian.point_cloud_laplacian(vertices)
    else:
        L, M = robust_laplacian.mesh_laplacian(vertices, triangles)

    # robust_laplacian and igl may have opposite signs, so adjust
    # To match the paper's formula: Q = -L + L @ M^-1 @ L
    # robust_laplacian typically returns -L, so flip the sign
    L = -L

    return L.tocsr(), M


def _compute_laplacian_manual(vertices: np.ndarray, triangles: np.ndarray) -> tuple[sp.csr_matrix, sp.dia_matrix]:
    """Manual cotangent Laplacian computation (fallback).

    Used when robust_laplacian library is not available.

    Args:
        vertices: (N, 3) array of vertex coordinates.
        triangles: (F, 3) array of triangle vertex indices.

    Returns:
        Tuple of (L, M) where:
            - L: (N, N) sparse CSR Laplacian matrix.
            - M: (N, N) sparse diagonal mass matrix.
    """
    num_verts = len(vertices)

    # Build using lil_matrix (fast insertion)
    L = sp.lil_matrix((num_verts, num_verts), dtype=np.float64)
    areas = np.zeros(num_verts, dtype=np.float64)

    for tri in triangles:
        i0, i1, i2 = tri

        v0 = vertices[i0]
        v1 = vertices[i1]
        v2 = vertices[i2]

        # Compute cotangent weights
        cot0 = _cotangent(v1, v0, v2)  # Angle at vertex 0
        cot1 = _cotangent(v0, v1, v2)  # Angle at vertex 1
        cot2 = _cotangent(v0, v2, v1)  # Angle at vertex 2

        # Add to Laplacian matrix
        # Edge (i0, i1) weight = cot2
        L[i0, i1] += cot2
        L[i1, i0] += cot2
        L[i0, i0] -= cot2
        L[i1, i1] -= cot2

        # Edge (i1, i2) weight = cot0
        L[i1, i2] += cot0
        L[i2, i1] += cot0
        L[i1, i1] -= cot0
        L[i2, i2] -= cot0

        # Edge (i2, i0) weight = cot1
        L[i2, i0] += cot1
        L[i0, i2] += cot1
        L[i2, i2] -= cot1
        L[i0, i0] -= cot1

        # Compute area and add to each vertex
        area = _triangle_area(v0, v1, v2)
        areas[i0] += area / 3.0
        areas[i1] += area / 3.0
        areas[i2] += area / 3.0

    # Convert to CSR format (fast operations)
    L = L.tocsr()

    # Mass matrix (diagonal)
    M = sp.diags(areas)

    return L, M


def _cotangent(v1: np.ndarray, v_center: np.ndarray, v2: np.ndarray) -> float:
    """Compute cotangent of angle at v_center.

    Args:
        v1: First adjacent vertex position.
        v_center: Center vertex position (angle vertex).
        v2: Second adjacent vertex position.

    Returns:
        Cotangent of the angle at v_center.
    """
    e1 = v1 - v_center
    e2 = v2 - v_center

    # cos(theta) = (e1 . e2) / (|e1| * |e2|)
    # sin(theta) = |e1 x e2| / (|e1| * |e2|)
    # cot(theta) = cos(theta) / sin(theta) = (e1 . e2) / |e1 x e2|

    cross = np.cross(e1, e2)
    cross_norm = np.linalg.norm(cross)

    if cross_norm < 1e-10:
        return 0.0

    dot = np.dot(e1, e2)
    return dot / cross_norm


def _triangle_area(v0: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute triangle area using cross product.

    Args:
        v0: First vertex position.
        v1: Second vertex position.
        v2: Third vertex position.

    Returns:
        Area of the triangle.
    """
    cross = np.cross(v1 - v0, v2 - v0)
    return 0.5 * np.linalg.norm(cross)


def compute_system_matrix(L: sp.spmatrix, M: sp.spmatrix) -> sp.csr_matrix:
    """Compute system matrix Q from paper.

    Computes Q = -L + L @ M^-1 @ L as described in the paper.

    Args:
        L: Laplacian matrix.
        M: Mass matrix (diagonal).

    Returns:
        System matrix Q in sparse CSR format.
    """
    # Inverse of M (diagonal, so just reciprocal of diagonal elements)
    M_diag = M.diagonal()
    M_diag_safe = np.where(np.abs(M_diag) < 1e-10, 1e-10, M_diag)
    Minv = sp.diags(1.0 / M_diag_safe)

    # Q = -L + L @ Minv @ L
    Q = -L + L @ Minv @ L

    return Q.tocsr()


def is_laplacian_valid(L: sp.spmatrix) -> bool:
    """Check validity of Laplacian matrix.

    Args:
        L: Laplacian matrix to validate.

    Returns:
        True if the matrix is valid (sparse, no NaN or Inf values).
    """
    if not sp.issparse(L):
        return False

    # Check for NaN or Inf
    data = L.tocsr().data
    return not (np.any(np.isnan(data)) or np.any(np.isinf(data)))
