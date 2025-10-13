"""Copy and mirror skin weights."""

from logging import getLogger
import re

import maya.cmds as cmds

from ..lib import lib_skinCluster

logger = getLogger(__name__)


def copy_skin_weights_with_bind(src_obj: str, dst_objs: list[str], uv: bool = False) -> None:
    """Copy the skin weights from the source object to the destination object.

    Args:
        src_obj (str): The source transform object.
        dst_objs (str): The destination object.
        uv (bool, optional): Copy the UV weights. Defaults to False. Only destination object is a mesh.
    """
    # Check exist
    if not cmds.objExists(src_obj):
        raise ValueError(f"Node does not exist: {src_obj}")

    if not cmds.nodeType(src_obj) == "transform":
        raise ValueError(f"Node is not a transform: {src_obj}")

    not_exists_objs = [obj for obj in dst_objs if not cmds.objExists(obj)]
    if not_exists_objs:
        raise ValueError(f"Node does not exist: {not_exists_objs}")

    # Get source skinCluster
    src_shp = cmds.listRelatives(src_obj, shapes=True, fullPath=True)
    if not src_shp:
        raise ValueError(f"No shape found: {src_obj}")
    else:
        src_shp = src_shp[0]

    if cmds.nodeType(src_shp) != "mesh":
        raise ValueError(f"Node is not a mesh: {src_shp}")

    src_skinCluster = lib_skinCluster.get_skinCluster(src_shp)
    if not src_skinCluster:
        raise ValueError(f"No skinCluster found: {src_obj}")

    src_infs = cmds.skinCluster(src_skinCluster, q=True, inf=True)

    # Get destination data
    dst_data = {}
    for dst_obj in dst_objs:
        components = cmds.filterExpand(dst_obj, sm=[28, 31, 46])
        if components:
            shp = cmds.ls(components[0], objectsOnly=True)[0]
            dst_data.setdefault(shp, []).extend(components)
        else:
            shp = cmds.listRelatives(dst_obj, shapes=True, type="deformableShape")
            if not shp:
                cmds.warning(f"No shape found: {dst_obj}")
                continue

            if shp[0] not in dst_data:
                dst_data[shp[0]] = []

    # Copy weights
    if uv:
        src_uv_set = cmds.polyUVSet(src_shp, q=True, currentUVSet=True)[0]

    for dst_shp, components in dst_data.items():
        dst_skinCluster = lib_skinCluster.get_skinCluster(dst_shp)
        if not dst_skinCluster:
            dst_skinCluster = cmds.skinCluster(src_infs, dst_shp, tsb=True)[0]

            logger.debug(f"Create skinCluster: {dst_shp}")
        else:
            dst_infs = cmds.skinCluster(dst_skinCluster, q=True, inf=True)
            dif_infs = list(set(src_infs) - set(dst_infs))
            if dif_infs:
                cmds.skinCluster(dst_skinCluster, e=True, lw=True, wt=0.0, ai=dif_infs)

                logger.debug(f"Add influences: {dif_infs}")

        node_type = cmds.nodeType(dst_shp)
        cmds.select(src_shp, r=True)
        if components:
            cmds.select(components, add=True)
        else:
            cmds.select(dst_shp, add=True)

        if node_type == "mesh":
            # When specifying a skinCluster, weights cannot be applied only to the components when components are selected.
            # This is likely due to a specification change in Maya 2023 or later.
            if uv:
                dst_uv_set = cmds.polyUVSet(dst_shp, query=True, currentUVSet=True)[0]
                cmds.copySkinWeights(
                    noMirror=True, surfaceAssociation="closestPoint", influenceAssociation=["label", "closestJoint"], uvSpace=[src_uv_set, dst_uv_set]
                )

                logger.debug(f"Copy UV skin weights: {src_shp} -> {dst_shp}")
            else:
                cmds.copySkinWeights(noMirror=True, surfaceAssociation="closestPoint", influenceAssociation=["label", "closestJoint"])

                logger.debug(f"Copy skin weights: {src_shp} -> {dst_shp}")
        else:
            lib_skinCluster.copy_skin_weights_custom(src_skinCluster, dst_skinCluster)

            logger.debug(f"Copy skin weights custom: {src_shp} -> {dst_shp}")


def mirror_skin_weights(
    obj: str,
    left_right_names: list[str, str],
    right_left_names: list[str, str],
    mirror_inverse: bool = False,
) -> None:
    """Mirror the skin weights.

    Args:
        obj (str): The transform object.
        left_right_names (list[str, str]): The left and right names. 0 is regex, 1 is replace.
        right_left_names (list[str, str]): The right and left names. 0 is regex, 1 is replace.
        mirrorInverse (bool, optional): Mirror the inverse weights. Defaults to False.
    """
    if not left_right_names or not right_left_names:
        raise ValueError("Invalid substitute names.")

    if not cmds.objExists(obj):
        raise RuntimeError(f"Node does not exist: {obj}")

    if cmds.nodeType(obj) != "transform":
        raise RuntimeError(f"Node is not a transform: {obj}")

    shp = cmds.listRelatives(obj, shapes=True, fullPath=True)
    if not shp:
        raise RuntimeError(f"No shape found: {obj}")
    else:
        shp = shp[0]

    if "deformableShape" not in cmds.nodeType(shp, inherited=True):
        raise RuntimeError(f"Node is not a deformable shape: {shp}")

    skinCluster = lib_skinCluster.get_skinCluster(shp)
    if not skinCluster:
        raise RuntimeError(f"No skinCluster found: {obj}")

    infs = cmds.skinCluster(skinCluster, q=True, inf=True)

    not_exists_infs = []
    replace_infs = []
    p_left = re.compile(left_right_names[0])
    p_right = re.compile(right_left_names[0])

    for inf in infs:
        pos = cmds.xform(inf, q=True, ws=True, t=True)
        if pos[0] > 1e-3:
            replace_inf = p_left.sub(left_right_names[1], inf)
        elif pos[0] < -1e-3:
            replace_inf = p_right.sub(right_left_names[1], inf)
        else:
            continue

        if replace_inf == inf:
            cmds.warning(f"No change in name: {inf}")
        elif not cmds.objExists(replace_inf):
            not_exists_infs.append([inf, replace_inf])
        else:
            replace_infs.append(replace_inf)

    if not_exists_infs:
        for inf, replace_inf in not_exists_infs:
            logger.warning(f"Node does not exist: {replace_inf} ({inf})")
        raise RuntimeError("Some nodes do not exist.")

    if replace_infs:
        bind_infs = list(set(replace_infs) - set(infs))
        if bind_infs:
            cmds.skinCluster(skinCluster, e=True, lw=True, wt=0.0, ai=bind_infs)

            logger.debug(f"Add new influences: {replace_infs}")

    cmds.copySkinWeights(
        ss=skinCluster,
        ds=skinCluster,
        mirrorInverse=mirror_inverse,
        mirrorMode="YZ",
        surfaceAssociation="closestPoint",
        influenceAssociation=["label", "closestJoint"],
    )

    logger.debug(f"Mirror skin weights: {obj}")


def mirror_skin_weights_with_objects(
    src_obj: str, left_right_names: list[str, str], right_left_names: list[str, str], mirror_inverse: bool = False
) -> None:
    """Mirror the skin weights with objects.

    Notes:
        - Find the left and right objects based on the obj.
        - Bind the influences to the destination objects.
        - Transfer the skin weights.

    Args:
        src_obj (str): The object.
        left_right_names (list[str, str]): The left and right names. 0 is regex, 1 is replace.
        right_left_names (list[str, str]): The right and left names. 0 is regex, 1 is replace.
        mirrorInverse (bool, optional): Mirror the inverse weights. Defaults to False. If True, mirror the right to left.
    """
    if not left_right_names or not right_left_names:
        raise ValueError("Invalid substitute names.")

    if not cmds.objExists(src_obj):
        cmds.error(f"Node does not exist: {src_obj}")

    if cmds.nodeType(src_obj) != "transform":
        cmds.error(f"Node is not a transform: {src_obj}")

    src_shp = cmds.listRelatives(src_obj, shapes=True, fullPath=True)
    if not src_shp:
        cmds.error(f"No shape found: {src_obj}")
    else:
        src_shp = src_shp[0]

    if "deformableShape" not in cmds.nodeType(src_shp, inherited=True):
        cmds.error(f"Node is not a deformable shape: {src_shp}")

    src_skinCluster = lib_skinCluster.get_skinCluster(src_shp)
    if not src_skinCluster:
        cmds.error(f"No skinCluster found: {src_obj}")

    if not mirror_inverse:
        dst_obj = re.sub(left_right_names[0], left_right_names[1], src_obj)
    else:
        dst_obj = re.sub(right_left_names[0], right_left_names[1], src_obj)

    if not cmds.objExists(dst_obj):
        raise RuntimeError(f"Replace object does not exist: {dst_obj}")

    infs = cmds.skinCluster(src_skinCluster, q=True, inf=True)

    not_exists_infs = []
    bind_infs = []
    p_left = re.compile(left_right_names[0])
    p_right = re.compile(right_left_names[0])

    for inf in infs:
        name_changed = True
        pos = cmds.xform(inf, q=True, ws=True, t=True)
        if pos[0] > 1e-3:
            replace_inf = p_left.sub(left_right_names[1], inf)
        elif pos[0] < -1e-3:
            replace_inf = p_right.sub(right_left_names[1], inf)
        else:
            replace_inf = inf
            name_changed = False

        if replace_inf == inf and name_changed:
            cmds.warning(f"No change in name: {inf}")
            bind_infs.append(inf)
        elif not cmds.objExists(replace_inf):
            not_exists_infs.append([inf, replace_inf])
        else:
            bind_infs.append(replace_inf)

    if not_exists_infs:
        for inf, replace_inf in not_exists_infs:
            cmds.warning(f"Node does not exist: {replace_inf} ({inf})")

        cmds.error("Some nodes do not exist.")

    dst_shp = cmds.listRelatives(dst_obj, shapes=True)[0]
    dst_skinCluster = lib_skinCluster.get_skinCluster(dst_shp)
    if not dst_skinCluster:
        dst_skinCluster = cmds.skinCluster(bind_infs, dst_shp, tsb=True)[0]

        logger.debug(f"Create skinCluster: {dst_shp}")
    else:
        dst_infs = cmds.skinCluster(dst_skinCluster, q=True, inf=True)
        dif_infs = list(set(bind_infs) - set(dst_infs))
        if dif_infs:
            cmds.skinCluster(dst_skinCluster, e=True, lw=True, wt=0.0, ai=dif_infs)

            logger.debug(f"Add influences: {dif_infs}")

    cmds.copySkinWeights(
        ss=src_skinCluster,
        ds=dst_skinCluster,
        mirrorMode="YZ",
        mirrorInverse=mirror_inverse,
        surfaceAssociation="closestPoint",
        influenceAssociation=["label", "closestJoint"],
    )
