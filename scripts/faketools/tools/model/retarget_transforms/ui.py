"""Re target transforms tool."""

import glob
from logging import getLogger
import os

import maya.cmds as cmds

from ....lib_ui import maya_decorator, tool_data
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QStringListModel,
    Qt,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import extra_widgets
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Retarget Transform Main Window."""

    _method_list = ("Default", "Barycentric", "Rbf")
    _create_new_list = ("transform", "locator", "joint")
    _axis_list = ("X", "Y", "Z")

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="RetargetTransformsMainWindow",
            window_title="Retarget Transforms",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="retarget_transforms", category="model")
        tool_data_manager = tool_data.ToolDataManager("retarget_transforms", "model")
        tool_data_manager.ensure_data_dir()
        self.output_directory = tool_data_manager.get_data_dir()

        # Export Options
        layout = QGridLayout()

        label = QLabel("Method:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 0, 0)

        self.method_box = QComboBox()
        self.method_box.addItems(self._method_list)
        layout.addWidget(self.method_box, 0, 1)

        self.rbf_radius_label = QLabel("Rbf Radius:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.rbf_radius_label, 1, 0)

        self.rbf_radius_box = extra_widgets.ModifierSpinBox()
        self.rbf_radius_box.setRange(1.5, 10.0)
        self.rbf_radius_box.setSingleStep(0.1)
        layout.addWidget(self.rbf_radius_box, 1, 1)

        label = QLabel("File Name:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 2, 0)

        self.file_name_field = QLineEdit()
        self.file_name_field.setPlaceholderText("File Name")
        layout.addWidget(self.file_name_field, 2, 1)

        self.central_layout.addLayout(layout)

        export_button = QPushButton("Export")
        self.central_layout.addWidget(export_button)

        self.file_list_view = QListView()
        self.file_list_view.setEditTriggers(QListView.NoEditTriggers)
        self.file_list_model = QStringListModel()
        self.file_list_view.setModel(self.file_list_model)
        self.central_layout.addWidget(self.file_list_view)

        self.file_list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list_view.customContextMenuRequested.connect(self._on_context_menu)

        layout = QHBoxLayout()

        # Data Information
        self.node_length_label = QLabel(f"{self._get_node_length_label(0)}  ")
        layout.addWidget(self.node_length_label)

        separator = extra_widgets.VerticalSeparator()
        layout.addWidget(separator)

        self.method_label = QLabel(self._get_method_label("None"))
        layout.addWidget(self.method_label)

        layout.addStretch(1)

        self.central_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # Import Options
        self.is_rotation_checkbox = QCheckBox("Is Rotation")
        self.central_layout.addWidget(self.is_rotation_checkbox)

        self.create_new_checkbox = QCheckBox("Create New")
        self.central_layout.addWidget(self.create_new_checkbox)

        self.restore_hierarchy_checkbox = QCheckBox("Restore Hierarchy")
        self.central_layout.addWidget(self.restore_hierarchy_checkbox)

        layout = QGridLayout()

        self.object_type_label = QLabel("Object Type:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.object_type_label, 0, 0)

        self.object_type_box = QComboBox()
        self.object_type_box.addItems(self._create_new_list)
        layout.addWidget(self.object_type_box, 0, 1)

        self.object_size_label = QLabel("Size:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.object_size_label, 1, 0)

        self.object_size_box = extra_widgets.ModifierSpinBox()
        self.object_size_box.setRange(0.00, 100.0)
        self.object_size_box.setValue(1.0)
        layout.addWidget(self.object_size_box, 1, 1)

        layout.setColumnStretch(1, 1)

        self.central_layout.addLayout(layout)

        import_button = QPushButton("Import")
        self.central_layout.addWidget(import_button)

        # Signals & Slots
        self.method_box.currentIndexChanged.connect(self._update_method_options)
        self.create_new_checkbox.stateChanged.connect(self._update_create_new_options)
        self.file_list_view.clicked.connect(self._update_data_information)
        export_button.clicked.connect(self.export_transform_position)
        import_button.clicked.connect(self.import_transform_position)

        selection_model = self.file_list_view.selectionModel()
        selection_model.selectionChanged.connect(self._insert_file_name)

        # Initialize UI state
        self._restore_settings()
        self._update_file_list()

    @maya_decorator.error_handler
    def export_transform_position(self) -> None:
        """Export the positions of the selected objects."""
        method = self.method_box.currentText().lower()
        rbf_radius = self.rbf_radius_box.value()
        file_name = self.file_name_field.text()

        if not file_name:
            cmds.error("File name is empty.")

        command.export_transform_position(output_directory=self.output_directory, file_name=file_name, method=method, rbf_radius=rbf_radius)

        self._update_file_list()
        self._select_file(file_name)

    @maya_decorator.undo_chunk("Import Transform Position")
    @maya_decorator.error_handler
    def import_transform_position(self) -> None:
        """Import the positions of the selected objects."""
        sel_file_path = self._get_selected_file_path()
        if not sel_file_path:
            cmds.error("No file selected.")

        is_rotation = self.is_rotation_checkbox.isChecked()
        create_new = self.create_new_checkbox.isChecked()
        restore_hierarchy = self.restore_hierarchy_checkbox.isChecked()
        object_type = self.object_type_box.currentText()
        object_size = self.object_size_box.value()

        result_transforms = command.import_transform_position(
            sel_file_path,
            create_new=create_new,
            is_rotation=is_rotation,
            restore_hierarchy=restore_hierarchy,
            creation_object_type=object_type,
            creation_object_size=object_size,
        )

        if result_transforms:
            cmds.select(result_transforms, r=True)

    @maya_decorator.error_handler
    def _select_data_nodes(self) -> None:
        """Select the transform nodes from the selected file."""
        sel_file_path = self._get_selected_file_path()
        if not sel_file_path:
            cmds.error("No file selected.")

        transform_data = command.load_transform_position_data(sel_file_path)
        transform_nodes = transform_data["transforms"]

        not_exists_nodes = [node for node in transform_nodes if not cmds.objExists(node)]
        if not_exists_nodes:
            cmds.error(f"Nodes do not exist: {not_exists_nodes}")

        cmds.select(transform_nodes)

    @maya_decorator.error_handler
    def _remove_file(self) -> None:
        """Remove the selected file from the file list. ( Deletes the file )"""
        sel_file_path = self._get_selected_file_path()
        if not sel_file_path:
            cmds.error("No file selected.")

        os.remove(sel_file_path)
        self._update_file_list()

        logger.debug(f"Removed file: {sel_file_path}")

    @maya_decorator.error_handler
    def _open_directory(self) -> None:
        """Open file directory."""
        os.startfile(self.output_directory)

        logger.debug(f"Opened directory: {self.output_directory}")

    def _on_context_menu(self, point) -> None:
        """Show the context menu on the file list view."""
        menu = QMenu()

        action = menu.addAction("Select Nodes")
        action.triggered.connect(self._select_data_nodes)

        menu.addSeparator()

        action = menu.addAction("Remove File")
        action.triggered.connect(self._remove_file)

        action = menu.addAction("Refresh")
        action.triggered.connect(self._update_file_list)

        menu.addSeparator()

        action = menu.addAction("Open Directory")
        action.triggered.connect(self._open_directory)

        menu.exec_(self.file_list_view.mapToGlobal(point))

    def _update_method_options(self) -> None:
        """Update the method options based on the selected method."""
        method = self.method_box.currentText().lower()
        if method == "rbf":
            self.rbf_radius_label.setEnabled(True)
            self.rbf_radius_box.setEnabled(True)
        else:
            self.rbf_radius_label.setEnabled(False)
            self.rbf_radius_box.setEnabled(False)

    def _update_file_list(self) -> None:
        """Update the file list."""
        directory_file_list = glob.glob(os.path.join(self.output_directory, "*.pkl"))
        file_list = [os.path.splitext(os.path.basename(file))[0] for file in directory_file_list]

        self.file_list_model.setStringList(file_list)

        logger.debug(f"Updated file list: {file_list}")

    def _update_data_information(self) -> None:
        """Update the data information.

        Args:
            node_count (int): The number of nodes.
            method (str): The method.
        """
        sel_file_path = self._get_selected_file_path()
        try:
            transform_data = command.load_transform_position_data(sel_file_path)
        except Exception as e:
            logger.error(f"Failed to load transform data: {sel_file_path}\n{e}")
            self.node_length_label.setText(self._get_node_length_label(0))
            self.method_label.setText(self._get_method_label("None"))
            return

        node_count = len(transform_data["transforms"])
        method = transform_data["method"]

        self.node_length_label.setText(self._get_node_length_label(node_count))
        self.method_label.setText(self._get_method_label(method))

    def _insert_file_name(self, item) -> None:
        """Insert the file name to the file name field.

        Args:
            item (QModelIndex): The selected item.
        """
        indices = item.indexes()
        if not indices:
            return

        file_name = self.file_list_model.data(indices[0])
        self.file_name_field.setText(file_name)

    def _get_selected_file_path(self) -> str:
        """Get the selected file path.

        Returns:
            str: The selected file.
        """
        selected_index = self.file_list_view.selectionModel().selectedIndexes()
        if not selected_index:
            return None

        selected_file = self.file_list_model.data(selected_index[0])

        file_path = os.path.join(self.output_directory, f"{selected_file}.pkl")
        if not os.path.exists(file_path):
            raise ValueError(f"File does not exist: {file_path}")

        return file_path

    def _select_file(self, file_name: str) -> None:
        """Select the file in the file list.

        Args:
            file_name (str): The file name.
        """
        file_list = self.file_list_model.stringList()
        if file_name not in file_list:
            return

        index = file_list.index(file_name)
        self.file_list_view.setCurrentIndex(self.file_list_model.index(index))

    def _update_create_new_options(self) -> None:
        """Enable/Disable based on the state of the Create New checkbox."""
        state = self.create_new_checkbox.isChecked()
        self.object_type_label.setEnabled(state)
        self.object_type_box.setEnabled(state)
        self.object_size_label.setEnabled(state)
        self.object_size_box.setEnabled(state)
        self.restore_hierarchy_checkbox.setEnabled(state)

    @staticmethod
    def _get_node_length_label(node_count: int) -> str:
        """Get the node length label.

        Args:
            node_count (int): The number of nodes.

        Returns:
            str: The node length label.
        """
        return f"Nodes: {node_count}"

    @staticmethod
    def _get_method_label(method: str) -> str:
        """Get the method label.

        Args:
            method (str): The method.

        Returns:
            str: The method label.
        """
        return f"Method: {method}"

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)
            # Update UI state based on settings
            self._update_method_options()
            self._update_create_new_options()

        # Set minimum size
        self.adjustSize()
        width = self.minimumSizeHint().width()
        height = self.minimumSizeHint().height()
        self.resize(width, height)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def _collect_settings(self) -> dict:
        """Collect current UI settings.

        Returns:
            dict: Settings data
        """
        return {
            "method": self.method_box.currentText(),
            "rbf_radius": self.rbf_radius_box.value(),
            "is_rotation": self.is_rotation_checkbox.isChecked(),
            "create_new": self.create_new_checkbox.isChecked(),
            "restore_hierarchy": self.restore_hierarchy_checkbox.isChecked(),
            "object_type": self.object_type_box.currentText(),
            "object_size": self.object_size_box.value(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "method" in settings_data:
            self.method_box.setCurrentText(settings_data["method"])
        if "rbf_radius" in settings_data:
            self.rbf_radius_box.setValue(settings_data["rbf_radius"])
        if "is_rotation" in settings_data:
            self.is_rotation_checkbox.setChecked(settings_data["is_rotation"])
        if "create_new" in settings_data:
            self.create_new_checkbox.setChecked(settings_data["create_new"])
        if "restore_hierarchy" in settings_data:
            self.restore_hierarchy_checkbox.setChecked(settings_data["restore_hierarchy"])
        if "object_type" in settings_data:
            self.object_type_box.setCurrentText(settings_data["object_type"])
        if "object_size" in settings_data:
            self.object_size_box.setValue(settings_data["object_size"])

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """
    Show the retarget transforms tool UI.

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
