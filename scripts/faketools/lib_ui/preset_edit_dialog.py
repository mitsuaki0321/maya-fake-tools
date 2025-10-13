"""
Preset edit dialog for tool settings.

This module provides a dialog for editing (deleting) presets.

Example:
    >>> dialog = PresetEditDialog(settings_manager, parent=widget)
    >>> dialog.exec()
"""

import logging

import maya.cmds as cmds

from .maya_dialog import show_error_dialog, show_info_dialog
from .qt_compat import QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout
from .tool_settings import ToolSettingsManager

logger = logging.getLogger(__name__)


class PresetEditDialog(QDialog):
    """
    Dialog for editing presets.

    Currently supports deleting presets only.
    """

    def __init__(self, settings_manager: ToolSettingsManager, parent=None):
        """
        Initialize the preset edit dialog.

        Args:
            settings_manager (ToolSettingsManager): Settings manager instance
            parent: Parent widget

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> dialog = PresetEditDialog(settings, parent=main_window)
            >>> dialog.exec()
        """
        super().__init__(parent)
        self.settings_manager = settings_manager

        self.setWindowTitle("Edit Presets")
        self.setModal(True)
        self.resize(200, 150)

        self._setup_ui()
        self._refresh_preset_list()
        logger.debug("PresetEditDialog initialized")

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Label
        label = QLabel("Select preset to delete:")
        layout.addWidget(label)

        # List widget
        self.preset_list = QListWidget()
        self.preset_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.preset_list)

        # Action buttons (horizontal layout)
        action_layout = QHBoxLayout()

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.delete_button.setEnabled(False)
        action_layout.addWidget(self.delete_button, stretch=1)

        layout.addLayout(action_layout)

        logger.debug("PresetEditDialog UI setup complete")

    def _refresh_preset_list(self):
        """Refresh the preset list widget."""
        self.preset_list.clear()

        presets = self.settings_manager.list_presets()

        # Ensure "default" is always first
        if ToolSettingsManager.DEFAULT_PRESET_NAME in presets:
            presets.remove(ToolSettingsManager.DEFAULT_PRESET_NAME)
            presets.insert(0, ToolSettingsManager.DEFAULT_PRESET_NAME)

        self.preset_list.addItems(presets)
        logger.debug(f"Preset list refreshed: {len(presets)} presets")

    def _on_selection_changed(self):
        """Handle preset selection change."""
        selected_items = self.preset_list.selectedItems()
        has_selection = len(selected_items) > 0

        if has_selection:
            preset_name = selected_items[0].text()
            is_default = preset_name == ToolSettingsManager.DEFAULT_PRESET_NAME

            # Cannot delete "default"
            self.delete_button.setEnabled(not is_default)
        else:
            self.delete_button.setEnabled(False)

    def _get_selected_preset_name(self) -> str | None:
        """
        Get the currently selected preset name.

        Returns:
            str | None: Selected preset name, or None if no selection
        """
        selected_items = self.preset_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].text()

    def _on_delete_clicked(self):
        """Handle delete button click."""
        preset_name = self._get_selected_preset_name()
        if not preset_name:
            return

        if preset_name == ToolSettingsManager.DEFAULT_PRESET_NAME:
            show_error_dialog("Cannot Delete", f"The '{ToolSettingsManager.DEFAULT_PRESET_NAME}' preset cannot be deleted.")
            return

        # Confirm deletion
        result = cmds.confirmDialog(
            title="Delete Preset",
            message=f"Are you sure you want to delete preset '{preset_name}'?",
            button=["Delete", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
        )

        if result != "Delete":
            return

        try:
            self.settings_manager.delete_preset(preset_name)
            logger.info(f"Deleted preset: {preset_name}")
            self._refresh_preset_list()
            show_info_dialog("Preset Deleted", f"Preset '{preset_name}' has been deleted.")
        except Exception as e:
            logger.error(f"Failed to delete preset '{preset_name}': {e}")
            show_error_dialog("Delete Failed", f"Failed to delete preset: {e}")


__all__ = ["PresetEditDialog"]
