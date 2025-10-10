"""Command to pair selected nodes."""

from logging import getLogger

import maya.cmds as cmds

from .base_commands import PairCommand

logger = getLogger(__name__)


class SnapPositionCommand(PairCommand):
    """Command to snap the position from source node to target node."""

    _name = "SnapPositionCommand"
    _description = "Command to snap the position from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip snap position. Not a transform node: {source_node}, {target_node}")
            return

        cmds.xform(target_node, ws=True, t=cmds.xform(source_node, q=True, ws=True, t=True))

        logger.debug(f"Snapped position: {source_node} -> {target_node}")


class SnapRotationCommand(PairCommand):
    """Command to snap the rotation from source node to target node."""

    _name = "SnapRotationCommand"
    _description = "Command to snap the rotation from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip snap rotation. Not a transform node: {source_node}, {target_node}")
            return

        cmds.xform(target_node, ws=True, ro=cmds.xform(source_node, q=True, ws=True, ro=True))

        logger.debug(f"Snapped rotation: {source_node} -> {target_node}")


class SnapScaleCommand(PairCommand):
    """Command to snap the scale from source node to target node."""

    _name = "SnapScaleCommand"
    _description = "Command to snap the scale from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip snap scale. Not a transform node: {source_node}, {target_node}")
            return

        cmds.xform(target_node, r=True, s=cmds.xform(source_node, q=True, r=True, s=True))

        logger.debug(f"Snapped scale: {source_node} -> {target_node}")


class SnapTranslateAndRotateCommand(PairCommand):
    """Command to snap the translate and rotate from source node to target node."""

    _name = "SnapTranslateAndRotateCommand"
    _description = "Command to snap the translate and rotate from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip snap translate and rotate. Not a transform node: {source_node}, {target_node}")
            return

        cmds.xform(target_node, ws=True, t=cmds.xform(source_node, q=True, ws=True, t=True))
        cmds.xform(target_node, ws=True, ro=cmds.xform(source_node, q=True, ws=True, ro=True))

        logger.debug(f"Snapped translate and rotate: {source_node} -> {target_node}")


class CopyTransformCommand(PairCommand):
    """Command to copy the transform from source node to target node."""

    _name = "CopyTransformCommand"
    _description = "Command to copy the transform from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip copy transform. Not a transform node: {source_node}, {target_node}")
            return

        for attr in ["translate", "rotate", "scale"]:
            target_attrs = cmds.attributeQuery(attr, node=source_node, listChildren=True)
            target_attrs += [attr]

            locked_attrs = [a for a in target_attrs if cmds.getAttr(f"{target_node}.{a}", lock=True)]
            if locked_attrs:
                logger.warning(f"Skip copy transform. Locked attributes: {target_node}.{', '.join(locked_attrs)}")
                continue

            value = cmds.getAttr(f"{source_node}.{attr}")[0]
            cmds.setAttr(f"{target_node}.{attr}", *value)

        logger.debug(f"Copied transform: {source_node} -> {target_node}")


class ConnectTransformCommand(PairCommand):
    """Command to connect the transform from source node to target node."""

    _name = "ConnectTransformCommand"
    _description = "Command to connect the transform from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not cmds.objectType(source_node, isAType="transform") or not cmds.objectType(target_node, isAType="transform"):
            logger.warning(f"Skip connect transform. Not a transform node: {source_node}, {target_node}")
            return

        for attr in ["translate", "rotate", "scale"]:
            target_attrs = cmds.attributeQuery(attr, node=source_node, listChildren=True)
            target_attrs += [attr]

            for child_attr in target_attrs:
                source_attr = f"{source_node}.{child_attr}"
                target_attr = f"{target_node}.{child_attr}"

                if cmds.isConnected(target_attr, source_attr):
                    continue

                lock_state = cmds.getAttr(target_attr, lock=True)
                if lock_state:
                    cmds.setAttr(target_attr, lock=False)

                cmds.connectAttr(source_attr, target_attr, force=True)

                if lock_state:
                    cmds.setAttr(target_attr, lock=True)

        logger.debug(f"Connected transform: {source_node} -> {target_node}")


class CopyWeightCommand(PairCommand):
    """Command to copy the skin weights from source node to target node."""

    _name = "CopyWeightCommand"
    _description = "Command to copy the skin weights from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        pass  # TODO: Implement this method.


class ConnectTopologyCommand(PairCommand):
    """Command to connect the topology from source node to target node."""

    _name = "ConnectTopologyCommand"
    _description = "Command to connect the topology from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        pass  # TODO: Implement this method.


class CopyTopologyCommand(PairCommand):
    """Command to copy the topology from source node to target node."""

    _name = "CopyTopologyCommand"
    _description = "Command to copy the topology from source node to target node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        pass  # TODO: Implement this method.


class ParentCommand(PairCommand):
    """Command to parent the target node under the source node."""

    _name = "ParentCommand"
    _description = "Command to parent the target node under the source node"

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        try:
            cmds.parent(target_node, source_node)
            logger.debug(f"Parented: {target_node} under {source_node}")
        except RuntimeError as e:
            logger.warning(f"Failed to parent {target_node} under {source_node}: {e}")


__all__ = [
    "SnapPositionCommand",
    "SnapRotationCommand",
    "SnapScaleCommand",
    "SnapTranslateAndRotateCommand",
    "CopyTransformCommand",
    "ConnectTransformCommand",
    "CopyWeightCommand",
    "ConnectTopologyCommand",
    "CopyTopologyCommand",
    "ParentCommand",
]
