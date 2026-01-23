"""Texture Relocator command layer.

Pure Maya operations for relocating texture file paths.
"""

from dataclasses import dataclass
import glob
import logging
from pathlib import Path
import re
import shutil

import maya.cmds as cmds

logger = logging.getLogger(__name__)


@dataclass
class TextureInfo:
    """Information about a file texture node."""

    node: str
    file_path: str
    pattern: str
    is_udim: bool
    is_sequence: bool


def get_all_file_nodes() -> list[str]:
    """Get all file texture nodes in the scene.

    Returns:
        list[str]: List of file node names.
    """
    nodes = cmds.ls(type="file") or []
    return nodes


def get_texture_info(file_node: str) -> TextureInfo:
    """Get texture information from a file node.

    Args:
        file_node: Name of the file node.

    Returns:
        TextureInfo: Information about the texture.
    """
    file_path = cmds.getAttr(f"{file_node}.fileTextureName") or ""
    pattern = cmds.getAttr(f"{file_node}.computedFileTextureNamePattern") or ""

    uv_tiling_mode = cmds.getAttr(f"{file_node}.uvTilingMode")
    use_frame_ext = cmds.getAttr(f"{file_node}.useFrameExtension")

    is_udim = uv_tiling_mode > 0
    is_sequence = bool(use_frame_ext)

    return TextureInfo(
        node=file_node,
        file_path=file_path,
        pattern=pattern if pattern else file_path,
        is_udim=is_udim,
        is_sequence=is_sequence,
    )


def resolve_texture_files(file_node: str) -> list[str]:
    """Resolve actual texture files from UDIM/sequence pattern.

    Args:
        file_node: Name of the file node.

    Returns:
        list[str]: List of resolved file paths.
    """
    patterns = ["<UDIM>", "<f>", "<F>"]

    tex_path = cmds.getAttr(f"{file_node}.computedFileTextureNamePattern")
    if not tex_path:
        return []

    # Check if pattern contains UDIM/sequence tokens
    pattern_regex = ".*({}).*".format("|".join(patterns))
    if re.match(pattern_regex, tex_path):
        file_name = Path(tex_path).name
        dir_path = Path(tex_path).parent

        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            return []

        # Replace tokens with glob wildcard
        glob_pattern = re.sub("|".join(patterns), "*", file_name)
        matched_files = glob.glob(str(dir_path / glob_pattern))

        # Normalize path separators
        result = [p.replace("\\", "/") for p in matched_files]
        logger.debug(f"Resolved {len(result)} files for pattern: {tex_path}")
        return result
    else:
        # No pattern tokens, return single file if exists
        if Path(tex_path).exists():
            return [tex_path]
        return []


@dataclass
class CopyResult:
    """Result of a copy operation."""

    success: bool
    copied_files: list[str]
    skipped_files: list[str]
    error_message: str = ""


def copy_and_relink(
    file_node: str,
    dest_dir: Path,
    overwrite: bool = False,
) -> CopyResult:
    """Copy texture files to destination and update file node path.

    Args:
        file_node: Name of the file node.
        dest_dir: Destination directory path.
        overwrite: If True, overwrite existing files without asking.

    Returns:
        CopyResult: Result of the copy operation.
    """
    files = resolve_texture_files(file_node)
    copied = []
    skipped = []

    if not files:
        return CopyResult(
            success=False,
            copied_files=[],
            skipped_files=[],
            error_message=f"No files found for node: {file_node}",
        )

    for src_path_str in files:
        src_path = Path(src_path_str)
        if not src_path.exists():
            logger.warning(f"Source file not found: {src_path}")
            continue

        dest_path = dest_dir / src_path.name

        if dest_path.exists() and not overwrite:
            skipped.append(str(dest_path))
            continue

        try:
            shutil.copy2(src_path, dest_path)
            copied.append(str(dest_path))
        except Exception as e:
            logger.error(f"Failed to copy {src_path} to {dest_path}: {e}")
            return CopyResult(
                success=False,
                copied_files=copied,
                skipped_files=skipped,
                error_message=str(e),
            )

    # Update file node path
    pattern = cmds.getAttr(f"{file_node}.computedFileTextureNamePattern")
    if pattern:
        filename = Path(pattern).name
    else:
        filename = Path(cmds.getAttr(f"{file_node}.fileTextureName")).name

    new_path = str(dest_dir / filename)
    cmds.setAttr(f"{file_node}.fileTextureName", new_path, type="string")

    return CopyResult(
        success=True,
        copied_files=copied,
        skipped_files=skipped,
    )


def replace_path(file_node: str, new_dir: Path) -> bool:
    """Replace texture path with files in new directory.

    Assumes the same filename exists in the new directory.

    Args:
        file_node: Name of the file node.
        new_dir: New directory containing the texture files.

    Returns:
        bool: True if successful, False otherwise.
    """
    pattern = cmds.getAttr(f"{file_node}.computedFileTextureNamePattern")
    if pattern:
        filename = Path(pattern).name
    else:
        filename = Path(cmds.getAttr(f"{file_node}.fileTextureName")).name

    if not filename:
        logger.warning(f"No filename found for node: {file_node}")
        return False

    new_path = new_dir / filename

    # For non-UDIM/sequence textures, verify file exists
    uv_tiling_mode = cmds.getAttr(f"{file_node}.uvTilingMode")
    use_frame_ext = cmds.getAttr(f"{file_node}.useFrameExtension")

    if uv_tiling_mode == 0 and not use_frame_ext and not new_path.exists():
        logger.warning(f"Target file not found: {new_path}")
        return False

    cmds.setAttr(f"{file_node}.fileTextureName", str(new_path), type="string")
    return True


@dataclass
class BatchResult:
    """Result of a batch operation."""

    total_nodes: int
    success_count: int
    failed_nodes: list[str]
    skipped_files: list[str]


def batch_copy_and_relink(
    dest_dir: Path,
    overwrite: bool = False,
) -> BatchResult:
    """Copy all texture files in the scene to destination.

    Args:
        dest_dir: Destination directory path.
        overwrite: If True, overwrite existing files without asking.

    Returns:
        BatchResult: Result of the batch operation.
    """
    file_nodes = get_all_file_nodes()
    success_count = 0
    failed_nodes = []
    all_skipped = []

    for node in file_nodes:
        result = copy_and_relink(node, dest_dir, overwrite)
        if result.success:
            success_count += 1
        else:
            failed_nodes.append(node)
        all_skipped.extend(result.skipped_files)

    return BatchResult(
        total_nodes=len(file_nodes),
        success_count=success_count,
        failed_nodes=failed_nodes,
        skipped_files=all_skipped,
    )


def batch_replace_path(new_dir: Path) -> BatchResult:
    """Replace all texture paths in the scene with new directory.

    Args:
        new_dir: New directory containing the texture files.

    Returns:
        BatchResult: Result of the batch operation.
    """
    file_nodes = get_all_file_nodes()
    success_count = 0
    failed_nodes = []

    for node in file_nodes:
        if replace_path(node, new_dir):
            success_count += 1
        else:
            failed_nodes.append(node)

    return BatchResult(
        total_nodes=len(file_nodes),
        success_count=success_count,
        failed_nodes=failed_nodes,
        skipped_files=[],
    )


def get_files_to_overwrite(dest_dir: Path) -> list[str]:
    """Get list of files that would be overwritten.

    Args:
        dest_dir: Destination directory path.

    Returns:
        list[str]: List of file paths that exist in destination.
    """
    file_nodes = get_all_file_nodes()
    existing_files = []

    for node in file_nodes:
        files = resolve_texture_files(node)
        for src_path_str in files:
            src_path = Path(src_path_str)
            dest_path = dest_dir / src_path.name
            if dest_path.exists():
                existing_files.append(str(dest_path))

    return existing_files
