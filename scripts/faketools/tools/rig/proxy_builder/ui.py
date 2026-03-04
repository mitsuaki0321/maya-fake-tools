"""Proxy Builder UI layer.

Provides a four-tab interface for the proxy building workflow:
Cut -> Assign -> Finalize -> Plane.
"""

from __future__ import annotations

from logging import getLogger

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import QTabWidget, QWidget
from ....lib_ui.tool_settings import ToolSettingsManager
from .ui_assign import AssignTab
from .ui_cut import CutTab
from .ui_finalize import FinalizeTab
from .ui_plane import PlaneTab

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Main GUI window for Proxy Builder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            object_name="ProxyBuilderMainWindow",
            window_title="Proxy Builder",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="proxy_builder", category="rig")
        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._tab_cut = CutTab()
        self._tab_assign = AssignTab()
        self._tab_finalize = FinalizeTab()
        self._tab_plane = PlaneTab()

        self._tab_main = QTabWidget()
        self._tab_main.addTab(self._tab_cut, "Cut")
        self._tab_main.addTab(self._tab_assign, "Assign")
        self._tab_main.addTab(self._tab_finalize, "Finalize")
        self._tab_main.addTab(self._tab_plane, "Plane")
        self.central_layout.addWidget(self._tab_main)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self) -> None:
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def _collect_settings(self) -> dict:
        return {
            "active_step": self._tab_main.currentIndex(),
            "cut": self._tab_cut._collect_settings(),
            "assign": self._tab_assign._collect_settings(),
            "finalize": self._tab_finalize._collect_settings(),
            "plane": self._tab_plane._collect_settings(),
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, data: dict) -> None:
        self._tab_main.setCurrentIndex(data.get("active_step", 0))

        if "cut" in data:
            self._tab_cut._apply_settings(data["cut"])
        if "assign" in data:
            self._tab_assign._apply_settings(data["assign"])
        if "finalize" in data:
            self._tab_finalize._apply_settings(data["finalize"])
        if "plane" in data:
            self._tab_plane._apply_settings(data["plane"])

        if "window_geometry" in data:
            geo = data["window_geometry"]
            if "size" in geo:
                self.resize(*geo["size"])
            if "position" in geo:
                self.move(*geo["position"])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Proxy Builder UI.

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

    _instance = MainWindow(get_maya_main_window())
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
