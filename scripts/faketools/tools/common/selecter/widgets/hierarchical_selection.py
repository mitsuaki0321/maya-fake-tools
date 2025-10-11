"""Hierarchical selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib.lib_selection import get_children, get_hierarchy, get_leaf_nodes, get_parents, get_siblings
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QWidget
from .constants import HIERARCHY_COLOR, selecter_handler
from .selecter_button import SelecterButton


class HierarchicalSelectionWidget(QWidget):
    """Hierarchical Selection Widget.

    Provides DAG hierarchy navigation functionality:
    - Parent, children, siblings selection
    - Hierarchy traversal (all descendants, bottom nodes)
    """

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent=parent)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(base_window.get_spacing(self, "horizontal") * 0.5)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Parent selection button
        parent_button = SelecterButton("PAR", color=HIERARCHY_COLOR)
        main_layout.addWidget(parent_button)

        # Children selection button
        children_button = SelecterButton("CHI", color=HIERARCHY_COLOR)
        main_layout.addWidget(children_button)

        # Siblings selection button
        siblings_button = SelecterButton("SIB", color=HIERARCHY_COLOR)
        main_layout.addWidget(siblings_button)

        # All transform children button
        children_all_button = SelecterButton("ALL", color=HIERARCHY_COLOR)
        main_layout.addWidget(children_all_button)

        # Bottom children button
        children_bottom_button = SelecterButton("BTM", color=HIERARCHY_COLOR)
        main_layout.addWidget(children_bottom_button)

        # Full hierarchy button
        hierarchy_all_button = SelecterButton("HIE", color=HIERARCHY_COLOR)
        main_layout.addWidget(hierarchy_all_button)

        self.setLayout(main_layout)

        # Connect signals
        parent_button.clicked.connect(self.parent_selection)
        children_button.clicked.connect(self.children_selection)
        siblings_button.clicked.connect(self.siblings_selection)
        children_all_button.clicked.connect(self.children_all_transform_selection)
        children_bottom_button.clicked.connect(self.children_bottom_selection)
        hierarchy_all_button.clicked.connect(self.hierarchy_all_selection)

    @maya_decorator.undo_chunk("Selecter: Parent Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def parent_selection(self, nodes: list[str]):
        """Select the parent nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Parent node list.
        """
        result_nodes = get_parents(nodes)

        if not result_nodes:
            cmds.warning("No parent node found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Children Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def children_selection(self, nodes: list[str]):
        """Select the children nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Children node list.
        """
        result_nodes = get_children(nodes, include_shape=False)

        if not result_nodes:
            cmds.warning("No children nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Siblings Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def siblings_selection(self, nodes: list[str]):
        """Select the siblings nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Siblings node list.
        """
        result_nodes = get_siblings(nodes)

        if not result_nodes:
            cmds.warning("No sibling nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Children Transform All Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def children_all_transform_selection(self, nodes: list[str]):
        """Select all transform children nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: All transform children node list.
        """
        result_nodes = get_hierarchy(nodes, include_shape=False)

        if not result_nodes:
            cmds.warning("No children nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Children Bottom Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def children_bottom_selection(self, nodes: list[str]):
        """Select the bottom children nodes (leaf nodes).

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Leaf node list.
        """
        result_nodes = get_leaf_nodes(nodes)

        if not result_nodes:
            cmds.warning("No leaf nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Hierarchy All Selection")
    @maya_decorator.error_handler
    @selecter_handler
    def hierarchy_all_selection(self, nodes: list[str]):
        """Select the full hierarchy nodes (including shapes).

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Full hierarchy node list.
        """
        result_nodes = get_hierarchy(nodes, include_shape=True)

        if not result_nodes:
            cmds.warning("No nodes found in hierarchy.")
            return nodes

        return result_nodes


__all__ = ["HierarchicalSelectionWidget"]
