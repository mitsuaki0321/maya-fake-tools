"""
Maya attribute functions.
"""

import maya.api.OpenMaya as om
import maya.cmds as cmds


def is_modifiable(node: str, attribute: str, *, children: bool = False) -> bool:
    """Returns whether the attribute is modifiable.

    Args:
        node (str): The node name.
        attribute (str): The attribute name.
        children (bool): Whether to check child attributes. Default is False.

    Notes:
        - The static writable flag is not checked, so it may return False even if the attribute is actually not modifiable.

    Raises:
        ValueError: If the node or attribute does not exist.

    Returns:
        bool: Whether the attribute is modifiable.
    """
    if not cmds.objExists(node):
        raise ValueError(f"Node does not exist: {node}")

    if not cmds.attributeQuery(attribute, node=node, exists=True):
        raise ValueError(f"Attribute does not exist: {node}.{attribute}")

    sel = om.MSelectionList()
    sel.add(node)
    obj = sel.getDependNode(0)
    fn = om.MFnDependencyNode(obj)
    try:
        plug = fn.findPlug(attribute, False)
    except RuntimeError:
        return False

    return not bool(plug.isFreeToChange(checkAncestors=True, checkChildren=children))


def get_channelBox_attr(node: str) -> list:
    """Returns the channelBox show attributes.

    Args:
        node (str): The target node.

    Returns:
        list: The channelBox attributes.
    """
    if not cmds.objExists(node):
        raise ValueError(f"Node does not exist: {node}")

    keyable_attributes = cmds.listAttr(node, keyable=True) or []
    channel_attributes = cmds.listAttr(node, channelBox=True) or []

    return keyable_attributes + channel_attributes


class AttributeLockHandler:
    """Class to temporarily unlock locked attributes."""

    def __init__(self):
        """Constructor."""
        self._lock_attrs = []

    def stock_lock_attrs(self, node: str, attributes: list, *, include_parent: bool = False) -> None:
        """Stocks the lock attributes.

        Args:
            node (str): The target node.
            attributes (list): The target attributes.
            include_parent (bool): Whether to include the parent attribute. Default is False.
        """
        if not cmds.objExists(node):
            raise ValueError(f"Node does not exist: {node}")

        not_exist_attrs = [attr for attr in attributes if cmds.attributeQuery(attr, node=node, exists=True)]
        if not not_exist_attrs:
            raise ValueError(f"Attributes do not exist: {not_exist_attrs}")

        if include_parent:
            target_attributes = set(attributes)
            for attr in attributes:
                parent_attr = cmds.attributeQuery(attr, node=node, listParent=True)
                if parent_attr:
                    target_attributes.add(parent_attr[0])

            attributes = list(target_attributes)

        for attr in attributes:
            if not cmds.getAttr(f"{node}.{attr}", lock=True):
                continue
            cmds.setAttr(f"{node}.{attr}", lock=False)
            self._lock_attrs.append(attr)

    def restore_lock_attrs(self, node: str) -> None:
        """Restores the lock attributes.

        Args:
            node (str): The target node.
        """
        if not self._lock_attrs:
            return

        for attr in self._lock_attrs:
            cmds.setAttr(f"{node}.{attr}", lock=True)
        self._lock_attrs.clear()
