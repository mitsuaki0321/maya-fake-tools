"""Extra selection widget for selecter tool."""

from pathlib import Path

import maya.cmds as cmds

from .....lib_ui import maya_decorator
from .....lib_ui.qt_compat import QHBoxLayout, QMenu, QSize, QToolButton, QWidget
from .....lib_ui.ui_utils import get_line_height
from .....lib_ui.widgets.icon_button import IconButtonStyle, IconToolButton

_IMAGES_DIR = str(Path(__file__).resolve().parent.parent / "images")


class ExtraSelectionWidget(QWidget):
    """Extra Selection Widget.

    Provides additional selection utilities via a single menu button:
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
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Single icon button with popup menu for extra selection commands
        extra_button = IconToolButton(icon_name="ellipsis", style_mode=IconButtonStyle.PALETTE, auto_size=False, icon_dir=_IMAGES_DIR)
        extra_button.setToolTip("Extra Selection: LF / FL / REV")
        button_size = int(get_line_height(extra_button) * 2.0)
        extra_button.setFixedSize(button_size, button_size)
        extra_button.setIconSize(QSize(button_size, button_size))
        extra_button.setStyleSheet(extra_button.styleSheet() + "QToolButton::menu-indicator { image: none; }")
        main_layout.addWidget(extra_button)

        self.setLayout(main_layout)

        # Build popup menu
        menu = QMenu(self)
        menu.addAction("LF - Last to First", self.last_to_first_selection)
        menu.addAction("FL - First to Last", self.first_to_last_selection)
        menu.addAction("REV - Reverse", self.reverse_selection)

        extra_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        extra_button.setMenu(menu)

    @maya_decorator.error_handler
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

    @maya_decorator.error_handler
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

    @maya_decorator.error_handler
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
