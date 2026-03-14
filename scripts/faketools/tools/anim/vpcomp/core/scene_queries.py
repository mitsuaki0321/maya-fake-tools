"""Maya scene query utilities for vpcomp.

Panel listing, camera enumeration, objectSet creation / member management,
and DAG path resolution.
"""

from __future__ import annotations

from logging import getLogger

import maya.api.OpenMaya as om  # type: ignore
import maya.cmds as cmds  # type: ignore

logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OBJECT_SET_PREFIX = "vpcomp_"
OBJECT_SET_SUFFIX = "_set"

DEFAULT_CAMERA_IGNORE = {
    "topShape",
    "frontShape",
    "sideShape",
    "leftShape",
    "rightShape",
    "bottomShape",
}

UNKNOWN_CAMERA_LABEL = "<unknown>"

# ---------------------------------------------------------------------------
# Panel queries
# ---------------------------------------------------------------------------


def list_model_panels() -> list[str]:
    """Return existing modelPanel names."""
    panels = cmds.getPanel(type="modelPanel") or []
    return [p for p in panels if cmds.modelPanel(p, q=True, exists=True)]


def query_panel_camera(panel: str) -> str:
    """Return the camera assigned to *panel*, or a fallback label."""
    try:
        return cmds.modelPanel(panel, q=True, cam=True)
    except Exception as exc:
        logger.warning("query_panel_camera(%s) failed: %s", panel, exc)
        return UNKNOWN_CAMERA_LABEL


def get_active_model_panel() -> str | None:
    """Return the currently focused modelPanel, or *None*."""
    focused = cmds.getPanel(withFocus=True)
    if focused and cmds.getPanel(typeOf=focused) == "modelPanel":
        return focused
    return None


# ---------------------------------------------------------------------------
# Camera queries
# ---------------------------------------------------------------------------


def list_all_cameras() -> list[str]:
    """Return all camera shape nodes in the scene."""
    return cmds.ls(type="camera") or []


def list_user_cameras() -> list[str]:
    """Return camera shapes excluding Maya's default cameras."""
    return [c for c in list_all_cameras() if c not in DEFAULT_CAMERA_IGNORE]


def camera_shape(camera: str) -> str:
    """Resolve a camera transform or shape to its shape node.

    Raises:
        RuntimeError: If no camera shape is found.
    """
    if cmds.nodeType(camera) == "camera":
        return camera
    shapes = cmds.listRelatives(camera, shapes=True, fullPath=False) or []
    for shape in shapes:
        if cmds.nodeType(shape) == "camera":
            return shape
    raise RuntimeError(f"Camera shape not found: {camera}")


def camera_dag_path(camera_shape_name: str):
    """Return the MDagPath for a camera shape node."""
    sel = om.MSelectionList()
    sel.add(camera_shape_name)
    return sel.getDagPath(0)


_FILM_FIT_STR_TO_INT: dict[str, int] = {
    "fill": 0,
    "horizontal": 1,
    "vertical": 2,
    "overscan": 3,
}


def parse_film_fit(value) -> int:
    """Normalise a filmFit value to an integer.

    Maya may return an int or a string (e.g. ``"horizontal"``) depending
    on the version.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _FILM_FIT_STR_TO_INT.get(value.lower(), 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# ObjectSet operations
# ---------------------------------------------------------------------------


def make_set_name(camera: str) -> str:
    """Generate the vpcomp objectSet name for a camera.

    Convention: ``vpcomp_<camera>_set``
    """
    return f"{OBJECT_SET_PREFIX}{camera}{OBJECT_SET_SUFFIX}"


def create_object_set(set_name: str) -> str:
    """Create an empty objectSet if it does not already exist.

    Returns the set name.
    """
    if cmds.objExists(set_name):
        logger.debug("ObjectSet already exists: %s", set_name)
        return set_name
    cmds.sets(name=set_name, empty=True)
    logger.info("Created objectSet: %s", set_name)
    return set_name


def add_set_members(set_name: str, nodes: list[str]) -> None:
    """Add *nodes* to an existing objectSet.

    Only transform nodes are accepted; non-transform nodes are skipped
    with a warning.
    """
    if not nodes:
        return
    transforms = [n for n in nodes if "transform" in (cmds.nodeType(n, i=True) or [])]
    skipped = len(nodes) - len(transforms)
    if skipped:
        logger.warning("Skipped %d non-transform node(s) for %s", skipped, set_name)
    if not transforms:
        return
    cmds.sets(transforms, addElement=set_name)
    logger.debug("Added %d transform(s) to %s", len(transforms), set_name)


def remove_set_members(set_name: str, nodes: list[str]) -> None:
    """Remove *nodes* from an existing objectSet."""
    if not nodes:
        return
    cmds.sets(nodes, remove=set_name)
    logger.debug("Removed %d node(s) from %s", len(nodes), set_name)


def get_selection() -> list[str]:
    """Return the current Maya selection."""
    return cmds.ls(selection=True, long=True) or []
