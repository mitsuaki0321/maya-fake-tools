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


def get_blendshape_weights(mesh_name: str) -> list[str]:
    """Return weight alias names from the first blendShape node on the mesh.

    Args:
        mesh_name: Transform name of the mesh.

    Returns:
        List of weight alias names (e.g. ["smile", "frown"]).
        Empty list if no blendShape node is found.
    """
    import maya.cmds as cmds

    shapes = cmds.listRelatives(mesh_name, shapes=True, type="mesh", fullPath=True) or []
    if not shapes:
        return []

    history = cmds.listHistory(shapes[0], pruneDagObjects=True) or []
    bs_nodes = cmds.ls(history, type="blendShape") or []
    if not bs_nodes:
        return []

    aliases = cmds.aliasAttr(bs_nodes[0], query=True) or []
    # aliasAttr returns alternating [alias, attr, alias, attr, ...]
    return [aliases[i] for i in range(0, len(aliases), 2)]


def match_transform(node: str, target: str) -> None:
    """Copy the world-space transform matrix from *target* to *node*.

    Args:
        node: Transform node to modify.
        target: Transform node whose world matrix is copied.
    """
    import maya.cmds as cmds

    mat = cmds.xform(target, query=True, worldSpace=True, matrix=True)
    cmds.xform(node, worldSpace=True, matrix=mat)


def get_selected_face_indices() -> tuple[str, list[int]] | None:
    """Return (mesh_long_name, [face_indices]) from current face selection, or None if no faces selected.

    Raises:
        ValueError: If faces from multiple meshes are selected.
    """
    import maya.cmds as cmds

    faces = cmds.filterExpand(selectionMask=34, expand=True) or []
    if not faces:
        return None

    mesh_names = set()
    indices = []
    for f in faces:
        mesh, comp = f.split(".f[")
        mesh_names.add(mesh)
        indices.append(int(comp.rstrip("]")))

    if len(mesh_names) > 1:
        raise ValueError("Faces from multiple meshes selected")

    mesh_name = mesh_names.pop()
    long_names = cmds.ls(mesh_name, long=True)
    mesh_name = long_names[0] if long_names else mesh_name
    return mesh_name, sorted(indices)


def select_faces(mesh_name: str, face_indices: list[int]) -> None:
    """Select face components on a mesh in Maya.

    Args:
        mesh_name: Transform name of the mesh.
        face_indices: List of face indices to select.
    """
    import maya.cmds as cmds

    components = [f"{mesh_name}.f[{i}]" for i in face_indices]
    cmds.select(components, replace=True)


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
