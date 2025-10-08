"""
Remote slider command layer - Business logic for remote attribute slider.
"""

import maya.cmds as cmds

from ....lib import lib_attribute


class DagNodeValues:
    """Stores the values of specified attributes for specified nodes.

    This class is used to store reset values for nodes in the remote slider tool.

    Attributes:
        _data: Stored node attribute value data.
        _target_attrs: Target attributes to store.
    """

    def __init__(self, target_attrs: list[str]):
        """Initialize the class.

        Args:
            target_attrs: List of attribute names to track.
        """
        self._data = {}
        self._target_attrs = target_attrs

    def has_node(self, node: str) -> bool:
        """Check if the node exists in the data.

        Args:
            node: Node name.

        Returns:
            True if node exists in stored data.
        """
        return node in self._data

    def add_node(self, node: str):
        """Add a node and store its current attribute values.

        Args:
            node: Node name.

        Raises:
            RuntimeError: If node does not exist.
        """
        if not cmds.objExists(node):
            raise RuntimeError(f"Node does not exist: {node}")

        if self.has_node(node):
            cmds.warning(f"Node already added to data: {node}")
            return

        self._data[node] = {attr: cmds.getAttr(f"{node}.{attr}") for attr in self._target_attrs}

    def remove_node(self, node: str):
        """Remove a node from stored data.

        Args:
            node: Node name.
        """
        if not self.has_node(node):
            cmds.warning(f"Node does not exist in data: {node}")
            return

        del self._data[node]

    def update_node(self, node: str):
        """Update stored values for a node with current values.

        Args:
            node: Node name.

        Raises:
            RuntimeError: If node does not exist in Maya.
        """
        if not cmds.objExists(node):
            raise RuntimeError(f"Node does not exist: {node}")

        if not self.has_node(node):
            cmds.warning(f"Node does not exist in data: {node}")
            return

        self._data[node].update({attr: cmds.getAttr(f"{node}.{attr}") for attr in self._target_attrs})

    def get_node_value(self, node: str, attr: str) -> float:
        """Get a stored node attribute value.

        Args:
            node: Node name.
            attr: Attribute name.

        Returns:
            The stored attribute value.

        Raises:
            ValueError: If node or attribute not found in stored data.
        """
        if not self.has_node(node):
            raise ValueError(f"Node does not exist in data: {node}")

        if attr not in self._target_attrs:
            raise ValueError(f"Attribute does not exist in settings attributes: {attr}")

        return self._data[node][attr]


def validate_attributes(mode: str, node_attributes: list[str]) -> bool:
    """Validate if the attributes can be safely modified.

    Args:
        mode: Operation mode ('local_relative', 'local_absolute', 'world_relative').
        node_attributes: List of node.attribute strings.

    Returns:
        True if attributes can be modified, False otherwise.

    Notes:
        - World Relative mode only supports single translate or rotate attribute.
        - Checks if attributes are locked or connected.
    """
    status = True

    # In world_relative mode, also check sibling attributes
    if mode == "world_relative":
        # Check single attribute
        attributes = list(set([node_attribute.split(".")[-1] for node_attribute in node_attributes]))
        if len(attributes) > 1:
            cmds.warning("World Relative mode is only available for single attribute.")
            status = False
        else:
            # Check if the target attribute can be modified
            attribute = attributes[0]
            if attribute not in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
                cmds.warning("World Relative mode is only available for translate and rotate attributes.")
                status = False
            else:
                for i, node_attribute in enumerate(node_attributes):
                    node = node_attribute.split(".")[0]
                    if i == 0:
                        # Since node_attributes contains only one type of attribute, check only the first one
                        parent_attribute = cmds.attributeQuery(attribute, node=node, listParent=True)[0]

                    if not lib_attribute.is_modifiable(node, parent_attribute):
                        cmds.warning(f"Attribute is not modifiable: This attribute or its sibling attributes: {node_attribute}")
                        status = False

    elif mode in ["local_relative", "local_absolute"]:
        for node_attribute in node_attributes:
            node, attribute = node_attribute.split(".")
            if not lib_attribute.is_modifiable(node, attribute):
                cmds.warning(f"Attribute is not modifiable: {node_attribute}")
                status = False

    return status


def change_value_local_relative(node_attributes: list[str], diff_value: float):
    """Change attribute values in local relative mode.

    Args:
        node_attributes: List of node.attribute strings.
        diff_value: Difference to add to current values.
    """
    for node_attribute in node_attributes:
        current_value = cmds.getAttr(node_attribute)
        cmds.setAttr(node_attribute, current_value + diff_value)


def change_value_local_absolute(node_attributes: list[str], value: float):
    """Change attribute values in local absolute mode.

    Args:
        node_attributes: List of node.attribute strings.
        value: Absolute value to set.
    """
    for node_attribute in node_attributes:
        cmds.setAttr(node_attribute, value)


def change_value_world_relative(nodes: list[str], attribute: str, diff_value: float):
    """Change attribute values in world relative mode.

    Args:
        nodes: List of node names.
        attribute: Attribute name (must be translate or rotate).
        diff_value: Difference to add in world space.
    """
    axis = attribute[-1].lower()

    if "translate" in attribute:
        cmds.move(diff_value, nodes, relative=True, **{axis: True})
    else:
        cmds.rotate(diff_value, nodes, relative=True, fo=False, ws=True, **{axis: True})


def reset_value_local_relative(node_attributes: list[str], node_values: DagNodeValues) -> bool:
    """Reset attribute values to stored values in local relative mode.

    Args:
        node_attributes: List of node.attribute strings.
        node_values: DagNodeValues instance containing reset values.

    Returns:
        True if any scale attribute was reset (affects slider reset value).
    """
    for connect_element in node_attributes:
        node, attr = connect_element.split(".")
        reset_value = node_values.get_node_value(node, attr)
        cmds.setAttr(connect_element, reset_value)

    return False


def reset_value_local_absolute(node_attributes: list[str], control_attrs: list[str], control_reset_values: list[float]) -> bool:
    """Reset attribute values to default values in local absolute mode.

    Args:
        node_attributes: List of node.attribute strings.
        control_attrs: List of control attribute names.
        control_reset_values: List of default reset values.

    Returns:
        True if any scale attribute was reset (affects slider reset value).
    """
    absolute_only_scale = False

    for connect_element in node_attributes:
        _, attr = connect_element.split(".")
        reset_value = control_reset_values[control_attrs.index(attr)]
        cmds.setAttr(connect_element, reset_value)

        if "scale" in attr:
            absolute_only_scale = True

    return absolute_only_scale


def reset_value_world_relative(node_attributes: list[str], attribute: str, node_values: DagNodeValues) -> bool:
    """Reset attribute values to stored values in world relative mode.

    Args:
        node_attributes: List of node.attribute strings.
        attribute: Target attribute name.
        node_values: DagNodeValues instance containing reset values.

    Returns:
        False (scale not supported in world relative mode).
    """
    if "scale" in attribute:
        cmds.warning("World Relative mode is only available for translate and rotate attributes.")
        return False

    for connect_element in node_attributes:
        node, _ = connect_element.split(".")
        if "translate" in attribute:
            for reset_attr in ["translateX", "translateY", "translateZ"]:
                reset_value = node_values.get_node_value(node, reset_attr)
                cmds.setAttr(f"{node}.{reset_attr}", reset_value)
        else:
            for reset_attr in ["rotateX", "rotateY", "rotateZ"]:
                reset_value = node_values.get_node_value(node, reset_attr)
                cmds.setAttr(f"{node}.{reset_attr}", reset_value)

    return False


def step_value_local_relative(node_attributes: list[str], step_value: float):
    """Step attribute values in local relative mode.

    Args:
        node_attributes: List of node.attribute strings.
        step_value: Step value to add.
    """
    for node_attribute in node_attributes:
        current_value = cmds.getAttr(node_attribute)
        cmds.setAttr(node_attribute, current_value + step_value)


def step_value_local_absolute(node_attributes: list[str], current_slider_value: float, step_value: float):
    """Step attribute values in local absolute mode.

    Args:
        node_attributes: List of node.attribute strings.
        current_slider_value: Current slider value.
        step_value: Step value to add to slider value.
    """
    for node_attribute in node_attributes:
        cmds.setAttr(node_attribute, current_slider_value + step_value)


def step_value_world_relative(nodes: list[str], attribute: str, step_value: float):
    """Step attribute values in world relative mode.

    Args:
        nodes: List of node names.
        attribute: Attribute name (must be translate or rotate).
        step_value: Step value to add in world space.
    """
    axis = attribute[-1].lower()

    if "translate" in attribute:
        cmds.move(step_value, nodes, relative=True, **{axis: True})
    else:
        cmds.rotate(step_value, nodes, relative=True, fo=False, ws=True, **{axis: True})
