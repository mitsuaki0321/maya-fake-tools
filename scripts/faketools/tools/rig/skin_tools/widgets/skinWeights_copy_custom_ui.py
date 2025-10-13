"""
Copy weights tool using custom plug-in.
"""

from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_skinCluster
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.qt_compat import (
    QCheckBox,
    QDoubleValidator,
    QHBoxLayout,
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

logger = getLogger(__name__)


class SkinWeightsCopyCustomWidgets(QWidget):
    """Skin Weights Copy Custom Widgets."""

    def __init__(self, settings: ToolSettingsManager, parent=None, window_mode: bool = False):
        """Constructor.

        Args:
            settings: ToolSettingsManager instance
            parent: Parent widget
            window_mode: Whether to use window mode layout
        """
        super().__init__(parent=parent)

        self.settings = settings

        self.preview_mesh = None
        self.preview_mesh_node = None

        self.main_layout = QVBoxLayout()
        spacing = base_window.get_spacing(self)
        self.main_layout.setSpacing(spacing * 0.75)

        if not window_mode:
            margins = base_window.get_margins(self)
            self.main_layout.setContentsMargins(*[margin * 0.5 for margin in margins])

        layout = QHBoxLayout()

        label = QLabel("Blend:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label)

        self.blend_field = QLineEdit()
        self.blend_field.setValidator(QDoubleValidator(0.0, 1.0, 2))
        self.blend_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.blend_field.setFixedWidth(self.blend_field.sizeHint().width() / 2.0)
        layout.addWidget(self.blend_field)

        self.blend_slider = QSlider(Qt.Horizontal)
        self.blend_slider.setRange(0, 100)
        layout.addWidget(self.blend_slider)

        self.main_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.main_layout.addWidget(separator)

        self.only_unlock_inf_checkBox = QCheckBox("Use Only Unlocked Influences")
        self.main_layout.addWidget(self.only_unlock_inf_checkBox)

        self.reference_orig_checkBox = QCheckBox("Reference Original Shape")
        self.main_layout.addWidget(self.reference_orig_checkBox)

        self.add_missing_infs_checkBox = QCheckBox("Add Missing Influences")
        self.main_layout.addWidget(self.add_missing_infs_checkBox)

        separator = extra_widgets.HorizontalSeparator()
        self.main_layout.addWidget(separator)

        execute_button = QPushButton("Copy Skin Weights")
        self.main_layout.addWidget(execute_button)

        self.main_layout.addStretch()

        self.setLayout(self.main_layout)

        # Signal & Slot
        self.blend_field.textChanged.connect(self._blend_value_change)
        self.blend_slider.valueChanged.connect(self._blend_value_change)
        execute_button.clicked.connect(self.copy_skin_weights)

    def _blend_value_change(self):
        """Change the blend value."""
        sender = self.sender()

        if sender == self.blend_field:
            value = float(sender.text())
            self.blend_slider.setValue(value * 100)
        elif sender == self.blend_slider:
            value = sender.value() / 100
            self.blend_field.setText(str(value))

    @maya_decorator.undo_chunk("Copy Skin Weights Custom")
    @maya_decorator.error_handler
    def copy_skin_weights(self):
        """Copy the skin weights."""
        shapes = cmds.ls(sl=True, dag=True, type="deformableShape", ni=True, objectsOnly=True)
        if not shapes or len(shapes) < 2:
            cmds.error("Select 2 or more deformable shapes")

        src_shape = shapes[0]
        dst_shapes = shapes[1:]

        src_skinCluster = lib_skinCluster.get_skinCluster(src_shape)
        if not src_skinCluster:
            cmds.error(f"No skinCluster found: {src_shape}")

        blend_value = float(self.blend_field.text())

        only_unlock_inf = self.only_unlock_inf_checkBox.isChecked()
        reference_orig = self.reference_orig_checkBox.isChecked()
        add_missing_infs = self.add_missing_infs_checkBox.isChecked()

        for dst_shape in dst_shapes:
            dst_skinCluster = lib_skinCluster.get_skinCluster(dst_shape)
            if not dst_skinCluster:
                cmds.warning(f"No skinCluster found: {dst_shape}")
                continue

            lib_skinCluster.copy_skin_weights_custom(
                src_skinCluster,
                dst_skinCluster,
                only_unlock_influences=only_unlock_inf,
                blend_weights=blend_value,
                reference_orig=reference_orig,
                add_missing_influences=add_missing_infs,
            )

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "blend_value": self.blend_field.text(),
            "only_unlock_inf": self.only_unlock_inf_checkBox.isChecked(),
            "reference_orig": self.reference_orig_checkBox.isChecked(),
            "add_missing_infs": self.add_missing_infs_checkBox.isChecked(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "blend_value" in settings_data:
            self.blend_field.setText(str(settings_data["blend_value"]))
            self.blend_slider.setValue(float(settings_data["blend_value"]) * 100)
        if "only_unlock_inf" in settings_data:
            self.only_unlock_inf_checkBox.setChecked(settings_data["only_unlock_inf"])
        if "reference_orig" in settings_data:
            self.reference_orig_checkBox.setChecked(settings_data["reference_orig"])
        if "add_missing_infs" in settings_data:
            self.add_missing_infs_checkBox.setChecked(settings_data["add_missing_infs"])
