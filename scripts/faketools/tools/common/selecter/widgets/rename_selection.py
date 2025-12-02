"""Rename selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QWidget
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.ui_utils import get_text_width
from .. import command
from .constants import RENAME_COLOR
from .selecter_button import SelecterButton


class RenameSelectionWidget(QWidget):
    """Rename Selection Widget.

    Provides renaming functionality with placeholder support:
    - @ : Alpha placeholder (A, B, C, ...)
    - # : Number placeholder (1, 2, 3, ...)
    - ~ : Original name placeholder
    """

    def __init__(self, settings: ToolSettingsManager, parent=None):
        """Constructor.

        Args:
            settings (ToolSettingsManager): Tool settings manager for storing preferences.
            parent: Parent widget.
        """
        super().__init__(parent=parent)
        self.settings = settings

        main_layout = QHBoxLayout()
        main_layout.setSpacing(base_window.get_spacing(self, "horizontal") * 0.5)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Name field (wider than default)
        self.name_field = QLineEdit()
        min_width = get_text_width("example_node_name", self) * 2
        self.name_field.setMinimumWidth(min_width)
        self.name_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.name_field)

        # Rename button
        rename_button = SelecterButton("REN", color=RENAME_COLOR)
        main_layout.addWidget(rename_button)

        # Alpha placeholder label
        label = QLabel("@ : ")
        main_layout.addWidget(label)

        # Start alpha field
        self.start_alpha_field = QLineEdit("A")
        alpha_width = get_text_width("AAA", self) * 2
        self.start_alpha_field.setMaximumWidth(alpha_width)
        self.start_alpha_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.start_alpha_field)

        # Number placeholder label
        label = QLabel("# : ")
        main_layout.addWidget(label)

        # Start number field
        self.start_number_field = QLineEdit("1")
        number_width = get_text_width("999", self) * 2
        self.start_number_field.setMaximumWidth(number_width)
        self.start_number_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.start_number_field)

        self.setLayout(main_layout)

        # Connect signals
        rename_button.clicked.connect(self.rename_nodes)

    @maya_decorator.undo_chunk("Selecter: Rename")
    @maya_decorator.error_handler
    def rename_nodes(self):
        """Rename the nodes."""
        new_name = self.name_field.text()
        if not new_name:
            cmds.error("No new name specified.")

        start_alpha = self.start_alpha_field.text()
        start_number_text = self.start_number_field.text()

        # Convert start_number to integer
        try:
            start_number = int(start_number_text) if start_number_text else 1
        except ValueError:
            cmds.error(f"Invalid start number: {start_number_text}")

        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        nodes = command.solve_rename(nodes, new_name, start_alpha=start_alpha, start_number=start_number)

        cmds.select(nodes, r=True)

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "rename_name_field": self.name_field.text(),
            "rename_start_alpha_field": self.start_alpha_field.text(),
            "rename_start_number_field": self.start_number_field.text(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "rename_name_field" in settings_data:
            self.name_field.setText(settings_data["rename_name_field"])
        if "rename_start_alpha_field" in settings_data:
            self.start_alpha_field.setText(settings_data["rename_start_alpha_field"])
        if "rename_start_number_field" in settings_data:
            self.start_number_field.setText(settings_data["rename_start_number_field"])


__all__ = ["RenameSelectionWidget"]
