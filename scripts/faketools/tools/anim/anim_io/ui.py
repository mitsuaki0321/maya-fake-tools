"""Animation Import/Export UI layer."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import (
    BaseMainWindow,
    ToolDataManager,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
    get_save_file_name,
    show_warning_dialog,
    undo_chunk,
)
from ....lib_ui.base_window import get_margins, get_spacing
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)
from ....lib_ui.ui_utils import get_relative_size
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Animation IO Main Window."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="AnimIOMainWindow",
            window_title="Animation IO",
            central_layout="vertical",
        )
        self.settings = ToolSettingsManager(tool_name="anim_io", category="anim")

        tool_data_manager = ToolDataManager("anim_io", "anim")
        tool_data_manager.ensure_data_dir()
        self.default_directory = str(tool_data_manager.get_data_dir())

        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        spacing = get_spacing(self, direction="vertical")
        left, top, right, bottom = get_margins(self)

        # --- File Path ---
        file_layout = QHBoxLayout()
        file_layout.setSpacing(int(spacing * 0.5))
        file_label = QLabel("File Path:")
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a JSON file...")
        browse_button = QPushButton("...")
        browse_button.setFixedWidth(int(get_relative_size(self, width_ratio=0.2, height_ratio=0.1)[0]))
        browse_button.clicked.connect(self._browse_file)
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_path_edit, 1)
        file_layout.addWidget(browse_button)
        self.central_layout.addLayout(file_layout)

        # --- Export Group ---
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        export_layout.setSpacing(int(spacing * 0.5))
        export_layout.setContentsMargins(left, top, right, bottom)

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
        export_layout.addLayout(source_layout)

        export_button = QPushButton("Export")
        export_button.clicked.connect(self._on_export)
        export_layout.addWidget(export_button)

        export_group.setLayout(export_layout)
        self.central_layout.addWidget(export_group)

        # --- Import Group ---
        import_group = QGroupBox("Import")
        import_layout = QVBoxLayout()
        import_layout.setSpacing(int(spacing * 0.5))
        import_layout.setContentsMargins(left, top, right, bottom)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(int(spacing * 0.5))
        mode_label = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Replace", "Merge"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo, 1)
        import_layout.addLayout(mode_layout)

        ns_layout = QHBoxLayout()
        ns_layout.setSpacing(int(spacing * 0.5))
        ns_label = QLabel("Target Namespace:")
        self.target_namespace_edit = QLineEdit()
        self.target_namespace_edit.setPlaceholderText("(use file namespace)")
        ns_layout.addWidget(ns_label)
        ns_layout.addWidget(self.target_namespace_edit, 1)
        import_layout.addLayout(ns_layout)

        import_button = QPushButton("Import")
        import_button.clicked.connect(self._on_import)
        import_layout.addWidget(import_button)

        import_group.setLayout(import_layout)
        self.central_layout.addWidget(import_group)

        self.central_layout.addStretch()

        # --- Window Size ---
        width, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self.resize(width, height)

    def _browse_file(self):
        """Open file browser to select a file path."""
        current_path = self.file_path_edit.text() or self.default_directory
        file_path, _ = get_save_file_name(
            parent=self,
            caption="Select Animation File",
            directory=current_path,
            filter="JSON Files (*.json)",
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    @error_handler
    def _on_export(self):
        """Handle export button click."""
        file_path = self.file_path_edit.text()
        if not file_path:
            show_warning_dialog("Animation IO", "Please specify a file path.")
            return

        use_all = self.all_animated_radio.isChecked()

        if use_all:
            written_files = command.export_all_animation(file_path)
        else:
            written_files = command.export_animation(file_path)

        logger.info(f"Exported animation to {len(written_files)} file(s): {written_files}")

    @error_handler
    @undo_chunk("Animation IO: Import")
    def _on_import(self):
        """Handle import button click."""
        file_path = self.file_path_edit.text()
        if not file_path:
            show_warning_dialog("Animation IO", "Please specify a file path.")
            return

        mode = command.IMPORT_MODES[self.mode_combo.currentIndex()]
        target_ns = self.target_namespace_edit.text().strip()
        target_namespace = target_ns if target_ns else None

        modified_nodes = command.import_animation_from_file(file_path, mode=mode, target_namespace=target_namespace)

        if modified_nodes:
            cmds.select(modified_nodes, r=True)
            logger.info(f"Imported animation to {len(modified_nodes)} node(s): {modified_nodes}")
        else:
            logger.warning("No nodes were modified during import")

    def _collect_settings(self) -> dict:
        """Collect current UI settings."""
        return {
            "file_path": self.file_path_edit.text(),
            "source_all": self.all_animated_radio.isChecked(),
            "import_mode": self.mode_combo.currentIndex(),
            "target_namespace": self.target_namespace_edit.text(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI."""
        self.file_path_edit.setText(settings_data.get("file_path", ""))
        if settings_data.get("source_all", False):
            self.all_animated_radio.setChecked(True)
        else:
            self.selected_radio.setChecked(True)
        self.mode_combo.setCurrentIndex(settings_data.get("import_mode", 0))
        self.target_namespace_edit.setText(settings_data.get("target_namespace", ""))

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Animation IO UI."""
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
