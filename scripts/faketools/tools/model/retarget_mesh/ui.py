"""Re target mesh tool."""

from functools import partial
from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import maya_decorator
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_dialog import confirm_dialog, show_info_dialog
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.preset_edit_dialog import PresetEditDialog
from ....lib_ui.preset_save_dialog import PresetSaveDialog
from ....lib_ui.qt_compat import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStringListModel,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import extra_widgets, nodeAttr_widgets
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Re target Mesh Main Window."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="RetargetMeshMainWindow",
            window_title="Retarget Mesh",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="retarget_mesh", category="model")

        # Setup UI
        self.setup_ui()

        # Initialize UI state
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Menu
        self._add_preset_menu()

        # Mesh selection widgets
        self.src_node_widgets = SetNodeWidgets("Set Source Mesh")
        self.central_layout.addWidget(self.src_node_widgets)

        self.dst_node_widgets = SetNodesWidgets("Set Destination Mesh")
        self.central_layout.addWidget(self.dst_node_widgets)

        self.trg_node_widgets = SetNodesWidgets("Set Target Mesh")
        self.central_layout.addWidget(self.trg_node_widgets)

        # Basic options
        self.is_create_checkbox = QCheckBox("Create New Mesh")
        self.central_layout.addWidget(self.is_create_checkbox)

        separator1 = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator1)

        # Advanced parameters group
        params_group = QGroupBox("Advanced Parameters")
        params_layout = QVBoxLayout()

        # Radius Multiplier
        self.radius_multiplier_widget = FloatSpinBoxWidget(
            "Radius Multiplier",
            min_value=0.5,
            max_value=10.0,
            default_value=1.0,
            decimals=1,
            tooltip="Search radius multiplier. Increase for small/distant meshes.",
        )
        params_layout.addWidget(self.radius_multiplier_widget)

        # Max Vertices
        self.max_vertices_widget = IntSpinBoxWidget(
            "Max Vertices",
            min_value=100,
            max_value=10000,
            default_value=1000,
            tooltip="Maximum vertices per cluster. Lower values split large meshes into smaller groups.",
        )
        params_layout.addWidget(self.max_vertices_widget)

        # Min Source Vertices
        self.min_src_vertices_widget = IntSpinBoxWidget(
            "Min Source Vertices",
            min_value=4,
            max_value=100,
            default_value=10,
            tooltip="Minimum source vertices for RBF deformation. Higher values improve accuracy but may be slower.",
        )
        params_layout.addWidget(self.min_src_vertices_widget)

        # Max Iterations
        self.max_iterations_widget = IntSpinBoxWidget(
            "Max Iterations", min_value=1, max_value=20, default_value=10, tooltip="Maximum iterations for adaptive radius adjustment."
        )
        params_layout.addWidget(self.max_iterations_widget)

        params_group.setLayout(params_layout)
        self.central_layout.addWidget(params_group)

        separator2 = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator2)

        # Execute button
        button = QPushButton("Retarget Mesh")
        self.central_layout.addWidget(button)

        # Signal & Slot
        button.clicked.connect(self._retarget_mesh)

    @maya_decorator.undo_chunk("Retarget Mesh")
    @maya_decorator.error_handler
    def _retarget_mesh(self):
        """Retarget the mesh."""
        src_mesh = self.src_node_widgets.get_node()
        dst_meshes = self.dst_node_widgets.get_nodes()
        trg_meshes = self.trg_node_widgets.get_nodes()
        is_create = self.is_create_checkbox.isChecked()

        # Get parameter values
        radius_multiplier = self.radius_multiplier_widget.get_value()
        max_vertices = self.max_vertices_widget.get_value()
        min_src_vertices = self.min_src_vertices_widget.get_value()
        max_iterations = self.max_iterations_widget.get_value()

        command.retarget_mesh(
            src_mesh,
            dst_meshes,
            trg_meshes,
            is_create=is_create,
            radius_multiplier=radius_multiplier,
            max_vertices=max_vertices,
            min_src_vertices=min_src_vertices,
            max_iterations=max_iterations,
        )

    def _add_preset_menu(self):
        """Add the preset menu."""
        # Preset menu
        preset_menu = self.menuBar().addMenu("Preset")

        action = preset_menu.addAction("Save Settings...")
        action.triggered.connect(self._on_save_preset)

        action = preset_menu.addAction("Edit Settings...")
        action.triggered.connect(self._on_edit_presets)

        action = preset_menu.addAction("Reset Settings...")
        action.triggered.connect(self._on_reset_settings)

        preset_menu.addSeparator()

        # Preset list will be populated dynamically
        self.preset_menu = preset_menu
        self._update_preset_menu()

    def _update_preset_menu(self):
        """Update the preset menu with current presets."""
        # Remove all actions after the separator
        actions = self.preset_menu.actions()
        separator_index = -1
        for i, action in enumerate(actions):
            if action.isSeparator():
                separator_index = i
                break

        # Remove preset actions (everything after separator)
        if separator_index >= 0:
            for action in actions[separator_index + 1 :]:
                self.preset_menu.removeAction(action)

        # Add preset actions
        presets = self.settings.list_presets()

        # Ensure "default" is always first
        if "default" in presets:
            presets.remove("default")
            presets.insert(0, "default")

        for preset_name in presets:
            action = self.preset_menu.addAction(preset_name)
            action.triggered.connect(partial(self._on_load_preset, preset_name))

        logger.debug(f"Updated preset menu with {len(presets)} presets")

    def _on_save_preset(self):
        """Handle Save Settings menu action."""
        dialog = PresetSaveDialog(self.settings, parent=self)
        if dialog.exec():
            preset_name = dialog.get_preset_name()
            if preset_name:
                settings_data = self._collect_settings()
                self.settings.save_settings(settings_data, preset_name)
                self._update_preset_menu()
                show_info_dialog("Preset Saved", f"Settings saved to preset '{preset_name}'")
                logger.info(f"Saved preset: {preset_name}")

    def _on_edit_presets(self):
        """Handle Edit Settings menu action."""
        dialog = PresetEditDialog(self.settings, parent=self)
        dialog.exec()
        self._update_preset_menu()

    def _on_reset_settings(self):
        """Handle Reset Settings menu action."""
        result = confirm_dialog(title="Reset Settings", message="Reset all settings to default values?")

        if result:
            # Load empty settings to reset to defaults
            self._apply_settings({})
            logger.info("Settings reset to defaults")

    def _on_load_preset(self, preset_name: str):
        """Handle preset menu action.

        Args:
            preset_name (str): Name of the preset to load
        """
        settings_data = self.settings.load_settings(preset_name)
        if settings_data:
            self._apply_settings(settings_data)
            logger.info(f"Loaded preset: {preset_name}")

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)
        else:
            # First time: set minimum height
            self.adjustSize()
            # Keep only the width from sizeHint, use minimum height
            width = self.sizeHint().width()
            height = self.minimumSizeHint().height()
            self.resize(width, height)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def _collect_settings(self) -> dict:
        """Collect current UI settings.

        Returns:
            dict: Settings data
        """
        return {
            "is_create": self.is_create_checkbox.isChecked(),
            "radius_multiplier": self.radius_multiplier_widget.get_value(),
            "max_vertices": self.max_vertices_widget.get_value(),
            "min_src_vertices": self.min_src_vertices_widget.get_value(),
            "max_iterations": self.max_iterations_widget.get_value(),
            "window_geometry": {
                "size": [self.width(), self.height()],  # Save for width only, height will be ignored
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI.

        Args:
            settings_data (dict): Settings data to apply
        """
        # Apply settings with defaults
        self.is_create_checkbox.setChecked(settings_data.get("is_create", False))
        self.radius_multiplier_widget.set_value(settings_data.get("radius_multiplier", 1.0))
        self.max_vertices_widget.set_value(settings_data.get("max_vertices", 1000))
        self.min_src_vertices_widget.set_value(settings_data.get("min_src_vertices", 10))
        self.max_iterations_widget.set_value(settings_data.get("max_iterations", 10))

        # Always use minimum height
        self.adjustSize()
        min_height = self.minimumSizeHint().height()

        if "window_geometry" in settings_data and "size" in settings_data["window_geometry"]:
            # Restore width but use minimum height
            saved_width = settings_data["window_geometry"]["size"][0]
            self.resize(saved_width, min_height)
        else:
            # Use sizeHint width with minimum height
            width = self.sizeHint().width()
            self.resize(width, min_height)

        # Restore position if saved
        if "window_geometry" in settings_data and "position" in settings_data["window_geometry"]:
            self.move(*settings_data["window_geometry"]["position"])

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


class FloatSpinBoxWidget(QWidget):
    """Float spinbox widget with label."""

    def __init__(
        self,
        label: str,
        min_value: float = 0.0,
        max_value: float = 10.0,
        default_value: float = 1.0,
        decimals: int = 2,
        tooltip: str = "",
        parent=None,
    ):
        """Constructor."""
        super().__init__(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label_widget = QLabel(label + ":")
        label_widget.setMinimumWidth(150)
        label_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label_widget)

        # Spinbox
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setMinimum(min_value)
        self.spinbox.setMaximum(max_value)
        self.spinbox.setValue(default_value)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSingleStep(0.1 if decimals > 0 else 1.0)
        self.spinbox.setMinimumWidth(80)
        if tooltip:
            self.spinbox.setToolTip(tooltip)
        layout.addWidget(self.spinbox)

        layout.addStretch()

        self.setLayout(layout)

    def get_value(self) -> float:
        """Get the current value."""
        return self.spinbox.value()

    def set_value(self, value: float):
        """Set the value."""
        self.spinbox.setValue(value)


class IntSpinBoxWidget(QWidget):
    """Integer spinbox widget with label."""

    def __init__(self, label: str, min_value: int = 0, max_value: int = 100, default_value: int = 10, tooltip: str = "", parent=None):
        """Constructor."""
        super().__init__(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label_widget = QLabel(label + ":")
        label_widget.setMinimumWidth(150)
        label_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label_widget)

        # Spinbox
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(min_value)
        self.spinbox.setMaximum(max_value)
        self.spinbox.setValue(default_value)
        self.spinbox.setMinimumWidth(80)
        if tooltip:
            self.spinbox.setToolTip(tooltip)
        layout.addWidget(self.spinbox)

        layout.addStretch()

        self.setLayout(layout)

    def get_value(self) -> int:
        """Get the current value."""
        return self.spinbox.value()

    def set_value(self, value: int):
        """Set the value."""
        self.spinbox.setValue(value)


class SetNodeWidgets(QWidget):
    """Set Node Widgets."""

    def __init__(self, label: str, parent=None):
        """Constructor."""
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        button = QPushButton(label)
        layout.addWidget(button)

        self.node_field = QLineEdit()
        self.node_field.setReadOnly(True)
        layout.addWidget(self.node_field)

        self.setLayout(layout)

        button.clicked.connect(self._set_node)

    def _set_node(self):
        """Set the node."""
        sel_nodes = cmds.ls(sl=True, dag=True, type="mesh")
        if not sel_nodes:
            cmds.warning("Please select a transform node.")
            return

        self.node_field.setText(sel_nodes[0])

    def get_node(self):
        """Get the node."""
        return self.node_field.text()


class SetNodesWidgets(QWidget):
    """Set Nodes Widgets."""

    def __init__(self, label: str, parent=None):
        """Constructor."""
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        button = QPushButton(label)
        layout.addWidget(button)

        self.node_list_view = nodeAttr_widgets.NodeListView()
        self.model = QStringListModel()
        self.node_list_view.setModel(self.model)
        layout.addWidget(self.node_list_view)

        self.setLayout(layout)

        button.clicked.connect(self._set_nodes)

    def _set_nodes(self):
        """Set the nodes."""
        sel_nodes = cmds.ls(sl=True, dag=True, type="mesh")
        if not sel_nodes:
            cmds.warning("Please select transform nodes.")
            return

        self.model.setStringList(sel_nodes)

    def get_nodes(self):
        """Get the nodes."""
        return self.model.stringList()


def show_ui():
    """
    Show the Re target Mesh UI.

    Creates or raises the main window.

    Returns:
        MainWindow: The main window instance
    """
    global _instance

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
