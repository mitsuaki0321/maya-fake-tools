"""
Skin Weights Relax tool using Laplacian smoothing.
"""

from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_skinCluster
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QCheckBox, QGridLayout, QLabel, QPushButton, Qt, QVBoxLayout, QWidget
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.widgets import FieldSliderWidget, extra_widgets
from ..relax_weight import LaplacianSkinWeights

logger = getLogger(__name__)


class SkinWeightsRelaxWidgets(QWidget):
    """Skin Weights Relax Widgets using Laplacian smoothing."""

    def __init__(self, settings: ToolSettingsManager, parent=None, window_mode: bool = False):
        """Constructor.

        Args:
            settings (ToolSettingsManager): Settings manager instance
            parent (QWidget, optional): Parent widget. Defaults to None.
            window_mode (bool, optional): Window mode flag. Defaults to False.
        """
        super().__init__(parent=parent)

        self.settings = settings

        self.main_layout = QVBoxLayout()
        spacing = base_window.get_spacing(self)
        self.main_layout.setSpacing(spacing * 0.75)

        if not window_mode:
            margins = base_window.get_margins(self)
            self.main_layout.setContentsMargins(*[margin * 0.5 for margin in margins])

        # Options Grid
        layout = QGridLayout()

        # Iterations
        label = QLabel("Iterations:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 0, 0)

        self.iterations_widget = FieldSliderWidget(min_value=0, max_value=50, default_value=1, value_type="int")
        layout.addWidget(self.iterations_widget, 0, 1)

        # After Blend
        label = QLabel("After Blend:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 1, 0)

        self.after_blend_widget = FieldSliderWidget(min_value=0.0, max_value=1.0, default_value=1.0, decimals=2, value_type="float")
        layout.addWidget(self.after_blend_widget, 1, 1)

        layout.setColumnStretch(1, 1)

        self.main_layout.addLayout(layout)

        # Use Only Unlocked Influences checkbox
        self.only_unlock_inf_checkBox = QCheckBox("Use Only Unlocked Influences")
        self.main_layout.addWidget(self.only_unlock_inf_checkBox)

        separator = extra_widgets.HorizontalSeparator()
        self.main_layout.addWidget(separator)

        # Execute button
        execute_button = QPushButton("Relax Skin Weights")
        self.main_layout.addWidget(execute_button)

        self.main_layout.addStretch()

        self.setLayout(self.main_layout)

        # Signal & Slot
        execute_button.clicked.connect(self.relax_weights)

    @maya_decorator.undo_chunk("Relax Skin Weights")
    @maya_decorator.error_handler
    def relax_weights(self):
        """Relax the skin weights using Laplacian smoothing."""
        vertices = cmds.filterExpand(sm=31, ex=True)
        if not vertices:
            cmds.error("Select vertices.")

        shapes = list(set(cmds.ls(vertices, objectsOnly=True)))
        if len(shapes) > 1:
            cmds.error("Vertices must belong to the same object.")

        skinCluster = lib_skinCluster.get_skinCluster(shapes[0])
        if not skinCluster:
            cmds.error(f"Object is not bound to a skinCluster: {shapes[0]}")

        iterations = int(self.iterations_widget.value())
        after_blend = float(self.after_blend_widget.value())
        only_unlock_inf = self.only_unlock_inf_checkBox.isChecked()

        logger.debug(f"Relax options: iterations={iterations}, blend={after_blend}, only_unlock={only_unlock_inf}")

        LaplacianSkinWeights(skinCluster, vertices).smooth(iterations=iterations, blend_weights=after_blend, only_unlock_influences=only_unlock_inf)

        logger.info(f"Relaxed skin weights: {len(vertices)} vertices")

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "iterations": int(self.iterations_widget.value()),
            "after_blend": float(self.after_blend_widget.value()),
            "only_unlock_inf": self.only_unlock_inf_checkBox.isChecked(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "iterations" in settings_data:
            iterations = settings_data["iterations"]
            # Handle empty or invalid values with default of 1
            if iterations == "" or iterations is None:
                iterations = 1
            try:
                self.iterations_widget.setValue(int(iterations))
            except (ValueError, TypeError):
                self.iterations_widget.setValue(1)

        if "after_blend" in settings_data:
            after_blend = settings_data["after_blend"]
            # Handle empty or invalid values with default of 1.0
            if after_blend == "" or after_blend is None:
                after_blend = 1.0
            try:
                self.after_blend_widget.setValue(float(after_blend))
            except (ValueError, TypeError):
                self.after_blend_widget.setValue(1.0)

        if "only_unlock_inf" in settings_data:
            self.only_unlock_inf_checkBox.setChecked(settings_data["only_unlock_inf"])
