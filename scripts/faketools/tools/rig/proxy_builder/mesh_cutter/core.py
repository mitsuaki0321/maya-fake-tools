"""Mesh Cutter main orchestration."""

from collections.abc import Callable
from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


def _get_cut_fn(cutter_name: str) -> Callable[[str, str], list[int]]:
    """Return the appropriate cut function for a cutter node.

    Args:
        cutter_name (str): Node name of the cutter (polygon mesh or NURBS surface).

    Returns:
        Callable: The ``cut(cutter, target)`` callable from mesh or nurbs module.

    Raises:
        ValueError: If the cutter shape type is not supported.
    """
    shape = cmds.listRelatives(cutter_name, shapes=True)[0]
    node_type = cmds.nodeType(shape)

    if node_type == "nurbsSurface":
        from .nurbs import cut

        return cut
    if node_type == "mesh":
        from .mesh import cut

        return cut
    raise ValueError(f"Unsupported cutter type: {node_type}")


def run(
    cutters: list[str],
    target: str,
    separate_edges: bool = True,
    extract_faces: bool = True,
    duplicate: bool = False,
) -> list[str]:
    """Cut a target mesh using one or more cutters, then separate the pieces.

    For each cutter the appropriate cut module is selected automatically.
    After all cuts are applied the resulting edges are detached and the mesh
    is separated into individual pieces via ``polySeparate``.

    Args:
        cutters (list[str]): Mixed mesh / NURBS cutter node names.
        target (str): Node name of the target polygon mesh.
        separate_edges (bool): If True, detach cut edges before separating.
        extract_faces (bool): If True, allow polySeparate to extract faces into new pieces.
        duplicate (bool): If True, duplicate the target before cutting.

    Returns:
        list[str]: Separated piece transform names.
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
        cut_fn = _get_cut_fn(cutter)
        new_edges = cut_fn(cutter, target)
        if new_edges:
            first = new_edges[0]
            last = new_edges[-1]
            if separate_edges:
                logger.debug(
                    "detaching edges e[%d:%d] from cutter %s",
                    first,
                    last,
                    cutter,
                )
                cmds.polySplitEdge(
                    f"{target}.e[{first}:{last}]",
                    operation=1,
                    ch=False,
                )
                any_detach = True
            else:
                logger.debug(
                    "cutter %s produced edges e[%d:%d] but separate_edges=False",
                    cutter,
                    first,
                    last,
                )
        else:
            logger.debug("cutter %s produced no new edges", cutter)

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

    # polySeparate may return shapes; resolve to parent transforms
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
