"""
Preset save dialog for tool settings.

This module provides a simple dialog for saving presets with a name.

Example:
    >>> dialog = PresetSaveDialog(settings_manager, parent=widget)
    >>> if dialog.exec():
    ...     preset_name = dialog.get_preset_name()
    ...     print(f"Saved to: {preset_name}")
"""

import logging
from typing import Optional

import maya.cmds as cmds

from .maya_dialog import show_error_dialog
from .qt_compat import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from .tool_settings import ToolSettingsManager

logger = logging.getLogger(__name__)


class PresetSaveDialog(QDialog):
    """
    Dialog for saving presets.

    Provides a simple input field for preset name and Save/Cancel buttons.
    Validates preset name and confirms overwrite if preset already exists.
    """

    def __init__(self, settings_manager: ToolSettingsManager, parent=None):
        """
        Initialize the preset save dialog.

        Args:
            settings_manager (ToolSettingsManager): Settings manager instance
            parent: Parent widget

        Example:
            >>> settings = ToolSettingsManager("my_tool", "rig")
            >>> dialog = PresetSaveDialog(settings, parent=main_window)
            >>> if dialog.exec():
            ...     preset_name = dialog.get_preset_name()
        """
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._preset_name = None

        self.setWindowTitle("Save Preset")
        self.setModal(True)

        self._setup_ui()
        logger.debug("PresetSaveDialog initialized")

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)

        # Label and input field
        input_layout = QHBoxLayout()
        label = QLabel("Preset name:")
        input_layout.addWidget(label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter preset name...")
        input_layout.addWidget(self.name_input, stretch=1)

        layout.addLayout(input_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save_clicked)
        save_button.setDefault(True)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        logger.debug("PresetSaveDialog UI setup complete")

    def get_preset_name(self) -> Optional[str]:
        """
        Get the entered preset name.

        Returns:
            Preset name if dialog was accepted, None otherwise

        Example:
            >>> dialog = PresetSaveDialog(settings)
            >>> if dialog.exec():
            ...     name = dialog.get_preset_name()
            ...     print(name)
        """
        return self._preset_name

    def _on_save_clicked(self):
        """Handle save button click."""
        preset_name = self.name_input.text().strip()

        if not preset_name:
            show_error_dialog("Invalid Name", "Preset name cannot be empty.")
            return

        try:
            # Validate preset name
            self.settings_manager._validate_preset_name(preset_name)

            # Check if preset already exists
            if self.settings_manager.preset_exists(preset_name):
                result = cmds.confirmDialog(
                    title="Preset Exists",
                    message=f"Preset '{preset_name}' already exists. Overwrite?",
                    button=["Overwrite", "Cancel"],
                    defaultButton="Cancel",
                    cancelButton="Cancel",
                    dismissString="Cancel",
                )
                if result != "Overwrite":
                    return

            # Accept dialog
            self._preset_name = preset_name
            logger.info(f"Preset name confirmed: {preset_name}")
            self.accept()

        except ValueError as e:
            logger.error(f"Invalid preset name '{preset_name}': {e}")
            show_error_dialog("Invalid Preset Name", str(e))


__all__ = ["PresetSaveDialog"]
