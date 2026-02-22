"""PLY file import for mesh importer.

Creates Maya meshes from PLY data with optional vertex color support.
Uses trimesh for file parsing and Maya API (OpenMaya) for mesh creation.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

import maya.api.OpenMaya as om2
import maya.cmds as cmds

logger = getLogger(__name__)


def create_mesh_from_ply(file_path: str) -> tuple[str, bool]:
    """Read a PLY file and create a Maya mesh.

    Args:
        file_path: Path to the PLY file.

    Returns:
        tuple[str, bool]: (transform_node_name, has_vertex_colors).

    Raises:
        ImportError: If trimesh is not installed.
        RuntimeError: If mesh creation fails.
    """
    try:
        import trimesh
    except ImportError:
        raise ImportError("trimesh is required for PLY import. Install it via FakeTools > Dependency Installer.") from None

    logger.info(f"Loading PLY file: {file_path}")
    mesh = trimesh.load(file_path, process=False, force="mesh")

    vertices = mesh.vertices
    faces = mesh.faces
    logger.info(f"Loaded mesh: {len(vertices)} vertices, {len(faces)} faces")

    # Extract vertex colors if available
    vertex_colors = None
    has_vertex_colors = False
    if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
        colors = mesh.visual.vertex_colors
        if colors.shape[0] == len(vertices) and colors.shape[1] >= 3:
            vertex_colors = colors
            has_vertex_colors = True
            logger.info(f"Found vertex colors: {colors.shape}")

    # Create mesh name from filename
    mesh_name = Path(file_path).stem

    transform_name = _create_maya_mesh(mesh_name, vertices, faces)

    if has_vertex_colors:
        _apply_vertex_colors(transform_name, vertex_colors)

    _assign_default_material(transform_name)

    return transform_name, has_vertex_colors


def _create_maya_mesh(name: str, vertices, faces) -> str:
    """Create a Maya polygon mesh using the API.

    Args:
        name: Desired mesh name.
        vertices: Numpy array of vertex positions (N, 3).
        faces: Numpy array of face vertex indices (M, 3).

    Returns:
        str: Transform node name.
    """
    num_vertices = len(vertices)
    num_faces = len(faces)

    # Build MFloatPointArray for vertices
    points = om2.MFloatPointArray()
    for i in range(num_vertices):
        points.append(om2.MFloatPoint(float(vertices[i][0]), float(vertices[i][1]), float(vertices[i][2])))

    # Build polygon connectivity arrays
    face_counts = om2.MIntArray()
    face_connects = om2.MIntArray()
    for i in range(num_faces):
        face_counts.append(len(faces[i]))
        for vi in faces[i]:
            face_connects.append(int(vi))

    # Create the mesh
    fn_mesh = om2.MFnMesh()
    mesh_obj = fn_mesh.create(points, face_counts, face_connects)

    # Get the DAG path to rename
    dag_node = om2.MFnDagNode(mesh_obj)
    transform_name = dag_node.name()

    # Rename to desired name
    transform_name = cmds.rename(transform_name, name)

    logger.info(f"Created mesh: {transform_name} ({num_vertices} verts, {num_faces} faces)")
    return transform_name


def _apply_vertex_colors(transform_name: str, vertex_colors) -> None:
    """Apply vertex colors to a mesh using the API.

    Args:
        transform_name: Transform node name.
        vertex_colors: Numpy array of RGBA colors (N, 4) as uint8 (0-255).
    """
    # Get the mesh shape
    shapes = cmds.listRelatives(transform_name, shapes=True, type="mesh")
    if not shapes:
        logger.warning(f"No mesh shape found under {transform_name}")
        return

    shape_name = shapes[0]

    # Get MFnMesh from shape
    sel = om2.MSelectionList()
    sel.add(shape_name)
    dag_path = sel.getDagPath(0)
    fn_mesh = om2.MFnMesh(dag_path)

    # Create color set
    color_set_name = "colorSet1"
    fn_mesh.createColorSet(color_set_name, True)
    fn_mesh.setCurrentColorSetName(color_set_name)

    # Build MColorArray from vertex colors (normalize uint8 to 0.0-1.0)
    num_vertices = len(vertex_colors)
    colors = om2.MColorArray()
    vertex_ids = om2.MIntArray()

    for i in range(num_vertices):
        r = float(vertex_colors[i][0]) / 255.0
        g = float(vertex_colors[i][1]) / 255.0
        b = float(vertex_colors[i][2]) / 255.0
        a = float(vertex_colors[i][3]) / 255.0 if vertex_colors.shape[1] >= 4 else 1.0
        colors.append(om2.MColor((r, g, b, a)))
        vertex_ids.append(i)

    # Apply colors in batch
    fn_mesh.setVertexColors(colors, vertex_ids)

    # Enable vertex color display in viewport
    cmds.setAttr(f"{shape_name}.displayColors", 1)

    logger.info(f"Applied vertex colors to {shape_name} ({num_vertices} colors)")


def _assign_default_material(transform_name: str) -> None:
    """Assign the default material (initialShadingGroup) to the mesh.

    Args:
        transform_name: Transform node name.
    """
    try:
        cmds.sets(transform_name, edit=True, forceElement="initialShadingGroup")
        logger.debug(f"Assigned initialShadingGroup to {transform_name}")
    except Exception as e:
        logger.warning(f"Failed to assign default material to {transform_name}: {e}")
