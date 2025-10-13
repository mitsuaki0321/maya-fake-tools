"""Substitution selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib import lib_name, lib_transform
from .....lib.lib_selection import get_top_nodes
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QLineEdit, QSizePolicy, QWidget
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.ui_utils import get_line_height
from .....lib_ui.widgets import extra_widgets
from .....operations import mirror_transforms
from .. import command
from .constants import LEFT_TO_RIGHT, RIGHT_TO_LEFT, SUBSTITUTION_COLOR, selecter_handler
from .selecter_button import SelecterButton


class SubstitutionSelectionWidget(QWidget):
    """Substitution Selection Widget.

    Provides name substitution functionality:
    - Left/Right mirroring (L <-> R)
    - Custom text substitution
    - Selection by substituted name
    - Rename, mirror, duplicate operations
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

        # Left to Right button
        left_to_right_button = SelecterButton("LR", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(left_to_right_button)

        # Right to Left button
        right_to_left_button = SelecterButton("RL", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(right_to_left_button)

        # Search text field
        self.search_text_field = QLineEdit()
        self.search_text_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.search_text_field)

        # Arrow direction toggle
        self.arrow_button = extra_widgets.CheckBoxButton(icon_on="arrow-left", icon_off="arrow-right")
        main_layout.addWidget(self.arrow_button)

        # Replace text field
        self.replace_text_field = QLineEdit()
        self.replace_text_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.replace_text_field)

        # Select substitution button
        select_button = SelecterButton("SEL", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(select_button)

        # Rename substitution button
        rename_button = SelecterButton("REN", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(rename_button)

        # Mirror button
        mirror_button = SelecterButton("MIR", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(mirror_button)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Duplicate button
        duplicate_button = SelecterButton("DUP", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(duplicate_button)

        # Calculate button size dynamically
        line_height = get_line_height(self)
        button_size = int(line_height * 2.0)
        font_size = int(line_height * 0.75)

        # Mirror toggle for duplicate
        self.mirror_checkbox = extra_widgets.TextCheckBoxButton(text="MIR", width=button_size, height=button_size, font_size=font_size, parent=self)
        main_layout.addWidget(self.mirror_checkbox)

        # World/Local space toggle
        self.mirror_space_checkbox = extra_widgets.TextCheckBoxButton(
            text="WRD", width=button_size, height=button_size, font_size=font_size, parent=self
        )
        self.mirror_space_checkbox.setChecked(True)
        main_layout.addWidget(self.mirror_space_checkbox)

        # Position/Rotation checkboxes (horizontal layout)
        self.mirror_pos_checkbox = extra_widgets.TextCheckBoxButton(
            text="POS", width=button_size, height=button_size, font_size=font_size, parent=self
        )
        self.mirror_pos_checkbox.setChecked(True)
        main_layout.addWidget(self.mirror_pos_checkbox)

        self.mirror_rot_checkbox = extra_widgets.TextCheckBoxButton(
            text="ROT", width=button_size, height=button_size, font_size=font_size, parent=self
        )
        main_layout.addWidget(self.mirror_rot_checkbox)

        # Freeze transform checkbox
        self.freeze_checkbox = extra_widgets.TextCheckBoxButton(text="FRZ", width=button_size, height=button_size, font_size=font_size, parent=self)
        self.freeze_checkbox.setChecked(True)
        main_layout.addWidget(self.freeze_checkbox)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Duplicate original shape button
        duplicate_orig_button = SelecterButton("ORG", color=SUBSTITUTION_COLOR)
        main_layout.addWidget(duplicate_orig_button)

        self.setLayout(main_layout)

        # Connect signals
        left_to_right_button.clicked.connect(self.select_left_to_right)
        right_to_left_button.clicked.connect(self.select_right_to_left)
        select_button.clicked.connect(self.select_substitution)
        rename_button.clicked.connect(self.rename_substitution)
        mirror_button.clicked.connect(self.mirror_position)
        duplicate_button.clicked.connect(self.duplicate_substitution)
        duplicate_orig_button.clicked.connect(self.duplicate_original_substitution)

    @maya_decorator.undo_chunk("Selecter: Select Left to Right")
    @maya_decorator.error_handler
    @selecter_handler
    def select_left_to_right(self, nodes: list[str]):
        """Select the left to right nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Converted node list.
        """
        nodes = [node.split("|")[-1] for node in nodes]
        convert_names = lib_name.substitute_names(nodes, LEFT_TO_RIGHT[0], LEFT_TO_RIGHT[1])

        result_nodes = []
        for name, node in zip(convert_names, nodes, strict=False):
            if not cmds.objExists(name):
                cmds.warning(f"Node does not exist: {node}")
                continue

            if name == node:
                cmds.warning(f"Failed to name substitution: {node}")
                continue

            if name not in result_nodes:
                result_nodes.append(name)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Select Right to Left")
    @maya_decorator.error_handler
    @selecter_handler
    def select_right_to_left(self, nodes: list[str]):
        """Select the right to left nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Converted node list.
        """
        nodes = [node.split("|")[-1] for node in nodes]
        convert_names = lib_name.substitute_names(nodes, RIGHT_TO_LEFT[0], RIGHT_TO_LEFT[1])

        result_nodes = []
        for name, node in zip(convert_names, nodes, strict=False):
            if not cmds.objExists(name):
                cmds.warning(f"Node does not exist: {node}")
                continue

            if name == node:
                cmds.warning(f"Failed to name substitute: {node}")
                continue

            if name not in result_nodes:
                result_nodes.append(name)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Select Substitution")
    @maya_decorator.error_handler
    @selecter_handler
    def select_substitution(self, nodes: list[str]):
        """Select the substitution nodes.

        Args:
            nodes: List of node names.

        Returns:
            list[str]: Substituted node list.
        """
        search_text, replace_text = self._get_substitution_option()

        nodes = [node.split("|")[-1] for node in nodes]
        convert_names = lib_name.substitute_names(nodes, search_text, replace_text)

        result_nodes = []
        for name, node in zip(convert_names, nodes, strict=False):
            if not cmds.objExists(name):
                cmds.warning(f"Node does not exist: {node}")
                continue

            if name == node:
                cmds.warning(f"Failed to name substitute: {node}")
                continue

            if name not in result_nodes:
                result_nodes.append(name)

        if not result_nodes:
            cmds.warning("No matching nodes found.")
            return nodes

        return result_nodes

    @maya_decorator.undo_chunk("Selecter: Rename Substitution")
    @maya_decorator.error_handler
    def rename_substitution(self):
        """Rename the substitution nodes."""
        search_text, replace_text = self._get_substitution_option()

        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        result_nodes = command.substitute_rename(nodes, search_text, replace_text)

        cmds.select(result_nodes, r=True)

    @maya_decorator.undo_chunk("Selecter: Mirror Position")
    @maya_decorator.error_handler
    def mirror_position(self):
        """Mirror the position of the substitution nodes."""
        nodes = cmds.ls(sl=True, type="transform")
        if not nodes:
            cmds.error("No object selected.")

        mirror_pos = self.mirror_pos_checkbox.isChecked()
        mirror_rot = self.mirror_rot_checkbox.isChecked()
        mirror_space = "world" if self.mirror_space_checkbox.isChecked() else "local"
        search_text, replace_text = self._get_substitution_option()

        nodes = [node.split("|")[-1] for node in nodes]
        convert_names = lib_name.substitute_names(nodes, search_text, replace_text)

        result_nodes = []
        for name, node in zip(convert_names, nodes, strict=False):
            if not cmds.objExists(name):
                cmds.warning(f"Node does not exist: {node}")
                continue

            if name == node:
                cmds.warning(f"Failed to name substitute: {node}")
                continue

            # Copy source transform to target
            source_matrix = cmds.xform(node, query=True, matrix=True, worldSpace=True)
            cmds.xform(name, matrix=source_matrix, worldSpace=True)

            # Mirror target using operations.mirror_transforms
            mirror_transforms(name, axis="x", mirror_position=mirror_pos, mirror_rotation=mirror_rot, space=mirror_space)

            result_nodes.append(name)

        cmds.select(result_nodes, r=True)

    @maya_decorator.undo_chunk("Selecter: Duplicate Substitution")
    @maya_decorator.error_handler
    def duplicate_substitution(self):
        """Duplicate the substitution nodes."""
        search_text, replace_text = self._get_substitution_option()

        mirror = self.mirror_checkbox.isChecked()
        mirror_space = "world" if self.mirror_space_checkbox.isChecked() else "local"
        mirror_pos = self.mirror_pos_checkbox.isChecked()
        mirror_rot = self.mirror_rot_checkbox.isChecked()
        freeze = self.freeze_checkbox.isChecked()

        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        result_nodes = command.substitute_duplicate(nodes, search_text, replace_text)
        if not result_nodes:
            return

        if all(["dagNode" in cmds.nodeType(node, inherited=True) for node in result_nodes]):
            result_top_nodes = get_top_nodes(result_nodes)
            if mirror:
                for node in result_top_nodes:
                    # Mirror node using operations.mirror_transforms
                    mirror_transforms(node, axis="x", mirror_position=mirror_pos, mirror_rotation=mirror_rot, space=mirror_space)
                    if freeze:
                        lib_transform.freeze_transform(node)
                        lib_transform.freeze_transform_pivot(node)

            cmds.select(result_top_nodes, r=True)
        else:
            cmds.select(result_nodes, r=True)

    @maya_decorator.undo_chunk("Selecter: Duplicate Original Substitution")
    @maya_decorator.error_handler
    def duplicate_original_substitution(self):
        """Duplicate the original substitution nodes."""
        search_text, replace_text = self._get_substitution_option()

        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        result_nodes = command.substitute_duplicate_original(nodes, search_text, replace_text)

        cmds.select(result_nodes, r=True)

    def _get_substitution_option(self):
        """Get the substitution option.

        Returns:
            tuple: The search and replace text.
        """
        search_text = self.search_text_field.text()
        replace_text = self.replace_text_field.text()

        if self.arrow_button.isChecked():
            search_text, replace_text = replace_text, search_text

        if not search_text:
            cmds.error("No search text specified.")

        return search_text, replace_text

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "sub_left_field": self.search_text_field.text(),
            "sub_right_field": self.replace_text_field.text(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "sub_left_field" in settings_data:
            self.search_text_field.setText(settings_data["sub_left_field"])
        if "sub_right_field" in settings_data:
            self.replace_text_field.setText(settings_data["sub_right_field"])


__all__ = ["SubstitutionSelectionWidget"]
