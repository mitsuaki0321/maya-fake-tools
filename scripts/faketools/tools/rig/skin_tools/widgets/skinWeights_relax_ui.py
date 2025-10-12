"""
Skin Weights Relax tool using Laplacian smoothing.
"""

from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_skinCluster
from .....lib_ui import base_window, maya_decorator, optionvar
from .....lib_ui.qt_compat import (
    QCheckBox,
    QDoubleValidator,
    QGridLayout,
    QIntValidator,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    Qt,
    QVBoxLayout,
    QWidget,
)
from .....lib_ui.widgets import extra_widgets
from ..relax_weight import LaplacianSkinWeights

logger = getLogger(__name__)


class SkinWeightsRelaxWidgets(QWidget):
    """Skin Weights Relax Widgets using Laplacian smoothing."""

    def __init__(self, parent=None, window_mode: bool = False):
        """Constructor."""
        super().__init__(parent=parent)

        self.settings = optionvar.ToolOptionSettings(__name__)

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

        self.iterations_field = QLineEdit("1")
        self.iterations_field.setValidator(QIntValidator(0, 50))
        self.iterations_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.iterations_field.setFixedWidth(self.iterations_field.sizeHint().width() / 2.0)
        layout.addWidget(self.iterations_field, 0, 1)

        self.iterations_slider = QSlider(Qt.Horizontal)
        self.iterations_slider.setRange(0, 50)
        self.iterations_slider.setValue(1)
        layout.addWidget(self.iterations_slider, 0, 2)

        # After Blend
        label = QLabel("After Blend:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 1, 0)

        self.after_blend_field = QLineEdit("1.0")
        self.after_blend_field.setValidator(QDoubleValidator(0.0, 1.0, 2))
        self.after_blend_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.after_blend_field.setFixedWidth(self.after_blend_field.sizeHint().width() / 2.0)
        layout.addWidget(self.after_blend_field, 1, 1)

        self.after_blend_slider = QSlider(Qt.Horizontal)
        self.after_blend_slider.setRange(0, 100)
        self.after_blend_slider.setValue(100)
        layout.addWidget(self.after_blend_slider, 1, 2)

        layout.setColumnStretch(2, 1)

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

        # Restore settings
        self.iterations_field.setText(str(self.settings.read("iterations", 1)))
        self.iterations_slider.setValue(int(self.iterations_field.text()))
        self.after_blend_field.setText(str(self.settings.read("after_blend", 1.0)))
        self.after_blend_slider.setValue(int(float(self.after_blend_field.text()) * 100))
        self.only_unlock_inf_checkBox.setChecked(self.settings.read("only_unlock_inf", False))

        # Signal & Slot
        self.iterations_field.textChanged.connect(self._update_field_slider_value)
        self.iterations_slider.valueChanged.connect(self._update_field_slider_value)
        self.after_blend_field.textChanged.connect(self._update_field_slider_value)
        self.after_blend_slider.valueChanged.connect(self._update_field_slider_value)

        execute_button.clicked.connect(self.relax_weights)

    def _update_field_slider_value(self):
        """Update the field and slider value."""
        sender = self.sender()

        if sender == self.iterations_field:
            try:
                value = int(self.iterations_field.text())
                self.iterations_slider.setValue(value)
            except ValueError:
                pass
        elif sender == self.iterations_slider:
            value = self.iterations_slider.value()
            self.iterations_field.setText(str(value))

        if sender == self.after_blend_field:
            try:
                value = float(self.after_blend_field.text())
                self.after_blend_slider.setValue(int(value * 100))
            except ValueError:
                pass
        elif sender == self.after_blend_slider:
            value = self.after_blend_slider.value() / 100
            self.after_blend_field.setText(str(value))

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

        iterations = int(self.iterations_field.text())
        after_blend = float(self.after_blend_field.text())
        only_unlock_inf = self.only_unlock_inf_checkBox.isChecked()

        logger.debug(f"Relax options: iterations={iterations}, blend={after_blend}, only_unlock={only_unlock_inf}")

        LaplacianSkinWeights(skinCluster, vertices).smooth(iterations=iterations, blend_weights=after_blend, only_unlock_influences=only_unlock_inf)

        logger.info(f"Relaxed skin weights: {len(vertices)} vertices")

    def save_settings(self):
        """Save the option settings."""
        self.settings.write("iterations", int(self.iterations_field.text()))
        self.settings.write("after_blend", float(self.after_blend_field.text()))
        self.settings.write("only_unlock_inf", self.only_unlock_inf_checkBox.isChecked())
