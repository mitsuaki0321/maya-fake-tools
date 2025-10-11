"""Re target mesh tool."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import maya_decorator, optionvar
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QCheckBox, QLineEdit, QPushButton, QStringListModel, QVBoxLayout, QWidget
from ....lib_ui.widgets import extra_widgets, nodeAttr_widgets
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Re target Mesh Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="RetargetMeshMainWindow",
            window_title="Retarget Mesh",
            central_layout="vertical",
        )

        self.settings = optionvar.ToolOptionSettings(__name__)

        self.src_node_widgets = SetNodeWidgets("Set Source Mesh")
        self.central_layout.addWidget(self.src_node_widgets)

        self.dst_node_widgets = SetNodesWidgets("Set Destination Mesh")
        self.central_layout.addWidget(self.dst_node_widgets)

        self.trg_node_widgets = SetNodesWidgets("Set Target Mesh")
        self.central_layout.addWidget(self.trg_node_widgets)

        self.is_create_checkbox = QCheckBox("Create New Mesh")
        self.central_layout.addWidget(self.is_create_checkbox)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        button = QPushButton("Retarget Mesh")
        self.central_layout.addWidget(button)

        # Initialize UI state
        self._restore_settings()

        # Signal & Slot
        button.clicked.connect(self._retarget_mesh)

    @maya_decorator.undo_chunk("Retarget Mesh")
    @maya_decorator.error_handler
    def _retarget_mesh(self):
        """Retarget the mesh."""
        src_mesh = self.src_node_widgets.get_node()
        dst_meshes = self.dst_node_widgets.get_nodes()
        trg_meshes = self.trg_node_widgets.get_nodes()
        is_create = self.is_create_checkbox.isChecked()

        command.retarget_mesh(src_mesh, dst_meshes, trg_meshes, is_create=is_create)

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Restore window geometry
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])
        else:
            # Default size if no saved geometry
            size_hint = self.sizeHint()
            self.resize(size_hint.width() * 0.8, size_hint.height() * 0.4)

        # Restore checkbox state
        self.is_create_checkbox.setChecked(self.settings.read("is_create", True))

    def _save_settings(self):
        """Save UI settings to preferences."""
        # Save window geometry
        self.settings.set_window_geometry(
            size=[self.width(), self.height()],
            position=[self.x(), self.y()],
        )

        # Save checkbox state
        self.settings.write("is_create", self.is_create_checkbox.isChecked())

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


class SetNodeWidgets(QWidget):
    """Set Node Widgets."""

    def __init__(self, label: str, parent=None):
        """Constructor."""
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        button = QPushButton(label)
        layout.addWidget(button)

        self.node_field = QLineEdit()
        self.node_field.setReadOnly(True)
        layout.addWidget(self.node_field)

        self.setLayout(layout)

        button.clicked.connect(self._set_node)

    def _set_node(self):
        """Set the node."""
        sel_nodes = cmds.ls(sl=True, dag=True, type="mesh")
        if not sel_nodes:
            cmds.warning("Please select a transform node.")
            return

        self.node_field.setText(sel_nodes[0])

    def get_node(self):
        """Get the node."""
        return self.node_field.text()


class SetNodesWidgets(QWidget):
    """Set Nodes Widgets."""

    def __init__(self, label: str, parent=None):
        """Constructor."""
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        button = QPushButton(label)
        layout.addWidget(button)

        self.node_list_view = nodeAttr_widgets.NodeListView()
        self.model = QStringListModel()
        self.node_list_view.setModel(self.model)
        layout.addWidget(self.node_list_view)

        self.setLayout(layout)

        button.clicked.connect(self._set_nodes)

    def _set_nodes(self):
        """Set the nodes."""
        sel_nodes = cmds.ls(sl=True, dag=True, type="mesh")
        if not sel_nodes:
            cmds.warning("Please select transform nodes.")
            return

        self.model.setStringList(sel_nodes)

    def get_nodes(self):
        """Get the nodes."""
        return self.model.stringList()


def show_ui():
    """
    Show the Re target Mesh UI.

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
