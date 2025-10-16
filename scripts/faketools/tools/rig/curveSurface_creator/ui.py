"""Create curve/surface UI."""

from logging import getLogger

import maya.cmds as cmds

from ....lib.lib_componentfilter import ComponentFilter
from ....lib_ui import (
    BaseMainWindow,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
    repeatable,
    undo_chunk,
)
from ....lib_ui.preset_menu_manager import PresetMenuManager
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    Qt,
)
from ....lib_ui.widgets import extra_widgets
from . import command

logger = getLogger(__name__)
_instance = None  # Global instance for singleton pattern


class MainWindow(BaseMainWindow):
    """
    Curve/Surface Creator Main Window.

    Provides UI for creating curves and surfaces from selected objects
    with various options for degree, divisions, bindings, and more.
    """

    def __init__(self, parent=None):
        """
        Initialize the Curve/Surface Creator window.

        Args:
            parent: Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="CurveSurfaceCreatorMainWindow",
            window_title="Curve/Surface Creator",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="curveSurface_creator", category="rig")

        # Setup preset menu using composition
        self.preset_manager = PresetMenuManager(
            window=self, settings_manager=self.settings, collect_callback=self._collect_settings, apply_callback=self._apply_settings
        )
        self.preset_manager.add_menu()

        self._add_menu()
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QGridLayout()
        row = 0

        # Main Options - Horizontal layout
        # Select Type and Object Type on same row
        label = QLabel("Select:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.select_type_combo = QComboBox()
        self.select_type_combo.addItems(["Selected", "Hierarchy"])
        layout.addWidget(self.select_type_combo, row, 1)

        label = QLabel("Object:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 2)

        self.object_type_combo = QComboBox()
        self.object_type_combo.addItems(["Curve", "Surface", "Mesh"])
        layout.addWidget(self.object_type_combo, row, 3)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 6)
        row += 1

        # Curve Options

        # Degree - Radio buttons
        label = QLabel("Degree:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        degree_1_button = QRadioButton("1")
        layout.addWidget(degree_1_button, row, 1)

        degree_3_button = QRadioButton("3")
        layout.addWidget(degree_3_button, row, 2)

        degree_1_button.setChecked(True)

        self.degree_button_group = QButtonGroup()
        self.degree_button_group.addButton(degree_1_button, 1)  # ID 1 for degree 1
        self.degree_button_group.addButton(degree_3_button, 3)  # ID 3 for degree 3
        row += 1

        # Options: □Center □Close □Reverse - Use HBoxLayout for equal spacing
        label = QLabel("Options:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        # Create horizontal layout for checkboxes with equal spacing
        checkbox_layout = QHBoxLayout()
        self.center_checkbox = QCheckBox("Center")
        checkbox_layout.addWidget(self.center_checkbox)

        self.close_checkbox = QCheckBox("Close")
        checkbox_layout.addWidget(self.close_checkbox)

        self.reverse_checkbox = QCheckBox("Reverse")
        checkbox_layout.addWidget(self.reverse_checkbox)

        checkbox_layout.addStretch()  # Add stretch to push checkboxes left

        # Add the horizontal layout spanning columns 1-3
        layout.addLayout(checkbox_layout, row, 1, 1, 3)
        row += 1

        # Divisions and Skip - Horizontal layout
        label = QLabel("Divisions:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.divisions_spin_box = QSpinBox()
        self.divisions_spin_box.setRange(0, 100)
        self.divisions_spin_box.setValue(0)
        layout.addWidget(self.divisions_spin_box, row, 1)

        label = QLabel("Skip:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 2)

        self.skip_spin_box = QSpinBox()
        self.skip_spin_box.setRange(0, 100)
        self.skip_spin_box.setValue(0)
        layout.addWidget(self.skip_spin_box, row, 3)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 6)
        row += 1

        # Surface Options

        # Axis: [combo]
        self.surface_axis_label = QLabel("Axis:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.surface_axis_label, row, 0)

        self.surface_axis_combo = QComboBox()
        self.surface_axis_combo.addItems(["X", "Y", "Z", "Normal", "Binormal", "Surface Normal", "Surface Binormal", "Mesh Normal", "Mesh Binormal"])
        layout.addWidget(self.surface_axis_combo, row, 1, 1, 2)
        row += 1

        # Reference Object (for Surface/Mesh Normal/Binormal)
        self.reference_object_label = QLabel("Reference:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.reference_object_label, row, 0)

        self.reference_object_line_edit = extra_widgets.QLineEditWithButton()
        self.reference_object_line_edit.set_button_text("<<")
        layout.addWidget(self.reference_object_line_edit, row, 1, 1, 3)
        row += 1

        # Width and Width Center - Horizontal layout
        self.surface_width_label = QLabel("Width:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.surface_width_label, row, 0)

        self.surface_width_spin_box = QDoubleSpinBox()
        self.surface_width_spin_box.setRange(0.00, 100.0)
        self.surface_width_spin_box.setSingleStep(0.5)
        layout.addWidget(self.surface_width_spin_box, row, 1)

        self.surface_width_center_label = QLabel("Center:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.surface_width_center_label, row, 2)

        self.surface_width_center_spin_box = QDoubleSpinBox()
        self.surface_width_center_spin_box.setRange(0.0, 1.0)
        self.surface_width_center_spin_box.setSingleStep(0.5)
        layout.addWidget(self.surface_width_center_spin_box, row, 3)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 6)
        row += 1

        # Bind Options

        # Is Bind
        label = QLabel("Is Bind:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.is_bind_checkbox = QCheckBox()
        layout.addWidget(self.is_bind_checkbox, row, 1)
        row += 1

        # Bind method
        self.bind_method_label = QLabel("Bind Method:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.bind_method_label, row, 0)

        self.bind_method_combo = QComboBox()
        self.bind_method_combo.addItems(["Linear", "Ease", "Step"])
        layout.addWidget(self.bind_method_combo, row, 1, 1, 3)
        row += 1

        # Smooth level
        self.smooth_level_label = QLabel("Smooth Levels:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.smooth_level_label, row, 0)

        self.smooth_level_spin_box = QSpinBox()
        self.smooth_level_spin_box.setRange(0, 100)
        layout.addWidget(self.smooth_level_spin_box, row, 1)
        row += 1

        # Parent influence ratio
        self.parent_influence_label = QLabel("Parent Influence:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.parent_influence_label, row, 0)

        self.parent_influence_spin_box = QDoubleSpinBox()
        self.parent_influence_spin_box.setRange(0.0, 1.0)
        self.parent_influence_spin_box.setSingleStep(0.1)
        self.parent_influence_spin_box.setValue(0.0)
        layout.addWidget(self.parent_influence_spin_box, row, 1)
        row += 1

        # Remove end influence
        self.remove_end_label = QLabel("Remove End:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.remove_end_label, row, 0)

        self.remove_end_checkbox = QCheckBox()
        layout.addWidget(self.remove_end_checkbox, row, 1)
        row += 1

        # To skin cage
        self.to_skin_cage_label = QLabel("To Skin Cage:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.to_skin_cage_label, row, 0)

        self.to_skin_cage_checkbox = QCheckBox()
        layout.addWidget(self.to_skin_cage_checkbox, row, 1)
        row += 1

        self.to_skin_cage_div_label = QLabel("Division Levels:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.to_skin_cage_div_label, row, 0)

        self.to_skin_cage_spinBox = QSpinBox()
        self.to_skin_cage_spinBox.setRange(1, 100)
        layout.addWidget(self.to_skin_cage_spinBox, row, 1)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 6)
        row += 1

        create_button = QPushButton("Create")
        layout.addWidget(create_button, row, 0, 1, 6)

        self.central_layout.addLayout(layout)

        # Signal & Slot
        self.is_bind_checkbox.stateChanged.connect(self._change_bind_mode)
        self.object_type_combo.currentIndexChanged.connect(self._change_surface_mode)
        self.surface_axis_combo.currentIndexChanged.connect(self._change_reference_object_mode)
        self.to_skin_cage_checkbox.stateChanged.connect(self.to_skin_cage_div_label.setEnabled)
        self.to_skin_cage_checkbox.stateChanged.connect(self.to_skin_cage_spinBox.setEnabled)
        self.reference_object_line_edit.button_clicked.connect(self._set_reference_object_from_selection)

        create_button.clicked.connect(self.create_curve_surface)

        # Initialize UI state
        self._change_bind_mode()
        self._change_surface_mode()
        self._change_reference_object_mode()

    def _add_menu(self):
        """Add the menu bar actions."""
        # Edit menu
        edit_menu = self.menuBar().addMenu("Edit")

        action = edit_menu.addAction("Move CVs Position")
        action.triggered.connect(self.move_cvs_position)

        action = edit_menu.addAction("Create Curve to Vertices")
        action.triggered.connect(self.create_curve_to_vertices)

        edit_menu.addSeparator()

        action = edit_menu.addAction("Create Curve on Surface U")
        action.triggered.connect(lambda: self.create_curve_on_surface("u"))

        action = edit_menu.addAction("Create Curve on Surface V")
        action.triggered.connect(lambda: self.create_curve_on_surface("v"))

    def _apply_settings(self, settings_data: dict):
        """
        Apply settings data to UI.

        Args:
            settings_data (dict): Settings data to apply
        """
        # Restore option settings
        self.select_type_combo.setCurrentIndex(settings_data.get("select_type_index", 0))
        self.object_type_combo.setCurrentIndex(settings_data.get("object_type_index", 0))

        # Restore degree radio button
        degree_id = settings_data.get("degree_id", 1)  # Default to degree 1
        button = self.degree_button_group.button(degree_id)
        if button:
            button.setChecked(True)

        self.center_checkbox.setChecked(settings_data.get("center", False))
        self.close_checkbox.setChecked(settings_data.get("close", False))
        self.reverse_checkbox.setChecked(settings_data.get("reverse", False))
        self.divisions_spin_box.setValue(settings_data.get("divisions", 0))
        self.skip_spin_box.setValue(settings_data.get("skip", 0))
        self.surface_axis_combo.setCurrentIndex(settings_data.get("surface_axis_index", 0))
        self.surface_width_spin_box.setValue(settings_data.get("surface_width", 1.0))
        self.surface_width_center_spin_box.setValue(settings_data.get("surface_width_center", 0.5))
        self.reference_object_line_edit.setText(settings_data.get("reference_object", ""))
        self.is_bind_checkbox.setChecked(settings_data.get("is_bind", False))
        self.bind_method_combo.setCurrentIndex(settings_data.get("bind_method_index", 0))
        self.smooth_level_spin_box.setValue(settings_data.get("smooth_levels", 0))
        self.parent_influence_spin_box.setValue(settings_data.get("parent_influence_ratio", 0.0))
        self.remove_end_checkbox.setChecked(settings_data.get("remove_end", False))
        self.to_skin_cage_checkbox.setChecked(settings_data.get("to_skin_cage", False))
        self.to_skin_cage_spinBox.setValue(settings_data.get("skin_cage_division_levels", 1))

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Load default preset
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _collect_settings(self) -> dict:
        """
        Collect current UI settings into a dictionary.

        Returns:
            dict: Current UI settings
        """
        return {
            "select_type_index": self.select_type_combo.currentIndex(),
            "object_type_index": self.object_type_combo.currentIndex(),
            "degree_id": self.degree_button_group.checkedId(),
            "center": self.center_checkbox.isChecked(),
            "close": self.close_checkbox.isChecked(),
            "reverse": self.reverse_checkbox.isChecked(),
            "divisions": self.divisions_spin_box.value(),
            "skip": self.skip_spin_box.value(),
            "surface_axis_index": self.surface_axis_combo.currentIndex(),
            "surface_width": self.surface_width_spin_box.value(),
            "surface_width_center": self.surface_width_center_spin_box.value(),
            "reference_object": self.reference_object_line_edit.text(),
            "is_bind": self.is_bind_checkbox.isChecked(),
            "bind_method_index": self.bind_method_combo.currentIndex(),
            "smooth_levels": self.smooth_level_spin_box.value(),
            "parent_influence_ratio": self.parent_influence_spin_box.value(),
            "remove_end": self.remove_end_checkbox.isChecked(),
            "to_skin_cage": self.to_skin_cage_checkbox.isChecked(),
            "skin_cage_division_levels": self.to_skin_cage_spinBox.value(),
        }

    def _save_settings(self):
        """Save UI settings to default preset."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def _change_bind_mode(self):
        """Update UI state based on bind checkbox state."""
        is_bind = self.is_bind_checkbox.isChecked()

        self.bind_method_label.setEnabled(is_bind)
        self.bind_method_combo.setEnabled(is_bind)

        self.smooth_level_label.setEnabled(is_bind)
        self.smooth_level_spin_box.setEnabled(is_bind)

        self.parent_influence_label.setEnabled(is_bind)
        self.parent_influence_spin_box.setEnabled(is_bind)

        self.remove_end_label.setEnabled(is_bind)
        self.remove_end_checkbox.setEnabled(is_bind)

        is_surface = self.object_type_combo.currentIndex() == 1  # Surface is index 1
        self.to_skin_cage_label.setEnabled(is_bind and is_surface)
        self.to_skin_cage_checkbox.setEnabled(is_bind and is_surface)

        is_to_skin_cage = self.to_skin_cage_checkbox.isChecked()
        self.to_skin_cage_div_label.setEnabled(is_bind and is_surface and is_to_skin_cage)
        self.to_skin_cage_spinBox.setEnabled(is_bind and is_surface and is_to_skin_cage)

    def _change_surface_mode(self):
        """Update UI state based on object type selection."""
        is_curve = self.object_type_combo.currentIndex() == 0  # Curve is index 0

        self.surface_axis_label.setEnabled(not is_curve)
        self.surface_axis_combo.setEnabled(not is_curve)

        self.surface_width_label.setEnabled(not is_curve)
        self.surface_width_spin_box.setEnabled(not is_curve)
        self.surface_width_center_label.setEnabled(not is_curve)
        self.surface_width_center_spin_box.setEnabled(not is_curve)

        is_surface = self.object_type_combo.currentIndex() == 1  # Surface is index 1
        is_bind = self.is_bind_checkbox.isChecked()
        self.to_skin_cage_label.setEnabled(is_surface and is_bind)
        self.to_skin_cage_checkbox.setEnabled(is_surface and is_bind)

        is_to_skin_cage = self.to_skin_cage_checkbox.isChecked()
        self.to_skin_cage_div_label.setEnabled(is_surface and is_bind and is_to_skin_cage)
        self.to_skin_cage_spinBox.setEnabled(is_surface and is_bind and is_to_skin_cage)

    def _change_reference_object_mode(self):
        """Update UI state based on surface axis selection."""
        axis_index = self.surface_axis_combo.currentIndex()
        # Surface Normal=5, Surface Binormal=6, Mesh Normal=7, Mesh Binormal=8
        needs_reference = axis_index >= 5

        self.reference_object_label.setEnabled(needs_reference)
        self.reference_object_line_edit.setEnabled(needs_reference)

    def _set_reference_object_from_selection(self):
        """Set reference object from current Maya selection with node type validation."""
        selection = cmds.ls(selection=True, transforms=True)
        if not selection:
            cmds.warning("Select a single transform to set as reference.")
            return

        selected_node = selection[0]

        # Get current axis type index
        axis_index = self.surface_axis_combo.currentIndex()

        # Determine required node type based on axis
        # Surface Normal=5, Surface Binormal=6, Mesh Normal=7, Mesh Binormal=8
        required_type = None
        if axis_index in [5, 6]:  # Surface Normal/Binormal
            required_type = "nurbsSurface"
        elif axis_index in [7, 8]:  # Mesh Normal/Binormal
            required_type = "mesh"

        if required_type:
            # Get shape node
            shapes = cmds.listRelatives(selected_node, shapes=True, noIntermediate=True)
            if not shapes:
                cmds.warning("Invalid Node", f"Selected node '{selected_node}' has no shape node.")
                return

            # Check if shape is the required type
            shape_type = cmds.nodeType(shapes[0])
            if shape_type != required_type:
                cmds.warning(f"Invalid node type: '{selected_node}' is '{shape_type}', expected '{required_type}'")
                return

        # Valid node - set in line edit
        self.reference_object_line_edit.setText(shapes[0])
        logger.debug(f"Set reference object: {shapes[0]}")

    @error_handler
    @undo_chunk("Create Curve Surface")
    def create_curve_surface(self):
        """Create a curve or surface based on UI settings."""
        # Get the options.
        # Basic Options
        select_type = self.select_type_combo.currentText().lower()

        object_type_map = {"Curve": "nurbsCurve", "Surface": "nurbsSurface", "Mesh": "mesh"}
        object_type = object_type_map[self.object_type_combo.currentText()]

        is_bind = self.is_bind_checkbox.isChecked()
        to_skin_cage = self.to_skin_cage_checkbox.isChecked()
        skin_cage_levels = self.to_skin_cage_spinBox.value()

        # Select Options
        skip = self.skip_spin_box.value()
        reverse = self.reverse_checkbox.isChecked()

        select_options = {"skip": skip, "reverse": reverse}

        # Curve Options
        degree = self.degree_button_group.checkedId()
        center = self.center_checkbox.isChecked()
        close = self.close_checkbox.isChecked()
        divisions = self.divisions_spin_box.value()
        surface_width = self.surface_width_spin_box.value()
        surface_width_center = self.surface_width_center_spin_box.value()

        if surface_width == 0.0:
            surface_width = 1e-3

        # Convert UI text to axis constant
        axis_map = {
            "x": "x",
            "y": "y",
            "z": "z",
            "normal": "normal",
            "binormal": "binormal",
            "surface normal": "surfaceNormal",
            "surface binormal": "surfaceBinormal",
            "mesh normal": "meshNormal",
            "mesh binormal": "meshBinormal",
        }
        surface_axis = axis_map[self.surface_axis_combo.currentText().lower()]

        # Get reference object
        reference_object = self.reference_object_line_edit.text().strip() or None

        create_options = {
            "degree": degree,
            "center": center,
            "close": close,
            "divisions": divisions,
            "surface_width": surface_width,
            "surface_width_center": surface_width_center,
            "surface_axis": surface_axis,
            "reference_object": reference_object,
        }

        # Bind Options
        method = self.bind_method_combo.currentText().lower()
        smooth_levels = self.smooth_level_spin_box.value()
        parent_influence_ratio = self.parent_influence_spin_box.value()
        remove_end = self.remove_end_checkbox.isChecked()

        bind_options = {
            "method": method,
            "smooth_iterations": smooth_levels,
            "parent_influence_ratio": parent_influence_ratio,
            "remove_end": remove_end,
        }

        # Create the curve surface
        result_objs = command.main(
            select_type=select_type,
            object_type=object_type,
            is_bind=is_bind,
            to_skin_cage=to_skin_cage,
            skin_cage_division_levels=skin_cage_levels,
            select_options=select_options,
            create_options=create_options,
            bind_options=bind_options,
        )

        cmds.select(result_objs, r=True)

    @error_handler
    @undo_chunk("Move CVs Position")
    @repeatable("Move CVs Position")
    def move_cvs_position(self):
        """Move curve CVs to vertex positions."""
        cvs = cmds.filterExpand(sm=28, ex=True)
        if not cvs:
            cmds.error("Select nurbsCurve CVs.")
            return

        for cv in cvs:
            command.move_cv_positions(cv)

    @error_handler
    @undo_chunk("Create Curve to Vertices")
    @repeatable("Create Curve to Vertices")
    def create_curve_to_vertices(self):
        """Create curves from selected vertices."""
        vertices = cmds.filterExpand(sm=31, ex=True)
        if not vertices:
            cmds.error("Select vertices.")
            return

        comp_filter = ComponentFilter(vertices)

        result_curves = []
        for mesh, components in comp_filter.get_components(component_type=["vertex"]).items():
            curve = command.create_curve_from_vertices(components)
            result_curves.append(curve)

            logger.debug(f"Created curve: {mesh} --> {curve}")

        cmds.select(result_curves, r=True)

    @error_handler
    @undo_chunk("Create Curve on Surface")
    @repeatable("Create Curve on Surface")
    def create_curve_on_surface(self, surface_axis: str):
        """
        Create a curve on a NURBS surface.

        Args:
            surface_axis: Surface direction ("u" or "v")
        """
        nurbs_surfaces = cmds.ls(sl=True, dag=True, type="nurbsSurface")
        if not nurbs_surfaces:
            cmds.error("Select nurbsSurface.")
            return

        for nurbs_surface in nurbs_surfaces:
            command.create_curve_on_surface(nurbs_surface, surface_axis)

    def closeEvent(self, event):
        """
        Handle window close event.

        Args:
            event: Close event
        """
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """
    Show the Curve/Surface Creator UI (entry point).

    Returns:
        MainWindow: The main window instance
    """
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
    _instance.adjustSize()  # Fit to minimum size
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
