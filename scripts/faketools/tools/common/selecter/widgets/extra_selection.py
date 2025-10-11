"""Extra selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QWidget
from .selecter_button import SelecterButton


class ExtraSelectionWidget(QWidget):
    """Extra Selection Widget.

    Provides additional selection utilities:
    - Last to First: Reorder selection to move last selected item to first
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

        # Last to First button
        last_to_first_button = SelecterButton("L2F")
        main_layout.addWidget(last_to_first_button)

        self.setLayout(main_layout)

        # Connect signals
        last_to_first_button.clicked.connect(self.last_to_first_selection)

    @maya_decorator.undo_chunk("Selecter: Last to First Selection")
    def last_to_first_selection(self):
        """Select the last object in the selection list and move it to first."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        if len(nodes) == 1:
            cmds.error("Only one object selected.")

        # Reorder: last item first, then rest
        cmds.select(nodes[-1], r=True)
        cmds.select(nodes[:-1], add=True)


__all__ = ["ExtraSelectionWidget"]
