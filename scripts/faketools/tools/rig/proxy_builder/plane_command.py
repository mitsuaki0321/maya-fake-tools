"""Proxy Builder - cutting plane creation API."""

from __future__ import annotations

from logging import getLogger
import math
import re

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ....lib.lib_math import vector_to_rotation
from ....lib.lib_mesh import MeshPoint
from ....lib.lib_selection import get_shapes
from ....lib_ui.shared_config import get_shared_config
from ....operations.mirror import mirror_transforms

logger = getLogger(__name__)

_DEFAULT_PLANE_PREFIX = "cut_plane"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_joint(joint: str) -> str:
    """Validate that *joint* exists and is a joint node.

    Args:
        joint (str): Joint node name.

    Returns:
        str: Validated joint name (resolved if necessary).

    Raises:
        ValueError: If the joint does not exist, is not unique, or is not a joint.
    """
    if not joint:
        raise ValueError("Joint is not specified.")

    found = cmds.ls(joint)
    if not found:
        raise ValueError(f"Joint does not exist: {joint}")
    if len(found) > 1:
        long_names = cmds.ls(joint, long=True)
        raise ValueError(f"Multiple nodes found with name '{joint}'. Please use full path:\n" + "\n".join(f"  - {n}" for n in long_names))

    if cmds.nodeType(found[0]) != "joint":
        raise ValueError(f"Node is not a joint: {found[0]}")

    return found[0]


def _resolve_aim_joint(joint: str) -> str:
    """Auto-resolve the aim joint for aim-based rotation.

    Resolution rules:
        1. Exactly one child joint → use child.
        2. Zero or multiple child joints → use parent joint.
        3. No parent and no children → raise ValueError.

    Args:
        joint (str): Source joint (must already be validated).

    Returns:
        str: Resolved aim joint name.

    Raises:
        ValueError: If neither parent nor child joints exist.
    """
    children = cmds.listRelatives(joint, children=True, type="joint") or []
    if len(children) == 1:
        return children[0]

    parent = cmds.listRelatives(joint, parent=True, type="joint") or []
    if parent:
        return parent[0]

    raise ValueError(f"Cannot auto-resolve aim joint for '{joint}': no child joints and no parent joint.")


def _resolve_aim_direction(
    joint: str,
    aim_target: str,
    aim_joint: str | None,
) -> om.MVector:
    """Resolve the aim direction vector for aim-based rotation.

    When *aim_joint* is explicitly provided, it always takes precedence
    and *aim_target* is ignored.

    Args:
        joint (str): Source joint (must already be validated).
        aim_target (str): ``"auto"``, ``"parent"``, or ``"chain"``.
        aim_joint (str | None): Explicit aim joint, or ``None`` to use *aim_target* logic.

    Returns:
        om.MVector: Normalised direction vector from *joint* toward the target.

    Raises:
        ValueError: If the required joints for the chosen mode do not exist.
    """
    joint_pos = om.MVector(cmds.xform(joint, query=True, translation=True, worldSpace=True))

    # Explicit aim_joint overrides aim_target
    if aim_joint is not None:
        aim_joint = _validate_joint(aim_joint)
        aim_pos = om.MVector(cmds.xform(aim_joint, query=True, translation=True, worldSpace=True))
        return (aim_pos - joint_pos).normal()

    if aim_target == "auto":
        resolved = _resolve_aim_joint(joint)
        logger.debug("Auto-resolved aim joint: %s -> %s", joint, resolved)
        aim_pos = om.MVector(cmds.xform(resolved, query=True, translation=True, worldSpace=True))
        return (aim_pos - joint_pos).normal()

    if aim_target == "parent":
        parent = cmds.listRelatives(joint, parent=True, type="joint") or []
        if not parent:
            raise ValueError(f"Cannot use aim_target='parent' for '{joint}': no parent joint.")
        parent_pos = om.MVector(cmds.xform(parent[0], query=True, translation=True, worldSpace=True))
        return (parent_pos - joint_pos).normal()

    if aim_target == "chain":
        parent = cmds.listRelatives(joint, parent=True, type="joint") or []
        children = cmds.listRelatives(joint, children=True, type="joint") or []
        if not parent:
            raise ValueError(f"Cannot use aim_target='chain' for '{joint}': no parent joint.")
        if len(children) != 1:
            raise ValueError(f"Cannot use aim_target='chain' for '{joint}': expected exactly 1 child joint, found {len(children)}.")
        parent_pos = om.MVector(cmds.xform(parent[0], query=True, translation=True, worldSpace=True))
        child_pos = om.MVector(cmds.xform(children[0], query=True, translation=True, worldSpace=True))
        return (child_pos - parent_pos).normal()

    raise ValueError(f"Invalid aim_target: '{aim_target}'. Must be 'auto', 'parent', or 'chain'.")


def _validate_plane_type(plane_type: str) -> None:
    """Validate plane_type parameter.

    Args:
        plane_type (str): ``"nurbs"`` or ``"poly"``.

    Raises:
        ValueError: If *plane_type* is unsupported.
    """
    if plane_type not in ("nurbs", "poly"):
        raise ValueError(f"Invalid plane_type: '{plane_type}'. Must be 'nurbs' or 'poly'.")


def _validate_target_mesh(target_mesh: str) -> str:
    """Validate that *target_mesh* exists and return its mesh shape name.

    Args:
        target_mesh (str): Transform node name.

    Returns:
        str: Mesh shape name.

    Raises:
        ValueError: If the node does not exist or has no mesh shape.
    """
    if not cmds.objExists(target_mesh):
        raise ValueError(f"Target mesh does not exist: {target_mesh}")

    shapes = get_shapes([target_mesh], shape_type="mesh")
    if not shapes:
        raise ValueError(f"'{target_mesh}' has no mesh shape.")

    return shapes[0]


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------


def _generate_plane_name(base_name: str | None) -> str:
    """Return a plane name.

    Args:
        base_name (str | None): Explicit name, or ``None`` for auto-generated.

    Returns:
        str: The name to pass to the Maya creation command.
    """
    if base_name:
        return base_name
    return _DEFAULT_PLANE_PREFIX


def _generate_mirror_name(source_name: str) -> str:
    """Generate a mirrored name by swapping L/R patterns.

    Uses the shared mirror_patterns config. If no pattern matches,
    appends ``_mirrored``.

    Args:
        source_name (str): Source plane name.

    Returns:
        str: Mirrored name.
    """
    config = get_shared_config()
    patterns = config.get("mirror_patterns", {})

    # Try left_to_right
    lr = patterns.get("left_to_right")
    if lr:
        result = re.sub(lr[0], lr[1], source_name)
        if result != source_name:
            return result

    # Try right_to_left
    rl = patterns.get("right_to_left")
    if rl:
        result = re.sub(rl[0], rl[1], source_name)
        if result != source_name:
            return result

    return f"{source_name}_mirrored"


# ---------------------------------------------------------------------------
# Geometry creation
# ---------------------------------------------------------------------------


def _create_nurbs_plane(
    size: tuple[float, float],
    axis: tuple[float, float, float],
    spans: tuple[int, int],
    name: str,
) -> str:
    """Create a NURBS plane.

    Args:
        size (tuple[float, float]): (width, height).
        axis (tuple[float, float, float]): Normal axis.
        spans (tuple[int, int]): (patchesU, patchesV).
        name (str): Node name.

    Returns:
        str: Transform name.
    """
    width, height = size
    length_ratio = height / width if width != 0 else 1.0

    result = cmds.nurbsPlane(
        width=width,
        lengthRatio=length_ratio,
        patchesU=spans[0],
        patchesV=spans[1],
        axis=axis,
        name=name,
    )
    return result[0]


def _create_poly_plane(
    size: tuple[float, float],
    axis: tuple[float, float, float],
    spans: tuple[int, int],
    name: str,
) -> str:
    """Create a polygon plane and delete its construction history.

    Args:
        size (tuple[float, float]): (width, height).
        axis (tuple[float, float, float]): Normal axis.
        spans (tuple[int, int]): (subdivisionsX, subdivisionsY).
        name (str): Node name.

    Returns:
        str: Transform name.
    """
    result = cmds.polyPlane(
        width=size[0],
        height=size[1],
        subdivisionsX=spans[0],
        subdivisionsY=spans[1],
        axis=axis,
        name=name,
    )
    transform = result[0]
    cmds.delete(transform, constructionHistory=True)
    return transform


# ---------------------------------------------------------------------------
# Orientation helpers
# ---------------------------------------------------------------------------


def _get_joint_local_axes(joint: str) -> tuple[om.MVector, om.MVector, om.MVector]:
    """Extract the local X, Y, Z axes from a joint's worldMatrix.

    Args:
        joint (str): Joint node name.

    Returns:
        tuple[om.MVector, om.MVector, om.MVector]: (localX, localY, localZ).
    """
    mat = om.MMatrix(cmds.getAttr(f"{joint}.worldMatrix"))
    local_x = om.MVector(mat[0], mat[1], mat[2]).normal()
    local_y = om.MVector(mat[4], mat[5], mat[6]).normal()
    local_z = om.MVector(mat[8], mat[9], mat[10]).normal()
    return local_x, local_y, local_z


def _axis_to_primary(axis: tuple[float, float, float]) -> str:
    """Determine the primary axis label from an axis vector.

    Picks the closest cardinal axis (x, y, z) by comparing absolute dot products.

    Args:
        axis (tuple[float, float, float]): Normal axis vector.

    Returns:
        str: ``"x"``, ``"y"``, or ``"z"``.
    """
    vec = om.MVector(axis).normal()
    dots = [abs(vec * om.MVector(1, 0, 0)), abs(vec * om.MVector(0, 1, 0)), abs(vec * om.MVector(0, 0, 1))]
    return ("x", "y", "z")[dots.index(max(dots))]


def _find_aim_axis_and_up(
    joint: str,
    aim_dir: om.MVector,
    axis: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Compute the rotation to orient a plane's normal along *aim_dir*.

    Algorithm:
        1. Get joint's local X, Y, Z from worldMatrix.
        2. Find which local axis has the largest |dot product| with *aim_dir*.
        3. That axis becomes the normal direction (sign-matched to *aim_dir*).
        4. Pick an up vector from the remaining axes.
        5. Use ``vector_to_rotation`` to convert to Euler angles.

    Args:
        joint (str): Source joint.
        aim_dir (om.MVector): Normalised direction vector for the plane normal.
        axis (tuple[float, float, float]): Primitive normal axis for primary_axis mapping.

    Returns:
        tuple[float, float, float]: Euler rotation in degrees.
    """
    # Local axes
    local_x, local_y, local_z = _get_joint_local_axes(joint)
    local_axes = [local_x, local_y, local_z]

    # Find best matching axis
    dots = [abs(aim_dir * ax) for ax in local_axes]
    best_idx = dots.index(max(dots))

    # Normal = best axis, sign-matched to aim_dir
    normal = local_axes[best_idx]
    if normal * aim_dir < 0:
        normal = -normal

    # Up = first remaining axis
    remaining = [i for i in range(3) if i != best_idx]
    up = local_axes[remaining[0]]

    # Determine primary/secondary axis from the axis parameter
    primary_axis = _axis_to_primary(axis)
    axis_labels = ["x", "y", "z"]
    secondary_candidates = [a for a in axis_labels if a != primary_axis]
    secondary_axis = secondary_candidates[0]

    rotation = vector_to_rotation(normal, up, primary_axis, secondary_axis)
    return (rotation[0], rotation[1], rotation[2])


def _get_joint_world_rotation(joint: str) -> tuple[float, float, float]:
    """Extract the world-space Euler rotation from a joint's worldMatrix.

    Args:
        joint (str): Joint node name.

    Returns:
        tuple[float, float, float]: Euler rotation in degrees.
    """
    mat = om.MMatrix(cmds.getAttr(f"{joint}.worldMatrix"))
    transform = om.MTransformationMatrix(mat)
    euler = transform.rotation()
    return (math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z))


def _get_plane_surface_axes(
    rotation: tuple[float, float, float],
    axis: tuple[float, float, float],
) -> tuple[om.MVector, om.MVector]:
    """Compute the two in-plane surface axes after applying rotation.

    The plane is created with its normal along *axis*, then the given *rotation*
    is applied in world space. This function returns the two axes that lie on
    the plane surface after that rotation.

    The returned axes match Maya's primitive UV convention:
        - axis~Y: width=X, height=Z
        - axis~X: width=Y, height=Z
        - axis~Z: width=X, height=Y

    Args:
        rotation (tuple[float, float, float]): Euler rotation in degrees.
        axis (tuple[float, float, float]): Primitive normal axis.

    Returns:
        tuple[om.MVector, om.MVector]: (width_axis, height_axis) matching Maya's plane UV layout.
    """
    # Determine UV directions matching Maya's nurbsPlane / polyPlane convention
    primary = _axis_to_primary(axis)
    if primary == "x":
        width_axis = om.MVector(0, 1, 0)
        height_axis = om.MVector(0, 0, 1)
    elif primary == "y":
        width_axis = om.MVector(1, 0, 0)
        height_axis = om.MVector(0, 0, 1)
    else:
        width_axis = om.MVector(1, 0, 0)
        height_axis = om.MVector(0, 1, 0)

    # Apply rotation
    euler = om.MEulerRotation(math.radians(rotation[0]), math.radians(rotation[1]), math.radians(rotation[2]))
    rot_mat = euler.asMatrix()

    width_axis = (width_axis * rot_mat).normal()
    height_axis = (height_axis * rot_mat).normal()

    return width_axis, height_axis


# ---------------------------------------------------------------------------
# Auto-sizing
# ---------------------------------------------------------------------------


def _resolve_axis_size(pos_dist: float | None, neg_dist: float | None) -> float | None:
    """Resolve a single axis half-size from positive/negative ray distances.

    Args:
        pos_dist (float | None): Distance in the positive direction.
        neg_dist (float | None): Distance in the negative direction.

    Returns:
        float | None: Full axis size, or ``None`` if both are missing.
    """
    if pos_dist is not None and neg_dist is not None:
        return max(pos_dist, neg_dist) * 2.0
    if pos_dist is not None:
        return pos_dist * 2.0
    if neg_dist is not None:
        return neg_dist * 2.0
    return None


def _raycast_auto_size(
    origin: tuple[float, float, float],
    axis_a: om.MVector,
    axis_b: om.MVector,
    mesh_shape: str,
) -> tuple[float, float] | None:
    """Estimate plane size by raycasting from *origin* along two surface axes.

    Fires 4 rays (positive/negative for each axis) and measures distances
    to the target mesh.

    Args:
        origin (tuple[float, float, float]): Ray origin (joint position).
        axis_a (om.MVector): First in-plane axis.
        axis_b (om.MVector): Second in-plane axis.
        mesh_shape (str): Mesh shape node name.

    Returns:
        tuple[float, float] | None: (width, height) or ``None`` if all rays miss.
    """
    mesh_point = MeshPoint(mesh_shape)
    origin_pt = list(origin)
    ray_length = 1000.0

    def _cast(direction: om.MVector) -> float | None:
        end = [origin[0] + direction.x * ray_length, origin[1] + direction.y * ray_length, origin[2] + direction.z * ray_length]
        hit = mesh_point.get_intersect_point(origin_pt, end)
        if hit is None:
            return None
        hit_point, hit_param = hit[0], hit[1]
        # hit_param == 0.0 means no meaningful intersection
        if hit_param == 0.0:
            return None
        dist = om.MVector(hit_point.x - origin[0], hit_point.y - origin[1], hit_point.z - origin[2]).length()
        return dist

    pos_a = _cast(axis_a)
    neg_a = _cast(-axis_a)
    pos_b = _cast(axis_b)
    neg_b = _cast(-axis_b)

    width = _resolve_axis_size(pos_a, neg_a)
    height = _resolve_axis_size(pos_b, neg_b)

    if width is None and height is None:
        return None

    # If one axis failed, use the other
    if width is None:
        width = height
    if height is None:
        height = width

    return (width, height)


def _bounding_box_fallback_size(target_mesh: str) -> tuple[float, float]:
    """Compute a fallback plane size from the mesh's bounding box.

    Uses the largest bounding-box dimension as both width and height.

    Args:
        target_mesh (str): Transform node name.

    Returns:
        tuple[float, float]: (width, height).
    """
    bbox = cmds.exactWorldBoundingBox(target_mesh)
    dx = bbox[3] - bbox[0]
    dy = bbox[4] - bbox[1]
    dz = bbox[5] - bbox[2]
    max_dim = max(dx, dy, dz)
    return (max_dim, max_dim)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_plane(
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float] = (1.0, 1.0),
    plane_type: str = "nurbs",
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    spans: tuple[int, int] = (1, 1),
    name: str | None = None,
) -> str:
    """Create a cutting plane with explicit parameters.

    Args:
        position (tuple[float, float, float]): World-space position.
        rotation (tuple[float, float, float]): World-space Euler rotation (degrees).
        size (tuple[float, float]): (width, height) of the plane.
        plane_type (str): ``"nurbs"`` or ``"poly"``.
        axis (tuple[float, float, float]): Primitive normal axis (passed to cmds ``ax`` flag).
        spans (tuple[int, int]): Patch/subdivision counts (U, V).
        name (str | None): Explicit name, or ``None`` for auto-generated.

    Returns:
        str: Transform name of the created plane.

    Raises:
        ValueError: If *plane_type* is invalid.
    """
    _validate_plane_type(plane_type)
    resolved_name = _generate_plane_name(name)

    if plane_type == "nurbs":
        transform = _create_nurbs_plane(size, axis, spans, resolved_name)
    else:
        transform = _create_poly_plane(size, axis, spans, resolved_name)

    cmds.xform(transform, translation=position, worldSpace=True)
    cmds.xform(transform, rotation=rotation, worldSpace=True)

    logger.info("Created cut plane: %s (type=%s, size=%s)", transform, plane_type, size)
    return transform


def create_plane_at_joint(
    joint: str,
    target_mesh: str | None = None,
    plane_type: str = "nurbs",
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    rotation_mode: str = "joint",
    aim_joint: str | None = None,
    aim_target: str = "auto",
    rotation: tuple[float, float, float] | None = None,
    size: tuple[float, float] | None = None,
    spans: tuple[int, int] = (1, 1),
    size_scale: float = 1.0,
    name: str | None = None,
) -> str:
    """Create a cutting plane at a joint's position.

    Args:
        joint (str): Joint to place the plane at.
        target_mesh (str | None): Mesh for auto-size raycasting.
        plane_type (str): ``"nurbs"`` or ``"poly"``.
        axis (tuple[float, float, float]): Primitive normal axis.
        rotation_mode (str): How to determine the plane rotation:
            - ``"aim"``: Auto-compute from joint→aim direction. See *aim_target*.
            - ``"manual"``: Use the explicit *rotation* value. Requires *rotation*.
            - ``"joint"``: Use the joint's world rotation (default). No extra args needed.
        aim_joint (str | None): Target joint for ``rotation_mode="aim"``.
            If provided, *aim_target* is ignored and the direction is computed
            from joint → aim_joint.  If ``None``, resolution depends on *aim_target*.
        aim_target (str): How to resolve the aim direction when *aim_joint* is ``None``:
            - ``"auto"``: Child joint preferred, parent fallback (default).
            - ``"parent"``: Always aim toward the parent joint.
            - ``"chain"``: Use the parent→child vector (requires exactly 1 child).
        rotation (tuple[float, float, float] | None): Euler rotation (degrees) for ``rotation_mode="manual"``.
        size (tuple[float, float] | None): Explicit (width, height), or ``None`` for auto.
        spans (tuple[int, int]): Patch/subdivision counts.
        size_scale (float): Multiplier applied to auto-sized dimensions (>= 1.0).
        name (str | None): Explicit name, or ``None`` for auto-generated.

    Returns:
        str: Transform name of the created plane.

    Raises:
        ValueError: If *joint* is invalid, *plane_type* is unsupported,
            *rotation_mode* is invalid, or *aim_target* is invalid.
    """
    joint = _validate_joint(joint)
    _validate_plane_type(plane_type)

    if rotation_mode not in ("aim", "manual", "joint"):
        raise ValueError(f"Invalid rotation_mode: '{rotation_mode}'. Must be 'aim', 'manual', or 'joint'.")

    # Position
    position = tuple(cmds.xform(joint, query=True, translation=True, worldSpace=True))

    # Rotation
    if rotation_mode == "aim":
        if aim_target not in ("auto", "parent", "chain"):
            raise ValueError(f"Invalid aim_target: '{aim_target}'. Must be 'auto', 'parent', or 'chain'.")
        if rotation is not None:
            logger.warning("rotation_mode='aim': rotation parameter is ignored.")
        aim_dir = _resolve_aim_direction(joint, aim_target, aim_joint)
        resolved_rotation = _find_aim_axis_and_up(joint, aim_dir, axis)
    elif rotation_mode == "manual":
        if rotation is None:
            logger.warning("rotation_mode='manual' but rotation is not specified. Falling back to joint rotation.")
            resolved_rotation = _get_joint_world_rotation(joint)
        else:
            if aim_joint is not None:
                logger.warning("rotation_mode='manual': aim_joint parameter is ignored.")
            resolved_rotation = rotation
    else:  # "joint"
        if aim_joint is not None:
            logger.warning("rotation_mode='joint': aim_joint parameter is ignored.")
        if rotation is not None:
            logger.warning("rotation_mode='joint': rotation parameter is ignored.")
        resolved_rotation = _get_joint_world_rotation(joint)

    # Size
    if size is not None:
        resolved_size = size
    elif target_mesh is not None:
        mesh_shape = _validate_target_mesh(target_mesh)
        axis_a, axis_b = _get_plane_surface_axes(resolved_rotation, axis)
        auto = _raycast_auto_size(position, axis_a, axis_b, mesh_shape)
        if auto is not None:
            resolved_size = (auto[0] * size_scale, auto[1] * size_scale)
        else:
            logger.warning("Raycast failed, falling back to bounding box size.")
            fallback = _bounding_box_fallback_size(target_mesh)
            resolved_size = (fallback[0] * size_scale, fallback[1] * size_scale)
    else:
        resolved_size = (1.0, 1.0)

    return create_plane(
        position=position,
        rotation=resolved_rotation,
        size=resolved_size,
        plane_type=plane_type,
        axis=axis,
        spans=spans,
        name=name,
    )


def mirror_plane(source: str, axis: str = "x") -> str:
    """Duplicate and mirror a cutting plane across the specified world axis.

    Args:
        source (str): Source plane transform name.
        axis (str): Mirror axis (``"x"``, ``"y"``, or ``"z"``). Defaults to ``"x"``.

    Returns:
        str: Mirrored plane transform name.

    Raises:
        ValueError: If *source* does not exist.
    """
    if not cmds.objExists(source):
        raise ValueError(f"Source plane does not exist: {source}")

    short_name = source.rsplit("|", 1)[-1]
    mirror_name = _generate_mirror_name(short_name)

    duplicated = cmds.duplicate(source, name=mirror_name)[0]
    mirror_transforms(duplicated, axis=axis)

    logger.info("Mirrored cut plane: %s -> %s (axis=%s)", source, duplicated, axis)
    return duplicated


__all__ = ["create_plane", "create_plane_at_joint", "mirror_plane"]
