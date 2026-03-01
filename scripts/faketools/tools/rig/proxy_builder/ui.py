"""Proxy Builder UI layer.

Provides a three-tab interface for the proxy building workflow:
Cut -> Assign -> Finalize.
"""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import BaseMainWindow, get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.ui_utils import get_relative_size
from . import assign_command, cut_command, finalize_command

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
        self._tab_main = QTabWidget()
        self._tab_main.addTab(self._build_cut_tab(), "Cut")
        self._tab_main.addTab(self._build_assign_tab(), "Assign")
        self._tab_main.addTab(self._build_finalize_tab(), "Finalize")
        self.central_layout.addWidget(self._tab_main)

    def _build_cut_tab(self) -> QWidget:
        """Build the Cut tab (Step 1)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = get_spacing(tab, direction="vertical")
        layout.setSpacing(int(spacing * 0.5))

        # --- Source Meshes ---
        layout.addWidget(QLabel("Source Meshes:"))

        row_source = QHBoxLayout()
        self._list_source = QListWidget()
        self._list_source.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_source.addWidget(self._list_source, 1)

        col_source_btns = QVBoxLayout()
        self._btn_add_source = QPushButton("Add")
        self._btn_remove_source = QPushButton("Remove")
        self._btn_clear_source = QPushButton("Clear")
        self._btn_sel_source = QPushButton("Select")
        col_source_btns.addWidget(self._btn_add_source)
        col_source_btns.addWidget(self._btn_remove_source)
        col_source_btns.addWidget(self._btn_clear_source)
        col_source_btns.addWidget(self._btn_sel_source)
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

        self._stack_cut_method.addWidget(page_planes)

        layout.addWidget(self._stack_cut_method, 1)

        # --- Keep Original Mesh ---
        self._chk_keep_original = QCheckBox("Keep Original Mesh")
        self._chk_keep_original.setChecked(True)
        layout.addWidget(self._chk_keep_original)

        # --- Cut button ---
        self._btn_cut = QPushButton("Cut")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_cut.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_cut)

        return tab

    def _build_assign_tab(self) -> QWidget:
        """Build the Assign tab (Step 2)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = get_spacing(tab, direction="vertical")
        layout.setSpacing(int(spacing * 0.5))

        # --- Piece Group ---
        row_piece_grp = QHBoxLayout()
        row_piece_grp.addWidget(QLabel("Piece Group:"))
        self._line_piece_group = QLineEdit("piece_grp")
        row_piece_grp.addWidget(self._line_piece_group, 1)
        self._btn_load_pieces = QPushButton("Load")
        row_piece_grp.addWidget(self._btn_load_pieces)
        layout.addLayout(row_piece_grp)

        # --- Pieces list ---
        row_pieces = QHBoxLayout()
        self._list_pieces = QListWidget()
        self._list_pieces.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_pieces.addWidget(self._list_pieces, 1)

        col_pieces_btns = QVBoxLayout()
        self._btn_add_pieces = QPushButton("Add")
        self._btn_remove_pieces = QPushButton("Remove")
        col_pieces_btns.addWidget(self._btn_add_pieces)
        col_pieces_btns.addWidget(self._btn_remove_pieces)
        col_pieces_btns.addStretch()
        row_pieces.addLayout(col_pieces_btns)

        layout.addLayout(row_pieces, 1)

        # --- Reference Mesh ---
        row_ref = QHBoxLayout()
        row_ref.addWidget(QLabel("Reference Mesh:"))
        self._line_ref_mesh = QLineEdit()
        self._line_ref_mesh.setReadOnly(True)
        self._line_ref_mesh.setPlaceholderText("(optional — enables weight mode)")
        row_ref.addWidget(self._line_ref_mesh, 1)
        self._btn_set_ref_mesh = QPushButton("Set")
        self._btn_sel_ref_mesh = QPushButton("Sel")
        row_ref.addWidget(self._btn_set_ref_mesh)
        row_ref.addWidget(self._btn_sel_ref_mesh)
        layout.addLayout(row_ref)

        # --- Joints ---
        layout.addWidget(QLabel("Joints:"))

        row_assign_joints = QHBoxLayout()
        self._list_assign_joints = QListWidget()
        self._list_assign_joints.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_assign_joints.addWidget(self._list_assign_joints, 1)

        col_assign_joints_btns = QVBoxLayout()
        self._btn_add_assign_joints = QPushButton("Add")
        self._btn_remove_assign_joints = QPushButton("Remove")
        col_assign_joints_btns.addWidget(self._btn_add_assign_joints)
        col_assign_joints_btns.addWidget(self._btn_remove_assign_joints)
        col_assign_joints_btns.addStretch()
        row_assign_joints.addLayout(col_assign_joints_btns)

        layout.addLayout(row_assign_joints, 1)

        lbl_joints_hint = QLabel("* Required for bone mode; optional filter for weight mode")
        lbl_joints_hint.setEnabled(False)
        layout.addWidget(lbl_joints_hint)

        # --- Output Group ---
        row_output = QHBoxLayout()
        row_output.addWidget(QLabel("Output Group:"))
        self._line_output_group = QLineEdit("proxy_grp")
        row_output.addWidget(self._line_output_group, 1)
        layout.addLayout(row_output)

        # --- Assign & Create Groups button ---
        self._btn_assign = QPushButton("Assign && Create Groups")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_assign.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_assign)

        return tab

    def _build_finalize_tab(self) -> QWidget:
        """Build the Finalize tab (Step 3)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = get_spacing(tab, direction="vertical")
        layout.setSpacing(int(spacing * 0.5))

        # --- Source Group ---
        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Source Group:"))
        self._line_finalize_group = QLineEdit("proxy_grp")
        row_src.addWidget(self._line_finalize_group, 1)
        self._btn_pick_finalize_group = QPushButton("Pick")
        row_src.addWidget(self._btn_pick_finalize_group)
        layout.addLayout(row_src)

        # --- Combine Mode ---
        layout.addWidget(QLabel("Combine Mode:"))
        self._radio_single = QRadioButton("Single Mesh per Joint")
        self._radio_per_shader = QRadioButton("Per Shader (shape parent)")
        self._radio_single.setChecked(True)
        self._btn_group_combine = QButtonGroup(self)
        self._btn_group_combine.addButton(self._radio_single, 0)
        self._btn_group_combine.addButton(self._radio_per_shader, 1)
        layout.addWidget(self._radio_single)
        layout.addWidget(self._radio_per_shader)

        # --- Groups list ---
        row_groups_header = QHBoxLayout()
        row_groups_header.addWidget(QLabel("Groups:"))
        row_groups_header.addStretch()
        self._btn_refresh_groups = QPushButton("Refresh")
        row_groups_header.addWidget(self._btn_refresh_groups)
        layout.addLayout(row_groups_header)

        self._list_finalize_groups = QListWidget()
        self._list_finalize_groups.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self._list_finalize_groups, 1)

        # --- Output Group ---
        row_final_output = QHBoxLayout()
        row_final_output.addWidget(QLabel("Output Group:"))
        self._line_finalize_output = QLineEdit("proxy_final_grp")
        row_final_output.addWidget(self._line_finalize_output, 1)
        layout.addLayout(row_final_output)

        # --- Finalize button ---
        self._btn_finalize = QPushButton("Finalize")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_finalize.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_finalize)

        return tab

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        # Cut tab
        self._btn_add_source.clicked.connect(self._on_add_source)
        self._btn_remove_source.clicked.connect(self._on_remove_source)
        self._btn_clear_source.clicked.connect(self._on_clear_source)
        self._btn_sel_source.clicked.connect(self._on_sel_source)
        self._radio_by_weights.toggled.connect(lambda checked: self._stack_cut_method.setCurrentIndex(0 if checked else 1))
        self._btn_add_joints.clicked.connect(self._on_add_joints)
        self._btn_remove_joints.clicked.connect(self._on_remove_joints)
        self._btn_add_cutters.clicked.connect(self._on_add_cutters)
        self._btn_remove_cutters.clicked.connect(self._on_remove_cutters)
        self._btn_cut.clicked.connect(self._on_cut)

        # Assign tab
        self._btn_load_pieces.clicked.connect(self._on_load_pieces)
        self._btn_add_pieces.clicked.connect(self._on_add_pieces)
        self._btn_remove_pieces.clicked.connect(self._on_remove_pieces)
        self._btn_set_ref_mesh.clicked.connect(self._on_set_ref_mesh)
        self._btn_sel_ref_mesh.clicked.connect(self._on_sel_ref_mesh)
        self._btn_add_assign_joints.clicked.connect(self._on_add_assign_joints)
        self._btn_remove_assign_joints.clicked.connect(self._on_remove_assign_joints)
        self._btn_assign.clicked.connect(self._on_assign)

        # Finalize tab
        self._btn_pick_finalize_group.clicked.connect(self._on_pick_finalize_group)
        self._btn_refresh_groups.clicked.connect(self._on_refresh_groups)
        self._btn_finalize.clicked.connect(self._on_finalize)

    # ------------------------------------------------------------------
    # Slots — Source Mesh (Cut tab)
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
        for item in reversed(self._list_source.selectedItems()):
            self._list_source.takeItem(self._list_source.row(item))

    def _on_clear_source(self) -> None:
        """Clear all items from the source list."""
        self._list_source.clear()

    def _on_sel_source(self) -> None:
        """Select all source meshes in Maya."""
        meshes = [self._list_source.item(i).text() for i in range(self._list_source.count())]
        valid = [m for m in meshes if cmds.objExists(m)]
        if valid:
            cmds.select(valid, replace=True)

    # ------------------------------------------------------------------
    # Slots — Joints list (Cut tab)
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
    # Slots — Cutters list (Cut tab)
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
    # Slots — Cut (Step 1)
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
    # Slots — Pieces (Assign tab)
    # ------------------------------------------------------------------

    def _on_load_pieces(self) -> None:
        """Load child meshes from the piece group into the pieces list."""
        group_name = self._line_piece_group.text().strip()
        if not group_name or not cmds.objExists(group_name):
            cmds.warning(f"Proxy Builder: Piece group '{group_name}' not found")
            return

        descendants = cmds.listRelatives(group_name, allDescendents=True, type="transform") or []
        meshes = [d for d in descendants if cmds.listRelatives(d, shapes=True, type="mesh")]

        self._list_pieces.clear()
        for m in meshes:
            self._list_pieces.addItem(m)
        logger.info("Loaded %d pieces from '%s'", len(meshes), group_name)

    def _on_add_pieces(self) -> None:
        """Add selected mesh transforms to the pieces list."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more mesh transforms")
            return
        existing = {self._list_pieces.item(i).text() for i in range(self._list_pieces.count())}
        for node in sel:
            shapes = cmds.listRelatives(node, shapes=True, type="mesh")
            if shapes and node not in existing:
                self._list_pieces.addItem(node)

    def _on_remove_pieces(self) -> None:
        """Remove selected items from the pieces list."""
        for item in reversed(self._list_pieces.selectedItems()):
            self._list_pieces.takeItem(self._list_pieces.row(item))

    # ------------------------------------------------------------------
    # Slots — Reference Mesh (Assign tab)
    # ------------------------------------------------------------------

    def _on_set_ref_mesh(self) -> None:
        """Set the reference mesh from Maya selection."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select a mesh transform")
            return
        mesh = sel[0]
        if not cmds.listRelatives(mesh, shapes=True, type="mesh"):
            cmds.warning(f"Proxy Builder: '{mesh}' is not a mesh transform")
            return
        self._line_ref_mesh.setText(mesh)

    def _on_sel_ref_mesh(self) -> None:
        """Select the reference mesh in Maya."""
        mesh = self._line_ref_mesh.text().strip()
        if mesh and cmds.objExists(mesh):
            cmds.select(mesh, replace=True)

    # ------------------------------------------------------------------
    # Slots — Assign Joints (Assign tab)
    # ------------------------------------------------------------------

    def _on_add_assign_joints(self) -> None:
        """Add selected joints to the assign joints list."""
        sel = cmds.ls(selection=True, type="joint")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more joints")
            return
        existing = {self._list_assign_joints.item(i).text() for i in range(self._list_assign_joints.count())}
        for joint in sel:
            if joint not in existing:
                self._list_assign_joints.addItem(joint)

    def _on_remove_assign_joints(self) -> None:
        """Remove selected items from the assign joints list."""
        for item in reversed(self._list_assign_joints.selectedItems()):
            self._list_assign_joints.takeItem(self._list_assign_joints.row(item))

    # ------------------------------------------------------------------
    # Slots — Assign (Step 2)
    # ------------------------------------------------------------------

    @error_handler
    @undo_chunk("Proxy Builder: Assign")
    def _on_assign(self) -> None:
        """Auto-assign pieces to joints and create proxy groups."""
        pieces = [self._list_pieces.item(i).text() for i in range(self._list_pieces.count())]
        if not pieces:
            cmds.warning("Proxy Builder: Add at least one piece")
            return

        ref_mesh = self._line_ref_mesh.text().strip() or None
        joints = [self._list_assign_joints.item(i).text() for i in range(self._list_assign_joints.count())]

        if not ref_mesh and not joints:
            cmds.warning("Proxy Builder: Bone mode requires at least one joint")
            return

        assignment = assign_command.auto_assign_pieces(
            pieces=pieces,
            reference_mesh=ref_mesh,
            joints=joints if joints else None,
        )

        total = sum(len(v) for v in assignment.values())
        logger.info("Assigned %d pieces to %d joints", total, len(assignment))

        parent_group = self._line_output_group.text().strip() or "proxy_grp"
        groups = assign_command.create_proxy_groups(
            assignment=assignment,
            parent_group=parent_group,
        )
        logger.info("Created %d proxy groups under '%s'", len(groups), parent_group)

    # ------------------------------------------------------------------
    # Slots — Finalize (Step 3)
    # ------------------------------------------------------------------

    def _on_pick_finalize_group(self) -> None:
        """Set the finalize source group from Maya selection."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select a group transform")
            return
        self._line_finalize_group.setText(sel[0])

    def _on_refresh_groups(self) -> None:
        """Refresh the list of proxy groups under the source group."""
        group_name = self._line_finalize_group.text().strip()
        if not group_name or not cmds.objExists(group_name):
            cmds.warning(f"Proxy Builder: Source group '{group_name}' not found")
            return

        self._list_finalize_groups.clear()
        children = cmds.listRelatives(group_name, children=True, type="transform") or []
        for child in children:
            meshes = cmds.listRelatives(child, children=True, type="transform") or []
            mesh_count = sum(1 for m in meshes if cmds.listRelatives(m, shapes=True, type="mesh"))
            self._list_finalize_groups.addItem(f"{child}  ({mesh_count} pieces)")

    @error_handler
    @undo_chunk("Proxy Builder: Finalize")
    def _on_finalize(self) -> None:
        """Finalize proxy groups."""
        parent_group = self._line_finalize_group.text().strip()
        if not parent_group or not cmds.objExists(parent_group):
            cmds.warning(f"Proxy Builder: Source group '{parent_group}' not found")
            return

        combine_mode = "per_shader" if self._btn_group_combine.checkedId() == 1 else "single"
        output_group = self._line_finalize_output.text().strip() or "proxy_final_grp"
        results = finalize_command.finalize_proxy_groups(
            parent_group=parent_group,
            combine_mode=combine_mode,
            output_group=output_group,
        )
        logger.info("Finalized %d proxy meshes", len(results))

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
            "cut_method": self._btn_group_cut_method.checkedId(),
            "keep_original": self._chk_keep_original.isChecked(),
            "merge_end_joints": self._chk_merge_end_joints.isChecked(),
            "piece_group": self._line_piece_group.text(),
            "output_group": self._line_output_group.text(),
            "finalize_group": self._line_finalize_group.text(),
            "finalize_output": self._line_finalize_output.text(),
            "combine_mode": "per_shader" if self._btn_group_combine.checkedId() == 1 else "single",
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict) -> None:
        self._tab_main.setCurrentIndex(settings_data.get("active_step", 0))

        cut_method = settings_data.get("cut_method", 0)
        if cut_method == 1:
            self._radio_by_planes.setChecked(True)
            self._stack_cut_method.setCurrentIndex(1)
        else:
            self._radio_by_weights.setChecked(True)
            self._stack_cut_method.setCurrentIndex(0)

        self._chk_keep_original.setChecked(settings_data.get("keep_original", True))
        self._chk_merge_end_joints.setChecked(settings_data.get("merge_end_joints", False))
        self._line_piece_group.setText(settings_data.get("piece_group", "piece_grp"))
        self._line_output_group.setText(settings_data.get("output_group", "proxy_grp"))
        self._line_finalize_group.setText(settings_data.get("finalize_group", "proxy_grp"))
        self._line_finalize_output.setText(settings_data.get("finalize_output", "proxy_final_grp"))

        combine_mode = settings_data.get("combine_mode", "single")
        if combine_mode == "per_shader":
            self._radio_per_shader.setChecked(True)
        else:
            self._radio_single.setChecked(True)

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
