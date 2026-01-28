"""Texture path management for glTF importer."""

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds

from .constants import IMAGE_EXTENSIONS

logger = getLogger(__name__)


class TextureManager:
    """Texture file management class."""

    def __init__(self, texture_dir: str):
        """Initialize texture manager.

        Args:
            texture_dir: Directory containing textures.
        """
        self.texture_dir = Path(texture_dir)

    def collect_textures(self) -> list[str]:
        """Collect texture files from the texture directory.

        Returns:
            list[str]: List of texture file paths.
        """
        texture_files = []

        if not self.texture_dir.exists():
            logger.warning(f"Texture directory does not exist: {self.texture_dir}")
            return texture_files

        # Search texture directory
        for file_path in self.texture_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                texture_files.append(str(file_path))

        # Also search parent directory (for textures next to FBX)
        parent_dir = self.texture_dir.parent
        for file_path in parent_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                texture_files.append(str(file_path))

        logger.info(f"Found {len(texture_files)} texture files")
        return texture_files

    def update_texture_paths(self) -> int:
        """Update Maya file node texture paths to use the texture directory.

        Returns:
            int: Number of updated file nodes.
        """
        if not self.texture_dir.exists():
            logger.warning(f"Texture directory does not exist: {self.texture_dir}")
            return 0

        file_nodes = cmds.ls(type="file") or []
        updated_count = 0

        for file_node in file_nodes:
            try:
                current_path = cmds.getAttr(f"{file_node}.fileTextureName")
                if not current_path:
                    continue

                # Get just the filename
                texture_name = Path(current_path).name

                # Construct new path in texture directory
                new_path = self.texture_dir / texture_name
                if new_path.exists():
                    cmds.setAttr(f"{file_node}.fileTextureName", str(new_path), type="string")
                    logger.debug(f"  {file_node}: {texture_name}")
                    updated_count += 1
                else:
                    # Try parent directory
                    alt_path = self.texture_dir.parent / texture_name
                    if alt_path.exists():
                        cmds.setAttr(f"{file_node}.fileTextureName", str(alt_path), type="string")
                        logger.debug(f"  {file_node}: {texture_name} (from parent)")
                        updated_count += 1

            except Exception as e:
                logger.warning(f"  Failed to update {file_node}: {e}")

        logger.info(f"Updated {updated_count} texture paths")
        return updated_count

    @staticmethod
    def guess_texture_type(texture_name: str) -> str:
        """Guess texture type from filename.

        Args:
            texture_name: Texture filename.

        Returns:
            str: Texture type (baseColor, normal, metallic, roughness, ao, emissive, opacity, height, unknown).
        """
        name_lower = texture_name.lower()

        if "basecolor" in name_lower or "albedo" in name_lower or "diffuse" in name_lower or "color" in name_lower:
            return "baseColor"
        elif "normal" in name_lower or "norm" in name_lower:
            return "normal"
        elif "metallic" in name_lower or "metal" in name_lower:
            return "metallic"
        elif "roughness" in name_lower or "rough" in name_lower:
            return "roughness"
        elif "ao" in name_lower or "ambient" in name_lower or "occlusion" in name_lower:
            return "ao"
        elif "emissive" in name_lower or "emission" in name_lower:
            return "emissive"
        elif "opacity" in name_lower or "alpha" in name_lower or "transparency" in name_lower:
            return "opacity"
        elif "height" in name_lower or "displacement" in name_lower or "disp" in name_lower:
            return "height"
        else:
            return "unknown"
