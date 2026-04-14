"""Proxy Builder — Assign tab (Step 2)."""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.extra_widgets import HorizontalSeparator
from . import assign_command
from .ui_common import SceneNodeListWidget, add_joints_to_list, remove_from_list, select_all_items

logger = getLogger(__name__)


class AssignTab(QWidget):
    """Assign tab widget for auto-assigning pieces to joints."""

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

        # --- Piece Group ---
        row_piece_grp = QHBoxLayout()
        row_piece_grp.addWidget(QLabel("Piece Group:"))
        self._line_piece_group = QLineEdit("piece_grp")
        row_piece_grp.addWidget(self._line_piece_group, 1)
        self._btn_set_piece_group = QPushButton("Set")
        row_piece_grp.addWidget(self._btn_set_piece_group)
        self._btn_load_pieces = QPushButton("Load")
        row_piece_grp.addWidget(self._btn_load_pieces)
        layout.addLayout(row_piece_grp)

        # --- Pieces list ---
        row_pieces = QHBoxLayout()
        self._list_pieces = SceneNodeListWidget()
        self._list_pieces.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_pieces.addWidget(self._list_pieces, 1)

        col_pieces_btns = QVBoxLayout()
        self._btn_add_pieces = QPushButton("Add")
        self._btn_remove_pieces = QPushButton("Remove")
        self._btn_select_all_pieces = QPushButton("Select All")

        # Match Set / Load button widths to each other
        piece_grp_btn_width = max(
            self._btn_set_piece_group.sizeHint().width(),
            self._btn_load_pieces.sizeHint().width(),
        )
        self._btn_set_piece_group.setFixedWidth(piece_grp_btn_width)
        self._btn_load_pieces.setFixedWidth(piece_grp_btn_width)

        # Match Add/Remove/Select All column widths
        btn_width = self._btn_select_all_pieces.sizeHint().width()
        self._btn_add_pieces.setFixedWidth(btn_width)
        self._btn_remove_pieces.setFixedWidth(btn_width)
        self._btn_select_all_pieces.setFixedWidth(btn_width)
        col_pieces_btns.addWidget(self._btn_add_pieces)
        col_pieces_btns.addWidget(self._btn_remove_pieces)
        col_pieces_btns.addWidget(self._btn_select_all_pieces)
        col_pieces_btns.addStretch()
        row_pieces.addLayout(col_pieces_btns)

        layout.addLayout(row_pieces, 1)

        # --- Assign Method radio buttons ---
        row_assign_method = QHBoxLayout()
        row_assign_method.addWidget(QLabel("Assign Method:"))
        self._radio_assign_by_weights = QRadioButton("By Weights")
        self._radio_assign_by_bones = QRadioButton("By Bones")
        self._radio_assign_by_weights.setChecked(True)
        self._btn_group_assign_method = QButtonGroup(self)
        self._btn_group_assign_method.addButton(self._radio_assign_by_weights, 0)
        self._btn_group_assign_method.addButton(self._radio_assign_by_bones, 1)
        row_assign_method.addWidget(self._radio_assign_by_weights)
        row_assign_method.addWidget(self._radio_assign_by_bones)
        row_assign_method.addStretch()
        layout.addLayout(row_assign_method)

        # --- QStackedWidget for assign method pages ---
        self._stack_assign_method = QStackedWidget()

        # -- By Weights page --
        page_weights = QWidget()
        lay_weights = QVBoxLayout(page_weights)
        lay_weights.setSpacing(int(spacing * 0.5))
        lay_weights.setContentsMargins(0, 0, 0, 0)

        row_ref = QHBoxLayout()
        row_ref.addWidget(QLabel("Reference Mesh:"))
        self._line_ref_mesh = QLineEdit()
        self._line_ref_mesh.setReadOnly(True)
        self._line_ref_mesh.setPlaceholderText("(skinned mesh)")
        row_ref.addWidget(self._line_ref_mesh, 1)
        self._btn_set_ref_mesh = QPushButton("Set")
        self._btn_set_ref_mesh.setFixedWidth(btn_width)
        row_ref.addWidget(self._btn_set_ref_mesh)
        lay_weights.addLayout(row_ref)

        lay_weights.addWidget(QLabel("Joints:"))

        row_joints_w = QHBoxLayout()
        self._list_assign_joints_w = SceneNodeListWidget()
        self._list_assign_joints_w.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_joints_w.addWidget(self._list_assign_joints_w, 1)

        col_joints_w_btns = QVBoxLayout()
        self._btn_add_assign_joints_w = QPushButton("Add")
        self._btn_remove_assign_joints_w = QPushButton("Remove")
        self._btn_select_all_assign_joints_w = QPushButton("Select All")
        col_joints_w_btns.addWidget(self._btn_add_assign_joints_w)
        col_joints_w_btns.addWidget(self._btn_remove_assign_joints_w)
        col_joints_w_btns.addWidget(self._btn_select_all_assign_joints_w)
        col_joints_w_btns.addStretch()
        row_joints_w.addLayout(col_joints_w_btns)

        lay_weights.addLayout(row_joints_w, 1)

        lbl_hint_w = QLabel("* Leave empty to use all influences")
        lbl_hint_w.setEnabled(False)
        lay_weights.addWidget(lbl_hint_w)

        self._stack_assign_method.addWidget(page_weights)

        # -- By Bones page --
        page_bones = QWidget()
        lay_bones = QVBoxLayout(page_bones)
        lay_bones.setSpacing(int(spacing * 0.5))
        lay_bones.setContentsMargins(0, 0, 0, 0)

        lay_bones.addWidget(QLabel("Joints:"))

        row_joints_b = QHBoxLayout()
        self._list_assign_joints_b = SceneNodeListWidget()
        self._list_assign_joints_b.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_joints_b.addWidget(self._list_assign_joints_b, 1)

        col_joints_b_btns = QVBoxLayout()
        self._btn_add_assign_joints_b = QPushButton("Add")
        self._btn_remove_assign_joints_b = QPushButton("Remove")
        self._btn_select_all_assign_joints_b = QPushButton("Select All")
        col_joints_b_btns.addWidget(self._btn_add_assign_joints_b)
        col_joints_b_btns.addWidget(self._btn_remove_assign_joints_b)
        col_joints_b_btns.addWidget(self._btn_select_all_assign_joints_b)
        col_joints_b_btns.addStretch()
        row_joints_b.addLayout(col_joints_b_btns)

        lay_bones.addLayout(row_joints_b, 1)

        self._stack_assign_method.addWidget(page_bones)

        layout.addWidget(self._stack_assign_method, 1)

        # --- Output Group ---
        row_output = QHBoxLayout()
        row_output.addWidget(QLabel("Output Group:"))
        self._line_output_group = QLineEdit("proxy_grp")
        row_output.addWidget(self._line_output_group, 1)
        layout.addLayout(row_output)

        layout.addWidget(HorizontalSeparator())

        # --- Assign & Create Groups button ---
        self._btn_assign = QPushButton("Assign && Create Groups")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_assign.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_assign)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_piece_group.clicked.connect(self._on_set_piece_group)
        self._btn_load_pieces.clicked.connect(self._on_load_pieces)
        self._btn_add_pieces.clicked.connect(self._on_add_pieces)
        self._btn_remove_pieces.clicked.connect(self._on_remove_pieces)
        self._btn_select_all_pieces.clicked.connect(lambda: select_all_items(self._list_pieces))
        self._radio_assign_by_weights.toggled.connect(lambda checked: self._stack_assign_method.setCurrentIndex(0 if checked else 1))
        self._btn_set_ref_mesh.clicked.connect(self._on_set_ref_mesh)
        self._btn_add_assign_joints_w.clicked.connect(lambda: add_joints_to_list(self._list_assign_joints_w))
        self._btn_remove_assign_joints_w.clicked.connect(lambda: remove_from_list(self._list_assign_joints_w))
        self._btn_select_all_assign_joints_w.clicked.connect(lambda: select_all_items(self._list_assign_joints_w))
        self._btn_add_assign_joints_b.clicked.connect(lambda: add_joints_to_list(self._list_assign_joints_b))
        self._btn_remove_assign_joints_b.clicked.connect(lambda: remove_from_list(self._list_assign_joints_b))
        self._btn_select_all_assign_joints_b.clicked.connect(lambda: select_all_items(self._list_assign_joints_b))
        self._btn_assign.clicked.connect(self._on_assign)

    # ------------------------------------------------------------------
    # Slots — Pieces
    # ------------------------------------------------------------------

    def _on_set_piece_group(self) -> None:
        """Set the piece group from Maya selection."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select a group transform")
            return
        self._line_piece_group.setText(sel[0])

    def _on_load_pieces(self) -> None:
        """Load child meshes from the piece group into the pieces list."""
        group_name = self._line_piece_group.text().strip()
        if not group_name or not cmds.objExists(group_name):
            cmds.warning(f"Proxy Builder: Piece group '{group_name}' not found")
            return

        descendants = cmds.listRelatives(group_name, allDescendents=True, type="transform") or []
        meshes = [d for d in descendants if cmds.listRelatives(d, shapes=True, type="mesh")]

        self._list_pieces.set_sync_enabled(False)
        self._list_pieces.clear()
        for m in meshes:
            self._list_pieces.addItem(m)
        self._list_pieces.set_sync_enabled(True)
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
        self._list_pieces.set_sync_enabled(False)
        for item in reversed(self._list_pieces.selectedItems()):
            self._list_pieces.takeItem(self._list_pieces.row(item))
        self._list_pieces.set_sync_enabled(True)

    # ------------------------------------------------------------------
    # Slots — Reference Mesh
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

    # ------------------------------------------------------------------
    # Slots — Assign
    # ------------------------------------------------------------------

    @error_handler
    @undo_chunk("Proxy Builder: Assign")
    def _on_assign(self) -> None:
        """Auto-assign pieces to joints and create proxy groups."""
        pieces = [self._list_pieces.item(i).text() for i in range(self._list_pieces.count())]
        if not pieces:
            cmds.warning("Proxy Builder: Add at least one piece")
            return

        method_id = self._btn_group_assign_method.checkedId()

        if method_id == 0:
            # By Weights
            ref_mesh = self._line_ref_mesh.text().strip() or None
            if not ref_mesh:
                cmds.warning("Proxy Builder: Set a reference mesh for weight mode")
                return
            joints = [self._list_assign_joints_w.item(i).text() for i in range(self._list_assign_joints_w.count())]
        else:
            # By Bones
            ref_mesh = None
            joints = [self._list_assign_joints_b.item(i).text() for i in range(self._list_assign_joints_b.count())]
            if not joints:
                cmds.warning("Proxy Builder: Add at least one joint for bone mode")
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
    # Settings
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "piece_group": self._line_piece_group.text(),
            "assign_method": self._btn_group_assign_method.checkedId(),
            "output_group": self._line_output_group.text(),
        }

    def _apply_settings(self, data: dict) -> None:
        self._line_piece_group.setText(data.get("piece_group", "piece_grp"))

        assign_method = data.get("assign_method", 0)
        if assign_method == 1:
            self._radio_assign_by_bones.setChecked(True)
            self._stack_assign_method.setCurrentIndex(1)
        else:
            self._radio_assign_by_weights.setChecked(True)
            self._stack_assign_method.setCurrentIndex(0)

        self._line_output_group.setText(data.get("output_group", "proxy_grp"))
