"""Selecter tool UI layer."""

import logging

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.cmds as cmds

from ....lib_ui import get_maya_main_window
from ....lib_ui.qt_compat import QHBoxLayout, QSizePolicy, QSpacerItem, Qt, QWidget
from ....lib_ui.tool_settings import ToolSettingsManager
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

        self.settings = ToolSettingsManager(tool_name="selecter", category="common")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 1, 1, 1)

        # Filter selection widget
        self.filter_selection_widget = FilterSelectionWidget(self.settings)
        main_layout.addWidget(self.filter_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Hierarchical selection widget
        self.hierarchical_selection_widget = HierarchicalSelectionWidget()
        main_layout.addWidget(self.hierarchical_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Substitution selection widget
        self.substitution_selection_widget = SubstitutionSelectionWidget(self.settings)
        main_layout.addWidget(self.substitution_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Rename selection widget
        self.rename_selection_widget = RenameSelectionWidget(self.settings)
        main_layout.addWidget(self.rename_selection_widget)

        # Separator
        separator = extra_widgets.VerticalSeparator()
        main_layout.addWidget(separator)

        # Extra selection widget
        self.extra_selection_widget = ExtraSelectionWidget()
        main_layout.addWidget(self.extra_selection_widget)

        # Spacer to push widgets to the left
        spacer = QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

        self.setLayout(main_layout)

        # Restore settings
        self._restore_settings()

    def _collect_settings(self) -> dict:
        """Collect current UI settings from all widgets.

        Returns:
            dict: Settings data
        """
        settings_data = {}

        # Collect settings from widgets that have the method
        if hasattr(self.filter_selection_widget, "_collect_settings"):
            settings_data["filter_selection"] = self.filter_selection_widget._collect_settings()

        if hasattr(self.substitution_selection_widget, "_collect_settings"):
            settings_data["substitution_selection"] = self.substitution_selection_widget._collect_settings()

        if hasattr(self.rename_selection_widget, "_collect_settings"):
            settings_data["rename_selection"] = self.rename_selection_widget._collect_settings()

        return settings_data

    def _apply_settings(self, settings_data: dict):
        """Apply settings to all widgets.

        Args:
            settings_data (dict): Settings data to apply
        """
        # Apply settings to widgets that have the method
        if "filter_selection" in settings_data and hasattr(self.filter_selection_widget, "_apply_settings"):
            self.filter_selection_widget._apply_settings(settings_data["filter_selection"])

        if "substitution_selection" in settings_data and hasattr(self.substitution_selection_widget, "_apply_settings"):
            self.substitution_selection_widget._apply_settings(settings_data["substitution_selection"])

        if "rename_selection" in settings_data and hasattr(self.rename_selection_widget, "_apply_settings"):
            self.rename_selection_widget._apply_settings(settings_data["rename_selection"])

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def closeEvent(self, event):
        """Handle widget close event."""
        self._save_settings()
        super().closeEvent(event)


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
