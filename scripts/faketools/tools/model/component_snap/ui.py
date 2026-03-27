"""Component Snap UI layer."""

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds

from ....lib_ui import BaseFramelessWindow, ToolSettingsManager, error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QComboBox, QDoubleSpinBox, QSlider, Qt
from ....lib_ui.widgets import IconButton, IconToggleButton, extra_widgets
from . import command

_IMAGES_DIR = Path(__file__).parent / "images"

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseFramelessWindow):
    """Component Snap Main Window."""

    _METHODS = ("index", "closest_position", "nearest_component")
    _METHOD_LABELS = ("Index", "Closest Position", "Nearest Component")

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="ComponentSnapMainWindow",
            window_title="Component Snap",
            central_layout="horizontal",
            resizable=True,
        )

        self.settings = ToolSettingsManager(tool_name="component_snap", category="model")
        self._setup_ui()
        self._restore_settings()

    def _setup_ui(self):
        """Build the UI."""
        # Method dropdown
        self.method_combo = QComboBox()
        self.method_combo.addItems(self._METHOD_LABELS)
        self.central_layout.addWidget(self.method_combo)

        separator = extra_widgets.VerticalSeparator()
        self.central_layout.addWidget(separator)

        # World/Local toggle
        self.space_toggle = IconToggleButton(icon_on="world", icon_off="local", icon_dir=_IMAGES_DIR)
        self.space_toggle.setChecked(True)
        self.space_toggle.setToolTip("World Space / Local Space")
        self.central_layout.addWidget(self.space_toggle)

        separator = extra_widgets.VerticalSeparator()
        self.central_layout.addWidget(separator)

        # Blend spinbox
        self.blend_spin = QDoubleSpinBox()
        self.blend_spin.setRange(0.0, 100.0)
        self.blend_spin.setValue(100.0)
        self.blend_spin.setSingleStep(1.0)
        self.blend_spin.setDecimals(2)
        self.blend_spin.setFixedWidth(int(self.blend_spin.sizeHint().width() * 1.2))
        self.central_layout.addWidget(self.blend_spin)

        # Blend slider
        self.blend_slider = QSlider(Qt.Horizontal)
        self.blend_slider.setRange(0, 10000)
        self.blend_slider.setValue(10000)
        self.central_layout.addWidget(self.blend_slider, stretch=1)

        # Sync slider <-> spinbox
        self.blend_slider.valueChanged.connect(self._on_slider_changed)
        self.blend_spin.valueChanged.connect(self._on_spin_changed)

        separator = extra_widgets.VerticalSeparator()
        self.central_layout.addWidget(separator)

        # Blend button
        self.blend_button = IconButton(icon_name="blend", icon_dir=_IMAGES_DIR)
        self.blend_button.setToolTip("Blend Snap")
        self.blend_button.clicked.connect(self._on_blend)
        self.central_layout.addWidget(self.blend_button)

        # Snap (100%) button
        self.snap_button = IconButton(icon_name="snap", icon_dir=_IMAGES_DIR)
        self.snap_button.setToolTip("Snap (100%)")
        self.snap_button.clicked.connect(self._on_snap)
        self.central_layout.addWidget(self.snap_button)

        # Rearrange button height to match spinbox
        spin_height = self.blend_spin.sizeHint().height()
        self.space_toggle.setMinimumHeight(spin_height)

        # Adjust size
        self.adjustSize()
        width = self.sizeHint().width()
        height = self.minimumSizeHint().height()
        self.resize(width, height)

    def _on_slider_changed(self, value: int):
        """Sync spinbox from slider value.

        Args:
            value: Slider value (0-10000).
        """
        self.blend_spin.blockSignals(True)
        self.blend_spin.setValue(value / 100.0)
        self.blend_spin.blockSignals(False)

    def _on_spin_changed(self, value: float):
        """Sync slider from spinbox value.

        Args:
            value: Spinbox value (0.0-100.0).
        """
        self.blend_slider.blockSignals(True)
        self.blend_slider.setValue(int(value * 100))
        self.blend_slider.blockSignals(False)

    def _get_space(self) -> str:
        """Get the current space mode.

        Returns:
            str: "world" or "local".
        """
        return "world" if self.space_toggle.isChecked() else "local"

    def _get_method(self) -> str:
        """Get the current matching method.

        Returns:
            str: Matching method key.
        """
        return self._METHODS[self.method_combo.currentIndex()]

    def _run_snap(self, blend: float) -> None:
        """Run the snap operation.

        Args:
            blend: Blend rate (0.0 to 1.0).
        """
        source_data = command.get_selection_data()
        logger.debug(f"source_data: {source_data}")
        if not source_data:
            cmds.warning("No source components selected.")
            return

        # Resolve source node long names to exclude from target search
        source_long_names = set()
        for node_name in source_data:
            long_names = cmds.ls(node_name, long=True)
            if long_names:
                source_long_names.add(long_names[0])

        # Find target: a mesh transform in the selection that is NOT a source node
        selection = cmds.ls(selection=True, long=True) or []
        target_mesh = None
        for node in selection:
            # Skip component selections (e.g. "pSphere1.vtx[0]")
            if "." in node.split("|")[-1]:
                continue
            if cmds.nodeType(node) == "transform":
                shapes = cmds.listRelatives(node, shapes=True, type="mesh")
                if shapes and node not in source_long_names:
                    target_mesh = node
                    break

        if target_mesh is None:
            cmds.warning("No target mesh selected. Select a target mesh as an object.")
            return

        space = self._get_space()
        method = self._get_method()
        total = 0

        for source_node, node_components in source_data.items():
            logger.debug(f"snap: source={source_node}, target={target_mesh}, count={len(node_components)}")
            count = command.snap(
                components=node_components,
                target_mesh=target_mesh,
                method=method,
                space=space,
                blend=blend,
            )
            total += count

        logger.info(f"Component Snap: {total} components processed.")

    @error_handler
    @undo_chunk("Component Snap")
    def _on_snap(self):
        """Execute full snap (100%)."""
        self._run_snap(blend=1.0)

    @error_handler
    @undo_chunk("Component Snap: Blend")
    def _on_blend(self):
        """Execute blend snap with the current percentage."""
        blend = self.blend_spin.value() / 100.0
        self._run_snap(blend=blend)

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def _collect_settings(self) -> dict:
        """Collect current UI settings.

        Returns:
            dict: Settings data.
        """
        return {
            "method": self.method_combo.currentIndex(),
            "blend_value": self.blend_spin.value(),
            "world_space": self.space_toggle.isChecked(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI.

        Args:
            settings_data: Settings data to apply.
        """
        if "method" in settings_data:
            self.method_combo.setCurrentIndex(settings_data["method"])
        if "blend_value" in settings_data:
            self.blend_spin.setValue(settings_data["blend_value"])
        if "world_space" in settings_data:
            self.space_toggle.setChecked(settings_data["world_space"])

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Component Snap UI.

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
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
