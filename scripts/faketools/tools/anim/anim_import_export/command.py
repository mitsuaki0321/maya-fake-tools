"""Animation Import/Export business logic.

Provides export and import of time-based keyframe animation data as JSON and pickle files.
One file per namespace. Supports replace/merge import modes and namespace remapping.
"""

from dataclasses import asdict, dataclass, field
import json
from logging import getLogger
import os
import pickle
from typing import Callable, Optional

import maya.cmds as cmds

from ....lib import lib_keyframe, lib_name

logger = getLogger(__name__)

FORMAT_IDENTIFIER = "faketools_animation"
FORMAT_VERSION = "1.0.0"
TIME_CURVE_TYPES = {"animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT"}
MODE_REPLACE = "replace"
MODE_MERGE = "merge"
IMPORT_MODES = (MODE_REPLACE, MODE_MERGE)
FORMAT_JSON = "json"
FORMAT_PICKLE = "pickle"
FILE_FORMATS = (FORMAT_JSON, FORMAT_PICKLE)


# =============================================================================
# Data Class
# =============================================================================


@dataclass
class AnimationData:
    """Animation data for a single namespace.

    Args:
        namespace (str): The namespace (empty string for root namespace).
        nodes (dict): Nested dict of node_name -> attr_name -> AnimCurveData.
        version (str): The format version.
        format (str): The format identifier for file validation.
    """

    namespace: str = ""
    nodes: dict[str, dict[str, lib_keyframe.AnimCurveData]] = field(default_factory=dict)
    version: str = FORMAT_VERSION
    format: str = FORMAT_IDENTIFIER

    @classmethod
    def from_dict(cls, data: dict) -> "AnimationData":
        """Validate and deserialize from dictionary.

        Args:
            data (dict): The dictionary data.

        Returns:
            AnimationData: The deserialized animation data.

        Raises:
            ValueError: If the data is not a valid AnimationData structure.
        """
        if not isinstance(data, dict):
            raise ValueError("Invalid data: expected a dictionary.")

        if data.get("format") != FORMAT_IDENTIFIER:
            raise ValueError(f"Invalid format: expected '{FORMAT_IDENTIFIER}', got '{data.get('format')}'.")

        if "version" not in data:
            raise ValueError("Missing 'version' key.")

        if "namespace" not in data or not isinstance(data["namespace"], str):
            raise ValueError("Missing or invalid 'namespace' key.")

        if "nodes" not in data or not isinstance(data["nodes"], dict):
            raise ValueError("Missing or invalid 'nodes' key.")

        nodes: dict[str, dict[str, lib_keyframe.AnimCurveData]] = {}
        for node_name, attrs_data in data["nodes"].items():
            nodes[node_name] = {}
            for attr_name, curve_data in attrs_data.items():
                nodes[node_name][attr_name] = lib_keyframe.AnimCurveData.from_dict(curve_data)

        return cls(
            namespace=data["namespace"],
            nodes=nodes,
            version=data["version"],
            format=data["format"],
        )


# =============================================================================
# Scene → Data
# =============================================================================


class AnimationDataBuilder:
    """Build AnimationData from Maya scene nodes."""

    def build(self, nodes: list[str], on_progress: Optional[Callable[[int, int], bool]] = None) -> list[AnimationData]:
        """Build animation data from specified nodes.

        Automatically splits by namespace, returning one AnimationData per namespace.

        Args:
            nodes (list[str]): The node names to collect animation from.
            on_progress (callable | None): Progress callback receiving (current, total).
                Return True to cancel the operation.

        Returns:
            list[AnimationData]: List of animation data, one per namespace.
        """
        # Collect all animated plugs first for progress counting
        node_plugs: list[tuple[str, list[str]]] = []
        for node in nodes:
            animated_plugs = self._get_animated_plugs([node])
            if animated_plugs:
                node_plugs.append((node, animated_plugs))

        total_plugs = sum(len(plugs) for _, plugs in node_plugs)
        current_plug = 0

        ns_nodes: dict[str, dict[str, dict[str, lib_keyframe.AnimCurveData]]] = {}

        for node, animated_plugs in node_plugs:
            leaf_name = lib_name.get_local_name(node)
            namespace = lib_name.get_namespace(leaf_name)
            bare_name = lib_name.get_without_namespace(leaf_name)

            if namespace not in ns_nodes:
                ns_nodes[namespace] = {}

            if bare_name not in ns_nodes[namespace]:
                ns_nodes[namespace][bare_name] = {}

            for plug in animated_plugs:
                if on_progress and on_progress(current_plug, total_plugs):
                    logger.warning("Export cancelled by user.")
                    break

                attr_name = plug.split(".")[-1]

                try:
                    time_anim_curve = lib_keyframe.TimeAnimCurve(plug)
                    anim_curve_data = time_anim_curve.get_keyframes()
                except (ValueError, RuntimeError) as e:
                    logger.warning(f"Failed to get keyframes for {plug}: {e}")
                    current_plug += 1
                    continue

                ns_nodes[namespace][bare_name][attr_name] = anim_curve_data
                current_plug += 1

        return [AnimationData(namespace=ns, nodes=nodes_data) for ns, nodes_data in ns_nodes.items()]

    def build_from_all(self, on_progress: Optional[Callable[[int, int], bool]] = None) -> list[AnimationData]:
        """Build animation data from all animated nodes in the scene.

        Args:
            on_progress (callable | None): Progress callback receiving (current, total).
                Return True to cancel the operation.

        Returns:
            list[AnimationData]: List of animation data, one per namespace.

        Raises:
            ValueError: If no animated nodes found in the scene.
        """
        all_nodes = self._get_all_animated_nodes()
        if not all_nodes:
            raise ValueError("No animated nodes found in the scene.")

        return self.build(all_nodes, on_progress=on_progress)

    def _get_animated_plugs(self, nodes: list[str]) -> list[str]:
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

    def _get_all_animated_nodes(self) -> list[str]:
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
# Data ↔ File
# =============================================================================


class AnimationFileIO:
    """Read and write AnimationData as JSON or pickle files."""

    def write(self, output_file: str, data_list: list[AnimationData], format: str = FORMAT_JSON) -> list[str]:
        """Write animation data to file(s).

        One file per AnimationData (one per namespace).
        If multiple items, namespace is appended to the filename.

        Args:
            output_file (str): The base output file path (without extension).
            data_list (list[AnimationData]): The animation data list to write.
            format (str): File format - "json" or "pickle".

        Returns:
            list[str]: List of files that were written.

        Raises:
            ValueError: If invalid format or empty data list.
            FileNotFoundError: If output directory does not exist.
        """
        if format not in FILE_FORMATS:
            raise ValueError(f"Invalid format: {format}. Must be one of {FILE_FORMATS}.")

        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

        if not data_list:
            raise ValueError("No animation data to export.")

        written_files = []
        use_namespace_suffix = len(data_list) > 1

        for data in data_list:
            if not data.nodes:
                continue

            if use_namespace_suffix:
                file_path = self._derive_namespace_filename(output_file, data.namespace, format)
            else:
                file_path = f"{output_file}.{format}"

            self._write_file(file_path, asdict(data), format)
            written_files.append(file_path)
            logger.info(f"Exported animation ({data.namespace or 'root'}) to: {file_path}")

        return written_files

    def load(self, file_path: str) -> AnimationData:
        """Load and validate a faketools animation file.

        Format is determined by file extension (.json or .pickle).

        Args:
            file_path (str): The file path to load.

        Returns:
            AnimationData: The loaded animation data.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file format is unsupported or data is invalid.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if file_path.endswith(".json"):
            with open(file_path, encoding="utf-8") as f:
                raw_data = json.load(f)
        elif file_path.endswith(".pickle"):
            with open(file_path, "rb") as f:
                raw_data = pickle.load(f)  # noqa: S301
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        return AnimationData.from_dict(raw_data)

    def _write_file(self, file_path: str, data: dict, format: str) -> None:
        """Write data to a single file.

        Args:
            file_path (str): The output file path.
            data (dict): The data dictionary to write.
            format (str): File format - "json" or "pickle".
        """
        if format == FORMAT_JSON:
            with open(file_path, mode="w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        elif format == FORMAT_PICKLE:
            with open(file_path, "wb") as f:
                pickle.dump(data, f)

    def _derive_namespace_filename(self, base_path: str, namespace: str, format: str) -> str:
        """Derive the output filename for a namespace.

        Args:
            base_path (str): The base output file path without extension (e.g., "C:/path/foo").
            namespace (str): The namespace string (e.g., "", "hoge", "char:sub").
            format (str): File format for extension.

        Returns:
            str: The derived file path (e.g., "C:/path/foo.hoge.json").
        """
        if not namespace:
            return f"{base_path}.{format}"

        safe_namespace = namespace.replace(":", "_")
        return f"{base_path}.{safe_namespace}.{format}"


# =============================================================================
# Data → Scene
# =============================================================================


def import_animation(data: AnimationData, mode: str = MODE_REPLACE, target_namespace: Optional[str] = None) -> list[str]:
    """Apply animation data to the scene.

    Args:
        data (AnimationData): The animation data to apply.
        mode (str): Import mode - "replace" (clear existing keys first) or "merge" (add/overwrite on same frame).
        target_namespace (str | None): Target namespace to apply. If None, uses the namespace from the data.

    Returns:
        list[str]: List of nodes that were modified.

    Raises:
        TypeError: If data is not AnimationData.
        ValueError: If mode is invalid.
    """
    if not isinstance(data, AnimationData):
        raise TypeError(f"Expected AnimationData, got {type(data).__name__}.")

    if mode not in IMPORT_MODES:
        raise ValueError(f"Invalid import mode: {mode}. Must be one of {IMPORT_MODES}.")

    effective_namespace = target_namespace if target_namespace is not None else data.namespace
    modified_nodes: dict[str, None] = {}

    for bare_name, attrs_data in data.nodes.items():
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
# Convenience Functions
# =============================================================================


def export_animation(
    output_file: str,
    nodes: Optional[list[str]] = None,
    format: str = FORMAT_JSON,
    on_progress: Optional[Callable[[int, int], bool]] = None,
) -> list[str]:
    """Build animation data from nodes and export to file(s).

    Automatically splits into separate files when multiple namespaces exist.

    Args:
        output_file (str): The base output file path (without extension).
        nodes (list[str] | None): Nodes to export. If None, uses selected nodes.
        format (str): File format - "json" or "pickle".
        on_progress (callable | None): Progress callback receiving (current, total).
            Return True to cancel.

    Returns:
        list[str]: List of files that were written.

    Raises:
        ValueError: If no animated nodes found or invalid format.
        FileNotFoundError: If output directory does not exist.
    """
    if nodes is None:
        nodes = cmds.ls(sl=True)

    if not nodes:
        raise ValueError("No nodes specified and no nodes selected.")

    builder = AnimationDataBuilder()
    data_list = builder.build(nodes, on_progress=on_progress)

    file_io = AnimationFileIO()
    return file_io.write(output_file, data_list, format=format)


def export_all_animation(
    output_file: str,
    format: str = FORMAT_JSON,
    on_progress: Optional[Callable[[int, int], bool]] = None,
) -> list[str]:
    """Export animation from all animated nodes in the scene.

    Args:
        output_file (str): The base output file path (without extension).
        format (str): File format - "json" or "pickle".
        on_progress (callable | None): Progress callback receiving (current, total).
            Return True to cancel.

    Returns:
        list[str]: List of files that were written.

    Raises:
        ValueError: If no animated nodes found in the scene.
    """
    builder = AnimationDataBuilder()
    data_list = builder.build_from_all(on_progress=on_progress)

    file_io = AnimationFileIO()
    return file_io.write(output_file, data_list, format=format)


def import_animation_from_file(input_file: str, mode: str = MODE_REPLACE, target_namespace: Optional[str] = None) -> list[str]:
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
    file_io = AnimationFileIO()
    data = file_io.load(input_file)
    return import_animation(data, mode=mode, target_namespace=target_namespace)
