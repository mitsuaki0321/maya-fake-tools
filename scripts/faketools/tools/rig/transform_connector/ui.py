"""Transform Connector UI."""

import logging

import maya.cmds as cmds

from ....lib_ui.maya_ui import error_handler, get_maya_window, undo_chunk
from ....lib_ui.qt_compat import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from . import command

logger = logging.getLogger(__name__)

_instance = None


class MainWindow(QWidget):
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
        super().__init__(parent)
        self.setWindowTitle("Transform Connector")
        self.setObjectName("TransformConnectorMainWindow")

        # Translate, Rotate, Scale, JointOrient, Visibility
        self.checkboxes = {}
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout(self)

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

        main_layout.addLayout(grid_layout)

        # Action buttons
        copy_value_button = QPushButton("Copy Value")
        copy_value_button.clicked.connect(self._copy_value)
        main_layout.addWidget(copy_value_button)

        connect_value_button = QPushButton("Connect Value")
        connect_value_button.clicked.connect(self._connect_attr)
        main_layout.addWidget(connect_value_button)

        zero_out_button = QPushButton("Zero Out")
        zero_out_button.clicked.connect(self._zero_out)
        main_layout.addWidget(zero_out_button)

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

    parent = get_maya_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
