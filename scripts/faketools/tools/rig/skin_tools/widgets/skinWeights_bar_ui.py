"""
SkinCluster weights utility tool.
"""

from logging import getLogger

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator, optionvar
from .....lib_ui.qt_compat import QHBoxLayout, QPushButton, QSizePolicy, QWidget
from .....lib_ui.widgets import extra_widgets
from .....operations.copy_weights import copy_skin_weights_with_bind, mirror_skin_weights, mirror_skin_weights_with_objects

LEFT_TO_RIGHT = ["(.*)(L)", r"\g<1>R"]
RIGHT_TO_LEFT = ["(.*)(R)", r"\g<1>L"]

logger = getLogger(__name__)


class SkinWeightsBar(QWidget):
    """Skin Weights Bar."""

    def __init__(self, parent=None, window_mode: bool = False):
        """Constructor."""
        super().__init__(parent=parent)

        self.settings = optionvar.ToolOptionSettings(__name__)

        self.main_layout = QHBoxLayout()
        spacing = base_window.get_spacing(self, direction="horizontal")
        self.main_layout.setSpacing(spacing * 0.75)

        if not window_mode:
            self.main_layout.setContentsMargins(0, 0, 0, 0)

        copy_button = QPushButton("COPY")
        self.main_layout.addWidget(copy_button, stretch=1)

        v_line = extra_widgets.VerticalSeparator()
        v_line.setFixedWidth(v_line.sizeHint().width() * 5)
        self.main_layout.addWidget(v_line)

        mir_self_button = QPushButton("MIR SELF")
        self.main_layout.addWidget(mir_self_button, stretch=1)

        mir_sub_button = QPushButton("MIR SUB")
        self.main_layout.addWidget(mir_sub_button, stretch=1)

        self.mir_dir_checkBox = extra_widgets.CheckBoxButton(icon_on="arrow-right", icon_off="arrow-left")
        self.mir_dir_checkBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.main_layout.addWidget(self.mir_dir_checkBox)

        v_line = extra_widgets.VerticalSeparator()
        v_line.setFixedWidth(v_line.sizeHint().width() * 5)
        self.main_layout.addWidget(v_line)

        self.uv_button = extra_widgets.CheckBoxButton(icon_on="uv-checked", icon_off="uv")
        self.uv_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.main_layout.addWidget(self.uv_button)

        self.setLayout(self.main_layout)

        # Option settings
        self.mir_dir_checkBox.setChecked(self.settings.read("mirror", False))
        self.uv_button.setChecked(self.settings.read("uv", False))

        # Signal & Slot
        copy_button.clicked.connect(self.copy_skin_weights)
        mir_self_button.clicked.connect(self.mirror_skin_weights)
        mir_sub_button.clicked.connect(self.mirror_skin_weights_sub)

    @maya_decorator.undo_chunk("Copy Skin Weights")
    @maya_decorator.error_handler
    def copy_skin_weights(self):
        """Copy the skin weights."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No objects selected")

        if len(sel_nodes) < 2:
            cmds.error("Select 2 more objects")

        copy_skin_weights_with_bind(sel_nodes[0], sel_nodes[1:], uv=self.uv_button.isChecked())

    @maya_decorator.undo_chunk("Mirror Skin Weights")
    @maya_decorator.error_handler
    def mirror_skin_weights(self):
        """Mirror the skin weights."""
        sel_nodes = cmds.ls(sl=True, type="transform")
        if not sel_nodes:
            cmds.error("No objects selected")

        for node in sel_nodes:
            mirror_skin_weights(
                node, left_right_names=LEFT_TO_RIGHT, right_left_names=RIGHT_TO_LEFT, mirror_inverse=self.mir_dir_checkBox.isChecked()
            )

    @maya_decorator.undo_chunk("Mirror Skin Weights Sub")
    @maya_decorator.error_handler
    def mirror_skin_weights_sub(self):
        """Mirror the skin weights."""
        sel_nodes = cmds.ls(sl=True, type="transform")
        if not sel_nodes:
            cmds.error("No objects selected")

        for node in sel_nodes:
            mirror_skin_weights_with_objects(
                node, left_right_names=LEFT_TO_RIGHT, right_left_names=RIGHT_TO_LEFT, mirror_inverse=self.mir_dir_checkBox.isChecked()
            )

    def save_settings(self):
        """Save the option settings."""
        self.settings.write("mirror", self.mir_dir_checkBox.isChecked())
        self.settings.write("uv", self.uv_button.isChecked())
