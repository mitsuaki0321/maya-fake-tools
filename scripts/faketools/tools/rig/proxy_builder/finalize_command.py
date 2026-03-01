"""Proxy Builder finalize command - Step 3 (Finalize) API."""

from logging import getLogger
from typing import Optional

import maya.cmds as cmds

from ....lib.lib_shape import combine_meshes, combine_meshes_per_shader, shape_parent

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------


def _joint_short_name(joint_name: str) -> str:
    """ジョイント名からパスとネームスペースを除去。"""
    return joint_name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_joint_from_group(group: str) -> Optional[str]:
    """プロキシグループの parentConstraint からジョイント名を取得。

    Args:
        group (str): プロキシグループ名。

    Returns:
        Optional[str]: ジョイント名。parentConstraint がない場合は None。
    """
    constraints = cmds.listRelatives(group, children=True, type="parentConstraint") or []
    if not constraints:
        return None
    targets = cmds.parentConstraint(constraints[0], query=True, targetList=True) or []
    return targets[0] if targets else None


def _get_or_create_group(name: str) -> str:
    """Get an existing group or create a new empty group."""
    if cmds.objExists(name):
        return name
    return cmds.group(empty=True, name=name)


def _cleanup_empty_transforms(group: str) -> None:
    """グループ内のシェイプを持たない空トランスフォームを削除。

    parentConstraint ノードは保持する。

    Args:
        group (str): 対象グループ名。
    """
    children = cmds.listRelatives(group, children=True) or []
    for child in children:
        if cmds.nodeType(child) == "parentConstraint":
            continue
        shapes = cmds.listRelatives(child, shapes=True) or []
        if not shapes:
            cmds.delete(child)


def _get_meshes_in_group(group: str) -> list[str]:
    """グループ内のメッシュトランスフォームを取得。

    Args:
        group (str): グループ名。

    Returns:
        list[str]: メッシュトランスフォーム名リスト。
    """
    children = cmds.listRelatives(group, children=True) or []
    meshes = []
    for child in children:
        if cmds.nodeType(child) == "parentConstraint":
            continue
        shapes = cmds.listRelatives(child, shapes=True, type="mesh") or []
        if shapes:
            meshes.append(child)
    return meshes


def _finalize_single(meshes: list[str], proxy_name: str, group: str) -> str:
    """全メッシュを1つにコンバインして命名する。

    Args:
        meshes (list[str]): メッシュリスト。
        proxy_name (str): 最終プロキシ名。
        group (str): 親グループ名。

    Returns:
        str: 最終プロキシ名。
    """
    if len(meshes) == 1:
        return cmds.rename(meshes[0], proxy_name)

    combined = combine_meshes(meshes, name=proxy_name)
    current_parent = cmds.listRelatives(combined, parent=True)
    if not current_parent or current_parent[0] != group:
        cmds.parent(combined, group)
    return combined


def _finalize_per_shader(meshes: list[str], proxy_name: str, group: str) -> str:
    """シェーダー別にコンバインし、シェイプペアレントで1トランスフォームにまとめる。

    Args:
        meshes (list[str]): メッシュリスト。
        proxy_name (str): 最終プロキシ名。
        group (str): 親グループ名。

    Returns:
        str: 最終プロキシ名。
    """
    shader_meshes = combine_meshes_per_shader(meshes)
    combined_list = list(shader_meshes.values())

    if len(combined_list) == 1:
        result = cmds.rename(combined_list[0], proxy_name)
        current_parent = cmds.listRelatives(result, parent=True)
        if not current_parent or current_parent[0] != group:
            cmds.parent(result, group)
        return result

    target = combined_list[0]
    sources = combined_list[1:]
    shape_parent(sources, target)
    result = cmds.rename(target, proxy_name)
    current_parent = cmds.listRelatives(result, parent=True)
    if not current_parent or current_parent[0] != group:
        cmds.parent(result, group)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def finalize_proxy_groups(
    parent_group: str = "proxy_grp",
    combine_mode: str = "single",
    output_group: str = "proxy_final_grp",
) -> list[str]:
    """各プロキシグループ内のピースをコンバインし最終命名する。

    parent_group の子グループ（*_proxy_grp）を走査し、各グループの
    parentConstraint からジョイント名を取得。ジョイント短縮名を使って
    ``{joint_short}_proxy`` に命名する。

    コンバイン後、空のトランスフォームを削除し、最終メッシュを
    output_group にフラットにペアレントする。

    Args:
        parent_group (str): プロキシグループの親グループ名。
        combine_mode (str): コンバインモード。
            ``"single"`` — 全メッシュを1つにコンバイン。
            ``"per_shader"`` — シェーダー別にコンバインし
            シェイプペアレントで1トランスフォームにまとめる。
        output_group (str): 最終メッシュの出力先グループ名。

    Returns:
        list[str]: 最終プロキシ名リスト。

    Raises:
        ValueError: parent_group が存在しない場合、または
            combine_mode が不正な場合。
    """
    if combine_mode not in ("single", "per_shader"):
        raise ValueError(f"Invalid combine_mode: '{combine_mode}'. Must be 'single' or 'per_shader'.")

    if not cmds.objExists(parent_group):
        raise ValueError(f"Parent group '{parent_group}' does not exist")

    children = cmds.listRelatives(parent_group, children=True) or []
    results: list[str] = []

    for child in children:
        joint_name = _get_joint_from_group(child)
        if not joint_name:
            logger.warning("Group '%s' has no parentConstraint, skipping", child)
            continue

        meshes = _get_meshes_in_group(child)
        if not meshes:
            logger.warning("Group '%s' has no meshes, skipping", child)
            continue

        joint_short = _joint_short_name(joint_name)
        proxy_name = f"{joint_short}_proxy"

        if combine_mode == "single":
            result = _finalize_single(meshes, proxy_name, child)
        else:
            result = _finalize_per_shader(meshes, proxy_name, child)

        _cleanup_empty_transforms(child)
        results.append(result)
        logger.debug("Finalized '%s' -> '%s' (%d meshes)", child, result, len(meshes))

    # Re-parent finalized meshes into a flat output group
    output_grp = _get_or_create_group(output_group)
    for result in results:
        current_parent = cmds.listRelatives(result, parent=True)
        if not current_parent or current_parent[0] != output_grp:
            cmds.parent(result, output_grp)

    logger.info("Finalized %d proxies into '%s' (mode: %s)", len(results), output_grp, combine_mode)
    return results
