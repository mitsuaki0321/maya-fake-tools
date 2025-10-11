"""
Transfer the driven keys.
"""

from dataclasses import asdict
import json
from logging import getLogger
import os
import re

import maya.cmds as cmds

from ....lib import lib_keyframe

logger = getLogger(__name__)


class DrivenKeyExportImport:
    """Export and import driven keys."""

    def export_driven_keys(self, output_file: str):
        """Export driven keys."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No nodes selected")

        if not output_file.endswith(".json"):
            raise ValueError(f"Invalid file format. Must be JSON file: {output_file}")

        if not os.path.exists(os.path.dirname(output_file)):
            raise FileNotFoundError(f"Output directory does not exist: {os.path.dirname(output_file)}")

        export_data = []
        for node in sel_nodes:
            attrs = cmds.listAttr(node, k=True)
            if not attrs:
                continue

            for attr in attrs:
                driver_plugs = cmds.setDrivenKeyframe(f"{node}.{attr}", q=True, driver=True)
                if not driver_plugs:
                    continue

                for driver_plug in driver_plugs:
                    attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=f"{node}.{attr}")
                    anim_curve_data = attr_anim_curve.get_keyframes(driver_plug)

                    set_driven_key_data = lib_keyframe.SetDrivenKeyData(
                        driven_plug=f"{node}.{attr}", driver_plug=driver_plug, anim_curve_data=anim_curve_data
                    )

                    export_data.append(asdict(set_driven_key_data))

                logger.debug(f"Exported driven keys: {node}.{attr}")

        with open(output_file, mode="w") as f:
            json.dump(export_data, f, indent=4)

        logger.debug(f"Exported driven keys to: {output_file}")

    def import_driven_keys(self, input_file: str):
        """Import driven keys."""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file does not exist: {input_file}")

        with open(input_file) as f:
            import_data = json.load(f)

        added_nodes = []
        for set_driven_key_data in import_data:
            driven_plug = set_driven_key_data["driven_plug"]
            driver_plug = set_driven_key_data["driver_plug"]

            if not cmds.objExists(driven_plug):
                cmds.warning(f"Driven plug does not exists: {driven_plug}")
                continue

            if not cmds.objExists(driver_plug):
                cmds.warning(f"Driver plug does not exists: {driver_plug}")
                continue

            anim_curve_data = lib_keyframe.AnimCurveData.from_dict(set_driven_key_data["anim_curve_data"])
            attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=driven_plug)
            attr_anim_curve.set_keyframes(anim_curve_data=anim_curve_data, driver_plug=driver_plug)

            node, _ = driven_plug.split(".")
            if node not in added_nodes:
                added_nodes.append(node)

        if added_nodes:
            cmds.select(added_nodes, r=True)

        logger.debug(f"Imported driven keys from: {input_file}")


class DrivenKeyTransfer:
    """Transfer driven keys."""

    def one_to_all(self):
        """Transfer driven keys from selected node to all selected nodes."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No nodes selected")

        if len(sel_nodes) < 2:
            cmds.error("Select more than 2 nodes. The first node is the source node, and the rest are target nodes.")

        source_node = sel_nodes[0]
        target_nodes = sel_nodes[1:]

        source_driven_plugs = cmds.setDrivenKeyframe(source_node, q=True, driven=True)
        if not source_driven_plugs:
            cmds.error(f"No driven keys found: {source_node}")

        for source_driven_plug in source_driven_plugs:
            source_driver_plugs = cmds.setDrivenKeyframe(source_driven_plug, q=True, driver=True)

            anim_curve_datas = {}
            attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=source_driven_plug)
            for source_driver_plug in source_driver_plugs:
                anim_curve_data = attr_anim_curve.get_keyframes(driver_plug=source_driver_plug)
                anim_curve_datas[source_driver_plug] = anim_curve_data

            for target_node in target_nodes:
                target_driven_plug = source_driven_plug.replace(source_node, target_node)
                if not cmds.objExists(target_driven_plug):
                    cmds.error(f"Target driven plug does not exists: {target_driven_plug}")

                target_attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=target_driven_plug)
                # Delete current driven keys
                target_driven_anim_curves = target_attr_anim_curve.get_anim_curves()
                if target_driven_anim_curves:
                    cmds.delete(target_driven_anim_curves)
                    logger.debug(f"Deleted driven keys: {target_driven_plug}")

                # Set driven keys
                for source_driver_plug, anim_curve_data in anim_curve_datas.items():
                    target_attr_anim_curve.set_keyframes(anim_curve_data=anim_curve_data, driver_plug=source_driver_plug)

                logger.debug(f"Transfer driven keys: {source_driven_plug} >> {target_driven_plug}")

    def one_to_replace(self, regex_name: str, replace_name: str, replace_driver: bool = False, force_delete: bool = False):
        """Transfer driven keys by replacing selected node names with regex. If replace_driver is True, replace driver names as well.

        Args:
            regex_name (str): The regex name.
            replace_name (str): The replace name.
            replace_driver (bool): If True, replace driver names as well.
            force_delete (bool): If True, delete the current driven keys before transfer.
        """
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No nodes selected")

        p = re.compile(regex_name)

        target_nodes = []
        for source_node in sel_nodes:
            # Check if the source node has driven keys
            source_driven_plugs = cmds.setDrivenKeyframe(source_node, q=True, driven=True)
            if not source_driven_plugs:
                cmds.error(f"No driven keys found: {source_node}")

            # Replace the source node to get the target node. Raise an error if it does not exist
            target_node = p.sub(replace_name, source_node)
            if not cmds.objExists(target_node):
                cmds.error(f"Target node does not exist: {source_node} >> {target_node}")

            # Raise an error if the target node name is the same as the source node name after replacement
            if target_node == source_node:
                cmds.error(f"Failed to replace other name: {source_node}")

            # Check if the target node has the attribute. Raise an error if it does not exist
            target_driven_plugs = []
            not_exists_target_driven_plugs = []
            for source_driven_plug in source_driven_plugs:
                target_driven_plug = source_driven_plug.replace(source_node, target_node)
                if cmds.objExists(target_driven_plug):
                    target_driven_plugs.append(target_driven_plug)
                else:
                    not_exists_target_driven_plugs.append(target_driven_plug)

            if not_exists_target_driven_plugs:
                cmds.error(f"Target plugs do not exist: {not_exists_target_driven_plugs}")

            if force_delete:
                for target_driven_plug in target_driven_plugs:
                    target_attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=target_driven_plug)
                    target_driven_anim_curves = target_attr_anim_curve.get_anim_curves()
                    if target_driven_anim_curves:
                        cmds.delete(target_driven_anim_curves)
                        logger.debug(f"Deleted driven keys: {target_driven_plug}")

            # Transfer driven keys
            for source_driven_plug, target_driven_plug in zip(source_driven_plugs, target_driven_plugs, strict=False):
                source_driver_plugs = cmds.setDrivenKeyframe(source_driven_plug, q=True, driver=True)

                anim_curve_datas = {}
                attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=source_driven_plug)
                for source_driver_plug in source_driver_plugs:
                    anim_curve_data = attr_anim_curve.get_keyframes(driver_plug=source_driver_plug)
                    if replace_driver:
                        source_driver, source_attr = source_driver_plug.split(".")
                        target_driver = p.sub(replace_name, source_driver)
                        target_driver_plug = f"{target_driver}.{source_attr}"
                        if not cmds.objExists(target_driver_plug):
                            cmds.error(f"Target driver plug does not exists: {source_driver_plug} >> {target_driver_plug}")

                        if target_driver_plug == source_driver_plug:
                            cmds.warning(f"Failed to replace other name: {source_driver_plug}")

                        source_driver_plug = target_driver_plug

                    anim_curve_datas[source_driver_plug] = anim_curve_data

                target_attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=target_driven_plug)
                # Delete current driven keys
                target_driven_anim_curves = target_attr_anim_curve.get_anim_curves()
                if target_driven_anim_curves:
                    cmds.delete(target_driven_anim_curves)
                    logger.debug(f"Deleted driven keys: {target_driven_plug}")

                # Set driven keys
                for driver_plug, anim_curve_data in anim_curve_datas.items():
                    target_attr_anim_curve.set_keyframes(anim_curve_data=anim_curve_data, driver_plug=driver_plug)

                logger.debug(f"Transfer driven keys: {source_driven_plug} >> {target_driven_plug}")

            target_nodes.append(target_node)

        return target_nodes


def cleanup_driven_keys(node: str) -> None:
    """Cleanup the driven keys.

    Args:
        node (str): The node name.
    """
    if not node:
        raise ValueError("Invalid node name")

    if not cmds.objExists(node):
        raise ValueError(f"Invalid node. Not exists: {node}")

    driven_plugs = cmds.setDrivenKeyframe(node, q=True, driven=True)
    if not driven_plugs:
        logger.debug(f"No driven keys found: {node}")
        return

    def _check_deletable(anim_curve_node: str) -> bool:
        """Check if the animation curve is deletable.

        Notes:
            - Deletable if all values are the same and all tangent weights are 0.0.

        Returns:
            bool: True if deletable. False otherwise.
        """
        values = cmds.keyframe(anim_curve_node, q=True, valueChange=True)
        tangent_weights = cmds.keyTangent(anim_curve_node, q=True, inAngle=True, outAngle=True)

        return bool(len(list(set(values))) == 1 and not any(tangent_weights))

    for driven_plug in driven_plugs:
        driven_source_plugs = cmds.listConnections(driven_plug, s=True, d=False, p=True)
        driven_source_node = cmds.ls(driven_source_plugs, objectsOnly=True)[0]
        if cmds.nodeType(driven_source_node) not in ["animCurveUU", "animCurveUL", "animCurveUA", "animCurveUT", "blendWeighted"]:
            continue

        if cmds.nodeType(driven_source_node) == "blendWeighted":
            blendWeighted_node = driven_source_node

            anim_curve_plugs = cmds.listConnections(f"{blendWeighted_node}.input", s=True, d=False, p=True, type="animCurve")
            if not anim_curve_plugs:
                cmds.delete(blendWeighted_node)
                logger.debug(f"Deleted blendWeighted node. Not found blendWeighted input nodes: {blendWeighted_node}")
                continue

            anim_curve_nodes = cmds.ls(anim_curve_plugs, objectsOnly=True)
            anim_curve_deleted_nodes = []
            for anim_curve_node in anim_curve_nodes:
                if _check_deletable(anim_curve_node):
                    cmds.delete(anim_curve_node)
                    anim_curve_deleted_nodes.append(anim_curve_node)
                    logger.debug(f"Deleted animation curve node: {anim_curve_node}")

            if len(anim_curve_deleted_nodes) == len(anim_curve_nodes) or not anim_curve_deleted_nodes:
                continue

            dif_anim_curve_nodes = list(set(anim_curve_nodes) - set(anim_curve_deleted_nodes))
            if len(dif_anim_curve_nodes) == 1:
                cmds.connectAttr(f"{dif_anim_curve_nodes[0]}.output", driven_plug, f=True)
                cmds.delete(blendWeighted_node)

                logger.debug(f"Deleted blendWeighted node: {blendWeighted_node}")
        else:
            print(driven_source_node)
            if _check_deletable(driven_source_node):
                cmds.delete(driven_source_node)
                logger.debug(f"Deleted animation curve node: {driven_source_node}")

    logger.debug(f"Cleanup driven keys: {node}")


def mirror_transform_anim_curve(transform: str, time_attrs: list[str] | None, value_attrs: list[str] | None) -> None:
    """Mirror the transform animation curve.

    Args:
        transform (str): The transform node.
        time_attrs (list[str]): The time attributes to mirror.
        value_attrs (list[str]): The value attributes to mirror.
    """
    if not transform:
        raise ValueError("Invalid transform node")

    if not cmds.objExists(transform):
        raise ValueError(f"Transform does not exists: {transform}")

    if "transform" not in cmds.nodeType(transform, inherited=True):
        raise ValueError(f"Invalid transform type: {transform}")

    if not time_attrs and not value_attrs:
        cmds.warning("No options to mirror. Please set mirror axis options.")
        return

    transform_attrs = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ"]

    invalid_attrs = []
    if time_attrs:
        for attr in time_attrs:
            if attr not in transform_attrs:
                invalid_attrs.append(attr)
    else:
        time_attrs = []

    if value_attrs:
        for attr in value_attrs:
            if attr not in transform_attrs:
                invalid_attrs.append(attr)
    else:
        value_attrs = []

    if invalid_attrs:
        cmds.error(f"Invalid attributes. Please set transform long name: {invalid_attrs}")

    driven_plugs = cmds.setDrivenKeyframe(transform, q=True, driven=True)
    if not driven_plugs:
        cmds.warning(f"No driven keys found: {transform}")
        return

    for driven_plug in driven_plugs:
        driven_attr = cmds.listAttr(driven_plug)[0]
        attr_anim_curve = lib_keyframe.AttributeAnimCurve(driven_plug=driven_plug)
        anim_curves = attr_anim_curve.get_anim_curves()

        for anim_curve in anim_curves:
            mirror_time = driven_attr in time_attrs
            mirror_value = driven_attr in value_attrs
            if not mirror_time and not mirror_value:
                continue
            lib_keyframe.mirror_anim_curve(anim_curve, mirror_time=mirror_time, mirror_value=mirror_value)


def get_driven_key_nodes() -> list[str]:
    """Get the driven key nodes.

    Notes:
        - If no nodes are selected, get all transform nodes.

    Returns:
        list[str]: The driven key nodes.
    """
    sel_nodes = cmds.ls(sl=True)
    if not sel_nodes:
        sel_nodes = cmds.ls(type="transform")

    driven_key_nodes = []
    for sel_node in sel_nodes:
        driven_plugs = cmds.setDrivenKeyframe(sel_node, q=True, driven=True)
        if not driven_plugs:
            continue

        driven_key_nodes.append(sel_node)

    return driven_key_nodes
