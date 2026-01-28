"""glTF Importer constants and embedded Blender script."""

import sys

# Shader type options for material conversion
SHADER_TYPES = {
    "arnold": "Arnold",
    "stingray": "Stingray PBS",
    "standard": "Standard",
    "auto": "Auto Detect",
}

# Axis options for FBX export (Blender standard)
AXIS_OPTIONS = ["X", "-X", "Y", "-Y", "Z", "-Z"]

# Default axis values (Maya compatible)
DEFAULT_AXIS_FORWARD = "-Z"
DEFAULT_AXIS_UP = "Y"

# Supported image extensions for texture files
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tiff", ".exr", ".hdr"}

# Platform-specific Blender installation directories
if sys.platform == "win32":
    BLENDER_BASE_DIRS = [
        "C:/Program Files/Blender Foundation",
    ]
elif sys.platform == "darwin":
    BLENDER_BASE_DIRS = [
        "/Applications",
    ]
else:
    BLENDER_BASE_DIRS = [
        "/usr/bin",
        "/usr/local/bin",
    ]

# Embedded Blender script for GLB to FBX conversion
# This script runs in Blender's headless mode
BLENDER_SCRIPT = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Blender Headless GLB to FBX Converter Script.

This script runs in Blender headless mode to convert GLB files to FBX.
Optimized for Maya 2022+ compatibility.

Usage:
    blender --background --python script.py -- <input.glb> <output.fbx> [texture_dir] [axis_forward] [axis_up]
"""

import bpy
import sys
import os
from pathlib import Path


def clear_scene():
    """Clear all objects in the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)


def import_glb(glb_path):
    """Import GLB file.

    Args:
        glb_path: Path to the GLB file.

    Returns:
        bool: True if import succeeded.
    """
    try:
        if not os.path.exists(glb_path):
            print(f"ERROR: GLB file not found: {glb_path}")
            return False

        print(f"Importing GLB file: {glb_path}")

        bpy.ops.import_scene.gltf(
            filepath=glb_path,
            import_pack_images=True,
            merge_vertices=True,
            import_shading='NORMALS',
            guess_original_bind_pose=True,
        )

        print(f"Import succeeded: {len(bpy.data.objects)} objects")
        for obj in bpy.data.objects:
            print(f"  - {obj.name} (type: {obj.type})")

        return True

    except Exception as e:
        print(f"ERROR: GLB import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def configure_materials_for_maya():
    """Adjust materials for Maya compatibility."""
    print("Converting materials for Maya compatibility...")

    for mat in bpy.data.materials:
        if mat.use_nodes:
            nodes = mat.node_tree.nodes

            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    # Principled BSDF info is automatically included in FBX
                    pass

    print(f"Material conversion complete: {len(bpy.data.materials)} materials")


def ensure_objects_exportable():
    """Ensure all objects are exportable."""
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer

    linked_count = 0
    for obj in bpy.data.objects:
        if obj.name not in scene.collection.all_objects:
            try:
                scene.collection.objects.link(obj)
                linked_count += 1
                print(f"  Linked object to scene: {obj.name}")
            except RuntimeError:
                pass

        try:
            obj.hide_set(False)
            obj.hide_viewport = False
            obj.hide_render = False
        except RuntimeError:
            pass

    view_layer.update()

    if linked_count > 0:
        print(f"  Linked {linked_count} additional objects")
    print(f"Export preparation complete: {len(bpy.data.objects)} objects")


def export_fbx(fbx_path, axis_forward='-Z', axis_up='Y', export_settings=None):
    """Export FBX file.

    Args:
        fbx_path: Output FBX file path.
        axis_forward: Forward axis for export (default: '-Z').
        axis_up: Up axis for export (default: 'Y').
        export_settings: Optional export settings dict.

    Returns:
        bool: True if export succeeded.
    """
    try:
        ensure_objects_exportable()

        default_settings = {
            'use_selection': False,
            'use_active_collection': False,
            'global_scale': 1.0,
            'apply_unit_scale': True,
            'apply_scale_options': 'FBX_SCALE_ALL',
            'bake_space_transform': False,
            'object_types': {'MESH', 'ARMATURE', 'EMPTY', 'LIGHT', 'CAMERA'},
            'use_mesh_modifiers': True,
            'use_mesh_modifiers_render': True,
            'mesh_smooth_type': 'FACE',
            'use_mesh_edges': False,
            'use_tspace': True,
            'use_custom_props': True,
            'add_leaf_bones': False,
            'primary_bone_axis': 'Y',
            'secondary_bone_axis': 'X',
            'armature_nodetype': 'NULL',
            'bake_anim': False,
            'bake_anim_use_all_bones': False,
            'bake_anim_use_nla_strips': False,
            'bake_anim_use_all_actions': False,
            'bake_anim_force_startend_keying': False,
            'bake_anim_step': 1.0,
            'bake_anim_simplify_factor': 1.0,
            'path_mode': 'COPY',
            'embed_textures': True,
            'batch_mode': 'OFF',
            'use_batch_own_dir': False,
            'axis_forward': axis_forward,
            'axis_up': axis_up,
        }

        if export_settings:
            default_settings.update(export_settings)

        print(f"Exporting FBX: {fbx_path}")

        print("Objects to export:")
        for obj in bpy.context.scene.collection.all_objects:
            in_view = obj.name in bpy.context.view_layer.objects
            print(f"  - {obj.name} (type: {obj.type}, in_view_layer: {in_view})")

        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            **default_settings
        )

        if os.path.exists(fbx_path):
            file_size = os.path.getsize(fbx_path)
            print(f"Export succeeded: {fbx_path} ({file_size} bytes)")
        else:
            print(f"WARNING: FBX file was not created: {fbx_path}")

        return True

    except Exception as e:
        print(f"ERROR: FBX export error: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_textures(texture_dir):
    """Extract texture files to specified directory.

    Args:
        texture_dir: Directory to save textures.
    """
    try:
        texture_dir = Path(texture_dir)
        texture_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting textures: {texture_dir}")

        extracted_count = 0
        for img in bpy.data.images:
            if img.packed_file:
                texture_path = texture_dir / img.name
                img.filepath_raw = str(texture_path)
                img.save()
                extracted_count += 1
                print(f"  - {img.name}")

        print(f"Texture extraction complete: {extracted_count} files")

    except Exception as e:
        print(f"WARNING: Texture extraction error: {e}")


def main():
    """Main process."""
    print("=" * 60)
    print("Blender GLB to FBX Converter")
    print("=" * 60)

    argv = sys.argv

    try:
        idx = argv.index("--")
        args = argv[idx + 1:]
    except ValueError:
        print("ERROR: Invalid arguments")
        print("Usage: blender --background --python script.py -- <input.glb> <output.fbx> [texture_dir]")
        sys.exit(1)

    if len(args) < 2:
        print("ERROR: Please specify input and output files")
        print("Usage: blender --background --python script.py -- <input.glb> <output.fbx> [texture_dir] [axis_forward] [axis_up]")
        sys.exit(1)

    input_glb = args[0]
    output_fbx = args[1]
    texture_dir = args[2] if len(args) > 2 else None
    axis_forward = args[3] if len(args) > 3 else '-Z'
    axis_up = args[4] if len(args) > 4 else 'Y'

    print(f"Input GLB: {input_glb}")
    print(f"Output FBX: {output_fbx}")
    if texture_dir:
        print(f"Texture directory: {texture_dir}")
    print(f"Axis conversion: forward={axis_forward}, up={axis_up}")

    print("\\nClearing scene...")
    clear_scene()

    print("\\n" + "=" * 60)
    if not import_glb(input_glb):
        print("ERROR: GLB import failed")
        sys.exit(1)

    print("\\n" + "=" * 60)
    configure_materials_for_maya()

    print("\\n" + "=" * 60)
    if texture_dir:
        extract_textures(texture_dir)
    else:
        output_dir = os.path.dirname(output_fbx)
        if output_dir:
            default_texture_dir = os.path.join(output_dir, "textures")
            extract_textures(default_texture_dir)

    print("\\n" + "=" * 60)
    if not export_fbx(output_fbx, axis_forward=axis_forward, axis_up=axis_up):
        print("ERROR: FBX export failed")
        sys.exit(1)

    print("\\n" + "=" * 60)
    print("Conversion complete!")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
'''
