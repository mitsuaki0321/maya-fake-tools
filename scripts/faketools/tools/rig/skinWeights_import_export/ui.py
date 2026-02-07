"""SkinCluster weights export and import tool."""

from logging import getLogger
import os
from pathlib import Path
import shutil
import tempfile

import maya.cmds as cmds

from ....lib_ui import maya_decorator, maya_ui, tool_data
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QFileSystemWatcher,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
)
from ....lib_ui.ui_utils import scale_by_dpi
from ....lib_ui.widgets import IconToggleButton, extra_widgets
from .command import SkinClusterData, SkinClusterDataIO, validate_export_weights
from .file_item_widget import FileItemWidget

logger = getLogger(__name__)
_instance = None
_IMAGES_DIR = Path(__file__).parent / "images"

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

        tool_data_manager = tool_data.ToolDataManager("skinWeights_import_export", "rig")
        tool_data_manager.ensure_data_dir()
        self.root_path = str(tool_data_manager.get_data_dir())

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

        # File tree widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.on_context_menu)
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setIndentation(scale_by_dpi(16, self))
        self.central_layout.addWidget(self.tree_widget)

        # File system watcher
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(self.root_path)
        self.file_watcher.directoryChanged.connect(self._populate_file_list)

        # Populate initial file list
        self._populate_file_list()

        layout = QHBoxLayout()

        self.format_checkBox = IconToggleButton(icon_on="binary", icon_off="ascii", icon_dir=_IMAGES_DIR)
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

        # Signal & Slot
        self.quick_export_button.clicked.connect(self.export_weights_quick)
        self.quick_import_button.clicked.connect(self.import_weights_quick)
        export_button.clicked.connect(self.export_weights)
        import_button.clicked.connect(self.import_weights)

        # Apply stylesheet to tree widget
        self.tree_widget.setStyleSheet(
            """
            QTreeWidget {
                border: 1px solid palette(mid);
                background-color: palette(base);
            }
            QTreeWidget::item {
                border: none;
                padding: 0px;
            }
            QTreeWidget::item:selected {
                background-color: palette(highlight);
            }
            """
        )

    def _populate_file_list(self):
        """Populate the tree widget with files and directories."""
        self.tree_widget.clear()

        if not os.path.exists(self.root_path):
            return

        # Build directory structure
        dir_items = {}  # path -> QTreeWidgetItem

        for root, dirs, files in os.walk(self.root_path):
            # Sort directories and files
            dirs.sort()
            files.sort()

            # Get or create parent item
            if root == self.root_path:
                parent_item = None
            else:
                parent_item = dir_items.get(root)

            # Add directories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)

                # Create directory item
                if parent_item:
                    dir_tree_item = QTreeWidgetItem(parent_item)
                else:
                    dir_tree_item = QTreeWidgetItem(self.tree_widget)

                # Create custom widget for directory
                widget = FileItemWidget(
                    dir_path,
                    on_select_influences=self._select_influences_from_item,
                    on_select_geometry=self._select_geometry_from_item,
                    parent=self.tree_widget,
                )

                dir_tree_item.setSizeHint(0, widget.sizeHint())
                self.tree_widget.setItemWidget(dir_tree_item, 0, widget)

                # Store directory item for children
                dir_items[dir_path] = dir_tree_item

                # Collapse by default
                dir_tree_item.setExpanded(False)

            # Add files (filter by extension)
            for file_name in files:
                if file_name.endswith(".json") or file_name.endswith(".pickle"):
                    file_path = os.path.join(root, file_name)

                    # Create file item
                    if parent_item:
                        file_tree_item = QTreeWidgetItem(parent_item)
                    else:
                        file_tree_item = QTreeWidgetItem(self.tree_widget)

                    # Create custom widget for file
                    widget = FileItemWidget(
                        file_path,
                        on_select_influences=self._select_influences_from_item,
                        on_select_geometry=self._select_geometry_from_item,
                        parent=self.tree_widget,
                    )

                    file_tree_item.setSizeHint(0, widget.sizeHint())
                    self.tree_widget.setItemWidget(file_tree_item, 0, widget)

    def _select_influences_from_item(self, file_path):
        """Select influences from a single file.

        Args:
            file_path (str): The file path
        """
        self._select_influences_impl([file_path])

    def _select_geometry_from_item(self, file_path):
        """Select geometry from a single file.

        Args:
            file_path (str): The file path
        """
        self._select_geometry_impl([file_path])

    def _select_influences_impl(self, file_path_list):
        """Select influences from file list.

        Args:
            file_path_list (list): List of file paths
        """
        if not file_path_list:
            cmds.error("No file selected.")

        sel_nodes = []
        for file_path in file_path_list:
            if os.path.isdir(file_path):
                # Recursively get files in directory
                for root, _, files in os.walk(file_path):
                    for file in files:
                        if file.endswith(".json") or file.endswith(".pickle"):
                            file_path_inner = os.path.join(root, file)
                            data = SkinClusterDataIO().load_data(file_path_inner)
                            for inf in data.influences:
                                if inf not in sel_nodes:
                                    sel_nodes.append(inf)
            else:
                data = SkinClusterDataIO().load_data(file_path)
                for inf in data.influences:
                    if inf not in sel_nodes:
                        sel_nodes.append(inf)

        cmds.select(sel_nodes, r=True)

    def _select_geometry_impl(self, file_path_list):
        """Select geometry from file list.

        Args:
            file_path_list (list): List of file paths
        """
        if not file_path_list:
            cmds.error("No file selected.")

        sel_nodes = []
        for file_path in file_path_list:
            if os.path.isdir(file_path):
                # Recursively get files in directory
                for root, _, files in os.walk(file_path):
                    for file in files:
                        if file.endswith(".json") or file.endswith(".pickle"):
                            file_path_inner = os.path.join(root, file)
                            data = SkinClusterDataIO().load_data(file_path_inner)
                            if data.geometry_name not in sel_nodes:
                                sel_nodes.append(data.geometry_name)
            else:
                data = SkinClusterDataIO().load_data(file_path)
                if data.geometry_name not in sel_nodes:
                    sel_nodes.append(data.geometry_name)

        cmds.select(sel_nodes, r=True)

    def on_context_menu(self, point):
        """Show the context menu for the tree widget."""
        menu = QMenu()

        # Check if any items are selected
        selected_items = self.tree_widget.selectedItems()
        has_selection = len(selected_items) > 0

        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(has_selection)
        delete_action.triggered.connect(self._delete_selected_items)
        menu.addAction(delete_action)

        menu.addSeparator()

        action = menu.addAction("Open Directory")
        action.triggered.connect(self._open_directory)
        menu.addAction(action)

        menu.exec_(self.tree_widget.mapToGlobal(point))

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
        self._select_influences_impl(file_path_list)

    @maya_decorator.error_handler
    def _select_geometry(self):
        """Select geometry."""
        file_path_list = self._get_file_path_list()
        self._select_geometry_impl(file_path_list)

    @maya_decorator.error_handler
    def _delete_selected_items(self):
        """Delete selected files and directories."""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return

        # Get file paths from selected items
        file_paths = []
        for item in selected_items:
            widget = self.tree_widget.itemWidget(item, 0)
            if widget:
                file_paths.append(widget.file_path)

        if not file_paths:
            return

        # Confirm deletion
        from ....lib_ui import maya_dialog

        count = len(file_paths)
        message = f"Delete {count} item(s)?\n\nThis action cannot be undone."
        if not maya_dialog.confirm_dialog("Confirm Deletion", message):
            return

        # Delete files and directories
        for file_path in file_paths:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.debug(f"Deleted file: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.debug(f"Deleted directory: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                cmds.warning(f"Failed to delete {os.path.basename(file_path)}: {e}")

        # Refresh the file list
        self._populate_file_list()

        logger.info(f"Deleted {count} item(s)")

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
        selected_items = self.tree_widget.selectedItems()

        result_path_list = []
        for item in selected_items:
            widget = self.tree_widget.itemWidget(item, 0)
            if widget:
                file_path = widget.file_path
                if os.path.isfile(file_path) and file_path not in result_path_list:
                    result_path_list.append(os.path.normpath(file_path))
                else:
                    # Directory - recursively get files
                    for root, _, files in os.walk(file_path):
                        for file in files:
                            if not (file.endswith(".json") or file.endswith(".pickle")):
                                continue

                            file_path_inner = os.path.join(root, file)
                            if file_path_inner not in result_path_list:
                                result_path_list.append(os.path.normpath(file_path_inner))

        logger.debug(f"Selected file path list: {result_path_list}")

        return result_path_list

    @maya_decorator.error_handler
    def export_weights(self):
        """Export the skinCluster weights."""
        format = self.format_checkBox.isChecked() and "pickle" or "json"
        dir_name = self.file_name_field.text()
        if not dir_name:
            cmds.error("No directory name specified.")

        shapes = cmds.ls(sl=True, dag=True, ni=True, type="deformableShape")
        if not shapes:
            cmds.error("No geometry selected.")

        validate_export_weights(shapes)

        output_dir_path = os.path.join(self.root_path, dir_name)
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path, exist_ok=True)

        for shape in shapes:
            skinCluster_data = SkinClusterData.from_geometry(shape)
            SkinClusterDataIO().export_weights(skinCluster_data, output_dir_path, format=format)

        logger.debug("Completed export skinCluster weights.")

        # Refresh file list
        self._populate_file_list()

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
            for shape, file_path in zip(shapes, file_path_list):
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

        validate_export_weights(shapes)

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
            for shape, file_path in zip(shapes, file_path_list):
                skinCluster_data = skinCluster_io_ins.load_data(file_path)
                skinCluster_io_ins.import_weights(skinCluster_data, shape)

                result_geos.append(skinCluster_data.geometry_name)

                if progress.breakPoint():
                    cmds.select(result_geos, r=True)
                    cmds.warning("Import skinCluster weights canceled.")
                    return

        cmds.select(result_geos, r=True)

        logger.debug("Completed import skinCluster weights.")


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
