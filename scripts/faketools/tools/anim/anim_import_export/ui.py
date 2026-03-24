"""Animation Import/Export UI layer."""

from logging import getLogger
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional

import maya.cmds as cmds

from ....lib import lib_name
from ....lib_ui import error_handler, maya_ui, show_warning_dialog, undo_chunk
from ....lib_ui.base_window import BaseMainWindow, get_margins, get_spacing
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QComboBox,
    QFileSystemWatcher,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QRadioButton,
    QSpinBox,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
)
from ....lib_ui.tool_data import ToolDataManager
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.ui_utils import get_text_width, scale_by_dpi
from ....lib_ui.widgets import IconToggleButton, extra_widgets
from . import command
from .file_item_widget import FileItemWidget

_IMAGES_DIR = Path(__file__).parent / "images"

logger = getLogger(__name__)
_instance = None

TEMP_DIR = os.path.normpath(os.path.join(tempfile.gettempdir(), "animIO"))
NS_FILE = "(File Namespace)"
NS_NONE = "(No Namespace)"


class MainWindow(BaseMainWindow):
    """Animation I/E Main Window."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="AnimImportExportMainWindow",
            window_title="Animation Import/Export",
            central_layout="vertical",
        )
        self.settings = ToolSettingsManager(tool_name="anim_import_export", category="anim")

        tool_data_manager = ToolDataManager("anim_import_export", "anim")
        tool_data_manager.ensure_data_dir()
        self.root_path = str(tool_data_manager.get_data_dir())

        self._setup_ui()
        self._restore_settings()

    def _setup_ui(self):
        """Setup the user interface."""
        spacing = get_spacing(self, direction="vertical")
        left, top, right, bottom = get_margins(self)

        # --- Quick Mode ---
        label = QLabel("Quick Mode")
        label.setStyleSheet("font-weight: bold;")
        self.central_layout.addWidget(label)

        quick_layout = QHBoxLayout()
        self.quick_export_button = QPushButton("Export")
        self.quick_export_button.clicked.connect(self._on_quick_export)
        self.quick_export_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_export_button.customContextMenuRequested.connect(self._on_quick_context_menu)
        quick_layout.addWidget(self.quick_export_button)

        self.quick_import_button = QPushButton("Import")
        self.quick_import_button.clicked.connect(self._on_quick_import)
        self.quick_import_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_import_button.customContextMenuRequested.connect(self._on_quick_context_menu)
        quick_layout.addWidget(self.quick_import_button)

        self.central_layout.addLayout(quick_layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # --- Advanced Mode ---
        label = QLabel("Advanced Mode")
        label.setStyleSheet("font-weight: bold;")
        self.central_layout.addWidget(label)

        # Source selection
        source_layout = QHBoxLayout()
        source_layout.setSpacing(int(spacing * 0.5))
        source_label = QLabel("Source:")
        self.selected_radio = QRadioButton("Selected Nodes")
        self.all_animated_radio = QRadioButton("All Animated Nodes")
        self.selected_radio.setChecked(True)
        self.source_group = QButtonGroup(self)
        self.source_group.addButton(self.selected_radio, 0)
        self.source_group.addButton(self.all_animated_radio, 1)
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.selected_radio)
        source_layout.addWidget(self.all_animated_radio)
        source_layout.addStretch()
        self.central_layout.addLayout(source_layout)

        # File tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setIndentation(scale_by_dpi(5, self))
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
        self.central_layout.addWidget(self.tree_widget)

        # File system watcher
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(self.root_path)
        self.file_watcher.directoryChanged.connect(self._populate_file_list)

        self._populate_file_list()

        # Export section
        export_layout = QHBoxLayout()
        export_layout.setSpacing(int(spacing * 0.5))

        self.format_toggle = IconToggleButton(icon_on="binary", icon_off="ascii", icon_dir=_IMAGES_DIR)
        self.format_toggle.setChecked(True)
        export_layout.addWidget(self.format_toggle)

        self.file_name_field = QLineEdit()
        self.file_name_field.setPlaceholderText("File Name")
        export_layout.addWidget(self.file_name_field, 1)

        export_button = QPushButton("Export")
        export_button.clicked.connect(self._on_export)
        export_layout.addWidget(export_button)
        self.central_layout.addLayout(export_layout)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        # Import section
        label_width = get_text_width("Target Namespace:", self) + int(spacing)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(int(spacing * 0.5))
        mode_label = QLabel("Mode:")
        mode_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_label.setFixedWidth(label_width)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Replace", "Merge"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo, 1)
        self.central_layout.addLayout(mode_layout)

        ns_layout = QHBoxLayout()
        ns_layout.setSpacing(int(spacing * 0.5))
        ns_label = QLabel("Target Namespace:")
        ns_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ns_label.setFixedWidth(label_width)
        self.namespace_combo = QComboBox()
        self.namespace_combo.setEditable(True)
        self.namespace_combo.addItems([NS_FILE, NS_NONE])
        ns_layout.addWidget(ns_label)
        ns_layout.addWidget(self.namespace_combo, 1)
        self.central_layout.addLayout(ns_layout)

        offset_layout = QHBoxLayout()
        offset_layout.setSpacing(int(spacing * 0.5))
        offset_label = QLabel("Time Offset:")
        offset_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        offset_label.setFixedWidth(label_width)
        self.time_offset_spin = QSpinBox()
        self.time_offset_spin.setRange(-100000, 100000)
        self.time_offset_spin.setValue(0)
        offset_layout.addWidget(offset_label)
        offset_layout.addWidget(self.time_offset_spin, 1)
        self.central_layout.addLayout(offset_layout)

        import_button = QPushButton("Import")
        import_button.clicked.connect(self._on_import)
        self.central_layout.addWidget(import_button)

    # -------------------------------------------------------------------------
    # UI State Helpers
    # -------------------------------------------------------------------------

    def _get_export_format(self) -> str:
        """Get the selected export format."""
        return command.FORMAT_PICKLE if self.format_toggle.isChecked() else command.FORMAT_JSON

    def _export_progress(self, current: int, total: int) -> bool:
        """Progress callback for export. Manages Maya progress bar lifecycle.

        Args:
            current (int): Current progress count.
            total (int): Total count.

        Returns:
            bool: True if the user cancelled.
        """
        if current == 0:
            self._progress = maya_ui.ProgressBar(total, msg="Exporting Animation...")
        cancelled = self._progress.breakPoint()
        if cancelled or current >= total - 1:
            cmds.progressBar(self._progress.pBar, e=True, endProgress=True)
        return cancelled

    def _resolve_target_namespace(self) -> Optional[str]:
        """Resolve the target namespace from the combo box.

        Returns:
            str | None: None for file namespace, "" for no namespace, or the specified namespace.
        """
        text = self.namespace_combo.currentText()
        if text == NS_FILE:
            return None
        if text == NS_NONE:
            return ""
        return text

    def _refresh_namespace_combo(self):
        """Refresh the namespace combo box with scene namespaces."""
        current_text = self.namespace_combo.currentText()
        self.namespace_combo.clear()
        self.namespace_combo.addItems([NS_FILE, NS_NONE])

        scene_namespaces = lib_name.list_all_namespace()
        if scene_namespaces:
            self.namespace_combo.addItems(scene_namespaces)

        index = self.namespace_combo.findText(current_text)
        if index >= 0:
            self.namespace_combo.setCurrentIndex(index)
        else:
            self.namespace_combo.setEditText(current_text)

    # -------------------------------------------------------------------------
    # File Tree
    # -------------------------------------------------------------------------

    def _populate_file_list(self):
        """Populate the tree widget with animation files."""
        self.tree_widget.clear()

        if not os.path.exists(self.root_path):
            return

        files = sorted(f for f in os.listdir(self.root_path) if f.endswith(".json") or f.endswith(".pickle"))
        for file_name in files:
            file_path = os.path.join(self.root_path, file_name)
            tree_item = QTreeWidgetItem(self.tree_widget)
            widget = FileItemWidget(
                file_path,
                on_select_nodes=self._select_nodes_from_file,
                parent=self.tree_widget,
            )
            tree_item.setSizeHint(0, widget.sizeHint())
            self.tree_widget.setItemWidget(tree_item, 0, widget)

    def _get_selected_file_paths(self) -> list[str]:
        """Get file paths from selected tree items."""
        result = []
        for item in self.tree_widget.selectedItems():
            widget = self.tree_widget.itemWidget(item, 0)
            if widget and os.path.isfile(widget.file_path):
                result.append(widget.file_path)
        return result

    # -------------------------------------------------------------------------
    # Node Selection
    # -------------------------------------------------------------------------

    @error_handler
    def _select_nodes_from_file(self, file_path):
        """Select scene nodes that match the animation file contents.

        Args:
            file_path (str): The animation file path.
        """
        file_io = command.AnimationFileIO()
        data = file_io.load(file_path)

        target_namespace = self._resolve_target_namespace()
        effective_namespace = target_namespace if target_namespace is not None else data.namespace

        node_names = []
        for bare_name in data.nodes:
            if effective_namespace:
                full_name = f"{effective_namespace}:{bare_name}"
            else:
                full_name = bare_name

            if cmds.objExists(full_name):
                node_names.append(full_name)

        if node_names:
            cmds.select(node_names, r=True)
            logger.info(f"Selected {len(node_names)} node(s)")
        else:
            logger.warning("No matching nodes found in scene")

    # -------------------------------------------------------------------------
    # Quick Mode
    # -------------------------------------------------------------------------

    @error_handler
    def _on_quick_export(self):
        """Quick export to temp directory."""
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)

        output_file = os.path.join(TEMP_DIR, "quick_anim")

        if self.all_animated_radio.isChecked():
            written = command.export_all_animation(output_file, format=command.FORMAT_PICKLE, on_progress=self._export_progress)
        else:
            written = command.export_animation(output_file, format=command.FORMAT_PICKLE, on_progress=self._export_progress)

        logger.info(f"Quick exported to {len(written)} file(s)")

    @error_handler
    @undo_chunk("Animation I/E: Quick Import")
    def _on_quick_import(self):
        """Quick import from temp directory."""
        if not os.path.exists(TEMP_DIR):
            show_warning_dialog("Animation I/E", "No quick export data found.")
            return

        anim_files = [os.path.join(TEMP_DIR, f) for f in os.listdir(TEMP_DIR) if f.endswith(".json") or f.endswith(".pickle")]
        if not anim_files:
            show_warning_dialog("Animation I/E", "No animation files found in temp directory.")
            return

        mode = command.IMPORT_MODES[self.mode_combo.currentIndex()]
        target_namespace = self._resolve_target_namespace()

        all_modified = []
        for file_path in anim_files:
            modified = command.import_animation_from_file(
                file_path, mode=mode, target_namespace=target_namespace, time_offset=self.time_offset_spin.value()
            )
            all_modified.extend(modified)

        if all_modified:
            cmds.select(all_modified, r=True)
            logger.info(f"Quick imported to {len(all_modified)} node(s)")
        else:
            logger.warning("No nodes were modified during quick import")

    def _on_quick_context_menu(self, point):
        """Show context menu for quick mode buttons."""
        menu = QMenu()
        action = menu.addAction("Open Directory")
        action.triggered.connect(lambda: os.startfile(TEMP_DIR) if os.path.exists(TEMP_DIR) else None)

        sender = self.sender()
        menu.exec_(sender.mapToGlobal(point))

    # -------------------------------------------------------------------------
    # Advanced Export
    # -------------------------------------------------------------------------

    @error_handler
    def _on_export(self):
        """Export animation to the tool data directory."""
        file_name = self.file_name_field.text().strip()
        if not file_name:
            show_warning_dialog("Animation I/E", "Please specify a file name.")
            return

        fmt = self._get_export_format()
        output_file = os.path.join(self.root_path, file_name)

        if self.all_animated_radio.isChecked():
            written = command.export_all_animation(output_file, format=fmt, on_progress=self._export_progress)
        else:
            written = command.export_animation(output_file, format=fmt, on_progress=self._export_progress)

        logger.info(f"Exported animation to {len(written)} file(s)")
        self._populate_file_list()

    # -------------------------------------------------------------------------
    # Advanced Import
    # -------------------------------------------------------------------------

    @error_handler
    @undo_chunk("Animation I/E: Import")
    def _on_import(self):
        """Import animation from selected tree files."""
        file_paths = self._get_selected_file_paths()
        if not file_paths:
            show_warning_dialog("Animation I/E", "Please select a file from the list.")
            return

        mode = command.IMPORT_MODES[self.mode_combo.currentIndex()]
        target_namespace = self._resolve_target_namespace()

        all_modified = []
        for file_path in file_paths:
            modified = command.import_animation_from_file(
                file_path, mode=mode, target_namespace=target_namespace, time_offset=self.time_offset_spin.value()
            )
            all_modified.extend(modified)

        if all_modified:
            cmds.select(all_modified, r=True)
            logger.info(f"Imported animation to {len(all_modified)} node(s)")
        else:
            logger.warning("No nodes were modified during import")

    # -------------------------------------------------------------------------
    # Tree Context Menu
    # -------------------------------------------------------------------------

    def _on_tree_context_menu(self, point):
        """Show context menu for the tree widget."""
        menu = QMenu()

        selected = self.tree_widget.selectedItems()
        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(len(selected) > 0)
        delete_action.triggered.connect(self._delete_selected_files)

        menu.addSeparator()

        open_action = menu.addAction("Open Directory")
        open_action.triggered.connect(lambda: os.startfile(self.root_path))

        menu.exec_(self.tree_widget.mapToGlobal(point))

    @error_handler
    def _delete_selected_files(self):
        """Delete selected files from the tree."""
        from ....lib_ui import maya_dialog

        file_paths = self._get_selected_file_paths()
        if not file_paths:
            return

        message = f"Delete {len(file_paths)} file(s)?\n\nThis action cannot be undone."
        if not maya_dialog.confirm_dialog("Confirm Deletion", message):
            return

        for file_path in file_paths:
            try:
                os.remove(file_path)
                logger.debug(f"Deleted: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

        self._populate_file_list()

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        """Collect current UI settings."""
        return {
            "source_all": self.all_animated_radio.isChecked(),
            "import_mode": self.mode_combo.currentIndex(),
            "target_namespace": self.namespace_combo.currentText(),
            "time_offset": self.time_offset_spin.value(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI."""
        if settings_data.get("source_all", False):
            self.all_animated_radio.setChecked(True)
        else:
            self.selected_radio.setChecked(True)
        self.mode_combo.setCurrentIndex(settings_data.get("import_mode", 0))

        self.time_offset_spin.setValue(settings_data.get("time_offset", 0))

        ns_text = settings_data.get("target_namespace", NS_FILE)
        index = self.namespace_combo.findText(ns_text)
        if index >= 0:
            self.namespace_combo.setCurrentIndex(index)
        else:
            self.namespace_combo.setEditText(ns_text)

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def showEvent(self, event):
        """Refresh namespace combo when window is shown."""
        super().showEvent(event)
        self._refresh_namespace_combo()

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Animation I/E UI."""
    global _instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass
    _instance = MainWindow(get_maya_main_window())
    _instance.show()
    return _instance
