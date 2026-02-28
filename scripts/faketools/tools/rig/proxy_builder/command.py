"""Proxy Builder command module - public API for mesh separation."""

from logging import getLogger
import re
from typing import Optional

import maya.cmds as cmds

from ....lib.lib_selection import get_shapes
from ....lib.lib_skinCluster import get_skinCluster
from . import separate_by_plane as _plane, separate_by_weights as _weights

logger = getLogger(__name__)

# Maximum face count allowed for mesh cutters.
# Mesh-based cutting runs polyCut per driver face, so high-poly cutters
# cause very long processing times.
MAX_CUTTER_MESH_FACES = 5


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------


def _proxy_group_name(mesh: str) -> str:
    """プロキシグループの名前を生成。"""
    return f"{mesh}_proxy_grp"


def _joint_short_name(joint_name: str) -> str:
    """ジョイント名からパスとネームスペースを除去。"""
    return joint_name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def _weight_proxy_name(mesh: str, joint_name: str) -> str:
    """ウェイト方式のプロキシメッシュ名を生成。"""
    return f"{mesh}_{_joint_short_name(joint_name)}_proxy"


def _plane_proxy_name(mesh: str, index: int) -> str:
    """プレーン方式のプロキシメッシュ名を生成。"""
    return f"{mesh}_piece_{index:03d}_proxy"


# ---------------------------------------------------------------------------
# Group organisation helper
# ---------------------------------------------------------------------------


def _collect_into_group(grp: str, nodes: list[str]) -> None:
    """ノードリストをグループ配下にペアレントする。既にグループ下にあるものはスキップ。"""
    for node in nodes:
        current_parent = cmds.listRelatives(node, parent=True)
        if not current_parent or current_parent[0] != grp:
            cmds.parent(node, grp)


def _cleanup_empty_transforms(transforms: list[str]) -> None:
    """不要になったトランスフォームを削除する。

    polySeparate 後にピースを別グループへ移動すると、分離元のトランスフォームが
    シェイプも子も持たない状態で残る。この関数でそれらを掃除する。

    同名ノードとの競合を避けるため、フルパスで渡すこと。

    Args:
        transforms (list[str]): 削除対象のトランスフォーム名リスト（フルパス推奨）。
    """
    for t in transforms:
        if cmds.objExists(t):
            logger.debug("Deleting empty transform: %s", t)
            cmds.delete(t)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def separate_by_weights(
    mesh: str,
    joints: Optional[list[str]] = None,
    duplicate: bool = True,
) -> list[str]:
    """Separate a skinned mesh by dominant joint weights.

    Each face is assigned to the joint with the highest combined vertex weight.
    The mesh is then split into per-joint pieces.

    Args:
        mesh (str): Source mesh transform name.
        joints (Optional[list[str]]): Joints to separate by. None uses all influences.
        duplicate (bool): If True, keep the original mesh intact.

    Returns:
        list[str]: Proxy mesh transform names.

    Raises:
        ValueError: If the mesh does not exist, has no mesh shape, or has no skinCluster.
    """
    _validate_mesh(mesh)

    shapes = get_shapes([mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{mesh}' has no mesh shape")

    skin_cluster = get_skinCluster(shapes[0])
    if not skin_cluster:
        raise ValueError(f"'{mesh}' has no skinCluster")

    logger.info("Separating '%s' by skin weights (skinCluster: %s)", mesh, skin_cluster)

    # Get weight data
    influences, weights = _weights.get_weights_per_vertex(skin_cluster)

    # Validate target joints
    if joints is not None:
        influence_set = set(influences)
        missing = [j for j in joints if j not in influence_set]
        if missing:
            logger.warning("Joints not found as influences: %s", missing)
        joints = [j for j in joints if j in influence_set]
        if not joints:
            raise ValueError("None of the specified joints are influences on this mesh")

    # Assign faces to joints
    face_map = _weights.assign_faces_to_joints(mesh, influences, weights, target_joints=joints)
    if not face_map:
        raise ValueError(f"No faces could be assigned for '{mesh}'")

    logger.info("Face assignment: %s", {j: len(faces) for j, faces in face_map.items()})

    # Create proxy group
    grp = _get_or_create_group(_proxy_group_name(mesh))

    # Extract per-joint meshes
    results: list[str] = []
    for joint_name, face_indices in face_map.items():
        proxy_name = _weight_proxy_name(mesh, joint_name)
        proxy_mesh = _weights.extract_faces_as_mesh(mesh, face_indices, proxy_name)
        results.append(proxy_mesh)
        logger.debug("Created proxy: %s (%d faces)", proxy_mesh, len(face_indices))

    _collect_into_group(grp, results)

    # Delete original if not duplicating
    if not duplicate:
        cmds.delete(mesh)

    logger.info("Created %d proxy meshes in '%s'", len(results), grp)
    return results


def separate_by_planes(
    mesh: str,
    cutters: list[str],
    duplicate: bool = True,
) -> list[str]:
    """Separate a mesh by cutting it with surface objects.

    Supports both NURBS surfaces and polygon meshes as cutters.

    Args:
        mesh (str): Source mesh transform name.
        cutters (list[str]): Cutter surface node names.
        duplicate (bool): If True, keep the original mesh intact.

    Returns:
        list[str]: Separated mesh transform names.

    Raises:
        ValueError: If the mesh or cutters do not exist or are invalid.
    """
    _validate_mesh(mesh)

    if not cutters:
        raise ValueError("No cutter surfaces provided")

    for cutter in cutters:
        if not cmds.objExists(cutter):
            raise ValueError(f"Cutter '{cutter}' does not exist")
        _validate_cutter_face_count(cutter)

    logger.info("Separating '%s' by %d cutting planes", mesh, len(cutters))

    pieces = _plane.cut_and_separate(mesh, cutters, duplicate=duplicate)

    # Record parent transforms before re-parenting (polySeparate leaves
    # an empty parent transform once all children are moved out).
    parent_candidates: set[str] = set()
    for piece in pieces:
        if cmds.objExists(piece):
            parent = cmds.listRelatives(piece, parent=True, fullPath=True)
            if parent:
                parent_candidates.add(parent[0])

    # Organize results into a group
    grp = _get_or_create_group(_proxy_group_name(mesh))
    start_index = _next_piece_index(grp, f"{mesh}_piece_")
    results: list[str] = []
    for i, piece in enumerate(pieces):
        if cmds.objExists(piece):
            piece = cmds.rename(piece, _plane_proxy_name(mesh, start_index + i))
            results.append(piece)

    _collect_into_group(grp, results)

    # Clean up empty transforms left behind by polySeparate
    _cleanup_empty_transforms(list(parent_candidates - {grp}))

    logger.info("Created %d pieces in '%s'", len(results), grp)
    return results


def separate_meshes_by_weights(
    meshes: list[str],
    joints: Optional[list[str]] = None,
    duplicate: bool = True,
    group: str = "proxy_grp",
) -> list[str]:
    """Separate multiple skinned meshes by dominant joint weights.

    Loops over each mesh and calls ``separate_by_weights``.
    All per-mesh proxy groups are collected under a single parent group.

    Args:
        meshes (list[str]): Source mesh transform names.
        joints (Optional[list[str]]): Joints to separate by. None uses all influences.
        duplicate (bool): If True, keep the original meshes intact.
        group (str): Parent group name for all per-mesh proxy groups.

    Returns:
        list[str]: All proxy mesh transform names (flat list).

    Raises:
        ValueError: If *meshes* is empty, or any individual mesh fails validation.
    """
    if not meshes:
        raise ValueError("No meshes provided")
    results: list[str] = []
    mesh_groups: list[str] = []
    for mesh in meshes:
        results.extend(separate_by_weights(mesh=mesh, joints=joints, duplicate=duplicate))
        grp_name = _proxy_group_name(mesh)
        if cmds.objExists(grp_name):
            mesh_groups.append(grp_name)
    parent_grp = _get_or_create_group(group)
    _collect_into_group(parent_grp, mesh_groups)
    logger.info("Separated %d meshes into %d total proxies (by weights) in '%s'", len(meshes), len(results), parent_grp)
    return results


def separate_meshes_by_planes(
    meshes: list[str],
    cutters: list[str],
    duplicate: bool = True,
    group: str = "proxy_grp",
) -> list[str]:
    """Separate multiple meshes by cutting planes.

    Loops over each mesh and calls ``separate_by_planes``.
    All per-mesh proxy groups are collected under a single parent group.

    Args:
        meshes (list[str]): Source mesh transform names.
        cutters (list[str]): Cutter surface node names.
        duplicate (bool): If True, keep the original meshes intact.
        group (str): Parent group name for all per-mesh proxy groups.

    Returns:
        list[str]: All separated mesh transform names (flat list).

    Raises:
        ValueError: If *meshes* is empty, or any individual mesh fails validation.
    """
    if not meshes:
        raise ValueError("No meshes provided")
    results: list[str] = []
    mesh_groups: list[str] = []
    for mesh in meshes:
        results.extend(separate_by_planes(mesh=mesh, cutters=cutters, duplicate=duplicate))
        grp_name = _proxy_group_name(mesh)
        if cmds.objExists(grp_name):
            mesh_groups.append(grp_name)
    parent_grp = _get_or_create_group(group)
    _collect_into_group(parent_grp, mesh_groups)
    logger.info("Separated %d meshes into %d total pieces (by planes) in '%s'", len(meshes), len(results), parent_grp)
    return results


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_mesh(mesh: str) -> None:
    """Validate that a mesh transform exists and has a mesh shape.

    Args:
        mesh (str): Node name to validate.

    Raises:
        ValueError: If the node doesn't exist or isn't a mesh transform.
    """
    if not cmds.objExists(mesh):
        raise ValueError(f"Mesh '{mesh}' does not exist")
    if cmds.nodeType(mesh) != "transform":
        raise ValueError(f"'{mesh}' is not a transform node")
    shapes = get_shapes([mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{mesh}' has no mesh shape")


def _validate_cutter_face_count(cutter: str) -> None:
    """Check that a mesh cutter does not exceed the face count limit.

    NURBS surface cutters are skipped (no limit).

    Args:
        cutter (str): Cutter node name.

    Raises:
        ValueError: If the cutter is a mesh with more faces than MAX_CUTTER_MESH_FACES.
    """
    shapes = cmds.listRelatives(cutter, shapes=True) or []
    if not shapes:
        return
    if cmds.nodeType(shapes[0]) != "mesh":
        return
    face_count = cmds.polyEvaluate(cutter, face=True)
    if face_count > MAX_CUTTER_MESH_FACES:
        raise ValueError(
            f"Cutter mesh '{cutter}' has {face_count} faces, exceeding the limit of {MAX_CUTTER_MESH_FACES}. "
            f"Use a lower-poly mesh or a NURBS surface instead."
        )


def _next_piece_index(grp: str, prefix: str) -> int:
    """Find the next available piece index within a group.

    Scans existing children whose names start with *prefix* followed by a
    three-digit number and returns ``max_existing + 1`` (or 0 if none exist).

    Args:
        grp (str): Group node name.
        prefix (str): Name prefix before the three-digit index (e.g. ``"body_piece_"``).

    Returns:
        int: Next available index.
    """
    children = cmds.listRelatives(grp, children=True) or []
    pattern = re.compile(re.escape(prefix) + r"(\d{3})")
    indices: list[int] = []
    for child in children:
        short_name = child.rsplit("|", 1)[-1]
        m = pattern.match(short_name)
        if m:
            indices.append(int(m.group(1)))
    if not indices:
        return 0
    return max(indices) + 1


def _get_or_create_group(name: str) -> str:
    """Get an existing group or create a new empty group.

    Args:
        name (str): Group node name.

    Returns:
        str: The group transform name.
    """
    if cmds.objExists(name):
        return name
    return cmds.group(empty=True, name=name)
