"""Filter selection widget for selecter tool."""

import re

import maya.cmds as cmds

from .....lib import lib_selection
from .....lib_ui import base_window, maya_decorator, maya_ui
from .....lib_ui.qt_compat import QHBoxLayout, QLineEdit, QSizePolicy, QWidget, Signal
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.widgets import TextToggleButton
from .constants import FILTER_COLOR
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
        self.filter_name_ignorecase_cb = TextToggleButton("Aa", parent=self)
        main_layout.addWidget(self.filter_name_ignorecase_cb)

        # All scene toggle for name filter (OFF=selection only, ON=all scene)
        self.filter_name_all_cb = TextToggleButton("ALL", parent=self)
        main_layout.addWidget(self.filter_name_all_cb)

        # Filter by name button
        filter_name_button = SelecterButton("NAM", color=FILTER_COLOR)
        main_layout.addWidget(filter_name_button)

        # Filter by type field
        self.filter_type_field = QLineEdit()
        self.filter_type_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.filter_type_field)

        # All scene toggle for type filter (OFF=selection only, ON=all scene)
        self.filter_type_all_cb = TextToggleButton("ALL", parent=self)
        main_layout.addWidget(self.filter_type_all_cb)

        # Filter by type button
        filter_type_button = SelecterButton("TYP", color=FILTER_COLOR)
        main_layout.addWidget(filter_type_button)

        self.setLayout(main_layout)

        # Connect signals
        filter_name_button.clicked.connect(self.select_by_name)
        filter_type_button.clicked.connect(self.select_by_type)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Filter Name")
    def select_by_name(self):
        """Select nodes by name filter."""
        # Get filter pattern
        filter_name = self.filter_name_field.text()
        if not filter_name:
            cmds.error("No filter name specified.")

        # Treat input as plain text substring search
        filter_name = f".*{re.escape(filter_name)}.*"

        ignorecase = self.filter_name_ignorecase_cb.isChecked()

        # Capture current selection for modifier key handling
        sel_nodes = cmds.ls(sl=True)

        # Determine source nodes
        if self.filter_name_all_cb.isChecked():
            source_nodes = cmds.ls()
        else:
            if not sel_nodes:
                cmds.error("No object selected.")
            source_nodes = sel_nodes

        # Filter nodes
        result_nodes = lib_selection.filter_by_regex(source_nodes, regex=filter_name, ignorecase=ignorecase)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            self.settings_changed.emit()
            return

        self._apply_selection(result_nodes, sel_nodes)
        self.settings_changed.emit()

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Filter Type")
    def select_by_type(self):
        """Select nodes by type filter."""
        # Get filter type
        filter_type = self.filter_type_field.text()
        if not filter_type:
            cmds.error("No filter type specified.")

        # Capture current selection for modifier key handling
        sel_nodes = cmds.ls(sl=True)

        # Determine source nodes
        if self.filter_type_all_cb.isChecked():
            source_nodes = cmds.ls()
        else:
            if not sel_nodes:
                cmds.error("No object selected.")
            source_nodes = sel_nodes

        # Filter nodes
        result_nodes = lib_selection.filter_by_type(source_nodes, node_type=filter_type)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            self.settings_changed.emit()
            return

        self._apply_selection(result_nodes, sel_nodes)
        self.settings_changed.emit()

    def _apply_selection(self, result_nodes: list[str], original_selection: list[str]):
        """Apply selection with modifier key handling.

        Args:
            result_nodes: Nodes to select.
            original_selection: Selection state before the operation.
        """
        mod_keys = maya_ui.get_modifiers()

        if not mod_keys:
            cmds.select(result_nodes, r=True)
        elif mod_keys == ["Shift", "Ctrl"] or "Shift" in mod_keys:
            if original_selection:
                cmds.select(original_selection, r=True)
            cmds.select(result_nodes, add=True)
        elif "Ctrl" in mod_keys and original_selection:
            cmds.select(original_selection, r=True)
            cmds.select(result_nodes, d=True)

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "filter_name_field": self.filter_name_field.text(),
            "filter_name_ignorecase": self.filter_name_ignorecase_cb.isChecked(),
            "filter_name_all": self.filter_name_all_cb.isChecked(),
            "filter_type_field": self.filter_type_field.text(),
            "filter_type_all": self.filter_type_all_cb.isChecked(),
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
        if "filter_name_all" in settings_data:
            self.filter_name_all_cb.setChecked(settings_data["filter_name_all"])
        if "filter_type_field" in settings_data:
            self.filter_type_field.setText(settings_data["filter_type_field"])
        if "filter_type_all" in settings_data:
            self.filter_type_all_cb.setChecked(settings_data["filter_type_all"])


__all__ = ["FilterSelectionWidget"]
