"""Proxy Builder assign command - Step 2 (Assign) API."""

from logging import getLogger
from time import perf_counter
from typing import Optional

from maya.api import OpenMaya as om2
import maya.cmds as cmds
import maya.OpenMaya as om1
import numpy as np

from ....lib.lib_selection import get_shapes
from ....lib.lib_skinCluster import get_skinCluster
from . import separate_by_weights as _weights

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------


def _joint_short_name(joint_name: str) -> str:
    """ジョイント名からパスとネームスペースを除去。"""
    return joint_name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def _proxy_grp_name_for_joint(joint_name: str) -> str:
    """ジョイント用のプロキシグループ名を生成。"""
    return f"{_joint_short_name(joint_name)}_proxy_grp"


# ---------------------------------------------------------------------------
# Group helpers
# ---------------------------------------------------------------------------


def _get_or_create_group(name: str) -> str:
    """Get an existing group or create a new empty group."""
    if cmds.objExists(name):
        return name
    return cmds.group(empty=True, name=name)


def _collect_into_group(grp: str, nodes: list[str]) -> None:
    """ノードリストをグループ配下にペアレントする。"""
    for node in nodes:
        current_parent = cmds.listRelatives(node, parent=True)
        if not current_parent or current_parent[0] != grp:
            cmds.parent(node, grp)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _get_vertex_positions(mesh: str) -> np.ndarray:
    """メッシュの全頂点ワールド座標を取得。

    Args:
        mesh (str): メッシュトランスフォーム名。

    Returns:
        np.ndarray: shape (num_verts, 3)
    """
    vtx_count = cmds.polyEvaluate(mesh, vertex=True)
    positions = cmds.xform(f"{mesh}.vtx[0:{vtx_count - 1}]", query=True, worldSpace=True, translation=True)
    return np.array(positions).reshape(-1, 3)


def _get_mesh_fn(mesh: str) -> om2.MFnMesh:
    """トランスフォームから MFnMesh を取得。"""
    shapes = get_shapes([mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{mesh}' has no mesh shape")
    sel = om2.MSelectionList()
    sel.add(shapes[0])
    dag_path = sel.getDagPath(0)
    return om2.MFnMesh(dag_path)


def _create_mesh_intersector(mesh: str) -> om1.MMeshIntersector:
    """メッシュの MMeshIntersector を作成（ワールド空間）。

    事前にアクセラレーション構造を構築するため、
    繰り返しの getClosestPoint クエリが高速になる。

    Args:
        mesh (str): メッシュトランスフォーム名。

    Returns:
        om1.MMeshIntersector: 構築済みインターセクター。
    """
    shapes = get_shapes([mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{mesh}' has no mesh shape")
    sel = om1.MSelectionList()
    sel.add(shapes[0])
    dag_path = om1.MDagPath()
    sel.getDagPath(0, dag_path)
    intersector = om1.MMeshIntersector()
    intersector.create(dag_path.node(), dag_path.inclusiveMatrix())
    return intersector


# ---------------------------------------------------------------------------
# Weight-based assignment internals
# ---------------------------------------------------------------------------


def _build_face_joint_map(
    fn_mesh: om2.MFnMesh,
    influences: list[str],
    weights_array: np.ndarray,
    target_joints: Optional[list[str]] = None,
) -> list[str]:
    """各フェイスの dominant joint を事前計算。

    Args:
        fn_mesh (om2.MFnMesh): 参照メッシュの MFnMesh。
        influences (list[str]): インフルエンスジョイント名リスト。
        weights_array (np.ndarray): ウェイト配列 shape (num_verts, num_influences)。
        target_joints (Optional[list[str]]): 対象ジョイント。None なら全インフルエンス。

    Returns:
        list[str]: face_index → dominant joint name のマッピング。
    """
    if target_joints is not None:
        target_set = set(target_joints)
        target_mask = np.array([1.0 if inf in target_set else 0.0 for inf in influences])
    else:
        target_mask = np.ones(len(influences))

    face_joint_map: list[str] = []
    for face_id in range(fn_mesh.numPolygons):
        vtx_indices = fn_mesh.getPolygonVertices(face_id)
        face_weights = weights_array[vtx_indices].sum(axis=0) * target_mask
        dominant_idx = int(np.argmax(face_weights))
        face_joint_map.append(influences[dominant_idx])

    return face_joint_map


def _assign_by_weights(
    pieces: list[str],
    reference_mesh: str,
    joints: Optional[list[str]] = None,
) -> dict[str, list[str]]:
    """ウェイトベースでピースをジョイントにアサインする。

    各ピースの全頂点について参照メッシュ上の最近接フェイスを特定し、
    そのフェイスの dominant joint で多数決を行う。

    Args:
        pieces (list[str]): アサイン対象ピース名リスト。
        reference_mesh (str): スキンウェイトを持つ参照メッシュ。
        joints (Optional[list[str]]): 対象ジョイント。None なら全インフルエンス。

    Returns:
        dict[str, list[str]]: {joint_name: [piece_names]}
    """
    shapes = get_shapes([reference_mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{reference_mesh}' has no mesh shape")

    skin_cluster = get_skinCluster(shapes[0])
    if not skin_cluster:
        raise ValueError(f"'{reference_mesh}' has no skinCluster")

    t0 = perf_counter()
    influences, weights = _weights.get_weights_per_vertex(skin_cluster)
    weights_array = np.array(weights)
    logger.debug("[perf] get_weights_per_vertex: %.3fs", perf_counter() - t0)

    if joints is not None:
        influence_set = set(influences)
        valid_joints = [j for j in joints if j in influence_set]
        if not valid_joints:
            raise ValueError("None of the specified joints are influences on the reference mesh")
        joints = valid_joints

    t0 = perf_counter()
    fn_mesh = _get_mesh_fn(reference_mesh)
    face_joint_map = _build_face_joint_map(fn_mesh, influences, weights_array, target_joints=joints)
    logger.debug("[perf] build_face_joint_map (%d faces): %.3fs", fn_mesh.numPolygons, perf_counter() - t0)

    t0 = perf_counter()
    intersector = _create_mesh_intersector(reference_mesh)
    logger.debug("[perf] create_mesh_intersector: %.3fs", perf_counter() - t0)

    point_on_mesh = om1.MPointOnMesh()
    assignment: dict[str, list[str]] = {}
    for piece in pieces:
        t1 = perf_counter()
        positions = _get_vertex_positions(piece)
        t_vtx = perf_counter() - t1

        t1 = perf_counter()
        joint_votes: dict[str, int] = {}
        for pos in positions:
            intersector.getClosestPoint(om1.MPoint(float(pos[0]), float(pos[1]), float(pos[2])), point_on_mesh)
            joint_name = face_joint_map[point_on_mesh.faceIndex()]
            joint_votes[joint_name] = joint_votes.get(joint_name, 0) + 1
        t_closest = perf_counter() - t1

        if joint_votes:
            winner = max(joint_votes, key=joint_votes.get)
            assignment.setdefault(winner, []).append(piece)
            logger.debug(
                "[perf] piece '%s' (%d verts): get_positions=%.3fs, closest_point=%.3fs -> '%s'",
                piece,
                len(positions),
                t_vtx,
                t_closest,
                winner,
            )

    return assignment


# ---------------------------------------------------------------------------
# Bone-based assignment internals
# ---------------------------------------------------------------------------


def _point_to_segment_distances(points: np.ndarray, seg_start: np.ndarray, seg_end: np.ndarray) -> np.ndarray:
    """複数の点と1つの線分の距離を一括計算。

    Args:
        points (np.ndarray): shape (N, 3)
        seg_start (np.ndarray): shape (3,)
        seg_end (np.ndarray): shape (3,)

    Returns:
        np.ndarray: shape (N,) 各点から線分への最短距離。
    """
    seg = seg_end - seg_start
    seg_len_sq = float(np.dot(seg, seg))

    if seg_len_sq < 1e-10:
        return np.linalg.norm(points - seg_start, axis=1)

    diff = points - seg_start
    t = np.clip(diff @ seg / seg_len_sq, 0.0, 1.0)
    closest = seg_start + t[:, np.newaxis] * seg
    return np.linalg.norm(points - closest, axis=1)


def _build_bone_segments(joints: list[str]) -> dict[str, list[tuple[np.ndarray, np.ndarray]]]:
    """ジョイントリストからボーンセグメントを構築。

    各ジョイントは「自分 → 子ジョイント」のセグメントを所有する。
    末端ジョイント（子なし）は除外される。

    Args:
        joints (list[str]): 対象ジョイント名リスト。

    Returns:
        dict[str, list[tuple[np.ndarray, np.ndarray]]]: {joint_name: [(start, end), ...]}
    """
    segments: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}

    for joint in joints:
        if not cmds.objExists(joint):
            logger.warning("Joint '%s' does not exist, skipping", joint)
            continue
        children = cmds.listRelatives(joint, children=True, type="joint") or []
        if not children:
            continue

        joint_pos = np.array(cmds.xform(joint, query=True, worldSpace=True, translation=True))
        segs: list[tuple[np.ndarray, np.ndarray]] = []
        for child in children:
            child_pos = np.array(cmds.xform(child, query=True, worldSpace=True, translation=True))
            segs.append((joint_pos, child_pos))
        segments[joint] = segs

    return segments


def _assign_by_bones(
    pieces: list[str],
    joints: list[str],
) -> dict[str, list[str]]:
    """ボーンセグメント距離でピースをジョイントにアサインする。

    各ジョイントの「自分 → 子ジョイント」セグメント群から最短距離で代表し、
    全頂点で多数決を行う。末端ジョイントはセグメントを持たないため除外。

    Args:
        pieces (list[str]): アサイン対象ピース名リスト。
        joints (list[str]): 対象ジョイント名リスト。

    Returns:
        dict[str, list[str]]: {joint_name: [piece_names]}
    """
    t0 = perf_counter()
    segments = _build_bone_segments(joints)
    if not segments:
        raise ValueError("No bone segments could be built (all joints may be end joints)")

    # Flatten segments for vectorized computation
    seg_joint_names: list[str] = []
    seg_starts: list[np.ndarray] = []
    seg_ends: list[np.ndarray] = []
    for joint_name, segs in segments.items():
        for start, end in segs:
            seg_joint_names.append(joint_name)
            seg_starts.append(start)
            seg_ends.append(end)
    logger.debug("[perf] build_bone_segments (%d joints, %d segments): %.3fs", len(segments), len(seg_joint_names), perf_counter() - t0)

    assignment: dict[str, list[str]] = {}
    for piece in pieces:
        t1 = perf_counter()
        positions = _get_vertex_positions(piece)
        t_vtx = perf_counter() - t1

        t1 = perf_counter()
        # Compute distances from all vertices to all segments: (num_segments, num_vertices)
        all_distances = np.stack([_point_to_segment_distances(positions, start, end) for start, end in zip(seg_starts, seg_ends)])

        # For each vertex, find closest segment
        closest_seg_indices = np.argmin(all_distances, axis=0)

        # Count votes per joint
        unique_indices, counts = np.unique(closest_seg_indices, return_counts=True)
        joint_votes: dict[str, int] = {}
        for seg_idx, count in zip(unique_indices, counts):
            jname = seg_joint_names[seg_idx]
            joint_votes[jname] = joint_votes.get(jname, 0) + int(count)
        t_dist = perf_counter() - t1

        if joint_votes:
            winner = max(joint_votes, key=joint_votes.get)
            assignment.setdefault(winner, []).append(piece)
            logger.debug(
                "[perf] piece '%s' (%d verts): get_positions=%.3fs, segment_distance=%.3fs -> '%s'",
                piece,
                len(positions),
                t_vtx,
                t_dist,
                winner,
            )

    return assignment


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def auto_assign_pieces(
    pieces: list[str],
    reference_mesh: Optional[str] = None,
    joints: Optional[list[str]] = None,
) -> dict[str, list[str]]:
    """ピース群をジョイントに自動アサインする。

    reference_mesh が指定された場合はウェイトベースで、
    指定されない場合はボーンセグメント距離ベースでアサインする。

    Args:
        pieces (list[str]): アサイン対象のピースメッシュ名リスト。
        reference_mesh (Optional[str]): スキンウェイトを持つ参照メッシュ。
            指定時はウェイトモード、None 時はボーンモード。
        joints (Optional[list[str]]): 対象ジョイント。
            ウェイトモード: None なら全インフルエンス。
            ボーンモード: 必須。

    Returns:
        dict[str, list[str]]: {joint_name: [piece_names]}

    Raises:
        ValueError: 入力が不正な場合。
    """
    if not pieces:
        raise ValueError("No pieces provided")

    for piece in pieces:
        if not cmds.objExists(piece):
            raise ValueError(f"Piece '{piece}' does not exist")

    if reference_mesh is not None:
        if not cmds.objExists(reference_mesh):
            raise ValueError(f"Reference mesh '{reference_mesh}' does not exist")
        logger.info("Auto-assigning %d pieces by weights (reference: '%s')", len(pieces), reference_mesh)
        return _assign_by_weights(pieces, reference_mesh, joints)

    if not joints:
        raise ValueError("Bone mode requires joints to be specified")
    logger.info("Auto-assigning %d pieces by bone distance (%d joints)", len(pieces), len(joints))
    return _assign_by_bones(pieces, joints)


def create_proxy_groups(
    assignment: dict[str, list[str]],
    parent_group: str = "proxy_grp",
) -> list[str]:
    """アサイン結果から parentConstraint 付きプロキシグループを作成する。

    各ジョイントに対して ``{joint_short}_proxy_grp`` を作成し、
    parentConstraint でジョイントに追従させる。

    Args:
        assignment (dict[str, list[str]]): {joint_name: [piece_names]} アサインマップ。
        parent_group (str): 全グループの親グループ名。

    Returns:
        list[str]: 作成したグループ名リスト。
    """
    if not assignment:
        raise ValueError("No assignment data provided")

    parent_grp = _get_or_create_group(parent_group)
    created_groups: list[str] = []

    for joint_name, pieces in assignment.items():
        if not cmds.objExists(joint_name):
            logger.warning("Joint '%s' does not exist, skipping", joint_name)
            continue

        grp_name = _proxy_grp_name_for_joint(joint_name)
        grp = _get_or_create_group(grp_name)

        # Add parentConstraint if not already present
        existing = cmds.listRelatives(grp, children=True, type="parentConstraint") or []
        if not existing:
            cmds.parentConstraint(joint_name, grp, maintainOffset=True)

        _collect_into_group(grp, pieces)
        created_groups.append(grp)
        logger.debug("Group '%s' -> joint '%s' (%d pieces)", grp, joint_name, len(pieces))

    _collect_into_group(parent_grp, created_groups)
    logger.info("Created %d proxy groups in '%s'", len(created_groups), parent_grp)
    return created_groups


def reassign_piece(
    piece: str,
    target_joint: str,
    parent_group: str = "proxy_grp",
) -> str:
    """ピースを別のジョイントのプロキシグループに移動する。

    対象グループが存在しない場合は新規作成し parentConstraint を付与する。

    Args:
        piece (str): 移動するピースメッシュ名。
        target_joint (str): 移動先のジョイント名。
        parent_group (str): 親グループ名。

    Returns:
        str: 移動先のグループ名。
    """
    if not cmds.objExists(piece):
        raise ValueError(f"Piece '{piece}' does not exist")
    if not cmds.objExists(target_joint):
        raise ValueError(f"Joint '{target_joint}' does not exist")

    parent_grp = _get_or_create_group(parent_group)
    grp_name = _proxy_grp_name_for_joint(target_joint)
    grp = _get_or_create_group(grp_name)

    existing = cmds.listRelatives(grp, children=True, type="parentConstraint") or []
    if not existing:
        cmds.parentConstraint(target_joint, grp, maintainOffset=True)

    cmds.parent(piece, grp)
    _collect_into_group(parent_grp, [grp])

    logger.info("Reassigned '%s' to joint '%s' (group: '%s')", piece, target_joint, grp)
    return grp


def get_proxy_group_assignment(
    parent_group: str = "proxy_grp",
) -> dict[str, list[str]]:
    """シーン階層から現在のアサイン状態を読み取る。

    parent_group の子グループを走査し、各グループの parentConstraint
    ターゲットジョイントとピースメッシュを取得する。

    Args:
        parent_group (str): 親グループ名。

    Returns:
        dict[str, list[str]]: {joint_name: [piece_names]}
    """
    if not cmds.objExists(parent_group):
        return {}

    assignment: dict[str, list[str]] = {}
    children = cmds.listRelatives(parent_group, children=True) or []

    for child in children:
        constraints = cmds.listRelatives(child, children=True, type="parentConstraint") or []
        if not constraints:
            continue

        targets = cmds.parentConstraint(constraints[0], query=True, targetList=True) or []
        if not targets:
            continue

        joint_name = targets[0]
        all_children = cmds.listRelatives(child, children=True) or []
        pieces = [c for c in all_children if cmds.nodeType(c) != "parentConstraint"]

        if pieces:
            assignment[joint_name] = pieces

    return assignment
