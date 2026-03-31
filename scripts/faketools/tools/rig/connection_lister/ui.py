"""Attribute connection tool."""

from __future__ import annotations

from functools import partial
from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import base_window, maya_decorator
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QItemSelectionModel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QStandardItem,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.widgets import nodeAttr_widgets
from ....single_commands import pair_commands
from ....single_commands.base_commands import PairCommand
from . import widgets

logger = getLogger(__name__)

_instance = None

# Transform attributes to display at the top of the attribute list
_TRANSFORM_ATTRS = [
    "translate",
    "rotate",
    "scale",
    "shear",
    "translateX",
    "translateY",
    "translateZ",
    "rotateX",
    "rotateY",
    "rotateZ",
    "scaleX",
    "scaleY",
    "scaleZ",
    "shearXY",
    "shearXZ",
    "shearYZ",
    "visibility",
]

_EXCEPT_ATTR_TYPES = {"TdataCompound"}


def _list_type_attributes(node: str) -> tuple[list[str], list[str]]:
    """List type-level attributes of a node.

    Queries attribute information (compound check, type check) for a
    representative node. Results are the same for all nodes of the same type.

    Args:
        node: A representative node name.

    Returns:
        Pair of (transform_attrs, write_attrs) excluding user-defined attributes.
    """
    transform_attrs: list[str] = []
    if "transform" in cmds.nodeType(node, inherited=True):
        transform_attrs = list(_TRANSFORM_ATTRS)

    user_attrs_set = set(cmds.listAttr(node, userDefined=True) or [])
    skip_set = set(transform_attrs) | user_attrs_set

    write_attrs: list[str] = []
    for attr in cmds.listAttr(node, write=True) or []:
        if attr in skip_set:
            continue
        try:
            if cmds.attributeQuery(attr, node=node, listChildren=True):
                continue
            if cmds.getAttr(f"{node}.{attr}", type=True) in _EXCEPT_ATTR_TYPES:
                continue
            write_attrs.append(attr)
            skip_set.add(attr)
        except (RuntimeError, ValueError, TypeError):
            logger.debug(f"Failed to list attribute: {node}.{attr}")

    return transform_attrs, write_attrs


def _get_common_attributes(nodes: list[str]) -> list[str]:
    """Get attributes common to all given nodes.

    Groups nodes by type and queries type-level attributes only once
    per unique node type. User-defined attributes are queried per node.

    Args:
        nodes: List of node names.

    Returns:
        Common attribute names, ordered by the first node.
    """
    if not nodes:
        return []

    node_type_map: dict[str, str] = {}
    type_groups: dict[str, list[str]] = {}
    for node in nodes:
        ntype = cmds.nodeType(node)
        node_type_map[node] = ntype
        type_groups.setdefault(ntype, []).append(node)

    type_cache: dict[str, tuple[list[str], list[str]]] = {}
    for ntype, group in type_groups.items():
        type_cache[ntype] = _list_type_attributes(group[0])

    user_attrs_map: dict[str, list[str]] = {}
    for node in nodes:
        user_attrs_map[node] = cmds.listAttr(node, userDefined=True) or []

    def build_attrs(node: str) -> list[str]:
        transform_attrs, write_attrs = type_cache[node_type_map[node]]
        return transform_attrs + user_attrs_map[node] + write_attrs

    first_attrs = build_attrs(nodes[0])

    if len(nodes) == 1:
        return first_attrs

    common_set = set(first_attrs)
    for node in nodes[1:]:
        common_set &= set(build_attrs(node))

    return [attr for attr in first_attrs if attr in common_set]


class MainWindow(base_window.BaseMainWindow):
    """Attribute Connection Lister Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="ConnectionListerMainWindow",
            window_title="Connection Lister",
            central_layout="vertical",
        )

        # Load button
        load_button_layout = QHBoxLayout()
        load_button_layout.setContentsMargins(0, 0, 0, 0)

        source_load_button = QPushButton("Load Source")
        load_button_layout.addWidget(source_load_button)

        dest_load_button = QPushButton("Load Destination")
        load_button_layout.addWidget(dest_load_button)

        self.central_layout.addLayout(load_button_layout)

        # Node list
        node_list_layout = QHBoxLayout()
        node_list_layout.setContentsMargins(0, 0, 0, 0)

        self.source_node_list = nodeAttr_widgets.NodeListView()
        node_list_layout.addWidget(self.source_node_list)

        self.dest_node_list = nodeAttr_widgets.NodeListView()
        node_list_layout.addWidget(self.dest_node_list)

        self.central_layout.addLayout(node_list_layout)

        # Node count
        node_count_layout = QHBoxLayout()
        node_count_layout.setContentsMargins(0, 0, 0, 0)

        self.source_node_count_label = widgets.NodeCountLabel()
        node_count_layout.addWidget(self.source_node_count_label)

        self.dest_node_count_label = widgets.NodeCountLabel()
        node_count_layout.addWidget(self.dest_node_count_label)

        self.central_layout.addLayout(node_count_layout)

        # Operation
        operation_layout = QVBoxLayout()

        # Operation switch
        operation_switch_widget = widgets.OperationSwitchWidget()
        operation_layout.addWidget(operation_switch_widget)

        self.operation_stack_widget = QStackedWidget()
        operation_layout.addWidget(self.operation_stack_widget)

        # Attribute list
        attr_layout = QWidget()
        layout = QGridLayout(attr_layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.central_layout.spacing())

        self.operation_stack_widget.addWidget(attr_layout)

        self.source_attr_list = nodeAttr_widgets.AttributeListView(self.source_node_list)
        layout.addWidget(self.source_attr_list, 0, 0)

        self.source_filter_line_edit = QLineEdit()
        self.source_filter_line_edit.setPlaceholderText("Filter attributes...")
        self.source_filter_line_edit.setClearButtonEnabled(True)
        layout.addWidget(self.source_filter_line_edit, 1, 0)

        self.dest_attr_list = nodeAttr_widgets.AttributeListView(self.dest_node_list)
        layout.addWidget(self.dest_attr_list, 0, 1)

        self.dest_filter_line_edit = QLineEdit()
        self.dest_filter_line_edit.setPlaceholderText("Filter attributes...")
        self.dest_filter_line_edit.setClearButtonEnabled(True)
        layout.addWidget(self.dest_filter_line_edit, 1, 1)

        copy_value_button = QPushButton("Copy Value")
        layout.addWidget(copy_value_button, 2, 0)

        connect_button = QPushButton("Connect")
        layout.addWidget(connect_button, 2, 1)

        # Command list
        command_layout = QWidget()
        layout = QVBoxLayout(command_layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Load single pair commands
        commands = pair_commands.__all__
        if commands:
            for cls_name in commands:
                cls = getattr(pair_commands, cls_name)
                button = QPushButton(cls.get_name())
                layout.addWidget(button)

                button.clicked.connect(partial(self._execute_single_command, cls_name))

            spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            layout.addItem(spacer)

        # Add QScrollArea for command list
        command_list_scroll_area = QScrollArea()
        command_list_scroll_area.setWidget(command_layout)
        command_list_scroll_area.setWidgetResizable(True)
        self.operation_stack_widget.addWidget(command_list_scroll_area)

        self.central_layout.addLayout(operation_layout)

        # Signal & Slot
        source_load_button.clicked.connect(lambda: self._list_nodes(self.source_node_list, self._source_display_attributes))
        dest_load_button.clicked.connect(lambda: self._list_nodes(self.dest_node_list, self._dest_display_attributes))
        self.source_node_list.node_changed.connect(lambda: self._set_node_count(self.source_node_list, self.source_node_count_label))
        self.dest_node_list.node_changed.connect(lambda: self._set_node_count(self.dest_node_list, self.dest_node_count_label))
        self.source_node_list.selectionModel().selectionChanged.connect(
            lambda: self._set_node_count(self.source_node_list, self.source_node_count_label)
        )  # noqa
        self.dest_node_list.selectionModel().selectionChanged.connect(lambda: self._set_node_count(self.dest_node_list, self.dest_node_count_label))
        operation_switch_widget.button_changed.connect(self.__switch_operation)
        self.source_filter_line_edit.textChanged.connect(self.source_attr_list.attr_model.setFilterFixedString)
        self.dest_filter_line_edit.textChanged.connect(self.dest_attr_list.attr_model.setFilterFixedString)
        copy_value_button.clicked.connect(self._copy_value)
        connect_button.clicked.connect(self._connect_attribute)

        # Track signal connection state to prevent duplicate connections
        self._source_selection_connected = False
        self._dest_selection_connected = False

        # Adjust size
        width = self.sizeHint().width()
        height = self.minimumSizeHint().height()
        self.resize(width * 0.8, height * 1.5)

    def __switch_operation(self, index) -> None:
        """Switch operation stack widget.

        Args:
            index (int): The index of the operation stack widget.
        """
        self.operation_stack_widget.setCurrentIndex(index)

    @maya_decorator.error_handler
    def _list_nodes(self, node_list_widget: nodeAttr_widgets.NodeListView, display_attributes_callback: callable) -> None:
        """Update the node list

        Args:
            node_list_widget (NodeList): The node list widget.
            display_attributes_callback (callable): The function to display the attributes of the node.
        """
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("Please select the nodes to list.")

        shift_pressed = QApplication.keyboardModifiers() == Qt.ShiftModifier
        if shift_pressed:
            nodes = node_list_widget.get_all_nodes()
            selection_indexes = node_list_widget.selectionModel().selectedIndexes()
            if not nodes:
                nodes = sel_nodes
            else:
                existing_nodes_set = set(nodes)
                for node in sel_nodes:
                    if node not in existing_nodes_set:
                        nodes.append(node)
        else:
            nodes = sel_nodes

        node_list_widget.replace_nodes(nodes)

        # Connect the signal after setting the model (only once, with flag check)
        selection_model = node_list_widget.selectionModel()
        if node_list_widget is self.source_node_list:
            if not self._source_selection_connected:
                selection_model.selectionChanged.connect(display_attributes_callback)
                self._source_selection_connected = True
        else:
            if not self._dest_selection_connected:
                selection_model.selectionChanged.connect(display_attributes_callback)
                self._dest_selection_connected = True

        # Select the current selection
        if shift_pressed and selection_indexes:
            for index in selection_indexes:
                node_list_widget.selectionModel().select(index, QItemSelectionModel.Select)
        else:
            selection_model.select(node_list_widget.node_model.index(0, 0), QItemSelectionModel.Select)

    def _set_node_count(self, node_list_widget: nodeAttr_widgets.NodeListView, node_count_label: widgets.NodeCountLabel) -> None:
        """Set the node count.

        Args:
            node_list_widget (NodeList): The node list widget.
            node_count_label (NodeCountLabel): The node count label.
        """
        total_count = node_list_widget.get_count()
        selected_count = node_list_widget.get_selected_count()
        node_count_label.set_count(selected_count, total_count)

    def _source_display_attributes(self) -> None:
        """Display the attributes of the selected source nodes."""
        self._display_attributes(self.source_node_list, self.source_attr_list)

    def _dest_display_attributes(self) -> None:
        """Display the attributes of the selected destination nodes."""
        self._display_attributes(self.dest_node_list, self.dest_attr_list)

    def _display_attributes(
        self,
        node_list_widget: nodeAttr_widgets.NodeListView,
        attr_list_widget: nodeAttr_widgets.AttributeListView,
    ) -> None:
        """Display the common attributes of the selected nodes.

        Args:
            node_list_widget: The node list widget.
            attr_list_widget: The attribute list widget.
        """
        source_model = attr_list_widget.model().sourceModel()
        selected_indexes = node_list_widget.selectionModel().selectedIndexes()
        if not selected_indexes:
            source_model.beginResetModel()
            source_model.clear()
            source_model.endResetModel()
            return

        selected_nodes = [index.data() for index in selected_indexes]
        common_attributes = _get_common_attributes(selected_nodes)

        source_model.beginResetModel()
        source_model.clear()
        for attr in common_attributes:
            item = QStandardItem(attr)
            source_model.appendRow(item)
        source_model.endResetModel()

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Copy Attribute Value")
    def _copy_value(self) -> None:
        """Copy the value of the source attribute to the destination attribute."""
        self._transfer_attribute(self._copy_value_impl)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Connect Attribute")
    def _connect_attribute(self) -> None:
        """Connect the source attribute to the destination attribute."""
        self._transfer_attribute(self._connect_attribute_impl)

    def _transfer_attribute(self, func: callable) -> None:
        """Transfer the attribute value.

        Args:
            func (callable): The function to transfer the attribute value. (copy_value or connect_attribute)
        """
        source_nodes = self.source_node_list.get_selected_nodes()
        dest_nodes = self.dest_node_list.get_selected_nodes()
        source_attrs = self.source_attr_list.get_selected_attributes()
        dest_attrs = self.dest_attr_list.get_selected_attributes()

        if not source_nodes or not dest_nodes or not source_attrs or not dest_attrs:
            cmds.error("Please select the source and destination nodes and attributes.")

        if len(source_nodes) > 1 and len(source_nodes) != len(dest_nodes):
            cmds.error("Please select the same number of nodes or select only one source node.")

        if len(source_attrs) > 1 and len(source_attrs) != len(dest_attrs):
            cmds.error("Please select the same number of attributes or select only one source attribute.")

        if len(source_nodes) == 1:
            source_nodes = source_nodes * len(dest_nodes)

        if len(source_attrs) == 1:
            source_attrs = source_attrs * len(dest_attrs)

        for source_node, dest_node in zip(source_nodes, dest_nodes):
            for source_attr, dest_attr in zip(source_attrs, dest_attrs):
                func(source_node, source_attr, dest_node, dest_attr)

    @staticmethod
    def _copy_value_impl(source_node: str, source_attr: str, dest_node: str, dest_attr: str) -> None:
        """Copy the value of the source attribute to the destination attribute.

        Args:
            source_node (str): The source node name.
            source_attr (str): The source attribute name.
            dest_node (str): The destination node name.
            dest_attr (str): The destination attribute name.
        """
        source_plug = f"{source_node}.{source_attr}"
        dest_plug = f"{dest_node}.{dest_attr}"
        if cmds.getAttr(dest_plug, lock=True):
            cmds.error(f"The attribute is locked: {dest_plug}")

        if cmds.connectionInfo(dest_plug, isDestination=True):
            cmds.error(f"The attribute is connected: {dest_plug}")

        source_type = cmds.getAttr(source_plug, type=True)
        dest_type = cmds.getAttr(dest_plug, type=True)

        if source_type == "string" or dest_type == "string":
            if source_type != dest_type:
                cmds.error("Both attributes must be strings.")
            cmds.setAttr(dest_plug, cmds.getAttr(source_plug), type="string")
        elif source_type == "matrix" or dest_type == "matrix":
            if source_type != dest_type:
                cmds.error("Both attributes must be matrices.")
            cmds.setAttr(dest_plug, cmds.getAttr(source_plug), type="matrix")
        else:
            num_source_elements = cmds.attributeQuery(source_attr, node=source_node, numberOfChildren=True)
            num_dest_elements = cmds.attributeQuery(dest_attr, node=dest_node, numberOfChildren=True)
            if num_source_elements or num_dest_elements:
                if num_source_elements != num_dest_elements:
                    cmds.error("The number of elements in the compound attributes does not match.")

                cmds.setAttr(dest_plug, *cmds.getAttr(source_plug)[0])
            else:
                cmds.setAttr(dest_plug, cmds.getAttr(source_plug))

        logger.debug(f"Copied: {source_plug} -> {dest_plug}")

    @staticmethod
    def _connect_attribute_impl(source_node: str, source_attr: str, dest_node: str, dest_attr: str) -> None:
        """Connect the source attribute to the destination attribute.

        Args:
            source_node (str): The source node name.
            source_attr (str): The source attribute name.
            dest_node (str): The destination node name.
            dest_attr (str): The destination attribute name.
        """
        source_plug = f"{source_node}.{source_attr}"
        dest_plug = f"{dest_node}.{dest_attr}"

        if cmds.isConnected(source_plug, dest_plug, iuc=True):
            logger.debug(f"Already connected, skipped: {source_plug} -> {dest_plug}")
            return

        locked = cmds.getAttr(dest_plug, lock=True)
        if locked:
            cmds.setAttr(dest_plug, lock=False)

        try:
            source_type = cmds.getAttr(source_plug, type=True)
            dest_type = cmds.getAttr(dest_plug, type=True)

            if source_type == "string" or dest_type == "string":
                if source_type != dest_type:
                    cmds.error("Both attributes must be strings.")
                cmds.connectAttr(source_plug, dest_plug, f=True)
            elif source_type == "matrix" or dest_type == "matrix":
                if source_type != dest_type:
                    cmds.error("Both attributes must be matrices.")
                cmds.connectAttr(source_plug, dest_plug, f=True)
            else:
                cmds.connectAttr(source_plug, dest_plug, f=True)

            logger.debug(f"Connected: {source_plug} -> {dest_plug}")
        finally:
            if locked:
                cmds.setAttr(dest_plug, lock=True)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Execute Single Command")
    def _execute_single_command(self, command_name: str) -> None:
        """Execute the single command.

        Args:
            command_name (str): The single command class name.
        """
        if not hasattr(pair_commands, command_name):
            cmds.error(f"Command does not exist: {command_name}")

        single_command_cls = getattr(pair_commands, command_name)
        if not issubclass(single_command_cls, PairCommand):
            cmds.error(f"Command is not a pair command: {command_name}")

        source_nodes = self.source_node_list.get_selected_nodes()
        dest_nodes = self.dest_node_list.get_selected_nodes()

        if not source_nodes or not dest_nodes:
            cmds.error("Please select the source and destination nodes.")

        if len(source_nodes) > 1 and len(source_nodes) != len(dest_nodes):
            cmds.error("Please select the same number of nodes or select only one source node.")

        if len(source_nodes) == 1:
            source_nodes = source_nodes * len(dest_nodes)

        single_command_cls(source_nodes, dest_nodes)

        logger.debug(f"Executed: {command_name}")


def show_ui():
    """
    Show the Connection lister UI.

    Creates or raises the main window.

    Returns:
        MainWindow: The main window instance
    """
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
