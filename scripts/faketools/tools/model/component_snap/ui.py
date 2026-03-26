"""Component Snap UI layer."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import BaseMainWindow, ToolSettingsManager, error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Component Snap Main Window."""

    _METHODS = ("index", "closest_position", "nearest_component")
    _METHOD_LABELS = ("Index", "Closest Position", "Nearest Component")

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(
            parent=parent,
            object_name="ComponentSnapMainWindow",
            window_title="Component Snap",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="component_snap", category="model")
        self._setup_ui()
        self._restore_settings()

    def _setup_ui(self):
        """Build the UI."""
        # Space mode
        space_layout = QHBoxLayout()
        self.world_button = QPushButton("World")
        self.local_button = QPushButton("Local")
        self.world_button.setCheckable(True)
        self.local_button.setCheckable(True)
        self.world_button.setChecked(True)

        self.space_group = QButtonGroup(self)
        self.space_group.addButton(self.world_button, 0)
        self.space_group.addButton(self.local_button, 1)

        space_layout.addWidget(self.world_button)
        space_layout.addWidget(self.local_button)
        self.central_layout.addLayout(space_layout)

        # Matching method
        method_widget = QWidget()
        method_layout = QVBoxLayout(method_widget)
        method_layout.setContentsMargins(0, 0, 0, 0)

        self.method_group = QButtonGroup(self)
        for i, label in enumerate(self._METHOD_LABELS):
            radio = QRadioButton(label)
            if i == 0:
                radio.setChecked(True)
            self.method_group.addButton(radio, i)
            method_layout.addWidget(radio)

        self.central_layout.addWidget(method_widget)

        # Execute
        self.execute_button = QPushButton("Execute")
        self.execute_button.clicked.connect(self._on_execute)
        self.central_layout.addWidget(self.execute_button)

        # Blend
        self.blend_button = QPushButton("Blend")
        self.blend_button.clicked.connect(self._on_blend)
        self.central_layout.addWidget(self.blend_button)

        # Blend value
        blend_layout = QHBoxLayout()
        self.blend_spin = QDoubleSpinBox()
        self.blend_spin.setRange(0.0, 100.0)
        self.blend_spin.setValue(50.0)
        self.blend_spin.setSingleStep(1.0)
        self.blend_spin.setDecimals(2)
        blend_layout.addWidget(self.blend_spin)
        blend_layout.addWidget(QLabel("%"))
        self.central_layout.addLayout(blend_layout)

        # Adjust size
        self.adjustSize()
        width = self.minimumSizeHint().width()
        height = self.minimumSizeHint().height()
        self.resize(width, height)

    def _get_space(self) -> str:
        """Get the current space mode.

        Returns:
            str: "world" or "local".
        """
        return "world" if self.space_group.checkedId() == 0 else "local"

    def _get_method(self) -> str:
        """Get the current matching method.

        Returns:
            str: Matching method key.
        """
        return self._METHODS[self.method_group.checkedId()]

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
    @undo_chunk("Component Snap: Execute")
    def _on_execute(self):
        """Execute full snap (100%)."""
        self._run_snap(blend=1.0)

    @error_handler
    @undo_chunk("Component Snap: Blend")
    def _on_blend(self):
        """Execute blend snap with the specified percentage."""
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
            "space": self.space_group.checkedId(),
            "method": self.method_group.checkedId(),
            "blend_value": self.blend_spin.value(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI.

        Args:
            settings_data: Settings data to apply.
        """
        if "space" in settings_data:
            button = self.space_group.button(settings_data["space"])
            if button:
                button.setChecked(True)
        if "method" in settings_data:
            button = self.method_group.button(settings_data["method"])
            if button:
                button.setChecked(True)
        if "blend_value" in settings_data:
            self.blend_spin.setValue(settings_data["blend_value"])

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
