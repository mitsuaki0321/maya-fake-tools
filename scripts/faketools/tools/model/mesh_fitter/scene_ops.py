"""Maya scene operations — thin wrappers around Maya commands.

All maya imports are lazy (inside functions) so this module can be
imported outside Maya without errors. These functions are intentionally
thin and not unit-tested — they delegate directly to Maya commands.
"""

from __future__ import annotations


def list_meshes() -> list[str]:
    """Return names of all mesh shapes in the current Maya scene."""
    import maya.cmds as cmds

    meshes = cmds.ls(type="mesh", long=True) or []
    # Return transform names (parent of shape)
    transforms = set()
    for m in meshes:
        parent = cmds.listRelatives(m, parent=True, fullPath=True)
        if parent:
            transforms.add(parent[0])
    return sorted(transforms)


def open_undo_chunk(name: str = "meshfit") -> None:
    """Open a Maya undo chunk so all operations can be undone as one step."""
    import maya.cmds as cmds

    cmds.undoInfo(openChunk=True, chunkName=name)


def close_undo_chunk() -> None:
    """Close the current Maya undo chunk."""
    import maya.cmds as cmds

    cmds.undoInfo(closeChunk=True)


def select_mesh(mesh_name: str) -> None:
    """Select a mesh in the Maya scene."""
    import maya.cmds as cmds

    cmds.select(mesh_name, replace=True)


def wait_cursor(state: bool) -> None:
    """Set or clear the Maya wait cursor."""
    import maya.cmds as cmds

    cmds.waitCursor(state=state)


def get_selected_transforms() -> list[str]:
    """Return transform node names currently selected, in selection order."""
    import maya.cmds as cmds

    return cmds.ls(sl=True, type="transform", long=True) or []


def get_selected_mesh() -> str | None:
    """Return the first selected transform that has a mesh shape, or None."""
    import maya.cmds as cmds

    for t in cmds.ls(sl=True, type="transform", long=True) or []:
        shapes = cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or []
        if shapes:
            return t
    return None


def is_transform(name: str) -> bool:
    """Check whether a node is a transform (or subclass like joint)."""
    import maya.cmds as cmds

    if not cmds.objExists(name):
        return False
    return cmds.objectType(name, isAType="transform")


def get_transform_world_position(name: str) -> list[float]:
    """Return world-space translation [x, y, z] of a transform node."""
    import maya.cmds as cmds

    return cmds.xform(name, query=True, worldSpace=True, translation=True)


def select_nodes(names: list[str]) -> None:
    """Select the given nodes in Maya, replacing current selection."""
    import maya.cmds as cmds

    cmds.select(names, replace=True)


def duplicate_mesh(mesh_name: str, new_name: str) -> str:
    """Duplicate a mesh in the Maya scene.

    Args:
        mesh_name: Source mesh transform name.
        new_name: Name for the duplicate.

    Returns:
        The name of the duplicated mesh.
    """
    import maya.cmds as cmds

    dupes = cmds.duplicate(mesh_name, name=new_name)
    return dupes[0]
