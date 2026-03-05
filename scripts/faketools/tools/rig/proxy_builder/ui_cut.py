"""Proxy Builder — Cut tab (Step 1)."""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.extra_widgets import HorizontalSeparator
from . import cut_command
from .ui_common import SceneNodeListWidget, select_all_items

logger = getLogger(__name__)


class CutTab(QWidget):
    """Cut tab widget for separating meshes by weights or planes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        spacing = get_spacing(self, direction="vertical")
        layout.setSpacing(int(spacing * 0.5))

        # --- Source Meshes ---
        layout.addWidget(QLabel("Source Meshes:"))

        row_source = QHBoxLayout()
        self._list_source = SceneNodeListWidget()
        self._list_source.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_source.addWidget(self._list_source, 1)

        col_source_btns = QVBoxLayout()
        self._btn_add_source = QPushButton("Add")
        self._btn_remove_source = QPushButton("Remove")
        self._btn_clear_source = QPushButton("Clear")
        col_source_btns.addWidget(self._btn_add_source)
        col_source_btns.addWidget(self._btn_remove_source)
        col_source_btns.addWidget(self._btn_clear_source)
        col_source_btns.addStretch()
        row_source.addLayout(col_source_btns)

        layout.addLayout(row_source, 1)

        # --- Cut Method radio buttons ---
        row_method = QHBoxLayout()
        row_method.addWidget(QLabel("Cut Method:"))
        self._radio_by_weights = QRadioButton("By Weights")
        self._radio_by_planes = QRadioButton("By Planes")
        self._radio_by_weights.setChecked(True)
        self._btn_group_cut_method = QButtonGroup(self)
        self._btn_group_cut_method.addButton(self._radio_by_weights, 0)
        self._btn_group_cut_method.addButton(self._radio_by_planes, 1)
        row_method.addWidget(self._radio_by_weights)
        row_method.addWidget(self._radio_by_planes)
        row_method.addStretch()
        layout.addLayout(row_method)

        # --- QStackedWidget for method-specific options ---
        self._stack_cut_method = QStackedWidget()

        # -- By Weights page --
        page_weights = QWidget()
        lay_weights = QVBoxLayout(page_weights)
        lay_weights.setSpacing(int(spacing * 0.5))
        lay_weights.setContentsMargins(0, 0, 0, 0)

        lay_weights.addWidget(QLabel("Joints:"))

        row_joints = QHBoxLayout()
        self._list_joints = SceneNodeListWidget()
        self._list_joints.setSelectionMode(QListWidget.ExtendedSelection)
        row_joints.addWidget(self._list_joints, 1)

        col_joints_btns = QVBoxLayout()
        self._btn_add_joints = QPushButton("Add")
        self._btn_remove_joints = QPushButton("Remove")
        self._btn_select_all_joints = QPushButton("Select All")
        col_joints_btns.addWidget(self._btn_add_joints)
        col_joints_btns.addWidget(self._btn_remove_joints)
        col_joints_btns.addWidget(self._btn_select_all_joints)
        col_joints_btns.addStretch()
        row_joints.addLayout(col_joints_btns)

        lay_weights.addLayout(row_joints, 1)

        lbl_hint = QLabel("* Leave empty to use all influences")
        lbl_hint.setEnabled(False)
        lay_weights.addWidget(lbl_hint)

        self._chk_merge_end_joints = QCheckBox("Merge End Joints into Parent")
        self._chk_merge_end_joints.setToolTip("End joints (no children) will be merged into their parent joint for separation")
        lay_weights.addWidget(self._chk_merge_end_joints)

        self._stack_cut_method.addWidget(page_weights)

        # -- By Planes page --
        page_planes = QWidget()
        lay_planes = QVBoxLayout(page_planes)
        lay_planes.setSpacing(int(spacing * 0.5))
        lay_planes.setContentsMargins(0, 0, 0, 0)

        lay_planes.addWidget(QLabel("Cutters:"))

        row_cutters = QHBoxLayout()
        self._list_cutters = SceneNodeListWidget()
        self._list_cutters.setSelectionMode(QListWidget.ExtendedSelection)
        row_cutters.addWidget(self._list_cutters, 1)

        col_cutters_btns = QVBoxLayout()
        self._btn_add_cutters = QPushButton("Add")
        self._btn_remove_cutters = QPushButton("Remove")
        self._btn_select_all_cutters = QPushButton("Select All")
        col_cutters_btns.addWidget(self._btn_add_cutters)
        col_cutters_btns.addWidget(self._btn_remove_cutters)
        col_cutters_btns.addWidget(self._btn_select_all_cutters)
        col_cutters_btns.addStretch()
        row_cutters.addLayout(col_cutters_btns)

        lay_planes.addLayout(row_cutters, 1)

        self._stack_cut_method.addWidget(page_planes)

        layout.addWidget(self._stack_cut_method, 1)

        # --- Keep Original Mesh ---
        self._chk_keep_original = QCheckBox("Keep Original Mesh")
        self._chk_keep_original.setChecked(True)
        layout.addWidget(self._chk_keep_original)

        layout.addWidget(HorizontalSeparator())

        # --- Cut button ---
        self._btn_cut = QPushButton("Cut")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_cut.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_cut)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_add_source.clicked.connect(self._on_add_source)
        self._btn_remove_source.clicked.connect(self._on_remove_source)
        self._btn_clear_source.clicked.connect(self._on_clear_source)
        self._radio_by_weights.toggled.connect(lambda checked: self._stack_cut_method.setCurrentIndex(0 if checked else 1))
        self._btn_add_joints.clicked.connect(self._on_add_joints)
        self._btn_remove_joints.clicked.connect(self._on_remove_joints)
        self._btn_select_all_joints.clicked.connect(lambda: select_all_items(self._list_joints))
        self._btn_add_cutters.clicked.connect(self._on_add_cutters)
        self._btn_remove_cutters.clicked.connect(self._on_remove_cutters)
        self._btn_select_all_cutters.clicked.connect(lambda: select_all_items(self._list_cutters))
        self._btn_cut.clicked.connect(self._on_cut)

    # ------------------------------------------------------------------
    # Slots — Source Mesh
    # ------------------------------------------------------------------

    def _on_add_source(self) -> None:
        """Add selected mesh transforms to the source list (skip duplicates)."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more mesh transforms")
            return
        existing = {self._list_source.item(i).text() for i in range(self._list_source.count())}
        for node in sel:
            shapes = cmds.listRelatives(node, shapes=True, type="mesh")
            if shapes and node not in existing:
                self._list_source.addItem(node)

    def _on_remove_source(self) -> None:
        """Remove selected items from the source list."""
        self._list_source.set_sync_enabled(False)
        for item in reversed(self._list_source.selectedItems()):
            self._list_source.takeItem(self._list_source.row(item))
        self._list_source.set_sync_enabled(True)

    def _on_clear_source(self) -> None:
        """Clear all items from the source list."""
        self._list_source.set_sync_enabled(False)
        self._list_source.clear()
        self._list_source.set_sync_enabled(True)

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
        self._list_joints.set_sync_enabled(False)
        for item in reversed(self._list_joints.selectedItems()):
            self._list_joints.takeItem(self._list_joints.row(item))
        self._list_joints.set_sync_enabled(True)

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
        self._list_cutters.set_sync_enabled(False)
        for item in reversed(self._list_cutters.selectedItems()):
            self._list_cutters.takeItem(self._list_cutters.row(item))
        self._list_cutters.set_sync_enabled(True)

    # ------------------------------------------------------------------
    # Slots — Cut
    # ------------------------------------------------------------------

    @error_handler
    @undo_chunk("Proxy Builder: Cut")
    def _on_cut(self) -> None:
        """Run cut based on the selected method."""
        meshes = [self._list_source.item(i).text() for i in range(self._list_source.count())]
        if not meshes:
            cmds.warning("Proxy Builder: Add at least one source mesh")
            return

        duplicate = self._chk_keep_original.isChecked()
        method_id = self._btn_group_cut_method.checkedId()

        if method_id == 0:
            # By Weights
            joints = [self._list_joints.item(i).text() for i in range(self._list_joints.count())]
            results = cut_command.separate_meshes_by_weights(
                meshes=meshes,
                joints=joints if joints else None,
                duplicate=duplicate,
                merge_end_joints=self._chk_merge_end_joints.isChecked(),
            )
        else:
            # By Planes
            cutters = [self._list_cutters.item(i).text() for i in range(self._list_cutters.count())]
            if not cutters:
                cmds.warning("Proxy Builder: Add at least one cutter surface")
                return
            results = cut_command.separate_meshes_by_planes(
                meshes=meshes,
                cutters=cutters,
                duplicate=duplicate,
            )

        if results:
            cmds.select(results, replace=True)
            logger.info("Created %d piece meshes", len(results))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "cut_method": self._btn_group_cut_method.checkedId(),
            "keep_original": self._chk_keep_original.isChecked(),
            "merge_end_joints": self._chk_merge_end_joints.isChecked(),
        }

    def _apply_settings(self, data: dict) -> None:
        cut_method = data.get("cut_method", 0)
        if cut_method == 1:
            self._radio_by_planes.setChecked(True)
            self._stack_cut_method.setCurrentIndex(1)
        else:
            self._radio_by_weights.setChecked(True)
            self._stack_cut_method.setCurrentIndex(0)

        self._chk_keep_original.setChecked(data.get("keep_original", True))
        self._chk_merge_end_joints.setChecked(data.get("merge_end_joints", False))
