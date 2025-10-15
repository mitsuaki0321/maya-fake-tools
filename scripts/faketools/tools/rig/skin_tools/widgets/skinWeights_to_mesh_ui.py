"""
Skin Weights to mesh converter tool.
"""

from functools import partial
from logging import getLogger

import maya.cmds as cmds

from .....lib import lib_skinCluster
from .....lib_ui import base_window, maya_decorator
from .....lib_ui.qt_compat import QGridLayout, QIntValidator, QLabel, QLineEdit, QPushButton, QSizePolicy, QSlider, Qt, QVBoxLayout, QWidget
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.widgets import extra_widgets
from .....operations.convert_weight import SkinClusterToMesh

logger = getLogger(__name__)


class SkinWeightsMeshConverterWidgets(QWidget):
    """Skin Weights Mesh Converter Widgets."""

    def __init__(self, settings: ToolSettingsManager, parent=None, window_mode: bool = False):
        """Constructor.

        Args:
            settings (ToolSettingsManager): Settings manager instance
            parent (QWidget, optional): Parent widget. Defaults to None.
            window_mode (bool, optional): Window mode flag. Defaults to False.
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

        layout = QGridLayout()

        label = QLabel("Mesh Divisions:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 0, 0)

        self.mesh_div_field = QLineEdit()
        self.mesh_div_field.setValidator(QIntValidator(1, 10))
        self.mesh_div_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.mesh_div_field.setFixedWidth(self.mesh_div_field.sizeHint().width() / 2.0)
        layout.addWidget(self.mesh_div_field, 0, 1)

        self.mesh_div_slider = QSlider(Qt.Horizontal)
        self.mesh_div_slider.setRange(1, 10)
        layout.addWidget(self.mesh_div_slider, 0, 2)

        label = QLabel("U Divisions:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 1, 0)

        self.u_div_field = QLineEdit()
        self.u_div_field.setValidator(QIntValidator(1, 10))
        self.u_div_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.u_div_field.setFixedWidth(self.u_div_field.sizeHint().width() / 2.0)
        layout.addWidget(self.u_div_field, 1, 1)

        self.u_div_slider = QSlider(Qt.Horizontal)
        self.u_div_slider.setRange(1, 10)
        layout.addWidget(self.u_div_slider, 1, 2)

        label = QLabel("V Divisions:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, 2, 0)

        self.v_div_field = QLineEdit()
        self.v_div_field.setValidator(QIntValidator(1, 10))
        self.v_div_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.v_div_field.setFixedWidth(self.v_div_field.sizeHint().width() / 2.0)
        layout.addWidget(self.v_div_field, 2, 1)

        self.v_div_slider = QSlider(Qt.Horizontal)
        self.v_div_slider.setRange(1, 10)
        layout.addWidget(self.v_div_slider, 2, 2)

        layout.setColumnStretch(2, 1)

        self.main_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.main_layout.addWidget(separator)

        template_button = QPushButton("Create Template Mesh")
        self.main_layout.addWidget(template_button)

        convert_button = QPushButton("Convert Skin Weights to Mesh")
        self.main_layout.addWidget(convert_button)

        self.main_layout.addStretch()

        self.setLayout(self.main_layout)

        # Signal & Slot
        self.mesh_div_field.textChanged.connect(partial(self._update_preview_values, self.mesh_div_field))
        self.mesh_div_slider.valueChanged.connect(partial(self._update_preview_values, self.mesh_div_slider))
        self.u_div_field.textChanged.connect(partial(self._update_preview_values, self.u_div_field))
        self.u_div_slider.valueChanged.connect(partial(self._update_preview_values, self.u_div_slider))
        self.v_div_field.textChanged.connect(partial(self._update_preview_values, self.v_div_field))
        self.v_div_slider.valueChanged.connect(partial(self._update_preview_values, self.v_div_slider))

        template_button.clicked.connect(self.create_template_mesh)
        convert_button.clicked.connect(self.convert_skin_weights_to_mesh)

    def _update_preview_values(self, sender, *args):
        """Update the preview values.

        Args:
            sender: The widget that triggered this update
            *args: Extra arguments from Qt signals (ignored)
        """
        # Check slide and field values
        if sender == self.mesh_div_field:
            text = self.mesh_div_field.text()
            if text:  # Only update if text is not empty
                try:
                    value = int(text)
                    self.mesh_div_slider.setValue(value)
                except ValueError:
                    pass  # Ignore invalid values during typing
        elif sender == self.mesh_div_slider:
            value = self.mesh_div_slider.value()
            self.mesh_div_field.setText(str(value))
        elif sender == self.u_div_field:
            text = self.u_div_field.text()
            if text:
                try:
                    value = int(text)
                    self.u_div_slider.setValue(value)
                except ValueError:
                    pass
        elif sender == self.u_div_slider:
            value = self.u_div_slider.value()
            self.u_div_field.setText(str(value))
        elif sender == self.v_div_field:
            text = self.v_div_field.text()
            if text:
                try:
                    value = int(text)
                    self.v_div_slider.setValue(value)
                except ValueError:
                    pass
        elif sender == self.v_div_slider:
            value = self.v_div_slider.value()
            self.v_div_field.setText(str(value))

        # Change preview values
        if self.preview_mesh is None and self.preview_mesh_node is None:
            logger.debug("No preview mesh found.")
            return

        if not cmds.objExists(self.preview_mesh) or not cmds.objExists(self.preview_mesh_node):
            logger.debug("Preview mesh not found.")
            return

        try:
            if cmds.nodeType(self.preview_mesh_node) == "polySmoothFace":
                value = self.mesh_div_slider.value()
                cmds.setAttr(f"{self.preview_mesh_node}.divisions", value)
                logger.debug(f"Update preview node values: {self.preview_mesh_node} >> {value}")
            elif cmds.nodeType(self.preview_mesh_node) == "nurbsTessellate":
                u_value = self.u_div_slider.value()
                cmds.setAttr(f"{self.preview_mesh_node}.uNumber", u_value)

                v_value = self.v_div_slider.value()
                cmds.setAttr(f"{self.preview_mesh_node}.vNumber", v_value)
                logger.debug(f"Update preview node values: {self.preview_mesh_node} >> {u_value}, {v_value}")
        except Exception as e:
            logger.warning(f"Failed to update preview values: {e}")

    @maya_decorator.undo_chunk("Create Template Mesh")
    @maya_decorator.error_handler
    def create_template_mesh(self):
        """Create a template mesh."""
        shapes = cmds.ls(sl=True, dag=True, type="geometryShape", ni=True)
        if not shapes:
            cmds.error("Select any geometry.")
        else:
            shape = shapes[0]

        skinCluster = lib_skinCluster.get_skinCluster(shape)
        if not skinCluster:
            cmds.error("No skinCluster found.")

        mesh_divisions = int(self.mesh_div_field.text())
        u_divisions = int(self.u_div_field.text())
        v_divisions = int(self.v_div_field.text())

        skinCluster_to_mesh_ins = SkinClusterToMesh(skinCluster, divisions=mesh_divisions, u_divisions=u_divisions, v_divisions=v_divisions)

        self.preview_mesh, self.preview_mesh_node = skinCluster_to_mesh_ins.preview()

        cmds.select(self.preview_mesh)

        logger.debug(f"Created template mesh: {self.preview_mesh}")

    @maya_decorator.undo_chunk("Convert Skin Weights to Mesh")
    @maya_decorator.error_handler
    def convert_skin_weights_to_mesh(self):
        """Convert the skin weights to mesh."""
        shapes = cmds.ls(sl=True, dag=True, type="geometryShape", ni=True)
        if not shapes:
            cmds.error("Select any geometry.")

        mesh_divisions = int(self.mesh_div_field.text())
        u_divisions = int(self.u_div_field.text())
        v_divisions = int(self.v_div_field.text())

        converted_meshes = []
        for shape in shapes:
            skinCluster = lib_skinCluster.get_skinCluster(shape)
            if not skinCluster:
                cmds.warning(f"No skinCluster found: {shape}")
                continue

            skinCluster_to_mesh_ins = SkinClusterToMesh(skinCluster, divisions=mesh_divisions, u_divisions=u_divisions, v_divisions=v_divisions)

            converted_mesh = skinCluster_to_mesh_ins.convert()
            converted_meshes.append(converted_mesh)

            logger.debug(f"Converted skin weights to mesh: {converted_mesh}")

        if converted_meshes:
            cmds.select(converted_meshes, r=True)

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Settings data
        """
        return {
            "mesh_divisions": self.mesh_div_field.text(),
            "u_divisions": self.u_div_field.text(),
            "v_divisions": self.v_div_field.text(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to widget.

        Args:
            settings_data (dict): Settings data to apply
        """
        if "mesh_divisions" in settings_data:
            mesh_divisions = settings_data["mesh_divisions"]
            # Handle empty or invalid values with default of 1
            if mesh_divisions == "" or mesh_divisions is None:
                mesh_divisions = 1
            try:
                self.mesh_div_field.setText(str(mesh_divisions))
                self.mesh_div_slider.setValue(int(mesh_divisions))
            except (ValueError, TypeError):
                self.mesh_div_field.setText("1")
                self.mesh_div_slider.setValue(1)

        if "u_divisions" in settings_data:
            u_divisions = settings_data["u_divisions"]
            # Handle empty or invalid values with default of 1
            if u_divisions == "" or u_divisions is None:
                u_divisions = 1
            try:
                self.u_div_field.setText(str(u_divisions))
                self.u_div_slider.setValue(int(u_divisions))
            except (ValueError, TypeError):
                self.u_div_field.setText("1")
                self.u_div_slider.setValue(1)

        if "v_divisions" in settings_data:
            v_divisions = settings_data["v_divisions"]
            # Handle empty or invalid values with default of 1
            if v_divisions == "" or v_divisions is None:
                v_divisions = 1
            try:
                self.v_div_field.setText(str(v_divisions))
                self.v_div_slider.setValue(int(v_divisions))
            except (ValueError, TypeError):
                self.v_div_field.setText("1")
                self.v_div_slider.setValue(1)
