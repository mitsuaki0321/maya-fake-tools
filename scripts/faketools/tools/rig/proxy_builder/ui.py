"""Proxy Builder UI layer.

Provides a tabbed interface for separating meshes by skin weights
or cutting planes.
"""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import BaseMainWindow, get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.ui_utils import get_relative_size
from . import command

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
        self._connect_signals()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        spacing = get_spacing(self.central_widget, direction="vertical")

        # --- Source Mesh row ---
        row_source = QHBoxLayout()
        lbl_source = QLabel("Source Mesh:")
        row_source.addWidget(lbl_source)

        self._line_source = QLineEdit()
        self._line_source.setReadOnly(True)
        self._line_source.setPlaceholderText("Select a mesh and click SET")
        row_source.addWidget(self._line_source, 1)

        btn_h = self._line_source.sizeHint().height()
        self._btn_set_source = QPushButton("SET")
        self._btn_set_source.setFixedHeight(btn_h)
        row_source.addWidget(self._btn_set_source)
        self._btn_sel_source = QPushButton("SEL")
        self._btn_sel_source.setFixedHeight(btn_h)
        row_source.addWidget(self._btn_sel_source)

        self.central_layout.addLayout(row_source)

        # --- Tab Widget ---
        self._tab_widget = QTabWidget()
        self.central_layout.addWidget(self._tab_widget, 1)

        # -- By Weights tab --
        tab_weights = QWidget()
        lay_weights = QVBoxLayout(tab_weights)
        lay_weights.setSpacing(int(spacing * 0.5))

        lay_weights.addWidget(QLabel("Joints:"))

        row_joints = QHBoxLayout()
        self._list_joints = QListWidget()
        self._list_joints.setSelectionMode(QListWidget.ExtendedSelection)
        row_joints.addWidget(self._list_joints, 1)

        col_joints_btns = QVBoxLayout()
        self._btn_add_joints = QPushButton("Add")
        self._btn_remove_joints = QPushButton("Remove")
        col_joints_btns.addWidget(self._btn_add_joints)
        col_joints_btns.addWidget(self._btn_remove_joints)
        col_joints_btns.addStretch()
        row_joints.addLayout(col_joints_btns)

        lay_weights.addLayout(row_joints, 1)

        lbl_hint = QLabel("* Leave empty to use all influences")
        lbl_hint.setEnabled(False)
        lay_weights.addWidget(lbl_hint)

        self._tab_widget.addTab(tab_weights, "By Weights")

        # -- By Planes tab --
        tab_planes = QWidget()
        lay_planes = QVBoxLayout(tab_planes)
        lay_planes.setSpacing(int(spacing * 0.5))

        lay_planes.addWidget(QLabel("Cutters:"))

        row_cutters = QHBoxLayout()
        self._list_cutters = QListWidget()
        self._list_cutters.setSelectionMode(QListWidget.ExtendedSelection)
        row_cutters.addWidget(self._list_cutters, 1)

        col_cutters_btns = QVBoxLayout()
        self._btn_add_cutters = QPushButton("Add")
        self._btn_remove_cutters = QPushButton("Remove")
        col_cutters_btns.addWidget(self._btn_add_cutters)
        col_cutters_btns.addWidget(self._btn_remove_cutters)
        col_cutters_btns.addStretch()
        row_cutters.addLayout(col_cutters_btns)

        lay_planes.addLayout(row_cutters, 1)

        self._tab_widget.addTab(tab_planes, "By Planes")

        # --- Keep Original Mesh ---
        self._chk_keep_original = QCheckBox("Keep Original Mesh")
        self._chk_keep_original.setChecked(True)
        self.central_layout.addWidget(self._chk_keep_original)

        # --- Separate button ---
        self._btn_separate = QPushButton("Separate")
        width, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_separate.setMinimumHeight(int(height * 0.08))
        self.central_layout.addWidget(self._btn_separate)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_source.clicked.connect(self._on_set_source)
        self._btn_sel_source.clicked.connect(self._on_sel_source)

        self._btn_add_joints.clicked.connect(self._on_add_joints)
        self._btn_remove_joints.clicked.connect(self._on_remove_joints)

        self._btn_add_cutters.clicked.connect(self._on_add_cutters)
        self._btn_remove_cutters.clicked.connect(self._on_remove_cutters)

        self._btn_separate.clicked.connect(self._on_separate)

    # ------------------------------------------------------------------
    # Slots — Source Mesh
    # ------------------------------------------------------------------

    def _on_set_source(self) -> None:
        """Set source mesh from Maya selection."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select a mesh transform")
            return
        node = sel[0]
        shapes = cmds.listRelatives(node, shapes=True, type="mesh")
        if not shapes:
            cmds.warning("Proxy Builder: Selected node has no mesh shape")
            return
        self._line_source.setText(node.rsplit("|", 1)[-1])
        self._line_source.setToolTip(node)

    def _on_sel_source(self) -> None:
        """Select the stored source mesh in Maya."""
        name = self._line_source.toolTip()
        if name and cmds.objExists(name):
            cmds.select(name, replace=True)

    # ------------------------------------------------------------------
    # Slots — Joints list
    # ------------------------------------------------------------------

    def _on_add_joints(self) -> None:
        """Add selected joints to the list (skip duplicates)."""
        sel = cmds.ls(selection=True, type="joint")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more joints")
            return
        existing = {self._list_joints.item(i).text() for i in range(self._list_joints.count())}
        for joint in sel:
            if joint not in existing:
                self._list_joints.addItem(joint)

    def _on_remove_joints(self) -> None:
        """Remove selected items from the joints list."""
        for item in reversed(self._list_joints.selectedItems()):
            self._list_joints.takeItem(self._list_joints.row(item))

    # ------------------------------------------------------------------
    # Slots — Cutters list
    # ------------------------------------------------------------------

    def _on_add_cutters(self) -> None:
        """Add selected surfaces/meshes to the cutters list (skip duplicates)."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more surfaces or meshes")
            return
        existing = {self._list_cutters.item(i).text() for i in range(self._list_cutters.count())}
        for node in sel:
            shapes = cmds.listRelatives(node, shapes=True) or []
            valid = any(cmds.nodeType(s) in ("mesh", "nurbsSurface") for s in shapes)
            if valid and node not in existing:
                self._list_cutters.addItem(node)

    def _on_remove_cutters(self) -> None:
        """Remove selected items from the cutters list."""
        for item in reversed(self._list_cutters.selectedItems()):
            self._list_cutters.takeItem(self._list_cutters.row(item))

    # ------------------------------------------------------------------
    # Slots — Separate
    # ------------------------------------------------------------------

    @error_handler
    @undo_chunk("Proxy Builder: Separate")
    def _on_separate(self) -> None:
        """Run separation based on the active tab."""
        source = self._line_source.toolTip()
        if not source or not cmds.objExists(source):
            cmds.warning("Proxy Builder: Set a valid source mesh first")
            return

        duplicate = self._chk_keep_original.isChecked()
        tab_index = self._tab_widget.currentIndex()

        if tab_index == 0:
            # By Weights
            joints = [self._list_joints.item(i).text() for i in range(self._list_joints.count())]
            results = command.separate_by_weights(
                mesh=source,
                joints=joints if joints else None,
                duplicate=duplicate,
            )
        else:
            # By Planes
            cutters = [self._list_cutters.item(i).text() for i in range(self._list_cutters.count())]
            if not cutters:
                cmds.warning("Proxy Builder: Add at least one cutter surface")
                return
            results = command.separate_by_planes(
                mesh=source,
                cutters=cutters,
                duplicate=duplicate,
            )

        if results:
            cmds.select(results, replace=True)
            logger.info("Created %d proxy meshes", len(results))

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
            "active_tab": self._tab_widget.currentIndex(),
            "keep_original": self._chk_keep_original.isChecked(),
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict) -> None:
        self._tab_widget.setCurrentIndex(settings_data.get("active_tab", 0))
        self._chk_keep_original.setChecked(settings_data.get("keep_original", True))

        if "window_geometry" in settings_data:
            geo = settings_data["window_geometry"]
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
