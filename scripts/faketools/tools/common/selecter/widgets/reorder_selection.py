"""Reorder selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QWidget
from .. import command
from .constants import REORDER_COLOR, REORDER_REVERSED_COLOR
from .selecter_button import SelecterButton


class ReorderWidget(QWidget):
    """Reorder Selection Widget.

    Provides outliner reordering utilities:
    - A-Z (normal): Sort by name (A→Z)
    - Z-A (normal): Sort by name (Z→A)
    - A-Z (reversed): Sort by reversed name (test→tset, then A→Z)
    - Z-A (reversed): Sort by reversed name (test→tset, then Z→A)
    """

    def __init__(self, parent=None):
        """Constructor.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent=parent)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(base_window.get_spacing(self, "horizontal") * 0.5)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Name ascending button (normal color)
        name_asc_button = SelecterButton("A-Z", color=REORDER_COLOR)
        name_asc_button.setToolTip("Sort by name (A→Z)")
        main_layout.addWidget(name_asc_button)

        # Name descending button (normal color)
        name_desc_button = SelecterButton("Z-A", color=REORDER_COLOR)
        name_desc_button.setToolTip("Sort by name (Z→A)")
        main_layout.addWidget(name_desc_button)

        # Reversed name ascending button (reversed color)
        reversed_asc_button = SelecterButton("A-Z", color=REORDER_REVERSED_COLOR)
        reversed_asc_button.setToolTip("Sort by reversed name (test→tset, then A→Z)")
        main_layout.addWidget(reversed_asc_button)

        # Reversed name descending button (reversed color)
        reversed_desc_button = SelecterButton("Z-A", color=REORDER_REVERSED_COLOR)
        reversed_desc_button.setToolTip("Sort by reversed name (test→tset, then Z→A)")
        main_layout.addWidget(reversed_desc_button)

        self.setLayout(main_layout)

        # Connect signals
        name_asc_button.clicked.connect(self.reorder_by_name_ascending)
        name_desc_button.clicked.connect(self.reorder_by_name_descending)
        reversed_asc_button.clicked.connect(self.reorder_by_reversed_name_ascending)
        reversed_desc_button.clicked.connect(self.reorder_by_reversed_name_descending)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Reorder by Name (A→Z)")
    def reorder_by_name_ascending(self):
        """Reorder selected nodes by name in ascending order (A→Z)."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No objects selected.")

        command.reorder_nodes_by_name(nodes, reverse=False)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Reorder by Name (Z→A)")
    def reorder_by_name_descending(self):
        """Reorder selected nodes by name in descending order (Z→A)."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No objects selected.")

        command.reorder_nodes_by_name(nodes, reverse=True)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Reorder by Reversed Name (Ascending)")
    def reorder_by_reversed_name_ascending(self):
        """Reorder selected nodes by reversed name in ascending order."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No objects selected.")

        command.reorder_nodes_by_reversed_name(nodes, reverse=False)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Selecter: Reorder by Reversed Name (Descending)")
    def reorder_by_reversed_name_descending(self):
        """Reorder selected nodes by reversed name in descending order."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No objects selected.")

        command.reorder_nodes_by_reversed_name(nodes, reverse=True)


__all__ = ["ReorderWidget"]
