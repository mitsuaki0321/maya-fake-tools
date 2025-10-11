"""Transform hierarchy management for retarget transforms."""

from __future__ import annotations

import logging

import maya.cmds as cmds

logger = logging.getLogger(__name__)


class TransformHierarchy:
    """Class to register and retrieve the hierarchy of transform nodes.

    Attributes:
        _hierarchy (dict): The hierarchy data.
            {
                'node_name': {
                    'parent': str, # Parent node name.
                    'children': list[str], # Children node names.
                    'depth': int # Depth of the node.
                    'register_parent': str, # Registered parent node name.
                    'register_children': list[str], # Registered children node names.
                }
            }
    """

    def __init__(self):
        """Constructor."""
        self._hierarchy = {}

    @classmethod
    def set_hierarchy_data(cls, data: dict) -> TransformHierarchy:
        """Set the hierarchy data.

        Args:
            data (dict): The hierarchy data.

        Returns:
            TransformHierarchy: The hierarchy handler instance.

        Raises:
            ValueError: If data is invalid or missing required fields.
        """
        if not data:
            raise ValueError("Hierarchy data is not specified.")

        if not isinstance(data, dict):
            raise ValueError("Hierarchy data is not a dictionary.")

        # Validate the data
        for node_data in data.values():
            if not isinstance(node_data, dict):
                raise ValueError(f"Invalid node data: {node_data}")

            if "parent" not in node_data:
                raise ValueError(f"Parent is not specified: {node_data}")

            if "children" not in node_data:
                raise ValueError(f"Children is not specified: {node_data}")

            if "depth" not in node_data:
                raise ValueError(f"Depth is not specified: {node_data}")

            if "register_parent" not in node_data:
                raise ValueError(f"Register parent is not specified: {node_data}")

            if "register_children" not in node_data:
                raise ValueError(f"Register children is not specified: {node_data}")

        instance = cls()
        instance._hierarchy = data

        return instance

    def get_hierarchy_data(self) -> dict:
        """Get the hierarchy data.

        Returns:
            dict: The hierarchy data.
        """
        return self._hierarchy

    def register_node(self, node: str) -> None:
        """Register the node to the hierarchy.

        Args:
            node (str): The target node.

        Raises:
            ValueError: If node is invalid or not a transform.
        """
        if not node:
            raise ValueError("Node is not specified.")

        if not cmds.objExists(node):
            raise ValueError(f"Node does not exist: {node}")

        if "transform" not in cmds.nodeType(node, inherited=True):
            raise ValueError(f"Node is not a transform: {node}")

        if node in self._hierarchy:
            cmds.warning(f"Node is already registered. Overwrite: {node}")

        parent_node = cmds.listRelatives(node, parent=True, path=True)
        child_nodes = cmds.listRelatives(node, children=True, path=True) or []

        full_path = cmds.ls(node, long=True)[0]
        depth = len(full_path.split("|")) - 1

        self._hierarchy[node] = {
            "parent": parent_node and parent_node[0] or None,
            "children": child_nodes,
            "register_parent": None,
            "register_children": [],
            "depth": depth,
        }

        self._update_register_hierarchy()

        logger.debug(f"Registered node: {node}")

    def _update_register_hierarchy(self) -> None:
        """Update the registered hierarchy in the data."""
        # Clear the registered hierarchy
        for node in self._hierarchy:
            self._hierarchy[node]["register_parent"] = None
            self._hierarchy[node]["register_children"] = []

        # Update the registered hierarchy
        for node in self._hierarchy:
            parent = self._hierarchy[node]["parent"]
            if not parent:
                continue

            full_path = cmds.ls(node, long=True)[0]
            parent_nodes = full_path.split("|")[1:-1]

            for parent_node in reversed(parent_nodes):
                if parent_node in self._hierarchy:
                    self._hierarchy[node]["register_parent"] = parent_node
                    self._hierarchy[parent_node]["register_children"].append(node)

                    logger.debug(f"Updated register hierarchy: {node} -> Parent: {parent_node}, Children: {node}")
                    break

    def get_parent(self, node: str) -> str | None:
        """Get the parent node of the node.

        Args:
            node (str): The target node.

        Returns:
            str | None: The parent node.

        Raises:
            ValueError: If node is not specified or not registered.
        """
        if not node:
            raise ValueError("Node is not specified.")

        if node not in self._hierarchy:
            raise ValueError(f"Node is not registered: {node}")

        return self._hierarchy[node]["parent"]

    def get_children(self, node: str) -> list[str]:
        """Get the children nodes of the node.

        Args:
            node (str): The target node.

        Returns:
            list[str]: The children nodes.

        Raises:
            ValueError: If node is not specified or not registered.
        """
        if not node:
            raise ValueError("Node is not specified.")

        if node not in self._hierarchy:
            raise ValueError(f"Node is not registered: {node}")

        return self._hierarchy[node]["children"]

    def get_registered_parent(self, node: str) -> str | None:
        """Get the registered parent node of the node.

        Args:
            node (str): The target node.

        Returns:
            str | None: The registered parent node.

        Raises:
            ValueError: If node is not specified or not registered.
        """
        if not node:
            raise ValueError("Node is not specified.")

        if node not in self._hierarchy:
            raise ValueError(f"Node is not registered: {node}")

        return self._hierarchy[node]["register_parent"]

    def get_registered_children(self, node: str) -> list[str]:
        """Get the registered children nodes of the node.

        Args:
            node (str): The target node.

        Returns:
            list[str]: The registered children nodes.

        Raises:
            ValueError: If node is not specified or not registered.
        """
        if not node:
            raise ValueError("Node is not specified.")

        if node not in self._hierarchy:
            raise ValueError(f"Node is not registered: {node}")

        return self._hierarchy[node]["register_children"]

    def __repr__(self):
        """Return the string representation of the hierarchy."""
        return f"{self.__class__.__name__}({self._hierarchy})"

    def __str__(self):
        """Return the string representation of the hierarchy."""
        return f"{self._hierarchy}"


__all__ = ["TransformHierarchy"]
