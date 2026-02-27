"""Mesh Cutter utility functions."""

import contextlib
from logging import getLogger
import re

import maya.api.OpenMaya as om
import maya.cmds as cmds

logger = getLogger(__name__)

_EDGE_INDEX_RE = re.compile(r"\[(\d+)\]")


def get_dag_path(node_name: str) -> om.MDagPath:
    """Get an MDagPath from a node name, extending to its shape node."""
    sel = om.MSelectionList()
    sel.add(node_name)
    dag = sel.getDagPath(0)
    with contextlib.suppress(RuntimeError):
        dag.extendToShape()
    return dag


def filter_cut_line_edges(
    mesh_name: str,
    verts_before: int,
) -> list[int]:
    """Return only cut-line edges among newly created edges.

    After polySplit/polyCut, new edges include both:
    - Cut-line edges connecting two new vertices (the actual cut)
    - Subdivision edges from splitting original edges (one old, one new vertex)

    Uses polyListComponentConversion with internal=True to select only
    edges where both endpoints are new vertices.

    Args:
        mesh_name (str): Polygon mesh node name.
        verts_before (int): Vertex count before cut operations.

    Returns:
        list[int]: Cut-line edge indices.
    """
    verts_after = om.MFnMesh(get_dag_path(mesh_name)).numVertices
    if verts_after <= verts_before:
        return []

    new_verts = cmds.ls(f"{mesh_name}.vtx[{verts_before}:{verts_after - 1}]", fl=True)
    if not new_verts:
        return []

    raw = cmds.polyListComponentConversion(new_verts, fromVertex=True, toEdge=True, internal=True)
    inner_edges = cmds.ls(raw, fl=True) if raw else []

    result = [int(m.group(1)) for e in inner_edges if (m := _EDGE_INDEX_RE.search(e))]
    logger.debug(
        "filter_cut_line_edges: %d new verts, %d cut-line edges",
        verts_after - verts_before,
        len(result),
    )
    return result
