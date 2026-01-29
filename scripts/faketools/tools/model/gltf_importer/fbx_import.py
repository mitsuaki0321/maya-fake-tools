"""Maya FBX import functionality."""

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds
import maya.mel as mel

logger = getLogger(__name__)


def ensure_fbx_plugin_loaded() -> bool:
    """Ensure FBX plugin is loaded.

    Returns:
        bool: True if plugin is loaded successfully.
    """
    try:
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            cmds.loadPlugin("fbxmaya")
            logger.info("FBX plugin loaded")
        return True
    except Exception as e:
        logger.error(f"Failed to load FBX plugin: {e}")
        return False


def import_fbx(fbx_path: str) -> list[str]:
    """Import FBX file into Maya.

    Args:
        fbx_path: Path to the FBX file.

    Returns:
        list[str]: List of imported node names.
    """
    logger.info("Importing FBX to Maya")

    fbx_path = Path(fbx_path)
    if not fbx_path.exists():
        logger.error(f"FBX file not found: {fbx_path}")
        return []

    if not ensure_fbx_plugin_loaded():
        return []

    try:
        # Get node list before import
        nodes_before = set(cmds.ls(assemblies=True))

        # Configure FBX import options
        mel.eval("FBXResetImport")
        mel.eval("FBXImportMode -v merge")  # Merge into current scene
        mel.eval("FBXImportMergeAnimationLayers -v false")
        mel.eval("FBXImportProtectDrivenKeys -v true")
        mel.eval("FBXImportConvertDeformingNullsToJoint -v true")
        mel.eval("FBXImportMergeBackNullPivots -v true")

        # Import FBX (convert backslashes to forward slashes for MEL)
        logger.info(f"Importing: {fbx_path}")
        fbx_path_mel = str(fbx_path).replace("\\", "/")
        mel.eval(f'FBXImport -f "{fbx_path_mel}"')

        # Get node list after import
        nodes_after = set(cmds.ls(assemblies=True))
        imported_nodes = list(nodes_after - nodes_before)

        # Fallback: search for related nodes if none detected
        if not imported_nodes:
            logger.warning("No nodes detected via assemblies, searching for related nodes...")
            fbx_name = fbx_path.stem
            related_nodes = cmds.ls(f"*{fbx_name}*", type="transform") or []
            related_nodes += cmds.ls("Joint_*", type="transform") or []
            imported_nodes = list(set(related_nodes))
            if imported_nodes:
                logger.info(f"Found related nodes: {len(imported_nodes)} objects")

        logger.info(f"Import succeeded: {len(imported_nodes)} objects")
        for node in imported_nodes:
            logger.debug(f"  - {node}")

        return imported_nodes

    except Exception as e:
        logger.error(f"FBX import error: {e}")
        return []
