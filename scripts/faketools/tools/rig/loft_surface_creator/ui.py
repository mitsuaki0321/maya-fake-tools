"""Loft Surface Creator UI."""

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
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    Qt,
    QVBoxLayout,
)
from ....lib_ui.widgets import extra_widgets
from . import command

logger = getLogger(__name__)
_instance = None  # Global instance for singleton pattern

# Input mode constants
MODE_ROOT_JOINTS = 0
MODE_DIRECT_CHAINS = 1


class MainWindow(BaseMainWindow):
    """Loft Surface Creator Main Window.

    Provides UI for creating lofted surfaces from joint chains
    with various options for divisions, bindings, and more.
    """

    def __init__(self, parent=None):
        """Initialize the Loft Surface Creator window.

        Args:
            parent: Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="LoftSurfaceCreatorMainWindow",
            window_title="Loft Surface Creator",
            central_layout="vertical",
        )

        # Internal data storage
        self._root_joints: list[str] = []
        self._joint_chains: list[list[str]] = []

        self.settings = ToolSettingsManager(tool_name="loft_surface_creator", category="rig")

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

        # Input Mode Selection
        label = QLabel("Input Mode:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.input_mode_combo = QComboBox()
        self.input_mode_combo.addItems(["Root Joints", "Direct Chains"])
        self.input_mode_combo.setToolTip(
            "Root Joints: Auto-expand joint chains from root joints\nDirect Chains: Manually specify each chain (column)"
        )
        layout.addWidget(self.input_mode_combo, row, 1, 1, 3)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Joint Input Section
        label = QLabel("Joints:", alignment=Qt.AlignRight | Qt.AlignTop)
        layout.addWidget(label, row, 0)

        joints_layout = QVBoxLayout()

        self.joints_list = QListWidget()
        self.joints_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.joints_list.setMinimumHeight(100)
        joints_layout.addWidget(self.joints_list)

        # Add/Remove buttons
        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Selected")
        self.add_button.clicked.connect(self._add_joints)
        buttons_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_joints)
        buttons_layout.addWidget(self.remove_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_joints)
        buttons_layout.addWidget(self.clear_button)

        joints_layout.addLayout(buttons_layout)
        layout.addLayout(joints_layout, row, 1, 1, 3)
        row += 1

        # Skip (only for Root Joints mode)
        self.skip_label = QLabel("Skip:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.skip_label, row, 0)

        self.skip_spin = QSpinBox()
        self.skip_spin.setRange(0, 100)
        self.skip_spin.setValue(0)
        self.skip_spin.setToolTip("Joints to skip in each chain (Root Joints mode only)")
        layout.addWidget(self.skip_spin, row, 1)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Surface Options
        label = QLabel("Output:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.output_type_combo = QComboBox()
        self.output_type_combo.addItems(["NURBS Surface", "Mesh"])
        layout.addWidget(self.output_type_combo, row, 1)
        row += 1

        # Surface Divisions
        label = QLabel("Surface Div:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.surface_divisions_spin = QSpinBox()
        self.surface_divisions_spin.setRange(0, 100)
        self.surface_divisions_spin.setValue(0)
        self.surface_divisions_spin.setToolTip("Additional divisions between curves in loft direction")
        layout.addWidget(self.surface_divisions_spin, row, 1)

        self.close_checkbox = QCheckBox("Close")
        layout.addWidget(self.close_checkbox, row, 2)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Curve Options
        label = QLabel("Curve Div:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.curve_divisions_spin = QSpinBox()
        self.curve_divisions_spin.setRange(0, 100)
        self.curve_divisions_spin.setValue(0)
        self.curve_divisions_spin.setToolTip("CVs to insert between joint positions")
        layout.addWidget(self.curve_divisions_spin, row, 1)
        row += 1

        # Center checkbox
        label = QLabel("Options:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.center_checkbox = QCheckBox("Center")
        self.center_checkbox.setToolTip("Center cubic curve CVs")
        layout.addWidget(self.center_checkbox, row, 1)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Bind Options
        label = QLabel("Is Bind:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label, row, 0)

        self.is_bind_checkbox = QCheckBox()
        layout.addWidget(self.is_bind_checkbox, row, 1)
        row += 1

        # Weight Method
        self.weight_method_label = QLabel("Weight Method:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.weight_method_label, row, 0)

        self.weight_method_combo = QComboBox()
        self.weight_method_combo.addItems(["Linear", "Ease", "Step"])
        layout.addWidget(self.weight_method_combo, row, 1, 1, 3)
        row += 1

        # Loft Weight Method
        self.loft_weight_method_label = QLabel("Loft Weight:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.loft_weight_method_label, row, 0)

        self.loft_weight_method_combo = QComboBox()
        self.loft_weight_method_combo.addItems(["Index", "Distance", "Projection"])
        self.loft_weight_method_combo.setToolTip(
            "Index: Index-based interpolation\nDistance: Distance along U=0 CVs\nProjection: Project onto AB line"
        )
        layout.addWidget(self.loft_weight_method_combo, row, 1, 1, 3)
        row += 1

        # Smooth Iterations
        self.smooth_label = QLabel("Smooth Iter:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.smooth_label, row, 0)

        self.smooth_spin = QSpinBox()
        self.smooth_spin.setRange(0, 100)
        self.smooth_spin.setValue(0)
        self.smooth_spin.setToolTip("Weight smoothing iterations (curve direction only)")
        layout.addWidget(self.smooth_spin, row, 1)
        row += 1

        # Parent Influence
        self.parent_influence_label = QLabel("Parent Influence:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.parent_influence_label, row, 0)

        self.parent_influence_spin = QDoubleSpinBox()
        self.parent_influence_spin.setRange(0.0, 1.0)
        self.parent_influence_spin.setSingleStep(0.1)
        self.parent_influence_spin.setValue(0.0)
        layout.addWidget(self.parent_influence_spin, row, 1)
        row += 1

        # Remove End
        self.remove_end_label = QLabel("Remove End:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.remove_end_label, row, 0)

        self.remove_end_checkbox = QCheckBox()
        self.remove_end_checkbox.setToolTip("Merge end joint weights to parent")
        layout.addWidget(self.remove_end_checkbox, row, 1)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Skin Cage Options
        self.to_skin_cage_label = QLabel("To Skin Cage:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.to_skin_cage_label, row, 0)

        self.to_skin_cage_checkbox = QCheckBox()
        self.to_skin_cage_checkbox.setToolTip("Convert to skin cage mesh (NURBS + Is Bind only)")
        layout.addWidget(self.to_skin_cage_checkbox, row, 1)
        row += 1

        self.skin_cage_div_label = QLabel("Cage Div Levels:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.skin_cage_div_label, row, 0)

        self.skin_cage_div_spin = QSpinBox()
        self.skin_cage_div_spin.setRange(1, 100)
        self.skin_cage_div_spin.setValue(1)
        layout.addWidget(self.skin_cage_div_spin, row, 1)
        row += 1

        h_line = extra_widgets.HorizontalSeparator()
        layout.addWidget(h_line, row, 0, 1, 4)
        row += 1

        # Create Button
        create_button = QPushButton("Create")
        layout.addWidget(create_button, row, 0, 1, 4)

        self.central_layout.addLayout(layout)

        # Signal & Slot
        self.input_mode_combo.currentIndexChanged.connect(self._change_input_mode)
        self.is_bind_checkbox.stateChanged.connect(self._change_bind_mode)
        self.output_type_combo.currentIndexChanged.connect(self._change_output_mode)
        self.to_skin_cage_checkbox.stateChanged.connect(self._change_skin_cage_mode)

        create_button.clicked.connect(self.create_loft_surface)

        # Initialize UI state
        self._change_input_mode()
        self._change_bind_mode()
        self._change_output_mode()

    def _change_input_mode(self):
        """Update UI state based on input mode selection."""
        mode = self.input_mode_combo.currentIndex()

        # Skip is only available in Root Joints mode
        is_root_mode = mode == MODE_ROOT_JOINTS
        self.skip_label.setEnabled(is_root_mode)
        self.skip_spin.setEnabled(is_root_mode)

        # Update button text based on mode
        if is_root_mode:
            self.add_button.setText("Add Selected")
            self.add_button.setToolTip("Add selected joints as root joints")
        else:
            self.add_button.setText("Add Chain")
            self.add_button.setToolTip("Add selected joints as a new chain (column)")

        # Refresh list display
        self._refresh_list_display()

    def _add_joints(self):
        """Add joints based on current mode."""
        mode = self.input_mode_combo.currentIndex()

        if mode == MODE_ROOT_JOINTS:
            self._add_root_joints()
        else:
            self._add_chain()

    def _add_root_joints(self):
        """Add selected joints as root joints."""
        selection = cmds.ls(selection=True, type="joint")
        if not selection:
            cmds.warning("Select joint(s) to add.")
            return

        for joint in selection:
            if joint not in self._root_joints:
                self._root_joints.append(joint)
                logger.debug(f"Added root joint: {joint}")

        self._refresh_list_display()

    def _add_chain(self):
        """Add selected joints as a chain (column)."""
        selection = cmds.ls(selection=True, type="joint")
        if not selection:
            cmds.warning("Select joint(s) to add as a chain.")
            return

        # Validate chain length if there are existing chains
        if self._joint_chains:
            expected_count = len(self._joint_chains[0])
            if len(selection) != expected_count:
                cmds.warning(f"Chain must have {expected_count} joints (same as existing chains). Selected: {len(selection)}")
                return

        self._joint_chains.append(list(selection))
        logger.debug(f"Added chain: {selection}")

        self._refresh_list_display()

    def _remove_joints(self):
        """Remove selected items from the list."""
        mode = self.input_mode_combo.currentIndex()
        selected_rows = sorted([item.row() for item in self.joints_list.selectedItems()], reverse=True)

        if mode == MODE_ROOT_JOINTS:
            for row in selected_rows:
                if 0 <= row < len(self._root_joints):
                    del self._root_joints[row]
        else:
            for row in selected_rows:
                if 0 <= row < len(self._joint_chains):
                    del self._joint_chains[row]

        self._refresh_list_display()

    def _clear_joints(self):
        """Clear all joints from the list."""
        mode = self.input_mode_combo.currentIndex()

        if mode == MODE_ROOT_JOINTS:
            self._root_joints.clear()
        else:
            self._joint_chains.clear()

        self._refresh_list_display()

    def _refresh_list_display(self):
        """Refresh the list widget display based on current data."""
        self.joints_list.clear()
        mode = self.input_mode_combo.currentIndex()

        if mode == MODE_ROOT_JOINTS:
            for joint in self._root_joints:
                self.joints_list.addItem(joint)
        else:
            for i, chain in enumerate(self._joint_chains):
                display_text = f"Chain {i}: [{', '.join(chain)}]"
                self.joints_list.addItem(display_text)

    def _change_bind_mode(self):
        """Update UI state based on bind checkbox state."""
        is_bind = self.is_bind_checkbox.isChecked()

        self.weight_method_label.setEnabled(is_bind)
        self.weight_method_combo.setEnabled(is_bind)

        self.loft_weight_method_label.setEnabled(is_bind)
        self.loft_weight_method_combo.setEnabled(is_bind)

        self.smooth_label.setEnabled(is_bind)
        self.smooth_spin.setEnabled(is_bind)

        self.parent_influence_label.setEnabled(is_bind)
        self.parent_influence_spin.setEnabled(is_bind)

        self.remove_end_label.setEnabled(is_bind)
        self.remove_end_checkbox.setEnabled(is_bind)

        # Skin cage only available for NURBS + is_bind
        is_nurbs = self.output_type_combo.currentIndex() == 0
        self.to_skin_cage_label.setEnabled(is_bind and is_nurbs)
        self.to_skin_cage_checkbox.setEnabled(is_bind and is_nurbs)

        self._change_skin_cage_mode()

    def _change_output_mode(self):
        """Update UI state based on output type selection."""
        is_nurbs = self.output_type_combo.currentIndex() == 0
        is_bind = self.is_bind_checkbox.isChecked()

        # Skin cage only available for NURBS + is_bind
        self.to_skin_cage_label.setEnabled(is_bind and is_nurbs)
        self.to_skin_cage_checkbox.setEnabled(is_bind and is_nurbs)

        self._change_skin_cage_mode()

    def _change_skin_cage_mode(self):
        """Update skin cage division controls state."""
        is_nurbs = self.output_type_combo.currentIndex() == 0
        is_bind = self.is_bind_checkbox.isChecked()
        is_skin_cage = self.to_skin_cage_checkbox.isChecked()

        enabled = is_bind and is_nurbs and is_skin_cage
        self.skin_cage_div_label.setEnabled(enabled)
        self.skin_cage_div_spin.setEnabled(enabled)

    def _apply_settings(self, settings_data: dict):
        """Apply settings data to UI.

        Args:
            settings_data (dict): Settings data to apply
        """
        # Restore input mode
        self.input_mode_combo.setCurrentIndex(settings_data.get("input_mode_index", 0))

        # Restore joints data
        self._root_joints = []
        for joint in settings_data.get("root_joints", []):
            if cmds.objExists(joint):
                self._root_joints.append(joint)

        self._joint_chains = []
        for chain in settings_data.get("joint_chains", []):
            valid_chain = [j for j in chain if cmds.objExists(j)]
            if valid_chain and len(valid_chain) == len(chain):
                self._joint_chains.append(valid_chain)

        self._refresh_list_display()

        self.skip_spin.setValue(settings_data.get("skip", 0))
        self.output_type_combo.setCurrentIndex(settings_data.get("output_type_index", 0))
        self.close_checkbox.setChecked(settings_data.get("close", False))
        self.surface_divisions_spin.setValue(settings_data.get("surface_divisions", 0))
        self.curve_divisions_spin.setValue(settings_data.get("curve_divisions", 0))
        self.center_checkbox.setChecked(settings_data.get("center", False))
        self.is_bind_checkbox.setChecked(settings_data.get("is_bind", False))
        self.weight_method_combo.setCurrentIndex(settings_data.get("weight_method_index", 0))
        self.loft_weight_method_combo.setCurrentIndex(settings_data.get("loft_weight_method_index", 0))
        self.smooth_spin.setValue(settings_data.get("smooth_iterations", 0))
        self.parent_influence_spin.setValue(settings_data.get("parent_influence_ratio", 0.0))
        self.remove_end_checkbox.setChecked(settings_data.get("remove_end", False))
        self.to_skin_cage_checkbox.setChecked(settings_data.get("to_skin_cage", False))
        self.skin_cage_div_spin.setValue(settings_data.get("skin_cage_division_levels", 1))

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _collect_settings(self) -> dict:
        """Collect current UI settings into a dictionary.

        Returns:
            dict: Current UI settings
        """
        return {
            "input_mode_index": self.input_mode_combo.currentIndex(),
            "root_joints": self._root_joints[:],
            "joint_chains": [chain[:] for chain in self._joint_chains],
            "skip": self.skip_spin.value(),
            "output_type_index": self.output_type_combo.currentIndex(),
            "close": self.close_checkbox.isChecked(),
            "surface_divisions": self.surface_divisions_spin.value(),
            "curve_divisions": self.curve_divisions_spin.value(),
            "center": self.center_checkbox.isChecked(),
            "is_bind": self.is_bind_checkbox.isChecked(),
            "weight_method_index": self.weight_method_combo.currentIndex(),
            "loft_weight_method_index": self.loft_weight_method_combo.currentIndex(),
            "smooth_iterations": self.smooth_spin.value(),
            "parent_influence_ratio": self.parent_influence_spin.value(),
            "remove_end": self.remove_end_checkbox.isChecked(),
            "to_skin_cage": self.to_skin_cage_checkbox.isChecked(),
            "skin_cage_division_levels": self.skin_cage_div_spin.value(),
        }

    def _save_settings(self):
        """Save UI settings to default preset."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    @error_handler
    @undo_chunk("Create Loft Surface")
    def create_loft_surface(self):
        """Create a lofted surface based on UI settings."""
        mode = self.input_mode_combo.currentIndex()

        # Get common options
        output_type_map = {0: "nurbsSurface", 1: "mesh"}
        output_type = output_type_map[self.output_type_combo.currentIndex()]

        close = self.close_checkbox.isChecked()
        surface_divisions = self.surface_divisions_spin.value()
        curve_divisions = self.curve_divisions_spin.value()
        center = self.center_checkbox.isChecked()
        is_bind = self.is_bind_checkbox.isChecked()

        weight_method_map = {0: "linear", 1: "ease", 2: "step"}
        weight_method = weight_method_map[self.weight_method_combo.currentIndex()]

        loft_weight_method_map = {0: "index", 1: "distance", 2: "projection"}
        loft_weight_method = loft_weight_method_map[self.loft_weight_method_combo.currentIndex()]

        smooth_iterations = self.smooth_spin.value()
        parent_influence_ratio = self.parent_influence_spin.value()
        remove_end = self.remove_end_checkbox.isChecked()
        to_skin_cage = self.to_skin_cage_checkbox.isChecked()
        skin_cage_division_levels = self.skin_cage_div_spin.value()

        # Create based on mode
        if mode == MODE_ROOT_JOINTS:
            # Validate root joints
            valid_joints = [j for j in self._root_joints if cmds.objExists(j)]
            if len(valid_joints) < 2:
                cmds.error("At least 2 root joints are required.")
                return

            skip = self.skip_spin.value()

            result, skin_cluster = command.create_from_root_joints(
                root_joints=valid_joints,
                skip=skip,
                close=close,
                output_type=output_type,
                surface_divisions=surface_divisions,
                center=center,
                curve_divisions=curve_divisions,
                is_bind=is_bind,
                weight_method=weight_method,
                smooth_iterations=smooth_iterations,
                parent_influence_ratio=parent_influence_ratio,
                remove_end=remove_end,
                loft_weight_method=loft_weight_method,
                to_skin_cage=to_skin_cage,
                skin_cage_division_levels=skin_cage_division_levels,
            )
        else:
            # Validate joint chains
            if len(self._joint_chains) < 2:
                cmds.error("At least 2 chains are required.")
                return

            # Validate each chain has at least 3 joints for degree 3 curves
            if len(self._joint_chains[0]) < 3:
                cmds.error("Each chain must have at least 3 joints for degree 3 curves.")
                return

            result, skin_cluster = command.main(
                joint_chains=self._joint_chains,
                close=close,
                output_type=output_type,
                surface_divisions=surface_divisions,
                center=center,
                curve_divisions=curve_divisions,
                is_bind=is_bind,
                weight_method=weight_method,
                smooth_iterations=smooth_iterations,
                parent_influence_ratio=parent_influence_ratio,
                remove_end=remove_end,
                loft_weight_method=loft_weight_method,
                to_skin_cage=to_skin_cage,
                skin_cage_division_levels=skin_cage_division_levels,
            )

        cmds.select(result, r=True)
        logger.info(f"Created loft surface: {result}")

    def showEvent(self, event):
        """Handle window show event.

        Args:
            event: Show event
        """
        super().showEvent(event)
        # Set minimum height on first show
        if not event.spontaneous():
            self.resize(self.width(), self.minimumSizeHint().height())

    def closeEvent(self, event):
        """Handle window close event.

        Args:
            event: Close event
        """
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Loft Surface Creator UI (entry point).

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
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
