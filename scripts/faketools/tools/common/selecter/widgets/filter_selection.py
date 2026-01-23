"""Filter selection widget for selecter tool."""

import re

import maya.cmds as cmds

from .....lib import lib_selection
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QLineEdit, QSizePolicy, QWidget, Signal
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.widgets import extra_widgets
from .constants import FILTER_COLOR, selecter_handler
from .selecter_button import SelecterButton


class FilterSelectionWidget(QWidget):
    """Filter Selection Widget.

    Provides filtering functionality for nodes by name (regex) and type.
    """

    settings_changed = Signal()

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

        # Filter by name field
        self.filter_name_field = QLineEdit()
        self.filter_name_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.filter_name_field)

        # Case sensitivity toggle
        from .....lib_ui.ui_utils import get_line_height

        line_height = get_line_height(self)
        button_size = int(line_height * 2.0)
        font_size = int(line_height * 0.75)
        self.filter_name_ignorecase_cb = extra_widgets.TextCheckBoxButton(
            text="Aa", width=button_size, height=button_size, font_size=font_size, parent=self
        )
        main_layout.addWidget(self.filter_name_ignorecase_cb)

        # Filter by name button
        filter_name_button = SelecterButton("NAM", color=FILTER_COLOR)
        main_layout.addWidget(filter_name_button)

        # Filter by type field
        self.filter_type_field = QLineEdit()
        self.filter_type_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.filter_type_field)

        # Filter by type button
        filter_type_button = SelecterButton("TYP", color=FILTER_COLOR)
        main_layout.addWidget(filter_type_button)

        self.setLayout(main_layout)

        # Connect signals
        filter_name_button.clicked.connect(self.select_by_name)
        filter_type_button.clicked.connect(self.select_by_type)

    @maya_decorator.undo_chunk("Selecter: Filter Name")
    @maya_decorator.error_handler
    @selecter_handler
    def select_by_name(self, nodes: list[str]):
        """Select nodes by name filter.

        Args:
            nodes: List of node names to filter.

        Returns:
            list[str]: Filtered node list.
        """
        # Get filter pattern
        filter_name = self.filter_name_field.text()
        if not filter_name:
            cmds.error("No filter name specified.")

        # Auto-convert simple alphanumeric to regex pattern
        if re.match(r"^[a-zA-Z0-9]+$", filter_name):
            filter_name = f".*{filter_name}.*"

        ignorecase = self.filter_name_ignorecase_cb.isChecked()

        # Filter nodes
        result_nodes = lib_selection.filter_by_regex(nodes, regex=filter_name, ignorecase=ignorecase)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            self.settings_changed.emit()
            return nodes

        self.settings_changed.emit()
        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Filter Type")
    @maya_decorator.error_handler
    @selecter_handler
    def select_by_type(self, nodes: list[str]):
        """Select nodes by type filter.

        Args:
            nodes: List of node names to filter.

        Returns:
            list[str]: Filtered node list.
        """
        # Get filter type
        filter_type = self.filter_type_field.text()
        if not filter_type:
            cmds.error("No filter type specified.")

        # Filter nodes
        result_nodes = lib_selection.filter_by_type(nodes, node_type=filter_type)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            self.settings_changed.emit()
            return nodes

        self.settings_changed.emit()
        return result_nodes

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "filter_name_field": self.filter_name_field.text(),
            "filter_name_ignorecase": self.filter_name_ignorecase_cb.isChecked(),
            "filter_type_field": self.filter_type_field.text(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "filter_name_field" in settings_data:
            self.filter_name_field.setText(settings_data["filter_name_field"])
        if "filter_name_ignorecase" in settings_data:
            self.filter_name_ignorecase_cb.setChecked(settings_data["filter_name_ignorecase"])
        if "filter_type_field" in settings_data:
            self.filter_type_field.setText(settings_data["filter_type_field"])


__all__ = ["FilterSelectionWidget"]
