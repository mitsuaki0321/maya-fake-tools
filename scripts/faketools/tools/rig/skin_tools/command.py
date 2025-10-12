"""
Convert weight commands.
"""

import itertools
from logging import getLogger
import re

import maya.cmds as cmds

from ....lib import lib_mesh, lib_skinCluster

logger = getLogger(__name__)


def get_influences_from_objects(objs: list[str]) -> list[str]:
    """Get the influences from the objects.

    Args:
        objs (list[str]): The Target objects.

    Returns:
        list[str]: The influences.
    """
    if not objs:
        raise ValueError("No objects specified")

    object_data = {}
    for obj in objs:
        components = cmds.filterExpand(obj, sm=[28, 31, 46])
        if components:
            shp = cmds.ls(components[0], objectsOnly=True)[0]
            object_data.setdefault(shp, []).extend(components)
        else:
            shp = cmds.listRelatives(obj, shapes=True, type="deformableShape")
            if not shp:
                cmds.warning(f"No shape found: {obj}")
                continue

            if shp[0] not in object_data:
                object_data[shp[0]] = []

    result_infs = []
    for shp, components in object_data.items():
        skinCluster = lib_skinCluster.get_skinCluster(shp)
        if not skinCluster:
            cmds.warning(f"Object is not bound to a skinCluster: {shp}")
            continue

        infs = cmds.skinCluster(skinCluster, q=True, inf=True)
        if not components:
            result_infs.extend(infs)
        else:
            # Get only influences with weights greater than 0
            weights = lib_skinCluster.get_skin_weights(skinCluster, components)
            weights = [sum(w) for w in zip(*weights, strict=False)]
            result_infs.extend([infs[i] for i, w in enumerate(weights) if w > 0.0])

    result_infs = list(dict.fromkeys(result_infs))

    logger.debug(f"Get influences from objects: {objs} -> {result_infs}")

    return result_infs


def average_skin_weights(components: list[str]) -> None:
    """Average the weights of the components.

    Args:
        components (list[str]): The components.
    """
    if not components:
        return

    objs = list(set(cmds.ls(components, objectsOnly=True)))
    if len(objs) > 1:
        raise RuntimeError("Components must belong to the same object")
    else:
        obj = objs[0]

    skinCluster = lib_skinCluster.get_skinCluster(obj)
    if not skinCluster:
        raise RuntimeError(f"Object is not bound to a skinCluster: {obj}")

    components = cmds.ls(components, flatten=True)
    weights = lib_skinCluster.get_skin_weights(skinCluster, components)
    num_components = len(components)

    average_weights = [sum(ws) / num_components for ws in list(zip(*weights, strict=False))]
    average_weights = [average_weights for _ in range(num_components)]

    lib_skinCluster.set_skin_weights(skinCluster, average_weights, components)

    logger.debug(f"Averaged skin weights: {components}")


def average_skin_weights_shell(mesh: str) -> None:
    """Average the weights of the mesh shell components.

    Args:
        mesh (str): The mesh node.
    """
    if not mesh:
        raise ValueError("No mesh node specified")

    if not cmds.objExists(mesh):
        raise RuntimeError(f"Node does not exist: {mesh}")

    if cmds.nodeType(mesh) != "mesh":
        raise RuntimeError(f"Node is not a mesh: {mesh}")

    vertex_shells = lib_mesh.MeshVertex(mesh).get_vertex_shells()
    if len(vertex_shells) < 2:
        logger.warning(f"Mesh has no shells: {mesh}")

    skinCluster = lib_skinCluster.get_skinCluster(mesh)
    if not skinCluster:
        raise RuntimeError(f"Object is not bound to a skinCluster: {mesh}")

    vertex_components = cmds.ls(f"{mesh}.vtx[*]", flatten=True)

    for vertex_shell in vertex_shells:
        components = [vertex_components[i] for i in vertex_shell]
        average_skin_weights(components)

    logger.debug(f"Averaged skin weights shell: {mesh}")


def combine_pair_skin_weights(components: list[str], method: str = "auto", static_inf: str | None = None, **kwargs) -> None:
    """Combine the pair influences weights of the components.

    Args:
        components (list[str]): The components. Only vertex, cv, or lattice points are supported.
        method (str, optional): The combine method. Defaults to 'auto'. Options are 'auto', 'manual'.
        static_inf (str): The static influence. If specified, the combined weights will be applied to this influence.

    Keyword Args:
        regex_name (str): The regex name. In case of 'auto' method.
        replace_name (str): The replace name. In case of 'auto' method.
        pair_infs (list[list[str, str]]): The pair influences. In case of 'manual' method.
    """
    if not components:
        raise ValueError("No components specified")

    if method not in ["auto", "manual"]:
        raise ValueError("Invalid method")

    # Validate the components
    components = cmds.filterExpand(components, sm=[28, 31, 46], ex=True)
    if not components:
        raise RuntimeError("No components specified or unsupported component type")

    objs = list(set(cmds.ls(components, objectsOnly=True)))
    if len(objs) > 1:
        raise RuntimeError("Components must belong to the same object")
    else:
        obj = objs[0]

    skinCluster = lib_skinCluster.get_skinCluster(obj)
    if not skinCluster:
        raise RuntimeError(f"Object is not bound to a skinCluster: {obj}")

    infs = cmds.skinCluster(skinCluster, q=True, inf=True)

    # Validate the influences
    if method == "auto":
        regex_name = kwargs.get("regex_name")
        if not regex_name:
            raise ValueError("Regex name is not specified.")
        replace_name = kwargs.get("replace_name")
        if not replace_name:
            raise ValueError("Replace name is not specified.")

        p = re.compile(regex_name)
        match_infs = [inf for inf in infs if p.match(inf)]
        pair_infs = []
        for inf in match_infs:
            target_inf = p.sub(replace_name, inf)
            if target_inf in infs:
                pair_infs.append([inf, target_inf])
            else:
                logger.warning(f"No corresponding influence found for: {inf}")

        logger.debug(f"Auto pair influences: {pair_infs}")
    elif method == "manual":
        pair_infs = kwargs.get("pair_infs", [])
        if not pair_infs:
            raise ValueError("No pair influences specified")

        if not all([len(pair_inf) == 2 for pair_inf in pair_infs]):
            raise RuntimeError("Influence pairs must be 2 elements")

        all_infs = list(itertools.chain(*pair_infs))
        if len(all_infs) != len(set(all_infs)):
            dup_infs = [inf for inf in all_infs if all_infs.count(inf) > 1]
            raise RuntimeError(f"Influence pairs must be unique: {dup_infs}")

        not_exists_infs = [inf for inf in all_infs if not cmds.objExists(inf)]
        if not_exists_infs:
            raise RuntimeError(f"Influences not found: {not_exists_infs}")

        not_bound_infs = [inf for inf in all_infs if inf not in infs]
        if not_bound_infs:
            raise RuntimeError(f"Influences not bound: {not_bound_infs}")

        logger.debug(f"Manual pair influences: {pair_infs}")

    if static_inf:
        if not cmds.objExists(static_inf):
            raise RuntimeError(f"Static influence not found: {static_inf}")

        if static_inf not in infs:
            raise RuntimeError(f"Static influence not bound: {static_inf}")

        if static_inf in all_infs:
            raise RuntimeError(f"Static influence cannot be in the pair influences: {static_inf}")

    weights = lib_skinCluster.get_skin_weights(skinCluster, components)

    if not static_inf:
        for i in range(len(weights)):
            for pair_inf in pair_infs:
                pair_weight = weights[i][infs.index(pair_inf[0])] + weights[i][infs.index(pair_inf[1])]
                if pair_weight > 0.0:
                    apply_weight = pair_weight / 2.0
                    weights[i][infs.index(pair_inf[0])] = apply_weight
                    weights[i][infs.index(pair_inf[1])] = apply_weight
    else:
        for i in range(len(weights)):
            current_total_weights = weights[i][infs.index(static_inf)]
            pair_total_weights = 0.0
            for pair_inf in pair_infs:
                current_total_weights += weights[i][infs.index(pair_inf[0])] + weights[i][infs.index(pair_inf[1])]
                pair_total_weights += weights[i][infs.index(pair_inf[0])] * 2.0

            if current_total_weights == 0.0:
                continue

            if current_total_weights > pair_total_weights:
                for pair_inf in pair_infs:
                    weights[i][infs.index(pair_inf[1])] = weights[i][infs.index(pair_inf[0])]

                weights[i][infs.index(static_inf)] = current_total_weights - pair_total_weights
            else:
                for pair_inf in pair_infs:
                    apply_weight = current_total_weights * weights[i][infs.index(pair_inf[0])] * 2.0 / pair_total_weights
                    weights[i][infs.index(pair_inf[0])] = apply_weight
                    weights[i][infs.index(pair_inf[1])] = apply_weight

                weights[i][infs.index(static_inf)] = 0.0

    logger.debug(f"Combined pair influences weights: {components}")

    lib_skinCluster.set_skin_weights(skinCluster, weights, components)


def combine_skin_weights(src_infs: list[str], target_inf: str, components: list[str]) -> None:
    """Combine the source influences weights to the target influence of the components.

    Args:
        src_infs (list[str]): The source influences.
        target_inf (str): The target influence.
        components (list[str]): The components. Only vertex, cv, or lattice points are supported.
    """
    if not src_infs:
        raise ValueError("No source influences specified")

    if not target_inf:
        raise ValueError("No target influence specified")

    if not components:
        raise ValueError("No components specified")

    # Validate the components
    components = cmds.filterExpand(components, sm=[28, 31, 46], ex=True)
    if not components:
        raise RuntimeError("No components specified or unsupported component type")

    objs = list(set(cmds.ls(components, objectsOnly=True)))
    if len(objs) > 1:
        raise RuntimeError("Components must belong to the same object")
    else:
        obj = objs[0]

    skinCluster = lib_skinCluster.get_skinCluster(obj)
    if not skinCluster:
        raise RuntimeError(f"Object is not bound to a skinCluster: {obj}")

    infs = cmds.skinCluster(skinCluster, q=True, inf=True)

    # Validate the influences
    if not cmds.objExists(target_inf):
        raise RuntimeError(f"Target influence not found: {target_inf}")
    if target_inf not in infs:
        raise RuntimeError(f"Target influence not bound: {target_inf}")

    not_exists_infs = [inf for inf in src_infs if not cmds.objExists(inf)]
    if not_exists_infs:
        raise RuntimeError(f"Source influences not found: {not_exists_infs}")

    not_bound_infs = [inf for inf in src_infs if inf not in infs]
    if not_bound_infs:
        raise RuntimeError(f"Source influences not bound: {not_bound_infs}")

    weights = lib_skinCluster.get_skin_weights(skinCluster, components)

    for i in range(len(weights)):
        src_total_weights = sum([weights[i][infs.index(src_inf)] for src_inf in src_infs])

        if src_total_weights == 0.0:
            continue

        for src_inf in src_infs:
            weights[i][infs.index(src_inf)] = 0.0

        weights[i][infs.index(target_inf)] = weights[i][infs.index(target_inf)] + src_total_weights

    logger.debug(f"Combined source influences weights: {components}")

    lib_skinCluster.set_skin_weights(skinCluster, weights, components)


def prune_small_weights(shapes: list[str], threshold: float = 0.0001) -> None:
    """Prune the small weights of the skinCluster.

    Args:
        shapes (list[str]): The deformable shapes.
        threshold (float): The threshold value.

    Notes:
        - Unlike Maya's pruneWeights, which considers skeleton locks, this function ignores them.
    """
    if not shapes:
        raise ValueError("No shapes specified")

    not_exist_shapes = [shape for shape in shapes if not cmds.objExists(shape)]
    if not_exist_shapes:
        raise ValueError(f"Nodes do not exist: {not_exist_shapes}")

    for shape in shapes:
        if "deformableShape" not in cmds.nodeType(shape, inherited=True):
            cmds.warning(f"Node is not a deformable shape: {shape}")
            continue

        skinCluster = lib_skinCluster.get_skinCluster(shape)
        if not skinCluster:
            cmds.warning(f"Object is not bound to a skinCluster: {shape}")
            continue

        infs = cmds.skinCluster(skinCluster, q=True, inf=True)
        lock_status = [cmds.getAttr(f"{inf}.lockInfluenceWeights") for inf in infs]
        for inf in infs:
            cmds.setAttr(f"{inf}.lockInfluenceWeights", False)

        cmds.skinPercent(skinCluster, shape, pruneWeights=threshold)

        for i, inf in enumerate(infs):
            cmds.setAttr(f"{inf}.lockInfluenceWeights", lock_status[i])

        logger.debug(f"Pruned small weights: {shape}")


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
