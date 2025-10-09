"""Scene Optimizer UI."""

from functools import partial
import logging

import maya.cmds as cmds

from ....lib import lib_optimize
from ....lib_ui.base_window import BaseMainWindow, get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QCheckBox, QHBoxLayout, QPushButton, QSizePolicy
from ....lib_ui.widgets import extra_widgets

logger = logging.getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """
    Scene Optimizer Main Window.

    Provides UI for selecting and executing various scene optimization operations.
    """

    def __init__(self, parent=None):
        """
        Initialize the Scene Optimizer main window.

        Args:
            parent (QWidget | None): Parent widget (typically Maya main window)
        """
        super().__init__(
            parent=parent,
            object_name="SceneOptimizerMainWindow",
            window_title="Scene Optimizer",
            central_layout="vertical",
        )

        # UI settings
        self.settings = ToolOptionSettings(__name__)

        # Optimizer instances and checkboxes
        self.optimize_cls_list = []
        for cls in lib_optimize.OptimizeBase.__subclasses__():
            self.optimize_cls_list.append(cls)
        self.enable_checkboxes = []

        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Create optimizer checkboxes and run buttons
        for optimize_cls in self.optimize_cls_list:
            layout = QHBoxLayout()

            checkbox = QCheckBox(optimize_cls._name)
            checkbox.setToolTip(optimize_cls._description)
            layout.addWidget(checkbox)
            self.enable_checkboxes.append(checkbox)

            button = QPushButton("Run")
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(partial(self._optimize_run, optimize_cls))
            layout.addWidget(button)

            self.central_layout.addLayout(layout)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        # Control buttons layout
        layout = QHBoxLayout()
        layout.setSpacing(get_spacing(QPushButton(), "horizontal") * 0.5)

        all_on_checked_button = QPushButton("All On")
        all_on_checked_button.clicked.connect(self._all_on_checked)
        layout.addWidget(all_on_checked_button)

        all_off_checked_button = QPushButton("All Off")
        all_off_checked_button.clicked.connect(self._all_off_checked)
        layout.addWidget(all_off_checked_button)

        toggle_checked_button = QPushButton("Toggle Checked")
        toggle_checked_button.clicked.connect(self._toggle_checked)
        layout.addWidget(toggle_checked_button)

        self.central_layout.addLayout(layout)

        self.central_layout.addWidget(extra_widgets.HorizontalSeparator())

        # Execute button
        execute_button = QPushButton("Optimize Scene")
        execute_button.clicked.connect(self._execute)
        self.central_layout.addWidget(execute_button)

    def _all_on_checked(self):
        """Enable all optimizer checkboxes."""
        for checkbox in self.enable_checkboxes:
            checkbox.setChecked(True)

    def _all_off_checked(self):
        """Disable all optimizer checkboxes."""
        for checkbox in self.enable_checkboxes:
            checkbox.setChecked(False)

    def _toggle_checked(self):
        """Toggle the state of all optimizer checkboxes."""
        for checkbox in self.enable_checkboxes:
            checkbox.setChecked(not checkbox.isChecked())

    @error_handler
    @undo_chunk("Optimize Run")
    def _optimize_run(self, optimize_cls):
        """Run a single optimization operation."""
        optimize_cls(echo=True)

    @error_handler
    @undo_chunk("Optimize Scene")
    def _execute(self):
        """Execute selected scene optimizations."""
        if not any([checkbox.isChecked() for checkbox in self.enable_checkboxes]):
            cmds.warning("Please check the optimize method you want to execute.")
            return

        for checkbox, optimize_cls in zip(self.enable_checkboxes, self.optimize_cls_list, strict=False):
            if checkbox.isChecked():
                optimize_cls(echo=True)

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
        for checkbox in self.enable_checkboxes:
            state = checkbox_states.get(checkbox.text(), True)
            checkbox.setChecked(state)

        logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to preferences."""
        # Save window geometry
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

        # Save checkbox states
        checkbox_states = {}
        for checkbox in self.enable_checkboxes:
            checkbox_states[checkbox.text()] = checkbox.isChecked()

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
    Show the Scene Optimizer UI.

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
