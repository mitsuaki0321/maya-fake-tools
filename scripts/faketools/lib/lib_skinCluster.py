"""
SkinCluster node functions.
"""

from collections.abc import Sequence
from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)

PLUGIN_NAME = "skinClusterWeight"


def load_skinWeights_plugin() -> None:
    """Load the skinWeights plugin."""
    if not cmds.pluginInfo(f"{PLUGIN_NAME}.py", query=True, loaded=True):
        cmds.loadPlugin(f"{PLUGIN_NAME}.py")


def get_skinCluster(shape: str) -> str | None:
    """Get the skinCluster node.

    Args:
        shape (str): The shape node.

    Returns:
        Optional[str]: The skinCluster node.
    """
    if not cmds.objExists(shape):
        cmds.error(f"Node does not exist: {shape}")

    if "deformableShape" not in cmds.nodeType(shape, inherited=True):
        cmds.error(f"Failed to get skinCluster. Node is not deformableShape: {shape}")

    if "|" not in shape and len(cmds.ls(shape)) > 1:
        cmds.error(f"Multiple nodes found with the name: {shape}. Please specify the full path.")

    shape = cmds.ls(shape)[0]
    history = cmds.listHistory(shape, pruneDagObjects=True, interestLevel=2) or []
    skinClusters = cmds.ls(history, type="skinCluster") or []
    if not skinClusters:
        return None

    for sc in skinClusters:
        geos = cmds.skinCluster(sc, q=True, geometry=True) or []
        if shape in geos:
            return sc

    return skinClusters[0]


def rebind_skinCluster_from_influence(infs: Sequence[str]) -> None:
    """Rebind the skinCluster node from the influences.

    Args:
        infs (Sequence[str]): The influences.
    """
    not_exists = [inf for inf in infs if not cmds.objExists(inf)]
    if not_exists:
        cmds.error(f"Node does not exist: {not_exists}")

    rebind_skinClusters = []
    for inf in infs:
        matrix_plugs = cmds.listConnections(f"{inf}.worldMatrix", s=False, d=True, type="skinCluster", p=True)
        if not matrix_plugs:
            continue

        for matrix_plug in matrix_plugs:
            bind_pre_matrix = matrix_plug.replace("matrix", "bindPreMatrix")
            if cmds.connectionInfo(bind_pre_matrix, isDestination=True):
                cmds.warning(f"BindPreMatrix is connected: {bind_pre_matrix}")
                continue

            world_inverse_matrix = cmds.getAttr(f"{inf}.worldInverseMatrix")
            cmds.setAttr(bind_pre_matrix, world_inverse_matrix, type="matrix")

            skinCluster = cmds.ls(matrix_plug, objectsOnly=True)[0]
            if skinCluster not in rebind_skinClusters:
                rebind_skinClusters.append(skinCluster)

    for skinCluster in rebind_skinClusters:
        cmds.skinCluster(skinCluster, e=True, recacheBindMatrices=True)

    logger.debug(f"Rebind skinCluster from influence: {rebind_skinClusters}")


def rebind_skinCluster(skinCluster: str) -> None:
    """Rebind the skinCluster node.

    Args:
        skinCluster (str): The skinCluster node.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    if cmds.listConnections(f"{skinCluster}.bindPreMatrix", s=True, d=False):
        cmds.error(f"BindPreMatrix is connected: {skinCluster}")

    indices = cmds.getAttr(f"{skinCluster}.matrix", multiIndices=True)
    for index in indices:
        inf = cmds.listConnections(f"{skinCluster}.matrix[{index}]", s=True, d=False, type="joint")
        if not inf:
            cmds.warning(f"Influence not found: {skinCluster}.matrix[{index}]")
            continue

        world_inverse_matrix = cmds.getAttr(f"{inf[0]}.worldInverseMatrix")
        cmds.setAttr(f"{skinCluster}.bindPreMatrix[{index}]", world_inverse_matrix, type="matrix")

    cmds.skinCluster(skinCluster, e=True, recacheBindMatrices=True)

    logger.debug(f"Rebind skinCluster: {skinCluster}")


def exchange_influences(skinCluster: str, src_infs: Sequence[str], tgt_infs: Sequence[str]) -> None:
    """Exchange the influences on the skinCluster node.

    Args:
        skinCluster (str): The target skinCluster node.
        src_infs (Sequence[str]): The source influences.
        tgt_infs (Sequence[str]): The target influences.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    if not src_infs or not tgt_infs:
        cmds.error("No influences specified")

    infs = cmds.skinCluster(skinCluster, query=True, influence=True)

    not_bind_infs = list(set(src_infs) - set(infs))
    if not_bind_infs:
        cmds.error(f"Unbound influences are included in the skinCluster: {not_bind_infs}")

    not_bind_infs = list(set(tgt_infs) - set(infs))
    if len(not_bind_infs) != len(tgt_infs):
        bind_infs = list(set(tgt_infs) - set(not_bind_infs))
        cmds.error(f"Influences already bound are included in the target influences: {bind_infs}")

    # Check connectable influences to the source skinCluster
    not_connectable_state = False
    indices = cmds.getAttr(f"{skinCluster}.matrix", multiIndices=True)
    for index in indices:
        plug_inf = cmds.listConnections(f"{skinCluster}.matrix[{index}]", s=True, d=False, type="joint")[0]
        if plug_inf not in src_infs:
            logger.debug(f"Influence not found: {plug_inf} in {src_infs}")
            continue

        bind_pre_matrix = f"{skinCluster}.bindPreMatrix[{index}]"
        if cmds.connectionInfo(bind_pre_matrix, isDestination=True):
            not_connectable_state = True
            logger.debug(f"BindPreMatrix is connected: {bind_pre_matrix}")
        elif cmds.getAttr(bind_pre_matrix, lock=True):
            not_connectable_state = True
            logger.debug(f"BindPreMatrix is locked: {bind_pre_matrix}")

    if not_connectable_state:
        cmds.error("SkinCluster is not connectable to the influences")

    # Exchange influences
    for index in indices:
        plug_inf = cmds.listConnections(f"{skinCluster}.matrix[{index}]", s=True, d=False, type="joint")[0]
        if plug_inf not in src_infs:
            logger.debug(f"Influence not found: {plug_inf} in {src_infs}")
            continue

        tgt_inf = tgt_infs[src_infs.index(plug_inf)]

        # Set bindPreMatrix
        world_inverse_matrix = cmds.getAttr(f"{tgt_inf}.worldInverseMatrix")
        cmds.setAttr(f"{skinCluster}.bindPreMatrix[{index}]", world_inverse_matrix, type="matrix")

        # Set lockInfluenceWeights
        lock_influence_weights = cmds.getAttr(f"{skinCluster}.lockWeights[{index}]")
        if not cmds.attributeQuery("lockInfluenceWeights", node=tgt_inf, ex=True):
            cmds.addAttr(tgt_inf, ln="lockInfluenceWeights", sn="liw", at="bool")

        cmds.setAttr(f"{tgt_inf}.lockInfluenceWeights", lock_influence_weights)
        cmds.connectAttr(f"{tgt_inf}.lockInfluenceWeights", f"{skinCluster}.lockWeights[{index}]", f=True)

        # Connect influenceColor
        cmds.connectAttr(f"{tgt_inf}.objectColorRGB", f"{skinCluster}.influenceColor[{index}]", f=True)

        # Connect matrix
        cmds.connectAttr(f"{tgt_inf}.worldMatrix[0]", f"{skinCluster}.matrix[{index}]", f=True)

        logger.debug(f"Exchange influence: {plug_inf} -> {tgt_inf}")

    cmds.skinCluster(skinCluster, e=True, recacheBindMatrices=True)

    logger.debug(f"Exchange influences: {skinCluster}")


def get_influences_from_skinCluster(skinClusters: Sequence[str]) -> list[str]:
    """Get the influences from the skinCluster nodes.

    Args:
        skinClusters (Sequence[str]): The skinCluster nodes.

    Returns:
        list[str]: The influences.
    """
    if not skinClusters:
        raise ValueError("No skinCluster nodes specified")

    result_infs = []
    for skinCluster in skinClusters:
        if not cmds.objExists(skinCluster):
            cmds.error(f"Node does not exist: {skinCluster}")

        if cmds.nodeType(skinCluster) != "skinCluster":
            cmds.error(f"Node is not a skinCluster: {skinCluster}")

        infs = cmds.skinCluster(skinCluster, query=True, influence=True)
        for inf in infs:
            if inf not in result_infs:
                result_infs.append(inf)

    return result_infs


def get_lock_influences(skinCluster: str, lock: bool = True) -> list[str]:
    """Get the lock influences.

    Args:
        skinCluster (str): The skinCluster node.
        lock (bool): If True, get the lock influences. If False, get the unlock influences.

    Returns:
        list[str]: The lock influences.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    infs = cmds.skinCluster(skinCluster, query=True, influence=True)
    result_infs = []
    for inf in infs:
        lock_state = cmds.getAttr(f"{inf}.lockInfluenceWeights")
        if lock == lock_state:
            result_infs.append(inf)

    return result_infs


def set_lock_influences(infs: Sequence[str], lock: bool = True) -> None:
    """Set the lock influences.

    Args:
        infs (Sequence[str]): The influences.
        lock (bool): If True, set the lock influences. If False, set the unlock influences.
    """
    not_exists = [inf for inf in infs if not cmds.objExists(inf)]
    if not_exists:
        cmds.error(f"Node does not exist: {not_exists}")

    for inf in infs:
        if not cmds.attributeQuery("lockInfluenceWeights", node=inf, ex=True):
            cmds.warning(f"Influence is not connected to the skinCluster: {inf}")
            continue

        skinCluster = cmds.listConnections(f"{inf}.lockInfluenceWeights", s=False, d=True, type="skinCluster")
        if not skinCluster:
            cmds.warning(f"Influence is not connected to the skinCluster: {inf}")
            continue

        cmds.setAttr(f"{inf}.lockInfluenceWeights", lock)

        logger.debug(f"Set lock influence: {inf} -> {lock}")


def copy_skin_weights_custom(
    src_skinCluster: str,
    dst_skinCluster: str,
    only_unlock_influences: bool = False,
    blend_weights: float = 1.0,
    reference_orig: bool = False,
    add_missing_influences: bool = True,
) -> None:
    """Copy the skin weights using the custom plugin.

    Args:
        src_skinCluster (str): The source skinCluster node.
        dst_skinCluster (str): The destination skinCluster node.
        only_unlock_influences (bool): Whether to copy weights within unlocked influences. Default is False.
        blend_weights (float): The blend weights. Default is 1.0.
        reference_orig (bool): Whether to reference points from the original shape. Default is False.
        add_missing_influences (bool): Whether to add missing influences src to dst skinCluster. Default is True.
    """
    if not src_skinCluster or not dst_skinCluster:
        raise ValueError(f"No skinCluster node specified: {src_skinCluster}, {dst_skinCluster}")

    if not cmds.objExists(src_skinCluster) or not cmds.objExists(dst_skinCluster):
        raise ValueError(f"SkinCluster node does not exist: {src_skinCluster}, {dst_skinCluster}")

    if cmds.nodeType(src_skinCluster) != "skinCluster" or cmds.nodeType(dst_skinCluster) != "skinCluster":
        raise ValueError(f"Node is not a skinCluster: {src_skinCluster}, {dst_skinCluster}")

    load_skinWeights_plugin()

    src_infs = cmds.skinCluster(src_skinCluster, query=True, influence=True)
    dst_infs = cmds.skinCluster(dst_skinCluster, query=True, influence=True)

    diff_infs = list(set(src_infs) - set(dst_infs))
    if diff_infs:
        if add_missing_influences:
            cmds.skinCluster(dst_skinCluster, e=True, lw=True, wt=0.0, ai=diff_infs)
        else:
            cmds.error(f"Influences do not match: {diff_infs}")

    cmds.copySkinWeightsCustom(
        ss=src_skinCluster,
        ds=dst_skinCluster,
        onlyUnlockInfluences=only_unlock_influences,
        blendWeights=blend_weights,
        referenceOrigShape=reference_orig,
    )

    logger.debug(f"Copy skin weights custom: {src_skinCluster} -> {dst_skinCluster}")


def get_skin_weights_custom(skinCluster: str, components: Sequence[str] | None = None, all_components: bool = False) -> list[float]:
    """Get the skin weights.

    Args:
        skinCluster (str): The skinCluster node.
        components (Sequence[str] | None): The specified components.
        all_components (bool): If True, export all components.

    Returns:
        list[float]: The skin weights.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    load_skinWeights_plugin()

    if all_components:
        weights = cmds.skinWeightExport(skinCluster, allComponents=True)
    else:
        if not components:
            cmds.error("No components specified")
        if not is_bound_to_skinCluster(skinCluster, components):
            cmds.error(f"Components are not bound to the skinCluster: {components}")

        weights = cmds.skinWeightExport(skinCluster, components=components)

    return weights


def set_skin_weights_custom(skinCluster: str, weights: dict, components: Sequence[str] | None) -> None:
    """Set the skin weights.

    Args:
        skinCluster (str): The skinCluster node.
        weights (dict): The skin weights.
        components (Sequence[str] | None): The specified components.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    load_skinWeights_plugin()

    cmds.skinWeightImport(skinCluster, weights=weights, components=components)

    logger.debug(f"Set skin weights: {skinCluster}")


def get_skin_weights(skinCluster: str, components: Sequence[str] | None = None, all_components: bool = False) -> list[float]:
    """Get the skin weights.

    Args:
        skinCluster (str): The skinCluster node.
        components (Sequence[str] | None): The specified components.
        all_components (bool): If True, export all components.

    Returns:
        list[float]: The skin weights.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    if all_components:
        components = cmds.skinCluster(skinCluster, query=True, components=True)
    else:
        if not components:
            cmds.error("No components specified")

        if not is_bound_to_skinCluster(skinCluster, components):
            cmds.error(f"Components are not bound to the skinCluster: {components}")

    weights = []
    for component in cmds.ls(components, flatten=True):
        weights.append(cmds.skinPercent(skinCluster, component, q=True, v=True))

    logger.debug(f"Get skin weights: {skinCluster}")

    return weights


def set_skin_weights(skinCluster: str, weights: list[list[float]], components: Sequence[str] | None) -> None:
    """Set the skin weights.

    Args:
        skinCluster (str): The skinCluster node.
        weights (list[list[float]]): The skin weights.
        components (Sequence[str] | None): The specified components.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    if not is_bound_to_skinCluster(skinCluster, components):
        cmds.error(f"Components are not bound to the skinCluster: {components}")

    infs = cmds.skinCluster(skinCluster, query=True, influence=True)
    components = cmds.ls(components, flatten=True)
    for component, weight in zip(components, weights, strict=False):
        cmds.skinPercent(skinCluster, component, transformValue=zip(infs, weight, strict=False))

    logger.debug(f"Set skin weights: {skinCluster}")


def flatten_skin_weights(nested_weights: list[list[float]]) -> list[float]:
    """Flatten the nested skin weights.

    Args:
        nested_weights (list[list[float]]): The nested skin weights.

    Returns:
        list[float]: The flattened skin weights.
    """
    return [weight for component_weights in nested_weights for weight in component_weights]


def unflatten_skin_weights(flat_weights: list[float], num_influences: int) -> list[list[float]]:
    """Unflatten the flat skin weights.

    Args:
        flat_weights (list[float]): The flat skin weights.
        num_influences (int): The number of influences.

    Returns:
        list[list[float]]: The unflattened skin weights.
    """
    return [flat_weights[i : i + num_influences] for i in range(0, len(flat_weights), num_influences)]


def is_bound_to_skinCluster(skinCluster: str, components: Sequence[str]) -> bool:
    """Check if the components are bound to the skinCluster node.

    Args:
        skinCluster (str): The skinCluster node.
        components (Sequence[str]): The components.

    Returns:
        bool: Whether the components are bound to the skinCluster node.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    skin_components = cmds.ls(cmds.skinCluster(skinCluster, query=True, components=True), flatten=True)
    components = cmds.ls(components, flatten=True)

    diff_components = list(set(components) - set(skin_components))
    return not diff_components


def remove_unused_influences(skinCluster: str) -> None:
    """Remove the unused influences from the skinCluster node.

    Args:
        skinCluster (str): The skinCluster node.
    """
    if not skinCluster:
        raise ValueError("No skinCluster node specified")

    if not cmds.objExists(skinCluster):
        cmds.error(f"Node does not exist: {skinCluster}")

    if cmds.nodeType(skinCluster) != "skinCluster":
        cmds.error(f"Node is not a skinCluster: {skinCluster}")

    infs = cmds.skinCluster(skinCluster, query=True, influence=True)
    weight_infs = cmds.skinCluster(skinCluster, query=True, weightedInfluence=True)
    if infs == weight_infs:
        return

    unused_infs = list(set(infs) - set(weight_infs))
    for inf in unused_infs:
        cmds.skinCluster(skinCluster, e=True, removeInfluence=inf)

    logger.debug(f"Remove unused influences: {skinCluster} >> {unused_infs}")
