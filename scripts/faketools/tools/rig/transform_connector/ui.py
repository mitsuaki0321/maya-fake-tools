"""Transform Connector UI."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QCheckBox, QGridLayout, QLabel, QPushButton, QSizePolicy, Qt
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """
    Transform Connector Main Window.

    Provides UI for copying, connecting, and zeroing out transform attributes
    between Maya transform nodes.
    """

    def __init__(self, parent=None):
        """
        Initialize the Transform Connector window.

        Args:
            parent (QWidget | None): Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="TransformConnectorMainWindow",
            window_title="Transform Connector",
            central_layout="vertical",
        )

        # UI settings
        self.settings = ToolOptionSettings(__name__)

        # Translate, Rotate, Scale, JointOrient, Visibility
        self.checkboxes = {}
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Attribute checkboxes grid
        grid_layout = QGridLayout()

        for i, (label, attribute) in enumerate(
            [
                ("Translate", "translate"),
                ("Rotate", "rotate"),
                ("Scale", "scale"),
                ("JointOrient", "jointOrient"),
                ("Visibility", "visibility"),
            ]
        ):
            # Label
            check_box_label = QLabel(f"{label}:")
            check_box_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            check_box_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid_layout.addWidget(check_box_label, i, 0)

            if label == "Visibility":
                # Visibility (single checkbox)
                checkbox = QCheckBox()
                grid_layout.addWidget(checkbox, i, 1)
                self.checkboxes.setdefault(attribute, []).append(checkbox)
            else:
                # X, Y, Z checkboxes
                for j, axis in enumerate(["X", "Y", "Z"]):
                    checkbox = QCheckBox(axis)
                    grid_layout.addWidget(checkbox, i, j + 1)
                    self.checkboxes.setdefault(attribute, []).append(checkbox)

                # On & Off Button
                on_button = QPushButton("On")
                on_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                grid_layout.addWidget(on_button, i, 4)

                off_button = QPushButton("Off")
                off_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                grid_layout.addWidget(off_button, i, 5)

                # Connect signals
                on_button.clicked.connect(lambda checked=False, attr=attribute: self._all_on_checked(self.checkboxes[attr]))
                off_button.clicked.connect(lambda checked=False, attr=attribute: self._all_off_checked(self.checkboxes[attr]))

        self.central_layout.addLayout(grid_layout)

        # Action buttons
        copy_value_button = QPushButton("Copy Value")
        copy_value_button.clicked.connect(self._copy_value)
        self.central_layout.addWidget(copy_value_button)

        connect_value_button = QPushButton("Connect Value")
        connect_value_button.clicked.connect(self._connect_attr)
        self.central_layout.addWidget(connect_value_button)

        zero_out_button = QPushButton("Zero Out")
        zero_out_button.clicked.connect(self._zero_out)
        self.central_layout.addWidget(zero_out_button)

    @staticmethod
    def _all_on_checked(checkboxes):
        """
        Check all checkboxes in the list.

        Args:
            checkboxes (list): List of QCheckBox widgets
        """
        for checkbox in checkboxes:
            checkbox.setChecked(True)

    @staticmethod
    def _all_off_checked(checkboxes):
        """
        Uncheck all checkboxes in the list.

        Args:
            checkboxes (list): List of QCheckBox widgets
        """
        for checkbox in checkboxes:
            checkbox.setChecked(False)

    @error_handler
    @undo_chunk("Transform Connector: Copy Value")
    def _copy_value(self):
        """Copy attribute values from source to destination nodes."""
        enable_attributes = self._get_enable_attributes()
        if not enable_attributes:
            cmds.warning("No attributes selected")
            return

        command.copy_value(enable_attributes)

    @error_handler
    @undo_chunk("Transform Connector: Connect Value")
    def _connect_attr(self):
        """Connect attributes from source to destination nodes."""
        enable_attributes = self._get_enable_attributes()
        if not enable_attributes:
            cmds.warning("No attributes selected")
            return

        command.connect_value(enable_attributes)

    @error_handler
    @undo_chunk("Transform Connector: Zero Out")
    def _zero_out(self):
        """Zero out specified attributes on selected nodes."""
        enable_attributes = self._get_enable_attributes()
        if not enable_attributes:
            cmds.warning("No attributes selected")
            return

        command.zero_out(enable_attributes)

    def _get_enable_attributes(self):
        """
        Get enabled attributes from checkboxes.

        Returns:
            list: List of enabled attribute names (e.g., ["translateX", "rotateY"])
        """
        enable_attributes = []
        for attribute, checkboxes in self.checkboxes.items():
            if attribute == "visibility":
                if checkboxes[0].isChecked():
                    enable_attributes.append(attribute)
            else:
                for axis, checkbox in zip(["X", "Y", "Z"], checkboxes, strict=False):
                    if checkbox.isChecked():
                        enable_attributes.append(f"{attribute}{axis}")

        return enable_attributes

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Restore window geometry
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

        # Restore checkbox states
        checkbox_states = self.settings.read("checkbox_states", {})
        for attribute, checkboxes in self.checkboxes.items():
            if attribute == "visibility":
                state = checkbox_states.get(attribute, False)
                checkboxes[0].setChecked(state)
            else:
                for axis, checkbox in zip(["X", "Y", "Z"], checkboxes, strict=False):
                    key = f"{attribute}{axis}"
                    state = checkbox_states.get(key, False)
                    checkbox.setChecked(state)

        logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to preferences."""
        # Save window geometry
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

        # Save checkbox states
        checkbox_states = {}
        for attribute, checkboxes in self.checkboxes.items():
            if attribute == "visibility":
                checkbox_states[attribute] = checkboxes[0].isChecked()
            else:
                for axis, checkbox in zip(["X", "Y", "Z"], checkboxes, strict=False):
                    key = f"{attribute}{axis}"
                    checkbox_states[key] = checkbox.isChecked()

        self.settings.write("checkbox_states", checkbox_states)
        logger.debug("UI settings saved")

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
    Show the Transform Connector UI.

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
