"""Create transform nodes on the curve tool."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import BaseMainWindow, error_handler, get_maya_main_window, undo_chunk
from ....lib_ui.qt_compat import QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, Qt
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import extra_widgets
from ....operations import create_transforms

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Transform Creator on Curve Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent, object_name="TransformCreatorOnCurveMainWindow", window_title="Transform Creator on Curve", central_layout="vertical"
        )

        self.settings = ToolSettingsManager(tool_name="transform_creator_on_curve", category="rig")

        self.method_box = QComboBox()
        self.method_box.addItems(self.method_data().keys())
        self.central_layout.addWidget(self.method_box)

        self.node_type_box = QComboBox()
        self.node_type_box.addItems(["locator", "joint"])
        self.central_layout.addWidget(self.node_type_box)

        layout = QHBoxLayout()

        size_label = QLabel("Size:")
        layout.addWidget(size_label)

        self.size_field = extra_widgets.ModifierSpinBox()
        self.size_field.setDecimals(2)
        layout.addWidget(self.size_field, stretch=1)

        self.central_layout.addLayout(layout)

        layout = QHBoxLayout()

        div_label = QLabel("Divisions:")
        layout.addWidget(div_label)

        self.divisions_field = QSpinBox()
        self.divisions_field.setMinimum(1)
        self.divisions_field.setMaximum(100)
        layout.addWidget(self.divisions_field, stretch=1)

        self.central_layout.addLayout(layout)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        self.include_rotation_cb = QCheckBox("Include Rotation")
        self.central_layout.addWidget(self.include_rotation_cb)

        layout = QHBoxLayout()
        layout.setSpacing(0)

        self.rotate_offset_field_x = QDoubleSpinBox()
        self.rotate_offset_field_x.setSingleStep(45.0)
        self.rotate_offset_field_x.setDecimals(2)
        self.rotate_offset_field_x.setMaximum(360.0)
        self.rotate_offset_field_x.setMinimum(-360.0)
        layout.addWidget(self.rotate_offset_field_x)

        self.rotate_offset_field_y = QDoubleSpinBox()
        self.rotate_offset_field_y.setSingleStep(45.0)
        self.rotate_offset_field_y.setDecimals(2)
        self.rotate_offset_field_y.setMaximum(360.0)
        self.rotate_offset_field_y.setMinimum(-360.0)
        layout.addWidget(self.rotate_offset_field_y)

        self.rotate_offset_field_z = QDoubleSpinBox()
        self.rotate_offset_field_z.setSingleStep(45.0)
        self.rotate_offset_field_z.setDecimals(2)
        self.rotate_offset_field_z.setMaximum(360.0)
        self.rotate_offset_field_z.setMinimum(-360.0)
        layout.addWidget(self.rotate_offset_field_z)

        self.central_layout.addLayout(layout)

        layout = QHBoxLayout()

        aim_label = QLabel("AimVector:")
        layout.addWidget(aim_label)

        self.aim_vector_box = QComboBox()
        self.aim_vector_box.addItems(self.aim_vector_data().keys())
        layout.addWidget(self.aim_vector_box, stretch=1)

        self.central_layout.addLayout(layout)

        layout = QHBoxLayout()

        up_label = QLabel("UpVector:")
        layout.addWidget(up_label)

        self.up_vector_box = QComboBox()
        self.up_vector_box.addItems(self.up_vector_data().keys())
        layout.addWidget(self.up_vector_box, stretch=1)

        self.central_layout.addLayout(layout)

        layout = QHBoxLayout()

        surface_dir_label = QLabel("SurfaceDir:")
        layout.addWidget(surface_dir_label)

        self.surface_direction_box = QComboBox()
        self.surface_direction_box.addItems(self.surface_direction_data().keys())
        layout.addWidget(self.surface_direction_box, stretch=1)

        self.central_layout.addLayout(layout)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        self.reverse_cb = QCheckBox("Reverse")
        self.central_layout.addWidget(self.reverse_cb)

        self.chain_cb = QCheckBox("Chain")
        self.central_layout.addWidget(self.chain_cb)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        self.create_button = QPushButton("Create")
        self.central_layout.addWidget(self.create_button)

        # Signal and slot
        self.method_box.currentIndexChanged.connect(self.switch_method)
        self.create_button.clicked.connect(self.create_transform)

        # Initialize
        # Rearrange label width
        max_width = 0
        for label in [size_label, div_label, aim_label, up_label, surface_dir_label]:
            max_width = max(max_width, label.sizeHint().width())

        for label in [size_label, div_label, aim_label, up_label, surface_dir_label]:
            label.setFixedWidth(max_width)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Restore settings and initialize
        self._restore_settings()
        self.switch_method(self.method_box.currentIndex())

    def aim_vector_data(self) -> dict:
        """Aim vector method list.

        Returns:
            dict: Aim vector label and method pairs.
        """
        return {"CurveTangent": "tangent", "NextPoint": "next_point", "PreviousPoint": "previous_point"}

    def up_vector_data(self) -> dict:
        """Up vector method list.

        Returns:
            dict: Up vector label and method pairs.
        """
        return {"SceneUp": "scene_up", "CurveNormal": "normal", "SurfaceNormal": "surface_normal"}

    def surface_direction_data(self) -> dict:
        """Surface direction method list.

        Returns:
            dict: Surface direction label and method pairs.
        """
        return {"U Direction": "u", "V Direction": "v"}

    def method_data(self) -> dict:
        """Return label and function pairs.

        Returns:
            dict: Label and function pairs.
        """
        return {
            "CVPositions": {"function": "cv_positions", "divisions": False},
            "EPPositions": {"function": "ep_positions", "divisions": False},
            "CVClosestPositions": {"function": "cv_closest_positions", "divisions": False},
            "ParameterPositions": {"function": "param_positions", "divisions": True},
            "LengthPositions": {"function": "length_positions", "divisions": True},
            "CloudPositions": {"function": "cloud_positions", "divisions": True},
        }

    def switch_method(self, index):
        """Switch enable or disable widgets by method.

        Args:
            index (int): Index of method box.
        """
        method_name = self.method_box.itemText(index)
        method_data = self.method_data()[method_name]

        self.divisions_field.setEnabled(method_data["divisions"])

    @error_handler
    @undo_chunk("Transform Creator on Curve: Create")
    def create_transform(self):
        """Create transform nodes."""
        # Get function name
        function_name = self.method_data()[self.method_box.currentText()]["function"]
        if not hasattr(create_transforms, function_name):
            raise ValueError(f"Invalid function name: {function_name}")

        # Default variables
        function = getattr(create_transforms, function_name)
        node_type = self.node_type_box.currentText()
        size = self.size_field.value()
        reverse = self.reverse_cb.isChecked()
        chain = self.chain_cb.isChecked()
        rotation_offset = [self.rotate_offset_field_x.value(), self.rotate_offset_field_y.value(), self.rotate_offset_field_z.value()]

        # Extra variables
        include_rotation = self.include_rotation_cb.isChecked()
        divisions = self.divisions_field.value()
        aim_vector_method = self.aim_vector_data()[self.aim_vector_box.currentText()]
        up_vector_method = self.up_vector_data()[self.up_vector_box.currentText()]
        surface_direction = self.surface_direction_data()[self.surface_direction_box.currentText()]

        # Create transform nodes
        make_transform = create_transforms.CreateTransforms(
            func=function, size=size, shape_type=node_type, chain=chain, reverse=reverse, rotation_offset=rotation_offset
        )

        result_nodes = make_transform.create(
            include_rotation=include_rotation,
            divisions=divisions,
            aim_vector_method=aim_vector_method,
            up_vector_method=up_vector_method,
            surface_direction=surface_direction,
        )

        if result_nodes:
            cmds.select(result_nodes, r=True)

        logger.info(f"Created transform nodes: {result_nodes}")

    def _collect_settings(self) -> dict:
        """Collect current UI settings (excluding window geometry).

        Returns:
            dict: Settings data
        """
        return {
            "method": self.method_box.currentIndex(),
            "node_type": self.node_type_box.currentIndex(),
            "size": self.size_field.value(),
            "divisions": self.divisions_field.value(),
            "include_rotation": self.include_rotation_cb.isChecked(),
            "rotate_offsetX": self.rotate_offset_field_x.value(),
            "rotate_offsetY": self.rotate_offset_field_y.value(),
            "rotate_offsetZ": self.rotate_offset_field_z.value(),
            "aim_vector": self.aim_vector_box.currentIndex(),
            "up_vector": self.up_vector_box.currentIndex(),
            "surface_direction": self.surface_direction_box.currentIndex(),
            "reverse": self.reverse_cb.isChecked(),
            "chain": self.chain_cb.isChecked(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI (excluding window geometry).

        Args:
            settings_data (dict): Settings data to apply
        """
        if "method" in settings_data:
            self.method_box.setCurrentIndex(settings_data["method"])
        if "node_type" in settings_data:
            self.node_type_box.setCurrentIndex(settings_data["node_type"])
        if "size" in settings_data:
            self.size_field.setValue(settings_data["size"])
        if "divisions" in settings_data:
            self.divisions_field.setValue(settings_data["divisions"])
        if "include_rotation" in settings_data:
            self.include_rotation_cb.setChecked(settings_data["include_rotation"])
        if "rotate_offsetX" in settings_data:
            self.rotate_offset_field_x.setValue(settings_data["rotate_offsetX"])
        if "rotate_offsetY" in settings_data:
            self.rotate_offset_field_y.setValue(settings_data["rotate_offsetY"])
        if "rotate_offsetZ" in settings_data:
            self.rotate_offset_field_z.setValue(settings_data["rotate_offsetZ"])
        if "aim_vector" in settings_data:
            self.aim_vector_box.setCurrentIndex(settings_data["aim_vector"])
        if "up_vector" in settings_data:
            self.up_vector_box.setCurrentIndex(settings_data["up_vector"])
        if "surface_direction" in settings_data:
            self.surface_direction_box.setCurrentIndex(settings_data["surface_direction"])
        if "reverse" in settings_data:
            self.reverse_cb.setChecked(settings_data["reverse"])
        if "chain" in settings_data:
            self.chain_cb.setChecked(settings_data["chain"])

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
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Transform Creator on Curve UI.

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
