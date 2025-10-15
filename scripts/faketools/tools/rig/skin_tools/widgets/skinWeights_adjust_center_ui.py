"""
Adjust the center weights of the selected vertices tool.
"""

from functools import partial
from logging import getLogger

import maya.cmds as cmds

from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QCheckBox, QGridLayout, QLabel, QLineEdit, QPushButton, Qt, QVBoxLayout, QWidget
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.widgets import extra_widgets
from ..command import combine_pair_skin_weights

logger = getLogger(__name__)


ADJUST_CENTER_WEIGHT = ["(.*)(L$)", r"\g<1>R"]


class AdjustCenterSkinWeightsWidgets(QWidget):
    """Adjust Center Skin Weights Widgets."""

    def __init__(self, settings: ToolSettingsManager = None, parent=None, window_mode: bool = False):
        """Constructor."""
        super().__init__(parent=parent)

        self.settings = settings

        self.main_layout = QVBoxLayout()
        spacing = base_window.get_spacing(self)
        self.main_layout.setSpacing(spacing * 0.75)

        if not window_mode:
            margins = base_window.get_margins(self)
            self.main_layout.setContentsMargins(*[margin * 0.5 for margin in margins])

        self.auto_search_checkbox = QCheckBox("Auto Search")
        self.main_layout.addWidget(self.auto_search_checkbox)

        layout = QGridLayout()

        self.src_label = QLabel("Source Influences:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.src_label, 0, 0)

        self.src_infs_field = QLineEdit()
        layout.addWidget(self.src_infs_field, 0, 1)

        self.src_infs_button = QPushButton("SET")
        layout.addWidget(self.src_infs_button, 0, 2)

        self.target_label = QLabel("Target Influences:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.target_label, 1, 0)

        self.target_infs_field = QLineEdit()
        layout.addWidget(self.target_infs_field, 1, 1)

        self.target_infs_button = QPushButton("SET")
        layout.addWidget(self.target_infs_button, 1, 2)

        separator = extra_widgets.HorizontalSeparator()
        layout.addWidget(separator, 2, 0, 1, 3)

        label = QLabel("Static Influence:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 3, 0)

        self.static_inf_field = QLineEdit()
        layout.addWidget(self.static_inf_field, 3, 1)

        static_inf_button = QPushButton("SET")
        layout.addWidget(static_inf_button, 3, 2)

        layout.setColumnStretch(1, 1)

        self.main_layout.addLayout(layout)

        button = QPushButton("Adjust Center Weights")
        self.main_layout.addWidget(button)

        self.main_layout.addStretch()

        self.setLayout(self.main_layout)

        # Signal & Slot
        self.auto_search_checkbox.stateChanged.connect(self._toggle_auto_search)
        self.src_infs_button.clicked.connect(partial(self._set_selected_nodes, self.src_infs_field))
        self.target_infs_button.clicked.connect(partial(self._set_selected_nodes, self.target_infs_field))
        static_inf_button.clicked.connect(partial(self._set_selected_node, self.static_inf_field))

        button.clicked.connect(self.exchange_influences)

        # Initialize UI
        self.auto_search_checkbox.setCheckState(Qt.Checked)
        self._toggle_auto_search(Qt.Checked)

    def _toggle_auto_search(self, state):
        """Toggle the auto search."""
        if state == Qt.Checked:
            self.src_label.setEnabled(False)
            self.src_infs_field.setEnabled(False)
            self.src_infs_button.setEnabled(False)
            self.target_label.setEnabled(False)
            self.target_infs_field.setEnabled(False)
            self.target_infs_button.setEnabled(False)
        else:
            self.src_label.setEnabled(True)
            self.src_infs_field.setEnabled(True)
            self.src_infs_button.setEnabled(True)
            self.target_label.setEnabled(True)
            self.target_infs_field.setEnabled(True)
            self.target_infs_button.setEnabled(True)

    @maya_decorator.error_handler
    def _set_selected_nodes(self, field):
        """Set the selected nodes to the field."""
        nodes = cmds.ls(sl=True, type="joint")
        if not nodes:
            if not cmds.ls(sl=True):
                field.setText("")
            else:
                cmds.error("Select joints.")

        field.setText(" ".join(nodes))

    @maya_decorator.error_handler
    def _set_selected_node(self, field):
        """Set the selected node to the field."""
        nodes = cmds.ls(sl=True, type="joint")
        if not nodes:
            if not cmds.ls(sl=True):
                field.setText("")
            else:
                cmds.error("Select a joint.")

        field.setText(nodes[0])

    @maya_decorator.undo_chunk("Adjust Center Weights")
    @maya_decorator.error_handler
    def exchange_influences(self):
        """Exchange the influences."""
        components = cmds.filterExpand(sm=[28, 31, 46], ex=True)
        if not components:
            cmds.error("No components selected.")

        static_inf = self.static_inf_field.text()
        if not static_inf:
            static_inf = None

        if self.auto_search_checkbox.isChecked():
            combine_pair_skin_weights(
                components, method="auto", static_inf=static_inf, regex_name=ADJUST_CENTER_WEIGHT[0], replace_name=ADJUST_CENTER_WEIGHT[1]
            )
        else:
            src_infs = self.src_infs_field.text().split()
            target_infs = self.target_infs_field.text().split()

            if not src_infs:
                cmds.error("Source influences are not set.")
            if not target_infs:
                cmds.error("Target influences are not set.")

            if len(src_infs) != len(target_infs):
                cmds.error("Influence count mismatch.")

            pair_infs = list(zip(src_infs, target_infs))

            combine_pair_skin_weights(components, method="manual", pair_infs=pair_infs, static_inf=static_inf)
