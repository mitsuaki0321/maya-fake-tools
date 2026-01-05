"""Texture Relocator UI layer."""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_dialog import confirm_dialog, show_info_dialog, show_warning_dialog
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton
from ....lib_ui.tool_settings import ToolSettingsManager
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Texture Relocator Main Window.

    Provides UI for relocating texture file paths in the scene.
    """

    def __init__(self, parent=None):
        """Initialize the Texture Relocator window.

        Args:
            parent: Parent widget (typically Maya main window).
        """
        super().__init__(
            parent=parent,
            object_name="TextureRelocatorMainWindow",
            window_title="Texture Relocator",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="texture_relocator", category="model")
        self._initial_resize_done = False
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Target Directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Target Directory:")
        self.dir_line_edit = QLineEdit()
        self.dir_line_edit.setPlaceholderText("Select target directory...")
        browse_button = QPushButton("...")
        browse_button.setFixedWidth(30)
        browse_button.clicked.connect(self._browse_directory)

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_line_edit)
        dir_layout.addWidget(browse_button)
        self.central_layout.addLayout(dir_layout)

        # Confirm overwrite checkbox
        self.confirm_overwrite_checkbox = QCheckBox("Confirm overwrite")
        self.confirm_overwrite_checkbox.setChecked(True)
        self.central_layout.addWidget(self.confirm_overwrite_checkbox)

        # Action buttons
        button_layout = QHBoxLayout()
        copy_button = QPushButton("Copy && Relink")
        copy_button.clicked.connect(self._on_copy_and_relink)
        replace_button = QPushButton("Replace Path")
        replace_button.clicked.connect(self._on_replace_path)

        button_layout.addWidget(copy_button)
        button_layout.addWidget(replace_button)
        self.central_layout.addLayout(button_layout)

    def _browse_directory(self):
        """Open directory browser dialog."""
        current_dir = self.dir_line_edit.text()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Target Directory",
            current_dir if current_dir else "",
        )
        if directory:
            self.dir_line_edit.setText(directory)

    def _get_target_directory(self) -> Path | None:
        """Get target directory from UI.

        Returns:
            Path object or None if invalid.
        """
        dir_text = self.dir_line_edit.text().strip()
        if not dir_text:
            show_warning_dialog("Warning", "Please specify a target directory.")
            return None

        target_dir = Path(dir_text)
        if not target_dir.exists():
            if confirm_dialog("Create Directory", f"Directory does not exist:\n{target_dir}\n\nCreate it?"):
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                return None

        return target_dir

    @error_handler
    @undo_chunk("Texture Relocator: Copy & Relink")
    def _on_copy_and_relink(self):
        """Copy textures to target directory and update paths."""
        target_dir = self._get_target_directory()
        if not target_dir:
            return

        confirm_overwrite = self.confirm_overwrite_checkbox.isChecked()

        # Check for files that would be overwritten
        if confirm_overwrite:
            existing_files = command.get_files_to_overwrite(target_dir)
            if existing_files:
                file_list = "\n".join(existing_files[:10])
                if len(existing_files) > 10:
                    file_list += f"\n... and {len(existing_files) - 10} more files"
                if not confirm_dialog(
                    "Overwrite Files",
                    f"The following files will be overwritten:\n\n{file_list}\n\nContinue?",
                ):
                    return
                # User confirmed, proceed with overwrite
                overwrite = True
            else:
                overwrite = False
        else:
            overwrite = True

        result = command.batch_copy_and_relink(target_dir, overwrite=overwrite)

        # Show result
        if result.failed_nodes:
            failed_list = ", ".join(result.failed_nodes[:5])
            if len(result.failed_nodes) > 5:
                failed_list += f" and {len(result.failed_nodes) - 5} more"
            show_warning_dialog(
                "Copy Complete with Warnings",
                f"Copied {result.success_count}/{result.total_nodes} textures.\nFailed nodes: {failed_list}",
            )
        else:
            show_info_dialog(
                "Copy Complete",
                f"Successfully copied and relinked {result.success_count} textures.",
            )

        logger.info(f"Copy & Relink complete: {result.success_count}/{result.total_nodes} succeeded")

    @error_handler
    @undo_chunk("Texture Relocator: Replace Path")
    def _on_replace_path(self):
        """Replace texture paths with target directory."""
        target_dir = self._get_target_directory()
        if not target_dir:
            return

        result = command.batch_replace_path(target_dir)

        # Show result
        if result.failed_nodes:
            failed_list = ", ".join(result.failed_nodes[:5])
            if len(result.failed_nodes) > 5:
                failed_list += f" and {len(result.failed_nodes) - 5} more"
            show_warning_dialog(
                "Replace Complete with Warnings",
                f"Replaced {result.success_count}/{result.total_nodes} paths.\nFailed nodes: {failed_list}",
            )
        else:
            show_info_dialog(
                "Replace Complete",
                f"Successfully replaced {result.success_count} texture paths.",
            )

        logger.info(f"Replace Path complete: {result.success_count}/{result.total_nodes} succeeded")

    def _collect_settings(self) -> dict:
        """Collect current UI settings into a dictionary.

        Returns:
            Current UI settings.
        """
        return {
            "target_directory": self.dir_line_edit.text(),
            "confirm_overwrite": self.confirm_overwrite_checkbox.isChecked(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings data to UI.

        Args:
            settings_data: Settings data to apply.
        """
        self.dir_line_edit.setText(settings_data.get("target_directory", ""))
        self.confirm_overwrite_checkbox.setChecked(settings_data.get("confirm_overwrite", True))

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
    """Show the Texture Relocator UI.

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
