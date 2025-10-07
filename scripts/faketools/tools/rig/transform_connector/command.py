"""Transform Connector command module."""

import logging

import maya.cmds as cmds

logger = logging.getLogger(__name__)


def copy_value(enable_attributes: list[str]) -> None:
    """
    Copy attribute values from source to destination nodes.

    The first selected node is the source, and all subsequent nodes are destinations.
    Copies the current value of each enabled attribute from source to destinations.

    Args:
        enable_attributes (list[str]): List of attributes to copy (e.g., ["translateX", "rotateY"])

    Raises:
        RuntimeError: If no transform nodes are selected or only one node is selected
    """
    sel_nodes = cmds.ls(sl=True, type="transform")
    if not sel_nodes:
        cmds.error("Select transform nodes.")
        return

    if len(sel_nodes) == 1:
        cmds.error("Select multiple transform nodes.")
        return

    src_node = sel_nodes[0]
    dest_nodes = sel_nodes[1:]

    logger.info(f"Copying values from {src_node} to {len(dest_nodes)} nodes")

    for dest_node in dest_nodes:
        for attribute in enable_attributes:
            src_attr = f"{src_node}.{attribute}"
            dest_attr = f"{dest_node}.{attribute}"

            if not cmds.attributeQuery(attribute, node=src_node, exists=True):
                cmds.warning(f"Failed to copy value. Attribute not exists: {src_attr}")
                continue

            if not cmds.attributeQuery(attribute, node=dest_node, exists=True):
                cmds.warning(f"Failed to copy value. Attribute not exists: {dest_attr}")
                continue

            if cmds.connectionInfo(src_attr, isDestination=True):
                cmds.error(f"Failed to copy value. Attribute is connected: {src_attr}")

            # Unlock if locked
            was_locked = cmds.getAttr(dest_attr, lock=True)
            if was_locked:
                cmds.setAttr(dest_attr, lock=False)

            # Copy value
            cmds.setAttr(dest_attr, cmds.getAttr(src_attr))

            # Restore lock state
            if was_locked:
                cmds.setAttr(dest_attr, lock=True)

            logger.debug(f"Copy value: {src_attr} -> {dest_attr}")


def connect_value(enable_attributes: list[str]) -> None:
    """
    Connect attributes from source to destination nodes.

    The first selected node is the source, and all subsequent nodes are destinations.
    Creates attribute connections from source to each destination for enabled attributes.

    Args:
        enable_attributes (list[str]): List of attributes to connect (e.g., ["translateX", "rotateY"])

    Raises:
        RuntimeError: If no transform nodes are selected or only one node is selected
    """
    sel_nodes = cmds.ls(sl=True, type="transform")
    if not sel_nodes:
        cmds.error("Select transform nodes.")
        return

    if len(sel_nodes) == 1:
        cmds.error("Select multiple transform nodes.")
        return

    src_node = sel_nodes[0]
    dest_nodes = sel_nodes[1:]

    logger.info(f"Connecting attributes from {src_node} to {len(dest_nodes)} nodes")

    for dest_node in dest_nodes:
        for attribute in enable_attributes:
            src_attr = f"{src_node}.{attribute}"
            dest_attr = f"{dest_node}.{attribute}"

            if not cmds.attributeQuery(attribute, node=src_node, exists=True):
                cmds.warning(f"Failed to connect value. Attribute not exists: {src_attr}")
                continue

            if not cmds.attributeQuery(attribute, node=dest_node, exists=True):
                cmds.warning(f"Failed to connect value. Attribute not exists: {dest_attr}")
                continue

            # Unlock if locked
            was_locked = cmds.getAttr(dest_attr, lock=True)
            if was_locked:
                cmds.setAttr(dest_attr, lock=False)

            # Connect attribute
            cmds.connectAttr(src_attr, dest_attr, force=True)

            # Restore lock state
            if was_locked:
                cmds.setAttr(dest_attr, lock=True)

            logger.debug(f"Connect value: {src_attr} -> {dest_attr}")


def zero_out(enable_attributes: list[str]) -> None:
    """
    Zero out specified attributes on selected nodes.

    Sets attributes to their default values:
    - Scale and visibility attributes: 1
    - All other attributes: 0

    Args:
        enable_attributes (list[str]): List of attributes to zero out (e.g., ["translateX", "rotateY"])

    Raises:
        RuntimeError: If no transform nodes are selected
    """
    sel_nodes = cmds.ls(sl=True, type="transform")
    if not sel_nodes:
        cmds.error("Select transform nodes.")
        return

    logger.info(f"Zeroing out attributes on {len(sel_nodes)} nodes")

    for node in sel_nodes:
        for attribute in enable_attributes:
            attr = f"{node}.{attribute}"

            if not cmds.attributeQuery(attribute, node=node, exists=True):
                cmds.warning(f"Failed to zero out. Attribute not exists: {attr}")
                continue

            if cmds.connectionInfo(attr, isDestination=True):
                cmds.error(f"Failed to zero out. Attribute is connected: {attr}")

            # Unlock if locked
            was_locked = cmds.getAttr(attr, lock=True)
            if was_locked:
                cmds.setAttr(attr, lock=False)

            # Set to default value
            if attribute in ["scaleX", "scaleY", "scaleZ", "visibility"]:
                cmds.setAttr(attr, 1)
            else:
                cmds.setAttr(attr, 0)

            # Restore lock state
            if was_locked:
                cmds.setAttr(attr, lock=True)

            logger.debug(f"Zero out: {attr}")


__all__ = ["copy_value", "connect_value", "zero_out"]
