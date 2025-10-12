"""
SkinWeights Tools. All skinWeights tools are integrated into one tool.
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_skinCluster
from ....lib_ui import ToolOptionSettings, error_handler, repeatable, undo_chunk
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QComboBox, QGroupBox, QStackedWidget, QVBoxLayout
from ....lib_ui.widgets import extra_widgets
from .command import average_skin_weights, average_skin_weights_shell, get_influences_from_objects, prune_small_weights
from .widgets import (
    influence_exchanger_ui,
    skinWeights_adjust_center_ui,
    skinWeights_bar_ui,
    skinWeights_combine_ui,
    skinWeights_copy_custom_ui,
    skinWeights_relax_ui,
    skinWeights_to_mesh_ui,
)

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Skin Weights Tools Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent, object_name="SkinToolsMainWindow", window_title="Skin Tools", central_layout="vertical")

        self.settings = ToolOptionSettings(__name__)
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""

        # Menu
        self.menu = self.menuBar()
        self._add_menu()

        # Add skinWeights bar
        self.skinWeightsBar = skinWeights_bar_ui.SkinWeightsBar()
        self.central_layout.addWidget(self.skinWeightsBar)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # Add skinWeights widgets combo box
        self.widgets_box = QComboBox()
        self.widgets_box.addItems(self.widgets_data().keys())
        self.central_layout.addWidget(self.widgets_box)

        # Add widgets group
        widgets_group = QGroupBox()
        widgets_group_layout = QVBoxLayout()
        widgets_group_layout.setSpacing(0)
        widgets_group_layout.setContentsMargins(0, 0, 0, 0)

        self.widgets_stack_widget = QStackedWidget()

        for widget in self.widgets_data().values():
            self.widgets_stack_widget.addWidget(widget())

        widgets_group_layout.addWidget(self.widgets_stack_widget)
        widgets_group.setLayout(widgets_group_layout)

        self.central_layout.addWidget(widgets_group)

        # Signal & Slot
        self.widgets_box.currentIndexChanged.connect(self.widgets_stack_widget.setCurrentIndex)

    def widgets_data(self):
        """List of widgets data."""
        return {
            "Copy Skin Weights Custom": skinWeights_copy_custom_ui.SkinWeightsCopyCustomWidgets,
            "Skin Weights to Mesh": skinWeights_to_mesh_ui.SkinWeightsMeshConverterWidgets,
            "Adjust Center Skin Weights": skinWeights_adjust_center_ui.AdjustCenterSkinWeightsWidgets,
            "Combine Skin Weights": skinWeights_combine_ui.CombineSkinWeightsWidgets,
            "Relax Skin Weights": skinWeights_relax_ui.SkinWeightsRelaxWidgets,
            "Influence Exchange": influence_exchanger_ui.InfluenceExchangerWidgets,
        }

    def _add_menu(self):
        """Add menu."""
        edit_menu = self.menu.addMenu("Edit")

        action = edit_menu.addAction("Select Influences")
        action.triggered.connect(self.select_influences)

        action = edit_menu.addAction("Rebind SkinCluster")
        action.triggered.connect(self.rebind_skinCluster)

        edit_menu.addSeparator()

        action = edit_menu.addAction("Prune Small Weights")
        action.triggered.connect(self.prune_small_weights)

        action = edit_menu.addAction("Remove Unused Influences")
        action.triggered.connect(self.remove_unused_influences)

        edit_menu.addSeparator()

        action = edit_menu.addAction("Average Skin Weights")
        action.triggered.connect(self.average_skin_weights)

        action = edit_menu.addAction("Average Skin Weights Shell")
        action.triggered.connect(self.average_skin_weights_shell)

    @error_handler
    @undo_chunk("Select Influences")
    @repeatable("Select Influences")
    def select_influences(self):
        """Select the influences."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("Select geometry or components.")

        influences = get_influences_from_objects(sel_nodes)
        if not influences:
            cmds.warning("No influences found.")
            return

        cmds.select(influences, r=True)

    @error_handler
    @undo_chunk("Rebind SkinCluster")
    @repeatable("Rebind SkinCluster")
    def rebind_skinCluster(self):
        """Rebind the skinCluster."""
        target_skinClusters = self._get_skinClusters()
        influences = cmds.ls(sl=True, type="joint")

        if target_skinClusters:
            for skinCluster in target_skinClusters:
                lib_skinCluster.rebind_skinCluster(skinCluster)

        if influences:
            lib_skinCluster.rebind_skinCluster_from_influence(influences)

    @error_handler
    @undo_chunk("Prune Small Weights")
    @repeatable("Prune Small Weights")
    def prune_small_weights(self):
        """Prune small weights."""
        sel_dag_nodes = cmds.ls(sl=True, dag=True, shapes=True, ni=True)
        if not sel_dag_nodes:
            cmds.error("Select geometry to prune small weights.")

        prune_small_weights(sel_dag_nodes, threshold=0.005)

    @error_handler
    @undo_chunk("Remove Unused Influences")
    @repeatable("Remove Unused Influences")
    def remove_unused_influences(self):
        """Remove unused influences."""
        shapes = cmds.ls(sl=True, dag=True, shapes=True, ni=True)
        if not shapes:
            cmds.error("Select geometry to remove unused influences.")

        for shape in shapes:
            skinCluster = lib_skinCluster.get_skinCluster(shape)
            if not skinCluster:
                cmds.warning(f"No skinCluster found: {shape}")
                continue

            lib_skinCluster.remove_unused_influences(skinCluster)

    @error_handler
    @undo_chunk("Average Skin Weights")
    @repeatable("Average Skin Weights")
    def average_skin_weights(self):
        """Average skin weights."""
        sel_components = cmds.filterExpand(sm=[28, 31, 46])
        if not sel_components:
            cmds.error("Select components to average skin weights.")

        average_skin_weights(sel_components)

    @error_handler
    @undo_chunk("Average Skin Weights Shell")
    @repeatable("Average Skin Weights Shell")
    def average_skin_weights_shell(self):
        """Average skin weights shell."""
        meshs = cmds.ls(sl=True, dag=True, type="mesh", ni=True)
        if not meshs:
            cmds.error("Select mesh to average skin weights shell.")

        for mesh in meshs:
            average_skin_weights_shell(mesh)

    def _get_skinClusters(self):
        """Get the skinClusters."""
        shapes = cmds.ls(sl=True, dag=True, type="deformableShape", objectsOnly=True, ni=True)
        skinClusters = cmds.ls(sl=True, type="skinCluster")

        target_skinClusters = []
        if shapes:
            for shape in shapes:
                skinCluster = lib_skinCluster.get_skinCluster(shape)
                if skinCluster and skinCluster not in target_skinClusters:
                    target_skinClusters.append(skinCluster)
        if skinClusters:
            for skinCluster in skinClusters:
                if skinCluster not in target_skinClusters:
                    target_skinClusters.append(skinCluster)

        return target_skinClusters

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

        # Restore last selected widget index
        last_widget_index = self.settings.read("last_widget_index", 0)
        if 0 <= last_widget_index < self.widgets_box.count():
            self.widgets_box.setCurrentIndex(last_widget_index)

    def _save_settings(self):
        """Save UI settings to preferences."""
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

        # Save last selected widget index
        self.settings.write("last_widget_index", self.widgets_box.currentIndex())

        # Save settings for SkinWeightsBar
        if hasattr(self.skinWeightsBar, "save_settings"):
            self.skinWeightsBar.save_settings()

        # Save settings for all widgets
        for i in range(self.widgets_stack_widget.count()):
            widget = self.widgets_stack_widget.widget(i)
            if hasattr(widget, "save_settings"):
                widget.save_settings()

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """
    Show the skin weights tools UI.

    Creates or raises the main window.

    Returns:
        MainWindow: The main window instance.
    """
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent=parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
