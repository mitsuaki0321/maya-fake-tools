"""UI module for Node Lister.

Three-stage filtering UI (selectFilter -> nodeFilter -> matchFilter)
for node acquisition, with attribute list, value editing, and deletion.
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import BaseMainWindow, ToolSettingsManager, error_handler, get_maya_main_window, get_spacing, undo_chunk
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QSortFilterProxyModel,
    QStandardItem,
    QStandardItemModel,
    Qt,
)
from ....lib_ui.ui_utils import get_relative_size
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Node Lister Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="NodeListerMainWindow",
            window_title="Node Lister",
            central_layout="vertical",
        )

        self._raw_nodes: list[str] = []
        self._updating_selection = False

        self.settings = ToolSettingsManager(tool_name="node_lister", category="rig")

        self._setup_ui()
        self._connect_signals()
        self._restore_settings()

        width, height = get_relative_size(self, width_ratio=2.0, height_ratio=3.5)
        self.resize(width, height)

    def _setup_ui(self) -> None:
        """Build the UI widgets."""
        spacing = get_spacing(self, direction="vertical")

        # --- selectFilter row ---
        select_row = QHBoxLayout()
        select_row.setSpacing(int(spacing * 0.5))
        select_label = QLabel("selectFilter:")
        self.select_combo = QComboBox()
        for f in command.DEFAULT_SELECT_FILTERS:
            self.select_combo.addItem(f.label)
        select_row.addWidget(select_label)
        select_row.addWidget(self.select_combo, 1)
        self.central_layout.addLayout(select_row)

        # --- Load button ---
        self.load_button = QPushButton("Load")
        self.central_layout.addWidget(self.load_button)

        # --- nodeFilter row ---
        node_filter_row = QHBoxLayout()
        node_filter_row.setSpacing(int(spacing * 0.5))
        node_filter_label = QLabel("nodeFilter:")
        self.node_filter_edit = QLineEdit()
        self.node_filter_edit.setPlaceholderText("node type")
        self.node_filter_inherited_cb = QCheckBox("i")
        self.node_filter_inherited_cb.setToolTip("inherited")
        node_filter_row.addWidget(node_filter_label)
        node_filter_row.addWidget(self.node_filter_edit, 1)
        node_filter_row.addWidget(self.node_filter_inherited_cb)
        self.central_layout.addLayout(node_filter_row)

        # --- matchFilter row ---
        match_filter_row = QHBoxLayout()
        match_filter_row.setSpacing(int(spacing * 0.5))
        match_filter_label = QLabel("matchFilter:")
        self.match_filter_edit = QLineEdit()
        self.match_filter_edit.setPlaceholderText("name regex")
        self.match_filter_ignorecase_cb = QCheckBox("i")
        self.match_filter_ignorecase_cb.setToolTip("ignorecase")
        match_filter_row.addWidget(match_filter_label)
        match_filter_row.addWidget(self.match_filter_edit, 1)
        match_filter_row.addWidget(self.match_filter_ignorecase_cb)
        self.central_layout.addLayout(match_filter_row)

        # --- Node list ---
        self.node_list = QListView()
        self.node_model = QStandardItemModel()
        self.node_list.setModel(self.node_model)
        self.node_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.node_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.node_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.central_layout.addWidget(self.node_list, 1)

        # --- Attribute list ---
        self.attr_source_model = QStandardItemModel()
        self.attr_proxy_model = QSortFilterProxyModel()
        self.attr_proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.attr_proxy_model.setSourceModel(self.attr_source_model)

        self.attr_list = QListView()
        self.attr_list.setModel(self.attr_proxy_model)
        self.attr_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.attr_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attr_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.central_layout.addWidget(self.attr_list, 1)

        # --- Attribute filter ---
        self.attr_filter_edit = QLineEdit()
        self.attr_filter_edit.setPlaceholderText("Filter attributes...")
        self.attr_filter_edit.setClearButtonEnabled(True)
        self.central_layout.addWidget(self.attr_filter_edit)

        # --- Value field ---
        self.value_field = QLineEdit()
        self.central_layout.addWidget(self.value_field)

        # --- Delete button ---
        self.delete_button = QPushButton("Delete Attributes")
        self.central_layout.addWidget(self.delete_button)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Node filter signals
        self.load_button.clicked.connect(self._load_nodes)
        self.node_filter_edit.textChanged.connect(self._apply_filters)
        self.node_filter_inherited_cb.toggled.connect(self._apply_filters)
        self.match_filter_edit.textChanged.connect(self._apply_filters)
        self.match_filter_ignorecase_cb.toggled.connect(self._apply_filters)
        self.node_list.selectionModel().selectionChanged.connect(self._on_node_selection_changed)
        self.node_list.customContextMenuRequested.connect(self._show_node_context_menu)

        # Attribute signals
        self.attr_filter_edit.textChanged.connect(self.attr_proxy_model.setFilterFixedString)
        self.attr_list.selectionModel().selectionChanged.connect(self._display_value)
        self.attr_list.customContextMenuRequested.connect(self._show_attr_context_menu)
        self.value_field.returnPressed.connect(self._set_value)
        self.delete_button.clicked.connect(self._delete_attributes)

    # ------------------------------------------------------------------
    # Node slots
    # ------------------------------------------------------------------

    @error_handler
    def _load_nodes(self) -> None:
        """Load nodes from the selected filter."""
        index = self.select_combo.currentIndex()
        select_filter = command.DEFAULT_SELECT_FILTERS[index]
        self._raw_nodes = select_filter.get_nodes()
        logger.debug("Loaded %d nodes via %s", len(self._raw_nodes), select_filter.label)
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply nodeFilter and matchFilter to cached nodes."""
        nodes = list(self._raw_nodes)

        type_str = self.node_filter_edit.text().strip()
        inherited = self.node_filter_inherited_cb.isChecked()
        nodes = command.filter_by_node_type(nodes, type_str, inherited)

        pattern = self.match_filter_edit.text().strip()
        ignorecase = self.match_filter_ignorecase_cb.isChecked()
        nodes = command.filter_by_name(nodes, pattern, ignorecase)

        self._update_node_list(nodes)

    def _update_node_list(self, nodes: list[str]) -> None:
        """Replace node list contents with the given nodes."""
        self._updating_selection = True
        try:
            self.node_model.beginResetModel()
            self.node_model.clear()
            for node in nodes:
                item = QStandardItem(node)
                item.setEditable(False)
                self.node_model.appendRow(item)
            self.node_model.endResetModel()
        finally:
            self._updating_selection = False

    def _on_node_selection_changed(self) -> None:
        """Update attribute list when node selection changes."""
        if self._updating_selection:
            return
        self._display_attributes()

    def _show_node_context_menu(self, pos) -> None:
        """Show context menu on the node list."""
        menu = QMenu(self)
        menu.addAction("Select All Nodes", self._select_all_nodes)
        menu.addSeparator()
        menu.addAction("Select Scene Nodes", self._select_scene_nodes)
        menu.addAction("Select All Scene Nodes", self._select_all_scene_nodes)
        menu.exec_(self.node_list.mapToGlobal(pos))

    def _select_all_nodes(self) -> None:
        """Select all nodes in the list."""
        self.node_list.selectAll()

    @error_handler
    @undo_chunk("Node Lister: Select Scene Nodes")
    def _select_scene_nodes(self) -> None:
        """Select the nodes in Maya scene that are selected in the node list."""
        selected = self._get_selected_nodes()
        if selected:
            cmds.select(selected, replace=True)
        else:
            cmds.select(clear=True)

    @error_handler
    @undo_chunk("Node Lister: Select All Scene Nodes")
    def _select_all_scene_nodes(self) -> None:
        """Select all nodes in the list in Maya scene."""
        all_nodes = self._get_all_nodes()
        if all_nodes:
            cmds.select(all_nodes, replace=True)
        else:
            cmds.select(clear=True)

    # ------------------------------------------------------------------
    # Attribute slots
    # ------------------------------------------------------------------

    def _display_attributes(self) -> None:
        """Display the common attributes of the selected nodes."""
        selected_nodes = self._get_selected_nodes()
        common_attrs = command.get_common_attributes(selected_nodes)

        self.attr_source_model.beginResetModel()
        self.attr_source_model.clear()
        for attr in common_attrs:
            item = QStandardItem(attr)
            self.attr_source_model.appendRow(item)
        self.attr_source_model.endResetModel()

    def _display_value(self) -> None:
        """Display the value of the selected attribute."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()

        if not nodes or not attrs:
            self.value_field.setText("")
            self.value_field.setEnabled(False)
            return

        value = cmds.getAttr(f"{nodes[-1]}.{attrs[-1]}")
        self.value_field.setText(str(value))

        attr_types: set[str] = set()
        for node in nodes:
            for attr in attrs:
                if cmds.getAttr(f"{node}.{attr}", lock=True):
                    self.value_field.setEnabled(False)
                    self.value_field.setStyleSheet("background-color: darkgrey;")
                    return

                if cmds.connectionInfo(f"{node}.{attr}", isDestination=True):
                    self.value_field.setEnabled(False)
                    self.value_field.setStyleSheet("background-color: lightyellow;")
                    return

                attr_type = cmds.getAttr(f"{node}.{attr}", type=True)
                attr_types.add(attr_type)

        if len(attr_types) > 1:
            self.value_field.setEnabled(False)
            self.value_field.setStyleSheet("background-color: pink;")
        else:
            self.value_field.setEnabled(True)
            self.value_field.setStyleSheet("")

    @error_handler
    @undo_chunk("Set Attribute Value")
    def _set_value(self) -> None:
        """Set the value of the selected attribute."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()

        if not nodes or not attrs:
            return

        if not self.value_field.text():
            cmds.error("No value is entered.")

        if not self.value_field.isEnabled():
            cmds.error("Cannot change the value because the attribute type is different, it is connected, or it is locked.")

        try:
            value = self.value_field.text()
            attr_type = cmds.getAttr(f"{nodes[-1]}.{attrs[-1]}", type=True)
            if attr_type == "bool":
                value = bool(int(value))
            elif attr_type in ["long", "short", "byte", "char", "enum", "time"]:
                value = int(value)
            elif attr_type == "string":
                value = str(value)
            elif attr_type in ["float", "double", "doubleLinear", "doubleAngle"]:
                value = float(value)
            elif attr_type == "matrix":
                value = eval(value)  # noqa: S307
            else:
                raise ValueError(f"Unsupported attribute type: {attr_type}")

            for node in nodes:
                for attr in attrs:
                    if attr_type == "matrix":
                        cmds.setAttr(f"{node}.{attr}", *value, type=attr_type)
                    elif attr_type == "string":
                        cmds.setAttr(f"{node}.{attr}", value, type=attr_type)
                    else:
                        cmds.setAttr(f"{node}.{attr}", value)

        except (ValueError, SyntaxError, TypeError) as e:
            cmds.error(f"Invalid input value: {value}. \n{e!s}")

    @error_handler
    @undo_chunk("Delete Attributes")
    def _delete_attributes(self) -> None:
        """Delete selected attributes."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()

        if not nodes or not attrs:
            return

        for node in nodes:
            for attr in attrs:
                try:
                    if cmds.attributeQuery(attr, node=node, exists=True):
                        cmds.deleteAttr(f"{node}.{attr}")
                except RuntimeError as e:
                    cmds.error(f"Failed to delete attribute {attr} from node {node}. \n{e!s}")

    def _show_attr_context_menu(self, pos) -> None:
        """Show context menu on the attribute list."""
        menu = QMenu(self)
        menu.addAction("Lock", self._lock_attributes)
        menu.addAction("Unlock", self._unlock_attributes)
        menu.addSeparator()
        menu.addAction("Keyable", self._keyable_attributes)
        menu.addAction("Unkeyable", self._unkeyable_attributes)
        menu.exec_(self.attr_list.mapToGlobal(pos))

    @error_handler
    @undo_chunk("Lock Attributes")
    def _lock_attributes(self) -> None:
        """Lock the selected attributes."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()
        if not nodes or not attrs:
            return
        for node in nodes:
            for attr in attrs:
                cmds.setAttr(f"{node}.{attr}", lock=True)
        self._display_value()

    @error_handler
    @undo_chunk("Unlock Attributes")
    def _unlock_attributes(self) -> None:
        """Unlock the selected attributes."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()
        if not nodes or not attrs:
            return
        for node in nodes:
            for attr in attrs:
                cmds.setAttr(f"{node}.{attr}", lock=False)
        self._display_value()

    @error_handler
    @undo_chunk("Keyable Attributes")
    def _keyable_attributes(self) -> None:
        """Set the selected attributes keyable."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()
        if not nodes or not attrs:
            return
        for node in nodes:
            for attr in attrs:
                cmds.setAttr(f"{node}.{attr}", keyable=True)

    @error_handler
    @undo_chunk("Unkeyable Attributes")
    def _unkeyable_attributes(self) -> None:
        """Set the selected attributes unkeyable."""
        nodes = self._get_selected_nodes()
        attrs = self._get_selected_attributes()
        if not nodes or not attrs:
            return
        for node in nodes:
            for attr in attrs:
                cmds.setAttr(f"{node}.{attr}", keyable=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_selected_nodes(self) -> list[str]:
        """Get selected node names from the node list."""
        return [index.data() for index in self.node_list.selectionModel().selectedIndexes()]

    def _get_all_nodes(self) -> list[str]:
        """Get all node names from the node list."""
        return [self.node_model.item(i).text() for i in range(self.node_model.rowCount())]

    def _get_selected_attributes(self) -> list[str]:
        """Get selected attribute names from the attribute list."""
        return [index.data() for index in self.attr_list.selectionModel().selectedIndexes()]

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        """Restore settings from disk."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _apply_settings(self, settings_data: dict) -> None:
        """Apply settings to UI widgets."""
        self.select_combo.setCurrentIndex(settings_data.get("select_filter_index", 0))
        self.node_filter_edit.setText(settings_data.get("node_filter_text", ""))
        self.node_filter_inherited_cb.setChecked(settings_data.get("node_filter_inherited", False))
        self.match_filter_edit.setText(settings_data.get("match_filter_text", ""))
        self.match_filter_ignorecase_cb.setChecked(settings_data.get("match_filter_ignorecase", False))

    def _collect_settings(self) -> dict:
        """Collect current UI state into a dict."""
        return {
            "select_filter_index": self.select_combo.currentIndex(),
            "node_filter_text": self.node_filter_edit.text(),
            "node_filter_inherited": self.node_filter_inherited_cb.isChecked(),
            "match_filter_text": self.match_filter_edit.text(),
            "match_filter_ignorecase": self.match_filter_ignorecase_cb.isChecked(),
        }

    def _save_settings(self) -> None:
        """Save current settings to disk."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def closeEvent(self, event) -> None:
        """Save settings on close."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Node Lister UI.

    Returns:
        MainWindow: The main window instance.
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
