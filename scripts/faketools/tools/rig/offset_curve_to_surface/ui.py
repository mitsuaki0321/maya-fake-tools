"""Offset Curve to Surface UI layer."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import (
    BaseMainWindow,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
    undo_chunk,
)
from ....lib_ui.preset_menu_manager import PresetMenuManager
from ....lib_ui.qt_compat import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QPushButton,
    Qt,
)
from ....lib_ui.widgets import extra_widgets
from . import command

logger = getLogger(__name__)
_instance = None  # Global instance for singleton pattern


class MainWindow(BaseMainWindow):
    """Main window for Offset Curve to Surface tool."""

    def __init__(self, parent=None):
        """Initialize the window."""
        super().__init__(
            parent=parent,
            object_name="OffsetCurveToSurfaceMainWindow",
            window_title="Offset Curve to Surface",
            central_layout="vertical",
        )
        self.settings = ToolSettingsManager("offset_curve_to_surface", "rig")

        # Setup preset menu using composition
        self.preset_manager = PresetMenuManager(
            window=self, settings_manager=self.settings, collect_callback=self._collect_settings, apply_callback=self._apply_settings
        )
        self.preset_manager.add_menu()

        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QGridLayout()
        row = 0

        # Axis Type
        label = QLabel("Axis:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Vector", "Normal", "Binormal", "Mesh Normal", "Mesh Binormal", "Surface Normal", "Surface Binormal"])
        self.axis_combo.currentIndexChanged.connect(self._update_ui_state)
        layout.addWidget(self.axis_combo, row, 1, 1, 3)
        row += 1

        # Vector
        self.vector_label = QLabel("Vector:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.vector_label, row, 0)

        self.vector_x_spin = QDoubleSpinBox()
        self.vector_x_spin.setRange(-1000.0, 1000.0)
        self.vector_x_spin.setValue(0.0)
        self.vector_x_spin.setDecimals(3)
        layout.addWidget(self.vector_x_spin, row, 1)

        self.vector_y_spin = QDoubleSpinBox()
        self.vector_y_spin.setRange(-1000.0, 1000.0)
        self.vector_y_spin.setValue(1.0)
        self.vector_y_spin.setDecimals(3)
        layout.addWidget(self.vector_y_spin, row, 2)

        self.vector_z_spin = QDoubleSpinBox()
        self.vector_z_spin.setRange(-1000.0, 1000.0)
        self.vector_z_spin.setValue(0.0)
        self.vector_z_spin.setDecimals(3)
        layout.addWidget(self.vector_z_spin, row, 3)
        row += 1

        # Reference Object
        self.reference_label = QLabel("Reference:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.reference_label, row, 0)

        self.reference_line_edit = extra_widgets.QLineEditWithButton()
        self.reference_line_edit.set_button_text("<<")
        self.reference_line_edit.button_clicked.connect(self._on_get_reference_object)
        layout.addWidget(self.reference_line_edit, row, 1, 1, 3)
        row += 1

        # Width
        label = QLabel("Width:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.001, 10000.0)
        self.width_spin.setValue(1.0)
        self.width_spin.setDecimals(3)
        layout.addWidget(self.width_spin, row, 1)

        # Width Center
        label = QLabel("Center:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 2)

        self.width_center_spin = QDoubleSpinBox()
        self.width_center_spin.setRange(0.0, 1.0)
        self.width_center_spin.setValue(0.5)
        self.width_center_spin.setDecimals(3)
        self.width_center_spin.setSingleStep(0.1)
        layout.addWidget(self.width_center_spin, row, 3)
        row += 1

        # Separator
        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Create Button
        create_button = QPushButton("Create")
        create_button.clicked.connect(self._on_create)
        layout.addWidget(create_button, row, 0, 1, 4)

        self.central_layout.addLayout(layout)

        # Initialize UI state
        self._update_ui_state()

    def _update_ui_state(self):
        """Update UI widget states based on current axis type."""
        axis_index = self.axis_combo.currentIndex()

        # Vector (index 0)
        is_vector = axis_index == 0
        self.vector_label.setEnabled(is_vector)
        self.vector_x_spin.setEnabled(is_vector)
        self.vector_y_spin.setEnabled(is_vector)
        self.vector_z_spin.setEnabled(is_vector)

        # Reference (Mesh Normal=3, Mesh Binormal=4, Surface Normal=5, Surface Binormal=6)
        requires_reference = axis_index >= 3
        self.reference_label.setEnabled(requires_reference)
        self.reference_line_edit.setEnabled(requires_reference)

    def _on_get_reference_object(self):
        """Get selected object and set as reference object."""
        # Get selected transform nodes
        selection = cmds.ls(selection=True, transforms=True)
        if not selection:
            logger.warning("Select a single transform to set as reference.")
            return

        selected_node = selection[0]

        # Get current axis type index
        axis_index = self.axis_combo.currentIndex()

        # Determine required node type based on axis
        # Mesh Normal=3, Mesh Binormal=4, Surface Normal=5, Surface Binormal=6
        required_type = None
        if axis_index in [3, 4]:  # Mesh Normal/Binormal
            required_type = "mesh"
        elif axis_index in [5, 6]:  # Surface Normal/Binormal
            required_type = "nurbsSurface"
        else:
            return

        # Get shape node
        shapes = cmds.listRelatives(selected_node, shapes=True, noIntermediate=True)
        if not shapes:
            logger.warning(f"Invalid Node: '{selected_node}' has no shape node.")
            return

        # Check if shape is the required type
        shape_type = cmds.nodeType(shapes[0])
        if shape_type != required_type:
            logger.warning(f"Invalid node type: '{selected_node}' is '{shape_type}', expected '{required_type}'")
            return

        # Valid node - set in line edit
        self.reference_line_edit.setText(shapes[0])
        logger.debug(f"Set reference object: {shapes[0]}")

    @error_handler
    @undo_chunk("Offset Curve to Surface")
    def _on_create(self):
        """Handle create button click."""
        # Get selected curves (dag=True to get shape nodes from transform selection)
        selected_curves = cmds.ls(sl=True, dag=True, type="nurbsCurve")
        if not selected_curves:
            raise ValueError("No curves selected. Please select one or more nurbsCurve.")

        # Get parameters
        axis_index = self.axis_combo.currentIndex()
        axis_map = ["vector", "normal", "binormal", "meshNormal", "meshBinormal", "surfaceNormal", "surfaceBinormal"]
        axis_type = axis_map[axis_index]

        surface_width = self.width_spin.value()
        surface_width_center = self.width_center_spin.value()

        # Get vector if axis_type is "vector"
        vector = None
        if axis_type == "vector":
            vector = [
                self.vector_x_spin.value(),
                self.vector_y_spin.value(),
                self.vector_z_spin.value(),
            ]

        # Get reference object if needed
        reference_object = None
        if axis_type in ["meshNormal", "meshBinormal", "surfaceNormal", "surfaceBinormal"]:
            reference_object = self.reference_line_edit.text().strip()
            if not reference_object:
                raise ValueError(f"Reference object is required for axis type '{axis_type}'.")

        # Create surfaces for each curve
        created_surfaces = []
        for curve_shape in selected_curves:
            try:
                offset_curve = command.OffsetCurveToSurface(curve_shape)
                surface = offset_curve.execute(
                    axis_type=axis_type,
                    surface_width=surface_width,
                    surface_width_center=surface_width_center,
                    vector=vector,
                    reference_object=reference_object,
                    divisions=0,
                )
                created_surfaces.append(surface)
                logger.info(f"Created surface from curve '{curve_shape}': {surface}")
            except Exception as e:
                logger.error(f"Failed to create surface from curve '{curve_shape}': {e}")
                raise

        # Select created surfaces
        if created_surfaces:
            cmds.select(created_surfaces, r=True)
            logger.info(f"Created {len(created_surfaces)} surface(s).")

    def _collect_settings(self) -> dict:
        """Collect current UI settings into a dictionary.

        Returns:
            dict: Current UI settings
        """
        return {
            "axis_index": self.axis_combo.currentIndex(),
            "vector_x": self.vector_x_spin.value(),
            "vector_y": self.vector_y_spin.value(),
            "vector_z": self.vector_z_spin.value(),
            "reference_object": self.reference_line_edit.text(),
            "width": self.width_spin.value(),
            "width_center": self.width_center_spin.value(),
        }

    def _apply_settings(self, settings: dict):
        """Apply settings data to UI.

        Args:
            settings (dict): Settings data to apply
        """
        self.axis_combo.setCurrentIndex(settings.get("axis_index", 0))
        self.vector_x_spin.setValue(settings.get("vector_x", 0.0))
        self.vector_y_spin.setValue(settings.get("vector_y", 1.0))
        self.vector_z_spin.setValue(settings.get("vector_z", 0.0))
        self.reference_line_edit.setText(settings.get("reference_object", ""))
        self.width_spin.setValue(settings.get("width", 1.0))
        self.width_center_spin.setValue(settings.get("width_center", 0.5))

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Load default preset
        settings = self.settings.load_settings("default")
        if settings:
            self._apply_settings(settings)

    def _save_settings(self):
        """Save UI settings to default preset."""
        settings = self._collect_settings()
        self.settings.save_settings(settings, "default")

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the tool UI (entry point)."""
    global _instance

    # Close existing instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    # Create new instance
    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
