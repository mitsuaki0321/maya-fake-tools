"""Node list widget."""

from logging import getLogger

import maya.cmds as cmds

from ...lib_ui import base_window, maya_decorator
from ...lib_ui.qt_compat import (
    QApplication,
    QEvent,
    QItemSelectionModel,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QSortFilterProxyModel,
    QStandardItem,
    QStandardItemModel,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

logger = getLogger(__name__)

# Default transform attributes to display
DEFAULT_TRANSFORM_ATTRS = [
    "translateX",
    "translateY",
    "translateZ",
    "rotateX",
    "rotateY",
    "rotateZ",
    "scaleX",
    "scaleY",
    "scaleZ",
    "visibility",
]


class BaseListView(QListView):
    """Base class for list views with common functionality."""

    def __init__(self, parent=None):
        """Initialize the base list view.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setSelectionMode(QListView.ExtendedSelection)
        self.setEditTriggers(QListView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.viewport().installEventFilter(self)

    def eventFilter(self, source, event) -> bool:
        """Event filter to handle right-click and middle-click context menu.

        Args:
            source: Event source object.
            event: Event object.

        Returns:
            bool: True if event was handled, False otherwise.
        """
        if source is self.viewport() and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                position = event.pos()
                global_position = self.viewport().mapToGlobal(position)
                self.show_context_menu(global_position)
                return True
            elif event.button() == Qt.MiddleButton:
                return True

        return super().eventFilter(source, event)

    def show_context_menu(self, position) -> None:
        """Show context menu. Must be implemented by subclasses.

        Args:
            position: Global position for the context menu.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement show_context_menu")


class NodeListView(BaseListView):
    """Node list view."""

    node_changed = Signal()

    def __init__(self, parent=None):
        """Initialize the NodeList.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.node_model = QStandardItemModel(self)
        self.setModel(self.node_model)

    def show_context_menu(self, position) -> None:
        """Show context menu for node list.

        Args:
            position: Global position for the context menu.
        """
        menu = QMenu()

        menu.addAction("Select All Nodes", self.selectAll)

        menu.addSeparator()

        menu.addAction("Select Scene Nodes", self._select_scene_nodes)
        menu.addAction("Select All Scene Nodes", self._select_all_scene_nodes)

        menu.addSeparator()

        menu.addAction("Remove Nodes", self._remove_nodes)

        menu.exec_(position)

    @maya_decorator.undo_chunk("Select Nodes")
    @maya_decorator.error_handler
    def _select_scene_nodes(self) -> None:
        """Select the nodes in Maya scene that are selected in the node list."""
        selected_nodes = self.get_selected_nodes()
        if selected_nodes:
            cmds.select(selected_nodes, replace=True)
        else:
            cmds.select(clear=True)

    @maya_decorator.undo_chunk("Select All Nodes")
    @maya_decorator.error_handler
    def _select_all_scene_nodes(self) -> None:
        """Select all nodes in the node list in Maya scene."""
        all_nodes = self.get_all_nodes()
        if all_nodes:
            cmds.select(all_nodes, replace=True)
        else:
            cmds.select(clear=True)

    def add_nodes(self, nodes: list[str]) -> None:
        """Add the nodes to the node list.

        Args:
            nodes (list[str]): The nodes to add.
        """
        if not nodes:
            return

        # Use beginInsertRows/endInsertRows for batch processing
        from ...lib_ui.qt_compat import QModelIndex

        first = self.node_model.rowCount()
        last = first + len(nodes) - 1
        self.node_model.beginInsertRows(QModelIndex(), first, last)
        for node in nodes:
            item = QStandardItem(node)
            self.node_model.appendRow(item)
        self.node_model.endInsertRows()

        self.node_changed.emit()

    def replace_nodes(self, nodes: list[str]) -> None:
        """Replace the nodes in the node list.

        Args:
            nodes (list[str]): The nodes to replace.
        """
        # Use beginResetModel/endResetModel for batch processing
        self.node_model.beginResetModel()
        self.node_model.clear()
        for node in nodes:
            item = QStandardItem(node)
            self.node_model.appendRow(item)
        self.node_model.endResetModel()
        self.node_changed.emit()

    def _remove_nodes(self) -> None:
        """Remove the selected nodes from the node list."""
        selected_indexes = self.selectionModel().selectedIndexes()
        for index in sorted(selected_indexes, key=lambda x: x.row(), reverse=True):
            self.node_model.removeRow(index.row())

        self.node_changed.emit()

    def get_selected_nodes(self) -> list[str]:
        """Get the selected nodes.

        Returns:
            list[str]: The selected nodes.
        """
        selected_indexes = self.selectionModel().selectedIndexes()
        return [index.data() for index in selected_indexes]

    def get_selected_count(self) -> int:
        """Get the number of selected nodes.

        Returns:
            int: The number of selected nodes.
        """
        return len(self.get_selected_nodes())

    def get_all_nodes(self) -> list[str]:
        """Get all the nodes.

        Returns:
            list[str]: All the nodes.
        """
        return [self.node_model.item(i).text() for i in range(self.node_model.rowCount())]

    def get_count(self) -> int:
        """Get the number of nodes.

        Returns:
            int: The number of nodes.
        """
        return self.node_model.rowCount()


class AttributeListView(BaseListView):
    """Attribute list view."""

    attribute_lock_changed = Signal()

    def __init__(self, node_widgets: NodeListView, parent=None):
        """Initialize the AttributeList.

        Args:
            node_widgets (NodeListView): The node list widget.
            parent: Parent widget.
        """
        super().__init__(parent)

        self.attr_model = QSortFilterProxyModel(self)
        self.attr_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.attribute_source_model = QStandardItemModel(self)
        self.attr_model.setSourceModel(self.attribute_source_model)
        self.setModel(self.attr_model)

        self.node_widgets = node_widgets

    def show_context_menu(self, position) -> None:
        """Show context menu for attribute list.

        Args:
            position: Global position for the context menu.
        """
        menu = QMenu()

        menu.addAction("Lock", self._lock_attributes)
        menu.addAction("Unlock", self._unlock_attributes)

        menu.addSeparator()

        menu.addAction("Keyable", self._keyable_attributes)
        menu.addAction("Unkeyable", self._unkeyable_attributes)

        menu.exec_(position)

    @maya_decorator.undo_chunk("Lock Attributes")
    @maya_decorator.error_handler
    def _lock_attributes(self) -> None:
        """Lock the selected attributes."""
        selected_nodes = self.node_widgets.get_selected_nodes()
        selected_attrs = self.get_selected_attributes()

        if not selected_nodes or not selected_attrs:
            return

        for node in selected_nodes:
            for attr in selected_attrs:
                cmds.setAttr(f"{node}.{attr}", lock=True)

        self.attribute_lock_changed.emit()

    @maya_decorator.undo_chunk("Unlock Attributes")
    @maya_decorator.error_handler
    def _unlock_attributes(self) -> None:
        """Unlock the selected attributes."""
        selected_nodes = self.node_widgets.get_selected_nodes()
        selected_attrs = self.get_selected_attributes()

        if not selected_nodes or not selected_attrs:
            return

        for node in selected_nodes:
            for attr in selected_attrs:
                cmds.setAttr(f"{node}.{attr}", lock=False)

        self.attribute_lock_changed.emit()

    @maya_decorator.undo_chunk("Keyable Attributes")
    @maya_decorator.error_handler
    def _keyable_attributes(self) -> None:
        """Set the selected attributes keyable."""
        selected_nodes = self.node_widgets.get_selected_nodes()
        selected_attrs = self.get_selected_attributes()

        if not selected_nodes or not selected_attrs:
            return

        for node in selected_nodes:
            for attr in selected_attrs:
                cmds.setAttr(f"{node}.{attr}", keyable=True)

    @maya_decorator.undo_chunk("Unkeyable Attributes")
    @maya_decorator.error_handler
    def _unkeyable_attributes(self) -> None:
        """Set the selected attributes unkeyable."""
        selected_nodes = self.node_widgets.get_selected_nodes()
        selected_attrs = self.get_selected_attributes()

        if not selected_nodes or not selected_attrs:
            return

        for node in selected_nodes:
            for attr in selected_attrs:
                cmds.setAttr(f"{node}.{attr}", keyable=False)

    def get_selected_attributes(self) -> list[str]:
        """Get the selected attributes.

        Returns:
            list[str]: The selected attributes.
        """
        selected_indexes = self.selectionModel().selectedIndexes()
        return [index.data() for index in selected_indexes]

    def get_all_attributes(self) -> list[str]:
        """Get all the attributes.

        Returns:
            list[str]: All the attributes.
        """
        source_model = self.attr_model.sourceModel()
        return [source_model.item(i).text() for i in range(source_model.rowCount())]


class NodeAttributeWidgets(QWidget):
    """Node attribute widgets."""

    def __init__(self, parent=None):
        """Initialize the NodeListWidget."""
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        spacing = base_window.get_spacing(self)
        self.main_layout.setSpacing(int(spacing * 0.75))

        load_button = QPushButton("Load")
        self.main_layout.addWidget(load_button)

        self.node_list = NodeListView()
        self.main_layout.addWidget(self.node_list)

        self.attr_list = AttributeListView(self.node_list)
        self.main_layout.addWidget(self.attr_list)

        self.filter_line_edit = QLineEdit()
        self.filter_line_edit.setPlaceholderText("Filter attributes...")
        self.main_layout.addWidget(self.filter_line_edit)

        self.setLayout(self.main_layout)

        # Signal & Slot
        load_button.clicked.connect(self._list_nodes)
        self.filter_line_edit.textChanged.connect(self.attr_list.attr_model.setFilterFixedString)

        # Track signal connection state
        self._selection_connected = False

    @maya_decorator.error_handler
    def _list_nodes(self) -> None:
        """Update the node list with selected nodes from Maya.

        If Shift key is pressed, adds to existing nodes. Otherwise replaces the list.
        """
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("Please select the nodes to list.")

        shift_pressed = QApplication.keyboardModifiers() == Qt.ShiftModifier
        if shift_pressed:
            nodes = self.get_all_nodes()
            selection_indexes = self.node_list.selectionModel().selectedIndexes()
            if not nodes:
                nodes = sel_nodes
            else:
                for node in sel_nodes:
                    if node not in nodes:
                        nodes.append(node)
        else:
            nodes = sel_nodes

        self.node_list.replace_nodes(nodes)

        # Connect the signal after setting the model (only once)
        selection_model = self.node_list.selectionModel()
        if not self._selection_connected:
            selection_model.selectionChanged.connect(self._display_attributes)
            self._selection_connected = True

        # Select the current selection
        if shift_pressed and selection_indexes:
            for index in selection_indexes:
                selection_model.select(index, QItemSelectionModel.Select)
        else:
            selection_model.select(self.node_list.node_model.index(0, 0), QItemSelectionModel.Select)

    def _display_attributes(self) -> None:
        """Display the common attributes of the selected nodes.

        Shows only attributes that are common to all selected nodes.
        """
        source_model = self.attr_list.model().sourceModel()
        selected_indexes = self.node_list.selectionModel().selectedIndexes()
        if not selected_indexes:
            source_model.beginResetModel()
            source_model.clear()
            source_model.endResetModel()
            return

        selected_nodes = [index.data() for index in selected_indexes]
        first_node_attrs = self._list_attributes(selected_nodes[0])

        # Use set for O(1) lookup when computing common attributes
        if len(selected_nodes) > 1:
            common_attrs_set = set(first_node_attrs)
            for node in selected_nodes[1:]:
                node_attrs_set = set(self._list_attributes(node))
                common_attrs_set &= node_attrs_set
            # Preserve order from the first node's attributes
            common_attributes = [attr for attr in first_node_attrs if attr in common_attrs_set]
        else:
            common_attributes = first_node_attrs

        # Batch update using beginResetModel/endResetModel
        source_model.beginResetModel()
        source_model.clear()
        for attr in common_attributes:
            item = QStandardItem(attr)
            source_model.appendRow(item)
        source_model.endResetModel()

    def _list_attributes(self, node: str, **kwargs) -> list[str]:
        """List writable attributes of a node.

        Includes default transform attributes (for transform nodes), user-defined attributes,
        and other writable attributes excluding compound attributes and specified types.

        Args:
            node (str): The node name.
            **kwargs: Optional keyword arguments.
                except_attr_types (list[str]): Attribute types to exclude.
                    Defaults to ["message", "TdataCompound"].

        Returns:
            list[str]: List of attribute names.
        """
        except_attr_types = kwargs.pop("except_attr_types", ["message", "TdataCompound"])

        result_attrs = []

        if "transform" in cmds.nodeType(node, inherited=True):
            result_attrs.extend(DEFAULT_TRANSFORM_ATTRS)

        user_attrs = cmds.listAttr(node, userDefined=True)
        if user_attrs:
            result_attrs.extend(user_attrs)

        write_attrs = cmds.listAttr(node, write=True) or []
        for attr in write_attrs:
            if attr in result_attrs:
                continue
            try:
                if cmds.attributeQuery(attr, node=node, listChildren=True):
                    continue
                if cmds.getAttr(f"{node}.{attr}", type=True) in except_attr_types:
                    continue
                result_attrs.append(attr)
            except (RuntimeError, ValueError, TypeError) as e:
                # Maya commands can raise various exceptions for invalid/inaccessible attributes
                logger.debug(f"Failed to query attribute: {node}.{attr}: {e}")

        return result_attrs

    def get_selected_nodes(self) -> list[str]:
        """Get the selected nodes.

        Returns:
            list[str]: The selected nodes.
        """
        return self.node_list.get_selected_nodes()

    def get_selected_attributes(self) -> list[str]:
        """Get the selected attributes.

        Returns:
            list[str]: The selected attributes.
        """
        return self.attr_list.get_selected_attributes()

    def get_all_nodes(self) -> list[str]:
        """Get all the nodes.

        Returns:
            list[str]: All the nodes.
        """
        return self.node_list.get_all_nodes()

    def get_all_attributes(self) -> list[str]:
        """Get all the attributes.

        Returns:
            list[str]: All the attributes.
        """
        return self.attr_list.get_all_attributes()
