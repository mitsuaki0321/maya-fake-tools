"""Cut a target mesh using each face of a driver mesh as a cut plane via polyCut."""

from logging import getLogger
from math import degrees, pi

import maya.api.OpenMaya as om
import maya.cmds as cmds

from .utility import filter_cut_line_edges, get_dag_path

logger = getLogger(__name__)

# Default normal direction when cutPlaneRotate=(0,0,0).
POLYCUT_DEFAULT_NORMAL = om.MVector(0, 0, 1)

_HALF_PI = pi / 2

# If any target vertex is closer than this to the cut plane, nudge the plane.
_PLANE_COINCIDENCE_THRESHOLD = 1e-4

# Per-attempt offset when nudging (multiplied by attempt number).
_PLANE_NUDGE_STEP = 2e-4

# Maximum nudge attempts before giving up.
_MAX_NUDGE_ATTEMPTS = 5

# (face_center, face_normal, ordered_face_vertices)
_FaceData = tuple[om.MPoint, om.MVector, list[om.MPoint]]


def cut(cutter_name: str, target_name: str) -> list[int]:
    """Cut target mesh using each cutter face as a cut plane.

    For each driver face:
      1. polyCut all target faces (f[*])
      2. Remove excess cut lines outside the driver face boundary

    Args:
        cutter_name (str): Node name of the driver polygon mesh (cut planes).
        target_name (str): Node name of the target polygon mesh to be cut.

    Returns:
        list[int]: New edge indices created by the cut.
    """
    logger.debug("start: driver=%s, target=%s", cutter_name, target_name)

    verts_before = om.MFnMesh(get_dag_path(target_name)).numVertices

    driver_faces = _get_driver_faces(cutter_name)
    logger.debug("driver faces: %d", len(driver_faces))

    cut_count = 0
    for fi, (center, normal, vertices) in enumerate(driver_faces):
        if normal.length() < 1e-10:
            logger.debug("  face %d: degenerate normal, skip", fi)
            continue

        # Nudge cut plane if it coincides with any target vertex
        target_points = om.MFnMesh(get_dag_path(target_name)).getPoints(om.MSpace.kWorld)
        center = _nudge_cut_plane(center, normal, target_points)

        euler = _normal_to_euler(normal)
        logger.debug(
            "  face %d: cutting all target faces, center=(%.3f,%.3f,%.3f), euler=(%.1f,%.1f,%.1f)",
            fi,
            center.x,
            center.y,
            center.z,
            euler[0],
            euler[1],
            euler[2],
        )

        before_vtx_count = _vertex_count(target_name)
        cmds.polyCut(
            f"{target_name}.f[*]",
            ch=False,
            ef=False,
            cutPlaneCenter=(center.x, center.y, center.z),
            cutPlaneRotate=euler,
            extractOffset=(0.0, 0.0, 0.0),
            worldSpace=True,
        )
        after_vtx_count = _vertex_count(target_name)

        # Remove excess cuts outside driver face boundary
        if before_vtx_count != after_vtx_count:
            new_vtxs = (
                cmds.ls(
                    f"{target_name}.vtx[{before_vtx_count}:{after_vtx_count - 1}]",
                    fl=True,
                )
                or []
            )
            _remove_excess_cuts(target_name, new_vtxs, vertices, normal)

        cut_count += 1

    cut_line_edges = filter_cut_line_edges(target_name, verts_before)
    logger.debug("done: %d polyCut operations, %d cut-line edges", cut_count, len(cut_line_edges))
    return cut_line_edges


def _get_driver_faces(driver_name: str) -> list[_FaceData]:
    """Return center, normal, and ordered vertices for each driver face.

    All coordinates are fetched in object space and manually transformed
    to world space via inclusiveMatrix.

    Returns:
        list: (face center, face normal, ordered face vertices) all in world space.
    """
    dag = get_dag_path(driver_name)
    world_mat = dag.inclusiveMatrix()
    faces: list[_FaceData] = []

    face_it = om.MItMeshPolygon(dag)
    while not face_it.isDone():
        center = face_it.center(om.MSpace.kObject) * world_mat

        # Ordered face vertices in world space
        points = face_it.getPoints(om.MSpace.kObject)
        verts = [p * world_mat for p in points]

        # Compute normal from world-space vertex edges
        normal = om.MVector(0, 0, 0)
        n_pts = len(verts)
        if n_pts >= 3:
            for i in range(n_pts):
                e0 = om.MVector(verts[(i + 1) % n_pts] - verts[i])
                e1 = om.MVector(verts[(i + 2) % n_pts] - verts[(i + 1) % n_pts])
                n = e0 ^ e1
                if n.length() > 1e-10:
                    normal = n.normalize()
                    break

        faces.append((center, normal, verts))
        face_it.next()

    return faces


def _nudge_cut_plane(
    center: om.MPoint,
    normal: om.MVector,
    points: om.MPointArray,
) -> om.MPoint:
    """Offset the cut plane if any target vertex lies on it.

    Args:
        center (om.MPoint): Cut plane center (world space).
        normal (om.MVector): Cut plane normal (unit vector, world space).
        points (om.MPointArray): Target mesh vertices (world space).

    Returns:
        om.MPoint: Original or nudged center.
    """
    for attempt in range(_MAX_NUDGE_ATTEMPTS + 1):
        coincident = any(abs(om.MVector(pt - center) * normal) < _PLANE_COINCIDENCE_THRESHOLD for pt in points)
        if not coincident:
            return center

        if attempt == _MAX_NUDGE_ATTEMPTS:
            logger.warning("cut plane still coincident after %d nudge attempts", attempt)
            return center

        offset = _PLANE_NUDGE_STEP * (attempt + 1)
        center = om.MPoint(
            center.x + normal.x * offset,
            center.y + normal.y * offset,
            center.z + normal.z * offset,
        )
        logger.debug("nudged cut plane by %.6f (attempt %d)", offset, attempt + 1)

    return center


def _vertex_count(mesh_name: str) -> int:
    """Return the current vertex count of a mesh."""
    return om.MFnMesh(get_dag_path(mesh_name)).numVertices


def _remove_excess_cuts(
    target_name: str,
    new_vtxs: list[str],
    face_verts: list[om.MPoint],
    normal: om.MVector,
) -> None:
    """Remove new vertices that fall outside the driver face boundary.

    Args:
        target_name (str): Target mesh node name.
        new_vtxs (list[str]): New vertex component names.
        face_verts (list[om.MPoint]): Ordered face vertices of the driver face (world space).
        normal (om.MVector): Driver face normal (world space).
    """
    n_verts = len(face_verts)
    if n_verts < 3 or not new_vtxs:
        return

    # Build edge vectors
    edge_vecs: list[om.MVector] = [om.MVector(face_verts[i + 1] - face_verts[i]) for i in range(n_verts - 1)]
    edge_vecs.insert(0, om.MVector(face_verts[0] - face_verts[n_verts - 1]))

    # Ensure normal aligns with vertex winding
    test_normal = normal
    winding_cross = edge_vecs[0] ^ edge_vecs[1]
    if winding_cross.length() > 1e-10 and winding_cross.angle(test_normal) > _HALF_PI:
        test_normal = test_normal * -1.0

    # Find vertices outside the face boundary
    del_vtxs: list[str] = []
    for vtx in new_vtxs:
        pos = cmds.xform(vtx, q=True, ws=True, t=True)
        v_point = om.MPoint(pos[0], pos[1], pos[2])
        for i in range(n_verts):
            cross = edge_vecs[i] ^ om.MVector(v_point - face_verts[i])
            if cross.length() < 1e-10:
                continue
            if cross.angle(test_normal) > _HALF_PI:
                del_vtxs.append(vtx)
                break

    # Delete internal edges of outside vertices
    if len(del_vtxs) > 1:
        raw = cmds.polyListComponentConversion(del_vtxs, fromVertex=True, toEdge=True, internal=True)
        del_edges = cmds.ls(raw, fl=True) if raw else []
        if del_edges:
            cmds.polyDelEdge(del_edges, cv=True, ch=False)


def _normal_to_euler(normal: om.MVector) -> tuple[float, float, float]:
    """Convert a normal vector to Euler angles (degrees) for polyCut cutPlaneRotate."""
    quat = POLYCUT_DEFAULT_NORMAL.rotateTo(normal)
    euler = quat.asEulerRotation()
    return (degrees(euler.x), degrees(euler.y), degrees(euler.z))
