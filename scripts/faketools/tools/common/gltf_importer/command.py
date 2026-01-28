"""glTF Importer command layer.

Re-exports from submodules for backward compatibility.
Provides the main import_gltf_file function.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds

from .blender import convert_glb_to_fbx, find_blender_executable
from .constants import SHADER_TYPES
from .fbx_import import import_fbx
from .material import MaterialConverter
from .texture import TextureManager

logger = getLogger(__name__)

__all__ = [
    # constants
    "SHADER_TYPES",
    # blender
    "find_blender_executable",
    "convert_glb_to_fbx",
    # fbx_import
    "import_fbx",
    # material
    "MaterialConverter",
    # texture
    "TextureManager",
    # main function
    "import_gltf_file",
]


def import_gltf_file(
    file_path: str | None = None,
    output_dir: str | None = None,
    shader_type: str = "auto",
) -> list[str]:
    """Import glTF/GLB file into Maya.

    Main import function that orchestrates the entire import process:
    1. Convert GLB to FBX using Blender
    2. Import FBX into Maya
    3. Update texture paths
    4. Optionally convert materials

    Args:
        file_path: Path to glTF/GLB file. If None, opens file dialog.
        output_dir: Directory for FBX output. If None, uses same directory as input file.
        shader_type: Material shader type ('arnold', 'stingray', 'standard', 'auto').

    Returns:
        list[str]: List of imported node names.
    """
    logger.info("=" * 60)
    logger.info("glTF Importer - Starting")
    logger.info("=" * 60)

    try:
        # Select file if not provided
        if file_path is None:
            file_path = cmds.fileDialog2(
                fileMode=1,
                caption="Select glTF/GLB File",
                fileFilter="GLB Files (*.glb);;glTF Files (*.gltf);;All Files (*.*)",
                dialogStyle=2,
            )

            if not file_path:
                logger.info("Cancelled by user")
                return []

            file_path = file_path[0]

        file_path = Path(file_path)
        logger.info(f"Input file: {file_path}")
        logger.info(f"Shader type: {shader_type}")

        # Convert GLB to FBX
        result = convert_glb_to_fbx(str(file_path), output_dir=output_dir)
        if not result:
            logger.error("FBX conversion failed")
            cmds.warning("glTF Importer: FBX conversion failed. Check if Blender is installed.")
            return []

        fbx_path, texture_dir = result

        # Import FBX into Maya
        imported_nodes = import_fbx(fbx_path)
        if not imported_nodes:
            logger.error("Maya import failed")
            cmds.warning("glTF Importer: Maya import failed.")
            return []

        # Process textures
        logger.info("Processing textures")
        texture_manager = TextureManager(texture_dir)
        textures = texture_manager.collect_textures()

        if textures:
            logger.info(f"Found {len(textures)} textures")
            updated_count = texture_manager.update_texture_paths()
            logger.info(f"Updated {updated_count} texture paths")
        else:
            logger.info("No textures found")

        # Convert materials (optional - FBX already brings materials)
        if shader_type != "auto":
            converter = MaterialConverter(shader_type)
            converter.convert_materials(imported_nodes)

        # Refresh viewport
        cmds.refresh()

        # Success message
        logger.info("=" * 60)
        logger.info("glTF Import Complete!")
        logger.info(f"Imported objects: {len(imported_nodes)}")
        logger.info("=" * 60)

        print(f"\nglTF Import Complete! Imported {len(imported_nodes)} objects.")

        return imported_nodes

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        cmds.warning(f"glTF Importer: Unexpected error - {e}")
        return []
