"""Animation Import/Export business logic.

Provides export and import of time-based keyframe animation data as JSON files.
Supports namespace separation, replace/merge import modes, and flexible namespace remapping.
"""

from dataclasses import asdict, dataclass
import json
from logging import getLogger
import os
from typing import Optional

import maya.cmds as cmds

from ....lib import lib_keyframe, lib_name

logger = getLogger(__name__)

FORMAT_IDENTIFIER = "faketools_animation"
FORMAT_VERSION = "1.0.0"
TIME_CURVE_TYPES = {"animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT"}
MODE_REPLACE = "replace"
MODE_MERGE = "merge"
IMPORT_MODES = (MODE_REPLACE, MODE_MERGE)


# =============================================================================
# Data Class
# =============================================================================


@dataclass
class AnimationData:
    """Animation data structure for import/export.

    Args:
        version (str): The format version.
        format (str): The format identifier for file validation.
        namespaces (dict): Nested dict of namespace -> node_name -> attr_name -> AnimCurveData.
    """

    version: str
    format: str
    namespaces: dict[str, dict[str, dict[str, lib_keyframe.AnimCurveData]]]

    @classmethod
    def from_dict(cls, data: dict) -> "AnimationData":
        """Deserialize from dictionary.

        Args:
            data (dict): The dictionary data.

        Returns:
            AnimationData: The deserialized animation data.
        """
        namespaces: dict[str, dict[str, dict[str, lib_keyframe.AnimCurveData]]] = {}
        for ns, nodes_data in data.get("namespaces", {}).items():
            namespaces[ns] = {}
            for node_name, attrs_data in nodes_data.items():
                namespaces[ns][node_name] = {}
                for attr_name, curve_data in attrs_data.items():
                    namespaces[ns][node_name][attr_name] = lib_keyframe.AnimCurveData.from_dict(curve_data)
        return cls(
            version=data.get("version", FORMAT_VERSION),
            format=data.get("format", FORMAT_IDENTIFIER),
            namespaces=namespaces,
        )


# =============================================================================
# Scene Query
# =============================================================================


def _get_animated_plugs(nodes: list[str]) -> list[str]:
    """Get all time-based animated plugs from the given nodes.

    Args:
        nodes (list[str]): The node names to inspect.

    Returns:
        list[str]: List of animated plug names (e.g., ["node.translateX", ...]).
    """
    animated_plugs = []
    for node in nodes:
        connections = cmds.listConnections(node, s=True, d=False, type="animCurve", p=True, c=True, scn=True) or []
        for i in range(0, len(connections), 2):
            node_plug = connections[i]
            curve_plug = connections[i + 1]
            if cmds.nodeType(curve_plug) in TIME_CURVE_TYPES:
                animated_plugs.append(node_plug)

    return animated_plugs


def get_all_animated_nodes() -> list[str]:
    """Get all nodes in the scene that have time-based animation curves.

    Returns:
        list[str]: List of animated node names.
    """
    anim_curves = cmds.ls(type=list(TIME_CURVE_TYPES))
    if not anim_curves:
        return []

    output_plugs = [f"{ac}.output" for ac in anim_curves]
    connected = cmds.listConnections(output_plugs, d=True, s=False, scn=True) or []
    return list(dict.fromkeys(connected))


# =============================================================================
# Data Building / Application
# =============================================================================


def build_animation_data(nodes: list[str]) -> AnimationData:
    """Build animation data from scene nodes.

    Args:
        nodes (list[str]): The node names to collect animation from.

    Returns:
        AnimationData: The structured animation data with namespace separation.
    """
    namespaces: dict[str, dict[str, dict[str, lib_keyframe.AnimCurveData]]] = {}

    for node in nodes:
        leaf_name = lib_name.get_local_name(node)
        namespace = lib_name.get_namespace(leaf_name)
        bare_name = lib_name.get_without_namespace(leaf_name)

        animated_plugs = _get_animated_plugs([node])
        if not animated_plugs:
            continue

        if namespace not in namespaces:
            namespaces[namespace] = {}

        if bare_name not in namespaces[namespace]:
            namespaces[namespace][bare_name] = {}

        for plug in animated_plugs:
            attr_name = plug.split(".")[-1]

            try:
                time_anim_curve = lib_keyframe.TimeAnimCurve(plug)
                anim_curve_data = time_anim_curve.get_keyframes()
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to get keyframes for {plug}: {e}")
                continue

            namespaces[namespace][bare_name][attr_name] = anim_curve_data

    return AnimationData(
        version=FORMAT_VERSION,
        format=FORMAT_IDENTIFIER,
        namespaces=namespaces,
    )


def import_animation(data: AnimationData, mode: str = "replace", target_namespace: Optional[str] = None) -> list[str]:
    """Apply animation data to the scene.

    Args:
        data (AnimationData): The animation data to apply.
        mode (str): Import mode - "replace" (clear existing keys first) or "merge" (add/overwrite on same frame).
        target_namespace (str | None): Target namespace to apply. If None, uses the namespace from the data.

    Returns:
        list[str]: List of nodes that were modified.

    Raises:
        ValueError: If mode is invalid.
    """
    if mode not in IMPORT_MODES:
        raise ValueError(f"Invalid import mode: {mode}. Must be one of {IMPORT_MODES}.")

    modified_nodes: dict[str, None] = {}

    for namespace, nodes_data in data.namespaces.items():
        effective_namespace = target_namespace if target_namespace is not None else namespace

        for bare_name, attrs_data in nodes_data.items():
            if effective_namespace:
                full_node_name = f"{effective_namespace}:{bare_name}"
            else:
                full_node_name = bare_name

            if not cmds.objExists(full_node_name):
                logger.warning(f"Node does not exist, skipping: {full_node_name}")
                continue

            for attr_name, anim_curve_data in attrs_data.items():
                plug = f"{full_node_name}.{attr_name}"

                if not cmds.objExists(plug):
                    logger.warning(f"Attribute does not exist, skipping: {plug}")
                    continue

                if mode == MODE_REPLACE:
                    cmds.cutKey(plug, clear=True)

                try:
                    time_anim_curve = lib_keyframe.TimeAnimCurve(plug)
                    time_anim_curve.set_keyframes(anim_curve_data)
                except (ValueError, RuntimeError) as e:
                    logger.warning(f"Failed to set keyframes for {plug}: {e}")
                    continue

                modified_nodes.setdefault(full_node_name, None)

    return list(modified_nodes.keys())


# =============================================================================
# File I/O
# =============================================================================


def _derive_namespace_filename(base_path: str, namespace: str) -> str:
    """Derive the output filename for a namespace.

    Args:
        base_path (str): The base output file path (e.g., "C:/path/foo.json").
        namespace (str): The namespace string (e.g., "", "hoge", "char:sub").

    Returns:
        str: The derived file path (e.g., "C:/path/foo.hoge.json").
    """
    directory = os.path.dirname(base_path)
    base_name = os.path.basename(base_path)
    stem = base_name.rsplit(".json", 1)[0]

    if not namespace:
        return os.path.join(directory, f"{stem}.json")

    safe_namespace = namespace.replace(":", "_")
    return os.path.join(directory, f"{stem}.{safe_namespace}.json")


def _validate_anim_file(raw_data: dict, file_path: str) -> None:
    """Validate raw JSON data as a faketools animation file.

    Args:
        raw_data (dict): The raw JSON data.
        file_path (str): The file path (for error messages).

    Raises:
        ValueError: If data is not a valid faketools animation file.
    """
    if not isinstance(raw_data, dict):
        raise ValueError(f"Invalid file format: {file_path}")

    if raw_data.get("format") != FORMAT_IDENTIFIER:
        raise ValueError(f"Not a faketools animation file. Expected format '{FORMAT_IDENTIFIER}', got '{raw_data.get('format')}': {file_path}")

    if "namespaces" not in raw_data or not isinstance(raw_data["namespaces"], dict):
        raise ValueError(f"Missing or invalid 'namespaces' key: {file_path}")

    if "version" not in raw_data:
        raise ValueError(f"Missing 'version' key: {file_path}")


def load_animation_file(file_path: str) -> AnimationData:
    """Load and validate a faketools animation file.

    Args:
        file_path (str): The file path to load.

    Returns:
        AnimationData: The loaded animation data.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file is not a valid faketools animation file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    _validate_anim_file(raw_data, file_path)
    return AnimationData.from_dict(raw_data)


def export_animation_to_file(output_file: str, data: AnimationData, split_by_namespace: bool = False) -> list[str]:
    """Write animation data to JSON file(s).

    Args:
        output_file (str): The output file path. Extension must be .json.
        data (AnimationData): The animation data to write.
        split_by_namespace (bool): If True, write separate files per namespace.

    Returns:
        list[str]: List of files that were written.

    Raises:
        ValueError: If invalid file format or no animation data.
        FileNotFoundError: If output directory does not exist.
    """
    if not output_file.endswith(".json"):
        raise ValueError(f"Invalid file format. Must be JSON file: {output_file}")

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    if not data.namespaces:
        raise ValueError("No animation data to export.")

    written_files = []

    if not split_by_namespace:
        with open(output_file, mode="w", encoding="utf-8") as f:
            json.dump(asdict(data), f, indent=4)
        written_files.append(output_file)
        logger.info(f"Exported animation to: {output_file}")
    else:
        for namespace, nodes_data in data.namespaces.items():
            ns_data = AnimationData(
                version=FORMAT_VERSION,
                format=FORMAT_IDENTIFIER,
                namespaces={namespace: nodes_data},
            )
            ns_file = _derive_namespace_filename(output_file, namespace)
            with open(ns_file, mode="w", encoding="utf-8") as f:
                json.dump(asdict(ns_data), f, indent=4)
            written_files.append(ns_file)
            logger.info(f"Exported animation ({namespace or 'root'}) to: {ns_file}")

    return written_files


# =============================================================================
# Convenience Functions
# =============================================================================


def export_animation(output_file: str, nodes: Optional[list[str]] = None, split_by_namespace: bool = False) -> list[str]:
    """Build animation data from nodes and export to file(s).

    Args:
        output_file (str): The output file path. Extension must be .json.
        nodes (list[str] | None): Nodes to export. If None, uses selected nodes.
        split_by_namespace (bool): If True, write separate files per namespace.

    Returns:
        list[str]: List of files that were written.

    Raises:
        ValueError: If no animated nodes found or invalid file format.
        FileNotFoundError: If output directory does not exist.
    """
    if nodes is None:
        nodes = cmds.ls(sl=True)

    if not nodes:
        raise ValueError("No nodes specified and no nodes selected.")

    data = build_animation_data(nodes)
    return export_animation_to_file(output_file, data, split_by_namespace=split_by_namespace)


def export_all_animation(output_file: str, split_by_namespace: bool = False) -> list[str]:
    """Export animation from all animated nodes in the scene.

    Args:
        output_file (str): The output file path.
        split_by_namespace (bool): If True, write separate files per namespace.

    Returns:
        list[str]: List of files that were written.

    Raises:
        ValueError: If no animated nodes found in the scene.
    """
    all_nodes = get_all_animated_nodes()
    if not all_nodes:
        raise ValueError("No animated nodes found in the scene.")

    return export_animation(output_file, nodes=all_nodes, split_by_namespace=split_by_namespace)


def import_animation_from_file(input_file: str, mode: str = "replace", target_namespace: Optional[str] = None) -> list[str]:
    """Load animation data from file and apply to the scene.

    Args:
        input_file (str): The input file path.
        mode (str): Import mode - "replace" or "merge".
        target_namespace (str | None): Target namespace to apply. If None, uses the namespace from the file.

    Returns:
        list[str]: List of nodes that were modified.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file is not valid or mode is invalid.
    """
    data = load_animation_file(input_file)
    return import_animation(data, mode=mode, target_namespace=target_namespace)
