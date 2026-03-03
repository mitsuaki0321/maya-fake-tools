"""Separate mesh by skin weights - assign each face to its dominant joint."""

from logging import getLogger
from typing import Optional

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds

from ....lib.lib_selection import get_shapes

logger = getLogger(__name__)


def get_weights_per_vertex(skin_cluster: str) -> tuple[list[str], list[list[float]]]:
    """Get all vertex weights via MFnSkinCluster.getWeights().

    Args:
        skin_cluster (str): SkinCluster node name.

    Returns:
        tuple[list[str], list[list[float]]]: (influences, weights).
            influences is a list of influence names.
            weights[vtx_idx][inf_idx] is the weight value.
    """
    sel = om.MSelectionList()
    sel.add(skin_cluster)
    sc_obj = sel.getDependNode(0)
    sc_fn = oma.MFnSkinCluster(sc_obj)

    # Get influence names
    inf_dag_array = sc_fn.influenceObjects()
    influences = [inf_dag_array[i].partialPathName() for i in range(len(inf_dag_array))]
    num_influences = len(influences)

    # Get geometry
    geo_dag = sc_fn.getPathAtIndex(0)
    mesh_fn = om.MFnMesh(geo_dag)
    num_vertices = mesh_fn.numVertices

    # Get all weights at once
    single_comp = om.MFnSingleIndexedComponent()
    vtx_comp = single_comp.create(om.MFn.kMeshVertComponent)
    single_comp.setCompleteData(num_vertices)

    flat_weights, _ = sc_fn.getWeights(geo_dag, vtx_comp)

    # Reshape flat array into per-vertex lists
    weights: list[list[float]] = []
    for vtx_idx in range(num_vertices):
        offset = vtx_idx * num_influences
        vtx_weights = [flat_weights[offset + i] for i in range(num_influences)]
        weights.append(vtx_weights)

    return influences, weights


def _get_hierarchy_depth(joint: str) -> int:
    """Return the DAG hierarchy depth of a joint (0 = root)."""
    full_path = cmds.ls(joint, long=True)[0]
    return full_path.count("|") - 1


def _get_joint_position(joint: str) -> om.MPoint:
    """Return the world-space position of a joint as an MPoint."""
    pos = cmds.xform(joint, query=True, worldSpace=True, translation=True)
    return om.MPoint(pos[0], pos[1], pos[2])


def assign_faces_to_joints(
    mesh: str,
    influences: list[str],
    weights: list[list[float]],
    target_joints: Optional[list[str]] = None,
) -> dict[str, list[int]]:
    """Assign each face to its dominant joint based on vertex weights.

    For each face, sums the weights of its vertices per influence and
    assigns the face to the influence with the highest total weight.

    When multiple joints share the exact same weight for a face, ties are
    broken by: (1) shallower hierarchy depth wins, (2) closer distance
    from the face centroid to the joint position wins.

    Args:
        mesh (str): Mesh transform or shape name.
        influences (list[str]): Influence joint names from get_weights_per_vertex.
        weights (list[list[float]]): Per-vertex weight data from get_weights_per_vertex.
        target_joints (Optional[list[str]]): If specified, only assign faces to these joints.
            Faces dominated by unlisted joints are assigned to the nearest listed joint
            by weight contribution.

    Returns:
        dict[str, list[int]]: {joint_name: [face_indices]}.
    """
    shapes = get_shapes([mesh], shape_type="mesh")
    if not shapes:
        return {}

    shape = shapes[0]
    sel = om.MSelectionList()
    sel.add(shape)
    mesh_dag = sel.getDagPath(0)

    num_influences = len(influences)

    # Build index set for target joints
    if target_joints is not None:
        target_set = set(target_joints)
        target_indices = [i for i, inf in enumerate(influences) if inf in target_set]
        if not target_indices:
            logger.warning("None of the target joints are influences on this skin cluster")
            return {}
    else:
        target_indices = list(range(num_influences))

    # Pre-compute hierarchy depths and positions for tiebreaking (lazy)
    depth_cache: dict[int, int] = {}
    pos_cache: dict[int, om.MPoint] = {}

    def _get_depth(inf_idx: int) -> int:
        if inf_idx not in depth_cache:
            depth_cache[inf_idx] = _get_hierarchy_depth(influences[inf_idx])
        return depth_cache[inf_idx]

    def _get_pos(inf_idx: int) -> om.MPoint:
        if inf_idx not in pos_cache:
            pos_cache[inf_idx] = _get_joint_position(influences[inf_idx])
        return pos_cache[inf_idx]

    result: dict[str, list[int]] = {}
    tie_count = 0

    face_it = om.MItMeshPolygon(mesh_dag)
    while not face_it.isDone():
        face_idx = face_it.index()
        vert_indices = face_it.getVertices()

        # Sum weights per influence for this face's vertices
        face_weights = [0.0] * num_influences
        for vid in vert_indices:
            for i in range(num_influences):
                face_weights[i] += weights[vid][i]

        # Find dominant joint among target joints
        best_inf_idx = target_indices[0]
        best_weight = face_weights[target_indices[0]]
        for inf_idx in target_indices[1:]:
            w = face_weights[inf_idx]
            if w > best_weight:
                best_weight = w
                best_inf_idx = inf_idx
            elif w == best_weight:
                # Tiebreak 1: shallower hierarchy wins
                depth_new = _get_depth(inf_idx)
                depth_cur = _get_depth(best_inf_idx)
                if depth_new < depth_cur:
                    best_inf_idx = inf_idx
                elif depth_new == depth_cur:
                    # Tiebreak 2: closer distance to face centroid wins
                    centroid = face_it.center(om.MSpace.kWorld)
                    dist_new = centroid.distanceTo(_get_pos(inf_idx))
                    dist_cur = centroid.distanceTo(_get_pos(best_inf_idx))
                    if dist_new < dist_cur:
                        best_inf_idx = inf_idx
                tie_count += 1

        joint_name = influences[best_inf_idx]
        if joint_name not in result:
            result[joint_name] = []
        result[joint_name].append(face_idx)

        face_it.next()

    if tie_count:
        logger.debug("Resolved %d weight ties by hierarchy depth / distance", tie_count)

    return result


def extract_faces_as_mesh(mesh: str, face_indices: list[int], name: str) -> str:
    """Duplicate a mesh and keep only the specified faces.

    Args:
        mesh (str): Source mesh transform name.
        face_indices (list[int]): Face indices to keep.
        name (str): Name for the new mesh.

    Returns:
        str: New mesh transform name.
    """
    dup = cmds.duplicate(mesh, name=name)[0]

    # Get total face count from the duplicate
    shapes = get_shapes([dup], shape_type="mesh")
    if not shapes:
        raise RuntimeError(f"Duplicated mesh '{dup}' has no mesh shape")

    total_faces = cmds.polyEvaluate(dup, face=True)
    keep_set = set(face_indices)

    # Build list of faces to delete (faces NOT in face_indices)
    delete_faces = [f"{dup}.f[{i}]" for i in range(total_faces) if i not in keep_set]

    if delete_faces:
        cmds.delete(delete_faces)

    # Clean up: delete history
    cmds.delete(dup, constructionHistory=True)

    return dup
