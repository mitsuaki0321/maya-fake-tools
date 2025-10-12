"""SkinCluster weights export and import tool."""

from logging import getLogger
import os
import shutil
import tempfile

import maya.cmds as cmds

from ....lib_ui import maya_decorator, maya_ui, optionvar, tool_data
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QFileSystemModel, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, Qt, QTreeView
from ....lib_ui.widgets import extra_widgets
from .command import SkinClusterData, SkinClusterDataIO

logger = getLogger(__name__)
_instance = None

TEMP_DIR = os.path.normpath(os.path.join(tempfile.gettempdir(), "skinWeights"))


class MainWindow(BaseMainWindow):
    """Main Window for Skin Weights Import/Export Tool."""

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(
            parent=parent,
            object_name="SkinWeightsImportExportMainWindow",
            window_title="Skin Weights Import/Export",
        )

        self.settings = optionvar.ToolOptionSettings(__name__)
        tool_data_manager = tool_data.ToolDataManager("skinWeights_import_export", "rig")
        tool_data_manager.ensure_data_dir()
        self.root_path = tool_data_manager.get_data_dir()

        # Quick mode
        label = QLabel("Quick Mode")
        label.setStyleSheet("font-weight: bold;")
        self.central_layout.addWidget(label)

        layout = QHBoxLayout()

        self.quick_export_button = QPushButton("Export")
        layout.addWidget(self.quick_export_button)
        self.quick_export_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_export_button.customContextMenuRequested.connect(self.on_quick_button_context_menu)

        self.quick_import_button = QPushButton("Import")
        layout.addWidget(self.quick_import_button)
        self.quick_import_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_import_button.customContextMenuRequested.connect(self.on_quick_button_context_menu)

        self.central_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # Advanced mode
        label = QLabel("Advanced Mode")
        label.setStyleSheet("font-weight: bold;")
        self.central_layout.addWidget(label)

        self.model = QFileSystemModel()
        self.model.setRootPath(self.root_path)
        self.model.setNameFilters(["*.json", "*.pickle"])
        self.model.setNameFilterDisables(False)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(self.root_path))

        tree_view_header = self.tree_view.header()
        tree_view_header.hide()

        for col in range(1, self.model.columnCount()):
            self.tree_view.hideColumn(col)

        self.model.setOption(QFileSystemModel.DontUseCustomDirectoryIcons, True)

        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)

        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)

        self.central_layout.addWidget(self.tree_view)

        layout = QHBoxLayout()

        self.format_checkBox = extra_widgets.CheckBoxButton(icon_on="binary", icon_off="ascii")
        self.format_checkBox.setChecked(True)
        layout.addWidget(self.format_checkBox)

        self.file_name_field = QLineEdit()
        self.file_name_field.setPlaceholderText("Directory Name")
        layout.addWidget(self.file_name_field, stretch=1)

        self.central_layout.addLayout(layout)

        layout = QHBoxLayout()

        export_button = QPushButton("Export")
        layout.addWidget(export_button)

        import_button = QPushButton("Import")
        layout.addWidget(import_button)

        self.central_layout.addLayout(layout)

        # Option settings
        self.file_name_field.setText(self.settings.read("file_name", ""))
        self.format_checkBox.setChecked(self.settings.read("format", True))

        # Signal & Slot
        self.quick_export_button.clicked.connect(self.export_weights_quick)
        self.quick_import_button.clicked.connect(self.import_weights_quick)
        export_button.clicked.connect(self.export_weights)
        import_button.clicked.connect(self.import_weights)

        # Initialize the UI
        minimum_size = self.minimumSizeHint()
        self.resize(minimum_size.width() * 2.0, minimum_size.height())

        self._restore_settings()

    def on_context_menu(self, point):
        """Show the context menu for the tree view."""
        menu = QMenu()

        action = menu.addAction("Select Influences")
        action.triggered.connect(self._select_influences)
        menu.addAction(action)

        action = menu.addAction("Select Geometry")
        action.triggered.connect(self._select_geometry)
        menu.addAction(action)

        menu.addSeparator()

        action = menu.addAction("Open Directory")
        action.triggered.connect(self._open_directory)
        menu.addAction(action)

        menu.exec_(self.tree_view.mapToGlobal(point))

    def on_quick_button_context_menu(self, point):
        """Show the context menu for quick mode."""
        menu = QMenu()

        action = menu.addAction("Select Influences")
        action.triggered.connect(self._select_influences_quick)
        menu.addAction(action)

        action = menu.addAction("Select Geometry")
        action.triggered.connect(self._select_geometry_quick)
        menu.addAction(action)

        menu.addSeparator()

        action = menu.addAction("Open Directory")
        action.triggered.connect(self._open_directory_quick)
        menu.addAction(action)

        sender = self.sender()
        if sender == self.quick_export_button:
            menu.exec_(self.quick_export_button.mapToGlobal(point))
        elif sender == self.quick_import_button:
            menu.exec_(self.quick_import_button.mapToGlobal(point))

    @maya_decorator.error_handler
    def _select_influences(self):
        """Select influences."""
        file_path_list = self._get_file_path_list()
        if not file_path_list:
            cmds.error("No file selected.")

        sel_nodes = []
        for file_path in file_path_list:
            data = SkinClusterDataIO().load_data(file_path)
            for inf in data.influences:
                if inf not in sel_nodes:
                    sel_nodes.append(inf)

        cmds.select(sel_nodes, r=True)

    @maya_decorator.error_handler
    def _select_geometry(self):
        """Select geometry."""
        file_path_list = self._get_file_path_list()
        if not file_path_list:
            cmds.error("No file selected.")

        sel_nodes = []
        for file_path in file_path_list:
            data = SkinClusterDataIO().load_data(file_path)
            if data.geometry_name not in sel_nodes:
                sel_nodes.append(data.geometry_name)

        cmds.select(sel_nodes, r=True)

    @maya_decorator.error_handler
    def _open_directory(self):
        """Open directory."""
        if not os.path.exists(self.root_path):
            cmds.error("The directory does not exist.")

        os.startfile(self.root_path)

    @maya_decorator.error_handler
    def _select_influences_quick(self):
        """Select influences quickly."""
        file_path_list = [os.path.join(TEMP_DIR, file) for file in os.listdir(TEMP_DIR)]
        if not file_path_list:
            cmds.error("No temp file found.")

        logger.debug(f"file_path_list: {file_path_list}")

        sel_nodes = []
        for file_path in file_path_list:
            data = SkinClusterDataIO().load_data(file_path)
            for inf in data.influences:
                if inf not in sel_nodes:
                    sel_nodes.append(inf)

        cmds.select(sel_nodes, r=True)

    @maya_decorator.error_handler
    def _select_geometry_quick(self):
        """Select geometry quickly."""
        file_path_list = [os.path.join(TEMP_DIR, file) for file in os.listdir(TEMP_DIR)]
        if not file_path_list:
            cmds.error("No temp file found.")

        logger.debug(f"file_path_list: {file_path_list}")

        sel_nodes = []
        for file_path in file_path_list:
            data = SkinClusterDataIO().load_data(file_path)
            if data.geometry_name not in sel_nodes:
                sel_nodes.append(data.geometry_name)

        cmds.select(sel_nodes, r=True)

    @maya_decorator.error_handler
    def _open_directory_quick(self):
        """Open directory quickly."""
        os.startfile(TEMP_DIR)

    def _get_file_path_list(self):
        """Get the selected file path list."""
        indexes = self.tree_view.selectionModel().selectedIndexes()
        file_path_list = [self.model.filePath(index) for index in indexes if index.column() == 0]

        result_path_list = []
        for file_path in file_path_list:
            if os.path.isfile(file_path) and file_path not in result_path_list:
                result_path_list.append(os.path.normpath(file_path))
            else:
                for root, _, files in os.walk(file_path):
                    for file in files:
                        if not (file.endswith(".json") or file.endswith(".pickle")):
                            continue

                        file_path = os.path.join(root, file)
                        if file_path not in result_path_list:
                            result_path_list.append(os.path.normpath(file_path))

        logger.debug(f"Selected file path list: {result_path_list}")

        return result_path_list

    @maya_decorator.error_handler
    def export_weights(self):
        """Export the skinCluster weights."""
        shapes = cmds.ls(sl=True, dag=True, ni=True, type="deformableShape")
        if not shapes:
            cmds.error("No geometry selected.")

        format = self.format_checkBox.isChecked() and "pickle" or "json"
        dir_name = self.file_name_field.text()
        if not dir_name:
            cmds.error("No directory name specified.")

        output_dir_path = os.path.join(self.root_path, dir_name)
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path, exist_ok=True)

        for shape in shapes:
            skinCluster_data = SkinClusterData.from_geometry(shape)
            SkinClusterDataIO().export_weights(skinCluster_data, output_dir_path, format=format)

        logger.debug("Completed export skinCluster weights.")

    @maya_decorator.undo_chunk("Import SkinCluster Weights")
    @maya_decorator.error_handler
    def import_weights(self):
        """Import the skinCluster weights.

        Notes:
            - If geometry is selected, import weights to the selected geometry.
            - The number of selected geometries must match the number of files to be imported.
            - If no geometry is selected, import weights to the geometry specified in the file.
        """
        file_path_list = self._get_file_path_list()
        if not file_path_list:
            cmds.error("No file selected.")

        shapes = cmds.ls(sl=True, dag=True, ni=True, type="deformableShape")

        if shapes:
            if len(shapes) != len(file_path_list):
                cmds.error("The number of selected geometry and files do not match.")
        else:
            shapes = [None] * len(file_path_list)

        result_geos = []
        skinCluster_io_ins = SkinClusterDataIO()

        with maya_ui.progress_bar(len(file_path_list), msg="Importing SkinCluster Weights") as progress:
            for shape, file_path in zip(shapes, file_path_list, strict=False):
                skinCluster_data = skinCluster_io_ins.load_data(file_path)
                skinCluster_io_ins.import_weights(skinCluster_data, shape)

                result_geos.append(skinCluster_data.geometry_name)

                if progress.breakPoint():
                    cmds.select(result_geos, r=True)
                    cmds.warning("Import skinCluster weights canceled.")
                    return

        cmds.select(result_geos, r=True)

        logger.debug("Completed import skinCluster weights.")

    @maya_decorator.error_handler
    def export_weights_quick(self):
        """Export the skinCluster weights quickly."""
        shapes = cmds.ls(sl=True, dag=True, ni=True, type="deformableShape")
        if not shapes:
            cmds.error("No geometry selected.")

        format = self.format_checkBox.isChecked() and "pickle" or "json"
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)

        os.makedirs(TEMP_DIR, exist_ok=True)

        for shape in shapes:
            skinCluster_data = SkinClusterData.from_geometry(shape)
            SkinClusterDataIO().export_weights(skinCluster_data, TEMP_DIR, format=format)

        logger.debug("Completed export skinCluster weights.")

    @maya_decorator.undo_chunk("Import SkinCluster Weights")
    @maya_decorator.error_handler
    def import_weights_quick(self):
        """Import the skinCluster weights quickly."""
        file_path_list = [os.path.join(TEMP_DIR, file) for file in os.listdir(TEMP_DIR)]
        if not file_path_list:
            cmds.error("No temp file found.")

        shapes = cmds.ls(sl=True, dag=True, ni=True, type="deformableShape")

        if shapes:
            if len(shapes) != len(file_path_list):
                cmds.error("The number of selected geometry and files do not match.")
        else:
            shapes = [None] * len(file_path_list)

        result_geos = []
        skinCluster_io_ins = SkinClusterDataIO()
        with maya_ui.progress_bar(len(file_path_list), msg="Importing SkinCluster Weights") as progress:
            for shape, file_path in zip(shapes, file_path_list, strict=False):
                skinCluster_data = skinCluster_io_ins.load_data(file_path)
                skinCluster_io_ins.import_weights(skinCluster_data, shape)

                result_geos.append(skinCluster_data.geometry_name)

                if progress.breakPoint():
                    cmds.select(result_geos, r=True)
                    cmds.warning("Import skinCluster weights canceled.")
                    return

        cmds.select(result_geos, r=True)

        logger.debug("Completed import skinCluster weights.")

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

    def _save_settings(self):
        """Save UI settings to preferences."""
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

    def closeEvent(self, event):
        """Close event."""
        self._save_settings()

        # Save the option settings
        self.settings.write("file_name", self.file_name_field.text())
        self.settings.write("format", self.format_checkBox.isChecked())

        super().closeEvent(event)


def show_ui():
    """
    Show the Skin Weights Import/Export Tool UI.

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
