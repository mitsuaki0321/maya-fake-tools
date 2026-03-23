"""Animation Import/Export business logic.

Provides export and import of time-based keyframe animation data as JSON files.
Supports namespace separation, replace/merge import modes, and flexible namespace remapping.
"""

from dataclasses import asdict
import json
from logging import getLogger
import os
from typing import Optional

import maya.cmds as cmds

from ....lib import lib_keyframe, lib_name

logger = getLogger(__name__)

FORMAT_IDENTIFIER = "faketools_anim"
FORMAT_VERSION = "1.0.0"


def get_animated_plugs(nodes: list[str]) -> list[str]:
    """Get all time-based animated plugs from the given nodes.

    Args:
        nodes (list[str]): The node names to inspect.

    Returns:
        list[str]: List of animated plug names (e.g., ["node.translateX", ...]).
    """
    animated_plugs = []
    for node in nodes:
        attrs = cmds.listAttr(node, k=True)
        if not attrs:
            continue

        for attr in attrs:
            plug = f"{node}.{attr}"
            times = cmds.keyframe(plug, query=True, timeChange=True)
            if times:
                animated_plugs.append(plug)

    return animated_plugs


def get_all_animated_nodes() -> list[str]:
    """Get all nodes in the scene that have time-based animation curves.

    Returns:
        list[str]: List of animated node names.
    """
    anim_curve_types = ["animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT"]
    anim_curves = cmds.ls(type=anim_curve_types)
    if not anim_curves:
        return []

    nodes: dict[str, None] = {}
    for anim_curve in anim_curves:
        connected = cmds.listConnections(anim_curve + ".output", d=True, s=False)
        if connected:
            for node in connected:
                nodes.setdefault(node, None)

    return list(nodes.keys())


def _build_export_data(nodes: list[str]) -> dict:
    """Build the animation export data dictionary from nodes.

    Args:
        nodes (list[str]): The node names to export animation from.

    Returns:
        dict: The structured export data with namespace separation.
    """
    data: dict = {
        "version": FORMAT_VERSION,
        "format": FORMAT_IDENTIFIER,
        "namespaces": {},
    }

    for node in nodes:
        leaf_name = lib_name.get_local_name(node)
        namespace = lib_name.get_namespace(leaf_name)
        bare_name = lib_name.get_without_namespace(leaf_name)

        animated_plugs = get_animated_plugs([node])
        if not animated_plugs:
            continue

        if namespace not in data["namespaces"]:
            data["namespaces"][namespace] = {}

        if bare_name not in data["namespaces"][namespace]:
            data["namespaces"][namespace][bare_name] = {}

        for plug in animated_plugs:
            attr_name = plug.split(".")[-1]

            try:
                time_anim_curve = lib_keyframe.TimeAnimCurve(plug)
                anim_curve_data = time_anim_curve.get_keyframes()
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to get keyframes for {plug}: {e}")
                continue

            data["namespaces"][namespace][bare_name][attr_name] = asdict(anim_curve_data)

    return data


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


def export_animation(output_file: str, nodes: Optional[list[str]] = None, split_by_namespace: bool = False) -> list[str]:
    """Export animation keyframes to JSON file(s).

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
    if not output_file.endswith(".json"):
        raise ValueError(f"Invalid file format. Must be JSON file: {output_file}")

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    if nodes is None:
        nodes = cmds.ls(sl=True)

    if not nodes:
        raise ValueError("No nodes specified and no nodes selected.")

    data = _build_export_data(nodes)

    if not data["namespaces"]:
        raise ValueError("No animation data found on the specified nodes.")

    written_files = []

    if not split_by_namespace:
        with open(output_file, mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        written_files.append(output_file)
        logger.info(f"Exported animation to: {output_file}")
    else:
        for namespace, nodes_data in data["namespaces"].items():
            ns_data = {
                "version": FORMAT_VERSION,
                "format": FORMAT_IDENTIFIER,
                "namespaces": {namespace: nodes_data},
            }
            ns_file = _derive_namespace_filename(output_file, namespace)
            with open(ns_file, mode="w", encoding="utf-8") as f:
                json.dump(ns_data, f, indent=4)
            written_files.append(ns_file)
            logger.info(f"Exported animation ({namespace or 'root'}) to: {ns_file}")

    return written_files


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


def validate_anim_file(file_path: str) -> dict:
    """Validate that a JSON file is a valid faketools animation file.

    Args:
        file_path (str): The file path to validate.

    Returns:
        dict: The loaded and validated data.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file is not a valid faketools animation file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid file format: {file_path}")

    if data.get("format") != FORMAT_IDENTIFIER:
        raise ValueError(f"Not a faketools animation file. Expected format '{FORMAT_IDENTIFIER}', got '{data.get('format')}': {file_path}")

    if "namespaces" not in data or not isinstance(data["namespaces"], dict):
        raise ValueError(f"Missing or invalid 'namespaces' key: {file_path}")

    if "version" not in data:
        raise ValueError(f"Missing 'version' key: {file_path}")

    return data


def import_animation(input_file: str, mode: str = "replace", target_namespace: Optional[str] = None) -> list[str]:
    """Import animation keyframes from a JSON file.

    Args:
        input_file (str): The input file path.
        mode (str): Import mode - "replace" (clear existing keys first) or "merge" (add/overwrite on same frame).
        target_namespace (str | None): Target namespace to apply. If None, uses the namespace from the file.

    Returns:
        list[str]: List of nodes that were modified.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file is not valid or mode is invalid.
    """
    if mode not in ("replace", "merge"):
        raise ValueError(f"Invalid import mode: {mode}. Must be 'replace' or 'merge'.")

    data = validate_anim_file(input_file)

    modified_nodes: dict[str, None] = {}

    for namespace, nodes_data in data["namespaces"].items():
        effective_namespace = target_namespace if target_namespace is not None else namespace

        for bare_name, attrs_data in nodes_data.items():
            if effective_namespace:
                full_node_name = f"{effective_namespace}:{bare_name}"
            else:
                full_node_name = bare_name

            if not cmds.objExists(full_node_name):
                logger.warning(f"Node does not exist, skipping: {full_node_name}")
                continue

            for attr_name, curve_data in attrs_data.items():
                plug = f"{full_node_name}.{attr_name}"

                if not cmds.objExists(plug):
                    logger.warning(f"Attribute does not exist, skipping: {plug}")
                    continue

                try:
                    anim_curve_data = lib_keyframe.AnimCurveData.from_dict(curve_data)
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse animation data for {plug}: {e}")
                    continue

                if mode == "replace":
                    cmds.cutKey(plug, clear=True)

                try:
                    time_anim_curve = lib_keyframe.TimeAnimCurve(plug)
                    time_anim_curve.set_keyframes(anim_curve_data)
                except (ValueError, RuntimeError) as e:
                    logger.warning(f"Failed to set keyframes for {plug}: {e}")
                    continue

                modified_nodes.setdefault(full_node_name, None)

    return list(modified_nodes.keys())
