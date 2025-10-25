"""Extra selection widget for selecter tool."""

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QWidget
from .selecter_button import SelecterButton


class ExtraSelectionWidget(QWidget):
    """Extra Selection Widget.

    Provides additional selection utilities:
    - LF (Last to First): Move last selected item to first
    - FL (First to Last): Move first selected item to last
    - REV (Reverse): Reverse the selection order
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
        last_to_first_button = SelecterButton("LF")
        last_to_first_button.setToolTip("Last to First: Move last selected item to first")
        main_layout.addWidget(last_to_first_button)

        # First to Last button
        first_to_last_button = SelecterButton("FL")
        first_to_last_button.setToolTip("First to Last: Move first selected item to last")
        main_layout.addWidget(first_to_last_button)

        # Reverse button
        reverse_button = SelecterButton("REV")
        reverse_button.setToolTip("Reverse: Reverse the selection order")
        main_layout.addWidget(reverse_button)

        self.setLayout(main_layout)

        # Connect signals
        last_to_first_button.clicked.connect(self.last_to_first_selection)
        first_to_last_button.clicked.connect(self.first_to_last_selection)
        reverse_button.clicked.connect(self.reverse_selection)

    @maya_decorator.undo_chunk("Selecter: Last to First Selection")
    def last_to_first_selection(self):
        """Move the last selected item to first position."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        if len(nodes) == 1:
            cmds.error("Only one object selected.")

        # Reorder: last item first, then rest
        cmds.select(nodes[-1], r=True)
        cmds.select(nodes[:-1], add=True)

    @maya_decorator.undo_chunk("Selecter: First to Last Selection")
    def first_to_last_selection(self):
        """Move the first selected item to last position."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        if len(nodes) == 1:
            cmds.error("Only one object selected.")

        # Reorder: rest first, then first item
        cmds.select(nodes[1:], r=True)
        cmds.select(nodes[0], add=True)

    @maya_decorator.undo_chunk("Selecter: Reverse Selection")
    def reverse_selection(self):
        """Reverse the selection order."""
        nodes = cmds.ls(sl=True, fl=True)
        if not nodes:
            cmds.error("No object selected.")

        if len(nodes) == 1:
            cmds.error("Only one object selected.")

        # Reverse the selection order
        cmds.select(nodes[::-1], r=True)


__all__ = ["ExtraSelectionWidget"]
