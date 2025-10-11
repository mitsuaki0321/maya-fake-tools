"""Commands to manipulate selected nodes."""

from logging import getLogger

import maya.cmds as cmds

from ..lib import lib_shape, lib_transform
from ..lib_ui import maya_ui
from .base_commands import AllCommand

logger = getLogger(__name__)


class LockAndHideCommand(AllCommand):
    """Command to lock and hide selected nodes."""

    _name = "Lock and Hide"
    _description = "Command to lock and hide selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to lock and hide.
        """
        super().execute(target_nodes)

        attrs = maya_ui.get_channels(long_name=True)

        for node in target_nodes:
            if not attrs:
                attrs = cmds.listAttr(node, k=True) or []
            if not attrs:
                continue

            adjusted_attrs = []
            for attr in attrs:
                if not cmds.attributeQuery(attr, node=node, exists=True):
                    logger.warning(f"Attribute '{attr}' does not exist on node '{node}'. Skipping.")
                    continue

                if attr == "visibility":
                    cmds.setAttr(f"{node}.{attr}", lock=False, keyable=False)
                else:
                    cmds.setAttr(f"{node}.{attr}", lock=True, keyable=False, channelBox=False)

                adjusted_attrs.append(attr)

            if adjusted_attrs:
                logger.debug(f"Locked and hid attributes {', '.join(adjusted_attrs)} on node '{node}'.")


class UnlockAndShowCommand(AllCommand):
    """Command to unlock and show selected nodes."""

    _name = "Unlock and Show"
    _description = "Command to unlock and show selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to unlock and show.
        """
        super().execute(target_nodes)

        node_type_map = {}
        for target_node in target_nodes:
            node_type = cmds.nodeType(target_node)
            node_type_map.setdefault(node_type, []).append(target_node)

        for node_type, nodes in node_type_map.items():
            tmp_node = cmds.createNode(node_type, ss=True)
            keyable_attrs = cmds.listAttr(tmp_node, keyable=True) or []
            non_keyable_attrs = cmds.listAttr(tmp_node, channelBox=True) or []
            locked_attrs = cmds.listAttr(tmp_node, locked=True) or []
            for target_node in nodes:
                for attr in keyable_attrs:
                    if not cmds.attributeQuery(attr, node=target_node, exists=True):
                        logger.warning(f"Attribute does not exist: {target_node}.{attr}, skipping.")
                        continue

                    cmds.setAttr(f"{target_node}.{attr}", keyable=True, channelBox=False)
                    if attr in locked_attrs:
                        cmds.setAttr(f"{target_node}.{attr}", lock=True)
                    else:
                        cmds.setAttr(f"{target_node}.{attr}", lock=False)

                for attr in non_keyable_attrs:
                    if not cmds.attributeQuery(attr, node=target_node, exists=True):
                        logger.warning(f"Attribute does not exist: {target_node}.{attr}, skipping.")
                        continue

                    cmds.setAttr(f"{target_node}.{attr}", keyable=False, channelBox=True)
                    if attr in locked_attrs:
                        cmds.setAttr(f"{target_node}.{attr}", lock=True)
                    else:
                        cmds.setAttr(f"{target_node}.{attr}", lock=False)

                logger.debug(f"Unlocked and shown: {target_node}")

            cmds.delete(tmp_node)


class ZeroOutTransformsCommand(AllCommand):
    """Command to zero out transforms of selected nodes."""

    _name = "Zero Out"
    _description = "Command to zero out transforms of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to zero out transforms.
        """
        super().execute(target_nodes)

        for target_node in target_nodes:
            if not cmds.objectType(target_node, isAType="transform"):
                logger.warning(f"Node is not a transform: {target_node}, skipping.")
                continue

            for attr in ["translate", "rotate", "scale"]:
                for axis in ["X", "Y", "Z"]:
                    full_attr = f"{attr}{axis}"
                    lock_state = cmds.getAttr(f"{target_node}.{full_attr}", lock=True)
                    if lock_state:
                        cmds.setAttr(f"{target_node}.{full_attr}", lock=False)

                    if attr == "scale":
                        cmds.setAttr(f"{target_node}.{full_attr}", 1)
                    else:
                        cmds.setAttr(f"{target_node}.{full_attr}", 0)

                    if lock_state:
                        cmds.setAttr(f"{target_node}.{full_attr}", lock=True)

            logger.debug(f"Zeroed out transforms for node: {target_node}")


class BreakConnectionsCommand(AllCommand):
    """Command to break all connections of selected nodes."""

    _name = "Break Connections"
    _description = "Command to break all connections of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to break connections.
        """
        super().execute(target_nodes)

        attrs = maya_ui.get_channels()
        if not attrs:
            logger.warning("No attributes found in the channel box to break connections.")
            return

        parent_attrs = []
        for attr in attrs:
            parent_attr = cmds.attributeQuery(attr, node=target_nodes[0], listParent=True)
            if parent_attr:
                parent_attrs.extend(parent_attr)

        if parent_attrs:
            attrs += parent_attrs

        for target_node in target_nodes:
            for attr in attrs:
                if not cmds.attributeQuery(attr, node=target_node, exists=True):
                    logger.warning(f"Attribute does not exist: {target_node}.{attr}, skipping.")
                    continue

                plug = f"{target_node}.{attr}"
                source_plug = cmds.listConnections(plug, s=True, d=False, p=True)
                if not source_plug:
                    logger.debug(f"No incoming connection for: {plug}, skipping.")
                    continue

                cmds.disconnectAttr(source_plug[0], plug)

                logger.debug(f"Broke connection from {source_plug[0]} to {plug}")


class FreezeTransformsCommand(AllCommand):
    """Command to freeze transforms of selected nodes."""

    _name = "Freeze Transforms"
    _description = "Command to freeze transforms of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to freeze transforms.
        """
        super().execute(target_nodes)

        for target_node in target_nodes:
            if not cmds.objectType(target_node, isAType="transform"):
                logger.warning(f"Node is not a transform: {target_node}, skipping.")
                continue

            lib_transform.freeze_transform(target_node)
            lib_transform.freeze_transform_pivot(target_node)

            logger.debug(f"Froze transforms and pivot for node: {target_node}")


class FreezeMeshVerticesCommand(AllCommand):
    """Command to freeze mesh vertices of selected nodes."""

    _name = "Freeze Mesh Vertices"
    _description = "Command to freeze mesh vertices of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to freeze mesh vertices.
        """
        super().execute(target_nodes)

        for target_node in target_nodes:
            if not cmds.objectType(target_node, isAType="transform"):
                logger.warning(f"Node is not a transform: {target_node}, skipping.")
                continue

            shapes = cmds.listRelatives(target_node, shapes=True, pa=True, type="mesh", ni=True) or []
            if not shapes:
                logger.warning(f"No mesh shapes found under: {target_node}, skipping.")
                continue
            else:
                mesh = shapes[0]

            try:
                cmds.polyCollapseTweaks(mesh)
            except RuntimeError:
                vertex_count = cmds.polyEvaluate(mesh, vertex=True)
                for i in range(vertex_count):
                    current_pos = cmds.getAttr(f"{mesh}.pnts[{i}]")[0]
                    if current_pos != (0.0, 0.0, 0.0):
                        cmds.setAttr(f"{mesh}.pnts[{i}]", 0.0, 0.0, 0.0)

            logger.debug(f"Froze mesh vertices for node: {target_node}")


class DeleteConstraintsCommand(AllCommand):
    """Command to delete constraints of selected nodes."""

    _name = "Delete Constraints"
    _description = "Command to delete constraints of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to delete constraints.
        """
        super().execute(target_nodes)

        transforms = []
        for node in target_nodes:
            if cmds.objectType(node, isAType="transform"):
                transforms.append(node)
            else:
                logger.warning(f"Node is not a transform: {node}, skipping.")

        if not transforms:
            return

        cmds.delete(transforms, constraints=True)

        logger.debug(f"Deleted constraints for nodes: {', '.join(transforms)}")


class JointsToChainCommand(AllCommand):
    """Command to convert selected joints to a joint chain."""

    _name = "Joints to Chain"
    _description = "Command to convert selected joints to a joint chain"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target joints to convert.
        """
        super().execute(target_nodes)

        if len(target_nodes) < 2:
            logger.warning("Select at least 2 nodes")
            return

        # Check root parent node
        nodes = cmds.ls(target_nodes, l=True)
        root_parent_node = cmds.listRelatives(nodes[0], p=True, f=True)
        is_root_node_world = False
        if root_parent_node:
            parent_node = root_parent_node[0]
            parent_nodes = [parent_node]
            while True:
                parent_node = cmds.listRelatives(parent_node, p=True, f=True)
                if not parent_node:
                    break
                parent_nodes.append(parent_node[0])

            parent_nodes = list(reversed(parent_nodes))
            for index, parent_node in enumerate(parent_nodes):
                if parent_node in nodes:
                    if index == 0:
                        root_parent_node = None
                    else:
                        root_parent_node = parent_nodes[index - 1]
                    break
        else:
            is_root_node_world = True

        # Create dummy parent nodes
        dummy_parent_nodes = []
        uuids = cmds.ls(nodes, uuid=True)
        for uuid in uuids:
            node = cmds.ls(uuid)[0]
            parent = cmds.listRelatives(node, p=True)
            if parent:
                mat = cmds.xform(node, q=True, ws=True, m=True)
                dummy = cmds.createNode("transform", ss=True)
                cmds.xform(dummy, ws=True, m=mat)
                cmds.parent(node, dummy)
                dummy_parent_nodes.append(dummy)

        # Chain transforms
        for i in range(len(uuids) - 1):
            uuid_nodes = cmds.ls([uuids[i + 1], uuids[i]])
            cmds.parent(*uuid_nodes)

        root_node = cmds.ls(uuids[0])[0]
        if root_parent_node:
            cmds.parent(root_node, root_parent_node)
        elif not is_root_node_world:
            cmds.parent(root_node, w=True)

        if dummy_parent_nodes:
            cmds.delete(dummy_parent_nodes)

        root_node = cmds.ls(uuids[0])[0]
        cmds.select(root_node, r=True)

        logger.debug(f"Chained nodes: {nodes}")


class MirrorJointsCommand(AllCommand):
    """Command to mirror selected joints."""

    _name = "Mirror Joints"
    _description = "Command to mirror selected joints"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target joints to mirror.
        """
        super().execute(target_nodes)

        if len(target_nodes) < 1:
            logger.warning("Select at least 1 node")
            return

        for target_node in target_nodes:
            if cmds.nodeType(target_node) != "joint":
                logger.warning(f"Not a joint: {target_node}")
                continue

            mirror_node = cmds.mirrorJoint(target_node, mirrorBehavior=True, mirrorYZ=True, searchReplace=["L", "R"])
            logger.debug(f"Mirrored joints: {target_node} -> {mirror_node}")


class DeleteExtraAttributesCommand(AllCommand):
    """Command to delete extra attributes of selected nodes."""

    _name = "Delete Extra Attributes"
    _description = "Command to delete extra attributes of selected nodes"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to delete extra attributes.
        """
        super().execute(target_nodes)

        for target_node in target_nodes:
            attrs = cmds.listAttr(target_node, ud=True) or []

            deleted_attrs = []
            for attr in attrs:
                cmds.setAttr(f"{target_node}.{attr}", lock=False)

                try:
                    cmds.deleteAttr(f"{target_node}.{attr}")
                    deleted_attrs.append(attr)
                except RuntimeError as e:
                    logger.warning(f"Failed to delete attribute {target_node}.{attr}: {e}")

            if deleted_attrs:
                logger.debug(f"Deleted extra attributes {', '.join(deleted_attrs)} from node: {target_node}")


class DuplicateOriginalShapeCommand(AllCommand):
    """Command to duplicate original shape from source to destination."""

    _name = "Duplicate Original Shape"
    _description = "Command to duplicate or connect original shape from source to destination"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes, expects exactly two nodes [source, destination].
        """
        super().execute(target_nodes)

        duplicate_nodes = []
        for target_node in target_nodes:
            if not cmds.objectType(target_node, isAType="transform"):
                logger.warning(f"Node is not a transform: {target_node}, skipping.")
                return

            shapes = cmds.listRelatives(target_node, shapes=True, pa=True, ni=True) or []
            if not shapes:
                logger.warning(f"No shapes found under: {target_node}, skipping.")
                return

            duplicate_node = lib_shape.duplicate_original_shape(shapes[0])
            duplicate_nodes.append(duplicate_node)

        if duplicate_nodes:
            cmds.select(duplicate_nodes, r=True)
            logger.debug(f"Processed nodes: {', '.join(duplicate_nodes)}")
        else:
            logger.warning("No nodes were processed.")


__all__ = [
    "LockAndHideCommand",
    "UnlockAndShowCommand",
    "ZeroOutTransformsCommand",
    "BreakConnectionsCommand",
    "FreezeTransformsCommand",
    "FreezeMeshVerticesCommand",
    "DeleteConstraintsCommand",
    "JointsToChainCommand",
    "MirrorJointsCommand",
    "DeleteExtraAttributesCommand",
    "DuplicateOriginalShapeCommand",
]
