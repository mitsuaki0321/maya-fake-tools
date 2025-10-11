"""Rename selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator, optionvar
from .....lib_ui.qt_compat import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QWidget
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

    def __init__(self, tool_settings: optionvar.ToolOptionSettings, parent=None):
        """Constructor.

        Args:
            tool_settings: Tool settings instance for storing preferences.
            parent: Parent widget.
        """
        super().__init__(parent=parent)
        self.tool_settings = tool_settings

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

        # Restore settings
        self.name_field.setText(self.tool_settings.read("rename_name_field", ""))
        self.start_alpha_field.setText(self.tool_settings.read("rename_start_alpha_field", "A"))
        self.start_number_field.setText(self.tool_settings.read("rename_start_number_field", "1"))

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
        start_number = self.start_number_field.text()

        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        nodes = command.solve_rename(nodes, new_name, start_alpha=start_alpha, start_number=start_number)

        cmds.select(nodes, r=True)

        # Save settings
        self.save_tool_options()

    def save_tool_options(self):
        """Save the tool option settings."""
        self.tool_settings.write("rename_name_field", self.name_field.text())
        self.tool_settings.write("rename_start_alpha_field", self.start_alpha_field.text())
        self.tool_settings.write("rename_start_number_field", self.start_number_field.text())


__all__ = ["RenameSelectionWidget"]
