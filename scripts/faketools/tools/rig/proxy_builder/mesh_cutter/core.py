"""Mesh Cutter main orchestration.

Every cutter is a polygon mesh; :func:`.mesh.cut` is called for each, the
resulting intersection edges are detached with ``polySplitEdge``, and the
target is finally separated into pieces via ``polySeparate``.
"""

from logging import getLogger

import maya.cmds as cmds

from .mesh import cut as mesh_cut

logger = getLogger(__name__)


def run(
    cutters: list[str],
    target: str,
    separate_edges: bool = True,
    extract_faces: bool = True,
    duplicate: bool = False,
) -> list[str]:
    """Cut a target mesh with one or more polygon cutters, then separate the pieces.

    Args:
        cutters (list[str]): Polygon cutter node names.
        target (str): Node name of the target polygon mesh.
        separate_edges (bool): If True, detach cut edges before separating.
        extract_faces (bool): If True, allow ``polySeparate`` to extract
            faces into new pieces.
        duplicate (bool): If True, duplicate the target before cutting.

    Returns:
        list[str]: Separated piece transform names. When no cuts were
            applied, a one-element list containing the (possibly
            duplicated) target is returned.
    """
    if not cutters:
        return [target]

    logger.debug(
        "run: target=%s, cutters=%s, separate_edges=%s, extract_faces=%s, duplicate=%s",
        target,
        cutters,
        separate_edges,
        extract_faces,
        duplicate,
    )

    if duplicate:
        target = cmds.duplicate(target)[0]
        logger.debug("duplicated target: %s", target)

    any_detach = False
    for cutter in cutters:
        new_edges = mesh_cut(cutter, target)
        if not new_edges:
            logger.debug("cutter %s produced no new edges", cutter)
            continue
        first = new_edges[0]
        last = new_edges[-1]
        if separate_edges:
            logger.debug("detaching edges e[%d:%d] from cutter %s", first, last, cutter)
            cmds.polySplitEdge(f"{target}.e[{first}:{last}]", operation=1, ch=False)
            any_detach = True
        else:
            logger.debug("cutter %s produced edges e[%d:%d] but separate_edges=False", cutter, first, last)

    if not any_detach:
        logger.debug("no edges detached, skipping polySeparate")
        return [target]

    if not extract_faces:
        logger.debug("extract_faces=False, skipping polySeparate")
        return [target]

    pieces = cmds.polySeparate(target, ch=False) or []
    if not pieces:
        logger.debug("polySeparate returned nothing")
        return [target]

    transforms: list[str] = []
    for node in pieces:
        if cmds.nodeType(node) == "transform":
            transforms.append(node)
        else:
            parent = cmds.listRelatives(node, parent=True)
            if parent:
                transforms.append(parent[0])
    logger.debug("separated into %d pieces: %s", len(transforms), transforms)
    return transforms or [target]
