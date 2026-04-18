"""Separate mesh by cutting planes using the mesh_cutter library."""

from logging import getLogger

import maya.cmds as cmds

from .mesh_cutter import run as mesh_cutter_run

logger = getLogger(__name__)


def cut_and_separate(
    mesh: str,
    cutters: list[str],
    duplicate: bool = True,
) -> list[str]:
    """Cut a mesh using polygon cutter meshes and separate the pieces.

    Args:
        mesh (str): Target polygon mesh transform name.
        cutters (list[str]): Polygon cutter mesh names.
        duplicate (bool): If True, duplicate the target before cutting.

    Returns:
        list[str]: Separated mesh transform names.
    """
    logger.debug("cut_and_separate: mesh=%s, cutters=%s, duplicate=%s", mesh, cutters, duplicate)

    pieces = mesh_cutter_run(
        cutters=cutters,
        target=mesh,
        separate_edges=True,
        extract_faces=True,
        duplicate=duplicate,
    )

    # Clean up construction history on each piece
    for piece in pieces:
        if cmds.objExists(piece):
            cmds.delete(piece, constructionHistory=True)

    logger.debug("cut_and_separate produced %d pieces", len(pieces))
    return pieces
