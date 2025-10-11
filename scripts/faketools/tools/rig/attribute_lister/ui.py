"""
UI module for Attribute Lister.
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import maya_decorator, optionvar
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QLineEdit
from ....lib_ui.widgets import nodeAttr_widgets

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Attribute Lister Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="AttributeListerMainWindow",
            window_title="Attribute Lister",
            central_layout="vertical",
        )

        self.tool_options = optionvar.ToolOptionSettings(__name__)

        self.view = nodeAttr_widgets.NodeAttributeWidgets()
        self.central_layout.addWidget(self.view)

        self.value_field = QLineEdit()
        self.view.main_layout.addWidget(self.value_field)

        # Signal & Slot
        self.view.attr_list.selectionModel().selectionChanged.connect(self._display_value)
        self.value_field.returnPressed.connect(self._set_value)
        self.view.attr_list.attribute_lock_changed.connect(self._display_value)

        # Restore settings
        self._restore_settings()

    def _display_value(self) -> None:
        """Display the value of the selected attribute."""
        nodes = self.view.get_selected_nodes()
        attrs = self.view.get_selected_attributes()

        if not nodes or not attrs:
            self.value_field.setText("")
            self.value_field.setEnabled(False)
            return

        value = cmds.getAttr(f"{nodes[-1]}.{attrs[-1]}")
        self.value_field.setText(str(value))

        attr_types = set()
        for node in nodes:
            for attr in attrs:
                if cmds.getAttr(f"{node}.{attr}", lock=True):
                    self.value_field.setEnabled(False)
                    self.value_field.setStyleSheet("background-color: darkgrey;")

                    logger.debug(f"Attribute is locked: {node}.{attr}")
                    return

                if cmds.connectionInfo(f"{node}.{attr}", isDestination=True):
                    self.value_field.setEnabled(False)
                    self.value_field.setStyleSheet("background-color: lightyellow;")

                    logger.debug(f"Attribute is connected: {node}.{attr}")
                    return

                attr_type = cmds.getAttr(f"{node}.{attr}", type=True)
                attr_types.add(attr_type)

        if len(attr_types) > 1:
            self.value_field.setEnabled(False)
            self.value_field.setStyleSheet("background-color: pink;")
        else:
            self.value_field.setEnabled(True)
            self.value_field.setStyleSheet("")

    @maya_decorator.undo_chunk("Set Attribute Value")
    @maya_decorator.error_handler
    def _set_value(self) -> None:
        """Set the value of the selected attribute."""
        nodes = self.view.get_selected_nodes()
        attrs = self.view.get_selected_attributes()

        if not nodes or not attrs:
            return

        if not self.value_field.text():
            cmds.error("No value is entered.")

        if not self.value_field.isEnabled():
            cmds.error("Cannot change the value because the attribute type is different, it is connected, or it is locked.")

        try:
            value = self.value_field.text()
            attr_type = cmds.getAttr(f"{nodes[-1]}.{attrs[-1]}", type=True)
            if attr_type == "bool":
                value = bool(int(value))
            elif attr_type in ["long", "short", "byte", "char", "enum", "time"]:
                value = int(value)
            elif attr_type == "string":
                value = str(value)
            elif attr_type in ["float", "double", "doubleLinear", "doubleAngle"]:
                value = float(value)
            elif attr_type == "matrix":
                value = eval(value)
            else:
                raise ValueError(f"Unsupported attribute type: {attr_type}")

            for node in nodes:
                for attr in attrs:
                    if attr_type == "matrix":
                        cmds.setAttr(f"{node}.{attr}", *value, type=attr_type)
                    elif attr_type == "string":
                        cmds.setAttr(f"{node}.{attr}", value, type=attr_type)
                    else:
                        cmds.setAttr(f"{node}.{attr}", value)

        except (ValueError, SyntaxError, TypeError) as e:
            cmds.error(f"Invalid input value: {value}. \n{str(e)}")

    def _restore_settings(self) -> None:
        """Restore UI settings from saved preferences."""
        geometry = self.tool_options.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

    def _save_settings(self) -> None:
        """Save UI settings to preferences."""
        self.tool_options.set_window_geometry(
            size=[self.width(), self.height()],
            position=[self.x(), self.y()],
        )

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """
    Show the Attribute lister UI.

    Creates or raises the main window.

    Returns:
        MainWindow: The main window instance
    """
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
