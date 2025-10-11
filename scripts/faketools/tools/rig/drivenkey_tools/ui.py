"""Set driven key tools."""

from logging import getLogger
import os
import tempfile

import maya.cmds as cmds

from ....lib import lib_keyframe
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QCheckBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
from ....lib_ui.tool_data import ToolDataManager
from ....lib_ui.widgets import extra_widgets
from . import command

logger = getLogger(__name__)

_instance = None

TEMP_DIR = os.path.normpath(os.path.join(tempfile.gettempdir(), "drivenKeys"))
REGEX = ["(.*)(L)", r"\g<1>R"]


class MainWindow(BaseMainWindow):
    """
    Driven Key Tools Main Window.

    Provides UI for creating and managing driven keys in Maya.
    """

    def __init__(self, parent=None):
        """
        Initialize the Driven Key Tools window.

        Args:
            parent (QWidget | None): Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="DrivenKeyToolsMainWindow",
            window_title="Driven Key Tools",
            central_layout="vertical",
        )

        # UI settings
        self.settings = ToolOptionSettings(__name__)

        # Tool data manager for file operations
        tool_data_manager = ToolDataManager("drivenkey_tools", "rig")
        tool_data_manager.ensure_data_dir()
        self.root_path = tool_data_manager.get_data_dir()

        self.menu_bar = self.menuBar()
        self._add_menu()
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""

        one_to_all_button = QPushButton("One to All")
        self.central_layout.addWidget(one_to_all_button)

        one_to_replace_button = QPushButton("One to Replace")
        self.central_layout.addWidget(one_to_replace_button)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.regex_line_edit = QLineEdit()
        layout.addWidget(self.regex_line_edit)

        self.replace_to_line_edit = QLineEdit()
        layout.addWidget(self.replace_to_line_edit)

        self.central_layout.addLayout(layout)

        self.replace_driver_check_box = QCheckBox("Replace Driver")
        self.central_layout.addWidget(self.replace_driver_check_box)

        self.force_delete_check_box = QCheckBox("Force Delete Driven Key")
        self.central_layout.addWidget(self.force_delete_check_box)

        self.mirror_check_box = QCheckBox("Mirror")
        self.central_layout.addWidget(self.mirror_check_box)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.time_label = QLabel("Time")
        self.time_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.time_label, 0, 0)

        self.time_translate_check_box = MirrorCheckBox("T", "translate")
        layout.addWidget(self.time_translate_check_box, 1, 0)

        self.time_rotate_check_box = MirrorCheckBox("R", "rotate")
        layout.addWidget(self.time_rotate_check_box, 2, 0)

        self.time_scale_check_box = MirrorCheckBox("S", "scale")
        layout.addWidget(self.time_scale_check_box, 3, 0)

        self.value_label = QLabel("Value")
        self.value_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.value_label, 0, 1)

        self.value_translate_check_box = MirrorCheckBox("T", "translate")
        layout.addWidget(self.value_translate_check_box, 1, 1)

        self.value_rotate_check_box = MirrorCheckBox("R", "rotate")
        layout.addWidget(self.value_rotate_check_box, 2, 1)

        self.value_scale_check_box = MirrorCheckBox("S", "scale")
        layout.addWidget(self.value_scale_check_box, 3, 1)

        self.central_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        label = QLabel("Mirror Curve")
        label.setStyleSheet("font-weight: bold;")
        self.central_layout.addWidget(label)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        mirror_curve_time_button = QPushButton("Time")
        layout.addWidget(mirror_curve_time_button)

        mirror_curve_value_button = QPushButton("Value")
        layout.addWidget(mirror_curve_value_button)

        self.central_layout.addLayout(layout)

        # Signal & Slot
        one_to_all_button.clicked.connect(self._transfer_one_to_all)
        one_to_replace_button.clicked.connect(self._transfer_one_to_replace)
        mirror_curve_time_button.clicked.connect(self.mirror_curve_time)
        mirror_curve_value_button.clicked.connect(self.mirror_curve_value)
        self.mirror_check_box.stateChanged.connect(self._update_mirror_check_box)

        # Initial state
        self._update_mirror_check_box()

    def _add_menu(self):
        """Add the menu."""
        menu = self.menu_bar.addMenu("Export/Import")

        export_temp_action = menu.addAction("Export")
        export_temp_action.triggered.connect(self.export_to_temp)

        import_temp_action = menu.addAction("Import")
        import_temp_action.triggered.connect(self.import_from_temp)

        menu.addSeparator()

        export_file_action = menu.addAction("Export File")
        export_file_action.triggered.connect(self.export_to_file)

        import_file_action = menu.addAction("Import File")
        import_file_action.triggered.connect(self.import_from_file)

        menu = self.menu_bar.addMenu("Options")

        option_action = menu.addAction("Select Driven Key Nodes")
        option_action.triggered.connect(self.select_driven_key_nodes)

        option_action = menu.addAction("Cleanup Driven Key")
        option_action.triggered.connect(self.cleanup_driven_keys)

    @error_handler
    def export_to_temp(self):
        """Export driven key to temp directory."""
        temp_dir = TEMP_DIR
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        temp_file = os.path.join(temp_dir, "driven_key.json")
        command.DrivenKeyExportImport().export_driven_keys(temp_file)

    @error_handler
    @undo_chunk("Import Driven Key")
    def import_from_temp(self):
        """Import driven key from temp directory."""
        temp_file = os.path.join(TEMP_DIR, "driven_key.json")
        if not os.path.exists(temp_file):
            cmds.warning("Driven key file does not exists")
            return

        command.DrivenKeyExportImport().import_driven_keys(temp_file)

    @error_handler
    def export_to_file(self):
        """Export driven key to file."""
        file_dialog = QFileDialog(self, directory=str(self.root_path))
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("JSON Files (*.json)")
        file_dialog.setDefaultSuffix("json")

        if file_dialog.exec_() == QFileDialog.Accepted:
            file_path = file_dialog.selectedFiles()[0]
            command.DrivenKeyExportImport().export_driven_keys(file_path)

    @error_handler
    @undo_chunk("Import Driven Key")
    def import_from_file(self):
        """Import driven key from file."""
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
        file_dialog.setNameFilter("JSON Files (*.json)")

        if file_dialog.exec_() == QFileDialog.Accepted:
            file_path = file_dialog.selectedFiles()[0]
            command.DrivenKeyExportImport().import_driven_keys(file_path)

    @error_handler
    @undo_chunk("Transfer Driven Key")
    def _transfer_one_to_all(self):
        """Transfer driven key one to all."""
        command.DrivenKeyTransfer().one_to_all()

    @error_handler
    @undo_chunk("Transfer Driven Key")
    def _transfer_one_to_replace(self):
        """Transfer driven key one to replace."""
        regex = self.regex_line_edit.text()
        replace_to = self.replace_to_line_edit.text()
        replace_driver = self.replace_driver_check_box.isChecked()
        force_delete = self.force_delete_check_box.isChecked()

        replaced_nodes = command.DrivenKeyTransfer().one_to_replace(regex, replace_to, replace_driver, force_delete)
        cmds.select(replaced_nodes, r=True)

        if not self.mirror_check_box.isChecked():
            return

        time_attrs = self.time_translate_check_box.get_values() + self.time_rotate_check_box.get_values() + self.time_scale_check_box.get_values()
        value_attrs = self.value_translate_check_box.get_values() + self.value_rotate_check_box.get_values() + self.value_scale_check_box.get_values()

        if not time_attrs and not value_attrs:
            return

        for node in replaced_nodes:
            command.mirror_transform_anim_curve(node, time_attrs, value_attrs)

    @error_handler
    @undo_chunk("Mirror Curve")
    def mirror_curve_time(self):
        """Mirror the curve time."""
        anim_curves = cmds.keyframe(q=True, sl=True, n=True)
        if not anim_curves:
            cmds.error("No animation curve selected")

        for anim_curve in anim_curves:
            lib_keyframe.mirror_anim_curve(anim_curve, mirror_time=True, mirror_value=False)

    @error_handler
    @undo_chunk("Mirror Curve")
    def mirror_curve_value(self):
        """Mirror the curve value."""
        anim_curves = cmds.keyframe(q=True, sl=True, n=True)
        if not anim_curves:
            cmds.error("No animation curve selected")

        for anim_curve in anim_curves:
            lib_keyframe.mirror_anim_curve(anim_curve, mirror_time=False, mirror_value=True)

    @error_handler
    @undo_chunk("Select Driven Key Nodes")
    def select_driven_key_nodes(self):
        """Select driven key nodes."""
        sel_nodes = command.get_driven_key_nodes()
        if not sel_nodes:
            cmds.warning("No driven key nodes found")
            return

        cmds.select(sel_nodes, r=True)

    @error_handler
    @undo_chunk("Cleanup Driven Key")
    def cleanup_driven_keys(self):
        """Cleanup driven keys."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.error("No nodes selected")

        for node in sel_nodes:
            command.cleanup_driven_keys(node)

    def _update_mirror_check_box(self):
        """Update the mirror check box."""
        state = self.mirror_check_box.isChecked()

        self.time_label.setEnabled(state)
        self.time_translate_check_box.set_enabled(state)
        self.time_rotate_check_box.set_enabled(state)
        self.time_scale_check_box.set_enabled(state)
        self.value_label.setEnabled(state)
        self.value_translate_check_box.set_enabled(state)
        self.value_rotate_check_box.set_enabled(state)
        self.value_scale_check_box.set_enabled(state)

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Restore window geometry
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

        # Restore option settings
        self.regex_line_edit.setText(self.settings.read("regex", REGEX[0]))
        self.replace_to_line_edit.setText(self.settings.read("replace_to", REGEX[1]))
        self.mirror_check_box.setChecked(self.settings.read("mirror", False))
        self.replace_driver_check_box.setChecked(self.settings.read("replace_driver", True))
        self.force_delete_check_box.setChecked(self.settings.read("force_delete", False))
        self.time_translate_check_box.set_values(self.settings.read("time_translate", []))
        self.time_rotate_check_box.set_values(self.settings.read("time_rotate", []))
        self.time_scale_check_box.set_values(self.settings.read("time_scale", []))
        self.value_translate_check_box.set_values(self.settings.read("value_translate", ["translateX", "translateY", "translateZ"]))
        self.value_rotate_check_box.set_values(self.settings.read("value_rotate", []))
        self.value_scale_check_box.set_values(self.settings.read("value_scale", []))

        logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to preferences."""
        # Save window geometry
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

        # Save option settings
        self.settings.write("regex", self.regex_line_edit.text())
        self.settings.write("replace_to", self.replace_to_line_edit.text())
        self.settings.write("mirror", self.mirror_check_box.isChecked())
        self.settings.write("replace_driver", self.replace_driver_check_box.isChecked())
        self.settings.write("force_delete", self.force_delete_check_box.isChecked())
        self.settings.write("time_translate", self.time_translate_check_box.get_values())
        self.settings.write("time_rotate", self.time_rotate_check_box.get_values())
        self.settings.write("time_scale", self.time_scale_check_box.get_values())
        self.settings.write("value_translate", self.value_translate_check_box.get_values())
        self.settings.write("value_rotate", self.value_rotate_check_box.get_values())
        self.settings.write("value_scale", self.value_scale_check_box.get_values())

        logger.debug("UI settings saved")

    def closeEvent(self, event):
        """
        Handle window close event.

        Args:
            event: Close event
        """
        self._save_settings()
        super().closeEvent(event)


class MirrorCheckBox(QWidget):
    """Mirror Check Box."""

    def __init__(self, label: str = "T", attribute: str = "translate", parent=None):
        """Initialize.

        Args:
            label: Label.
        """
        super().__init__(parent)

        self._attribute = attribute

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(f"{label}:")
        layout.addWidget(self.label)

        self.x_check_box = QCheckBox("")
        layout.addWidget(self.x_check_box)

        self.y_check_box = QCheckBox("")
        layout.addWidget(self.y_check_box)

        self.z_check_box = QCheckBox("")
        layout.addWidget(self.z_check_box)

        self.setLayout(layout)

    def get_values(self) -> list[str]:
        """Get the values.

        Returns:
            list[str]: The values.
        """
        values = []
        for check_box, axis in [(self.x_check_box, "X"), (self.y_check_box, "Y"), (self.z_check_box, "Z")]:
            if check_box.isChecked():
                values.append(f"{self._attribute}{axis}")

        return values

    def set_values(self, values: list[str]):
        """Set the values.

        Args:
            values (list[str]): The values.
        """
        for check_box, axis in [(self.x_check_box, "X"), (self.y_check_box, "Y"), (self.z_check_box, "Z")]:
            attribute = f"{self._attribute}{axis}"
            if attribute in values:
                check_box.setChecked(True)
            else:
                check_box.setChecked(False)

    def set_enabled(self, enabled: bool):
        """Set the enabled.

        Args:
            enabled (bool): The enabled.
        """
        self.label.setEnabled(enabled)
        for check_box in [self.x_check_box, self.y_check_box, self.z_check_box]:
            check_box.setEnabled(enabled)


def show_ui():
    """
    Show the Driven Key Tools UI.

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
