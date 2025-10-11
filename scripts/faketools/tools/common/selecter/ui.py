"""Selecter tool UI layer."""

import logging

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.cmds as cmds

from ....lib_ui import ToolOptionSettings, get_maya_main_window
from ....lib_ui.qt_compat import QHBoxLayout, QSizePolicy, QSpacerItem, Qt, QWidget
from ....lib_ui.widgets import extra_widgets
from .widgets import (
    ExtraSelectionWidget,
    FilterSelectionWidget,
    HierarchicalSelectionWidget,
    RenameSelectionWidget,
    SubstitutionSelectionWidget,
)

logger = logging.getLogger(__name__)


class DockableWidget(MayaQWidgetDockableMixin, QWidget):
    """Selecter Dockable Widget."""

    def __init__(self, parent=None, object_name="SelecterWidget", window_title="Selecter"):
        """Initialize the dockable widget.

        Args:
            parent: Parent widget.
            object_name: Object name for the widget.
            window_title: Window title.
        """
        super().__init__(parent=parent)

        self.setObjectName(object_name)
        self.setWindowTitle(window_title)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.settings = ToolOptionSettings(__name__)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 1, 1, 1)

        # Filter selection widget
        filter_selection_widget = FilterSelectionWidget(self.settings)
        main_layout.addWidget(filter_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Hierarchical selection widget
        hierarchical_selection_widget = HierarchicalSelectionWidget()
        main_layout.addWidget(hierarchical_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Substitution selection widget
        substitution_selection_widget = SubstitutionSelectionWidget(self.settings)
        main_layout.addWidget(substitution_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Rename selection widget
        rename_selection_widget = RenameSelectionWidget(self.settings)
        main_layout.addWidget(rename_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Extra selection widget
        extra_selection_widget = ExtraSelectionWidget()
        main_layout.addWidget(extra_selection_widget)

        # Spacer to push widgets to the left
        spacer = QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

        self.setLayout(main_layout)


# For backward compatibility
MainWindow = DockableWidget


def show_ui():
    """Show the tool UI docked below the shelf.

    Returns:
        DockableWidget: The main window instance.
    """
    # Delete the workspace control if it exists
    workspace_control_name = f"{__name__}MainWindowWorkspaceControl"

    if cmds.workspaceControl(workspace_control_name, exists=True):
        cmds.workspaceControl(workspace_control_name, e=True, close=True)
        cmds.deleteUI(workspace_control_name)

    # Create the main window
    window_name = f"{__name__}MainWindow"
    main_window = DockableWidget(parent=get_maya_main_window(), object_name=window_name, window_title="Selecter")

    main_window.show(dockable=True)

    # Dock below the shelf
    cmds.workspaceControl(workspace_control_name, e=True, dockToControl=("Shelf", "bottom"), tabToControl=("Shelf", -1))
    cmds.workspaceControl(workspace_control_name, e=True, actLikeMayaUIElement=True)

    return main_window


__all__ = ["MainWindow", "DockableWidget", "show_ui"]
