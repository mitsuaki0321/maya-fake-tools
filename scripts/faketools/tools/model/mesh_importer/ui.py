"""Mesh Importer UI layer."""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_dialog import show_info_dialog, show_warning_dialog
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from . import command
from .constants import PLY_EXTENSIONS, SHADER_TYPES

logger = getLogger(__name__)

_instance = None

_FILE_FILTER = "All Supported (*.glb *.gltf *.ply);;GLB Files (*.glb);;glTF Files (*.gltf);;PLY Files (*.ply);;All Files (*.*)"


class MainWindow(BaseMainWindow):
    """Mesh Importer Main Window.

    Provides UI for importing glTF/GLB and PLY files into Maya.
    """

    def __init__(self, parent=None):
        """Initialize the Mesh Importer window.

        Args:
            parent: Parent widget (typically Maya main window).
        """
        super().__init__(
            parent=parent,
            object_name="MeshImporterMainWindow",
            window_title="Mesh Importer",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="mesh_importer", category="model")
        self._initial_resize_done = False
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Main grid layout for form fields
        grid_layout = QGridLayout()
        row = 0

        # Input File
        input_label = QLabel("Input File:")
        input_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select glTF/GLB/PLY file...")
        self.input_edit.textChanged.connect(self._update_ui_for_format)
        input_browse_button = QPushButton("...")
        input_browse_button.setFixedWidth(30)
        input_browse_button.clicked.connect(self._browse_input_file)

        grid_layout.addWidget(input_label, row, 0)
        grid_layout.addWidget(self.input_edit, row, 1)
        grid_layout.addWidget(input_browse_button, row, 2)
        row += 1

        # Output Directory
        self.output_label = QLabel("Output Directory:")
        self.output_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.output_label.setToolTip("Optional: Leave empty to use same directory as input file")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("(Optional) Same as input file...")
        self.output_browse_button = QPushButton("...")
        self.output_browse_button.setFixedWidth(30)
        self.output_browse_button.clicked.connect(self._browse_output_dir)

        grid_layout.addWidget(self.output_label, row, 0)
        grid_layout.addWidget(self.output_edit, row, 1)
        grid_layout.addWidget(self.output_browse_button, row, 2)
        row += 1

        # Shader Type
        self.shader_label = QLabel("Shader Type:")
        self.shader_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.shader_combo = QComboBox()

        # Add shader types from constants
        for display_name in SHADER_TYPES.values():
            self.shader_combo.addItem(display_name)

        # Set default to "Auto Detect"
        auto_index = self.shader_combo.findText(SHADER_TYPES.get("auto", "Auto Detect"))
        if auto_index >= 0:
            self.shader_combo.setCurrentIndex(auto_index)

        grid_layout.addWidget(self.shader_label, row, 0)
        grid_layout.addWidget(self.shader_combo, row, 1)

        # Set column stretch so the middle column expands
        grid_layout.setColumnStretch(1, 1)

        self.central_layout.addLayout(grid_layout)

        # Action buttons
        self.central_layout.addLayout(self._create_buttons())

    def _create_buttons(self) -> QHBoxLayout:
        """Create the action buttons section.

        Returns:
            QHBoxLayout containing the action buttons.
        """
        layout = QHBoxLayout()

        import_button = QPushButton("Import")
        import_button.clicked.connect(self._on_import_clicked)

        layout.addWidget(import_button)
        return layout

    def _browse_input_file(self):
        """Open file browser dialog for input file selection."""
        current_file = self.input_edit.text()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mesh File",
            current_file if current_file else "",
            _FILE_FILTER,
        )
        if file_path:
            self.input_edit.setText(file_path)

    def _browse_output_dir(self):
        """Open directory browser dialog for output directory selection."""
        current_dir = self.output_edit.text()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current_dir if current_dir else "",
        )
        if directory:
            self.output_edit.setText(directory)

    def _is_ply_format(self) -> bool:
        """Check if the current input file is a PLY file.

        Returns:
            True if the input file has a PLY extension.
        """
        text = self.input_edit.text().strip()
        if not text:
            return False
        return Path(text).suffix.lower() in PLY_EXTENSIONS

    def _update_ui_for_format(self):
        """Update UI widget states based on the detected file format.

        PLY files do not use Shader Type or Output Directory, so those
        widgets are disabled when a PLY file is selected.
        """
        is_ply = self._is_ply_format()
        gltf_enabled = not is_ply

        self.output_label.setEnabled(gltf_enabled)
        self.output_edit.setEnabled(gltf_enabled)
        self.output_browse_button.setEnabled(gltf_enabled)
        self.shader_label.setEnabled(gltf_enabled)
        self.shader_combo.setEnabled(gltf_enabled)

    def _get_shader_key(self) -> str:
        """Get the shader type key from the combo box selection.

        Returns:
            Shader type key (e.g., 'arnold', 'auto').
        """
        display_name = self.shader_combo.currentText()
        for key, name in SHADER_TYPES.items():
            if name == display_name:
                return key
        return "auto"

    @error_handler
    @undo_chunk("Mesh Importer: Import")
    def _on_import_clicked(self):
        """Handle import button click."""
        file_path = self.input_edit.text().strip()
        if not file_path:
            show_warning_dialog("Warning", "Please select an input file.")
            return

        output_dir = self.output_edit.text().strip() or None
        shader_type = self._get_shader_key()

        result = command.import_file(
            file_path=file_path,
            output_dir=output_dir,
            shader_type=shader_type,
        )

        if result:
            show_info_dialog("Success", f"Imported {len(result)} objects.")
        else:
            show_warning_dialog("Import Failed", "Check Script Editor for details.")

    def _collect_settings(self) -> dict:
        """Collect current UI settings into a dictionary.

        Returns:
            Current UI settings.
        """
        return {
            "input_file": self.input_edit.text(),
            "output_dir": self.output_edit.text(),
            "shader_type": self.shader_combo.currentText(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings data to UI.

        Args:
            settings_data: Settings data to apply.
        """
        self.input_edit.setText(settings_data.get("input_file", ""))
        self.output_edit.setText(settings_data.get("output_dir", ""))

        shader_name = settings_data.get("shader_type", "")
        index = self.shader_combo.findText(shader_name)
        if index >= 0:
            self.shader_combo.setCurrentIndex(index)

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)
            logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to default preset."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")
        logger.debug("UI settings saved")

    def showEvent(self, event):
        """Handle window show event.

        Args:
            event: Show event.
        """
        super().showEvent(event)
        if not self._initial_resize_done:
            self._initial_resize_done = True
            current_width = self.width()
            new_width = int(current_width * 1.5)
            self.resize(new_width, self.height())

    def closeEvent(self, event):
        """Handle window close event.

        Args:
            event: Close event.
        """
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Mesh Importer UI.

    Creates or raises the main window.

    Returns:
        The main window instance.
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
