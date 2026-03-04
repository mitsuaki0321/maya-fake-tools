"""Proxy Builder UI layer.

Provides a four-tab interface for the proxy building workflow:
Cut -> Assign -> Finalize -> Plane.
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
    QComboBox,
    QDoubleValidator,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    Qt,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.extra_widgets import HorizontalSeparator
from . import assign_command, cut_command, finalize_command, plane

logger = getLogger(__name__)

_instance = None


class SceneNodeListWidget(QListWidget):
    """QListWidget that selects corresponding Maya scene nodes on item selection.

    Node names are resolved from ``Qt.UserRole`` data first, falling back to
    ``item.text()``.  A ``_sync_enabled`` flag prevents ``cmds.select`` from
    firing during programmatic list modifications (clear / addItem / takeItem).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sync_enabled = True
        self.itemSelectionChanged.connect(self._on_selection_changed)

    # -- public helpers --------------------------------------------------

    def set_sync_enabled(self, enabled: bool) -> None:
        """Enable / disable scene-selection syncing."""
        self._sync_enabled = enabled

    # -- internal --------------------------------------------------------

    def _node_name(self, item: QListWidgetItem) -> str:
        """Return the Maya node name stored on *item*."""
        data = item.data(Qt.UserRole)
        return data if data else item.text()

    def _on_selection_changed(self) -> None:
        if not self._sync_enabled:
            return
        items = self.selectedItems()
        if not items:
            return
        nodes = [self._node_name(it) for it in items]
        valid = [n for n in nodes if cmds.objExists(n)]
        if valid:
            cmds.select(valid, replace=True)


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
        self._tab_main.addTab(self._build_plane_tab(), "Plane")
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
        self._list_pieces = SceneNodeListWidget()
        self._list_pieces.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row_pieces.addWidget(self._list_pieces, 1)

        col_pieces_btns = QVBoxLayout()
        self._btn_add_pieces = QPushButton("Add")
        self._btn_remove_pieces = QPushButton("Remove")
        self._btn_select_all_pieces = QPushButton("Select All")

        # Match Load button width with Add/Remove column
        btn_width = self._btn_select_all_pieces.sizeHint().width()
        self._btn_load_pieces.setFixedWidth(btn_width)
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
        self._btn_load_finalize_groups = QPushButton("Load")
        row_src.addWidget(self._btn_load_finalize_groups)
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
        layout.addWidget(QLabel("Groups:"))

        self._list_finalize_groups = SceneNodeListWidget()
        self._list_finalize_groups.setSelectionMode(QAbstractItemView.ExtendedSelection)
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

    def _build_plane_tab(self) -> QWidget:
        """Build the Plane tab (cutting plane creation and mirroring)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = get_spacing(tab, direction="vertical")
        layout.setSpacing(int(spacing * 0.5))

        # === Create Plane at Joint ===
        grp_create = QGroupBox("Create Plane at Joint")
        lay_create = QVBoxLayout(grp_create)
        lay_create.setSpacing(int(spacing * 0.5))

        # Compute uniform label widths
        lbl_joints = QLabel("Joints:")
        lbl_target_mesh = QLabel("Target Mesh:")
        field_label_width = max(lbl_joints.sizeHint().width(), lbl_target_mesh.sizeHint().width())
        for lbl in (lbl_joints, lbl_target_mesh):
            lbl.setFixedWidth(field_label_width)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lbl_plane_type = QLabel("Plane Type:")
        lbl_rotation_mode = QLabel("Rotation Mode:")
        lbl_axis = QLabel("Axis:")
        for lbl in (lbl_plane_type, lbl_rotation_mode, lbl_axis):
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Joints
        row_joints = QHBoxLayout()
        row_joints.addWidget(lbl_joints)
        self._line_plane_joints = QLineEdit()
        self._line_plane_joints.setReadOnly(True)
        self._line_plane_joints.setPlaceholderText("(select one or more joints)")
        row_joints.addWidget(self._line_plane_joints, 1)
        self._btn_set_plane_joints = QPushButton("Set")
        row_joints.addWidget(self._btn_set_plane_joints)
        lay_create.addLayout(row_joints)

        # Target Mesh
        row_target = QHBoxLayout()
        row_target.addWidget(lbl_target_mesh)
        self._line_plane_target_mesh = QLineEdit()
        self._line_plane_target_mesh.setReadOnly(True)
        self._line_plane_target_mesh.setPlaceholderText("(optional, for auto-size)")
        row_target.addWidget(self._line_plane_target_mesh, 1)
        self._btn_set_plane_target_mesh = QPushButton("Set")
        row_target.addWidget(self._btn_set_plane_target_mesh)
        lay_create.addLayout(row_target)

        lay_create.addWidget(HorizontalSeparator())

        # Plane Type / Rotation Mode (grid for vertical alignment)
        grid_radios = QGridLayout()
        grid_radios.setContentsMargins(0, 0, 0, 0)

        self._radio_plane_nurbs = QRadioButton("NURBS")
        self._radio_plane_poly = QRadioButton("Poly")
        self._radio_plane_nurbs.setChecked(True)
        self._btn_group_plane_type = QButtonGroup(self)
        self._btn_group_plane_type.addButton(self._radio_plane_nurbs, 0)
        self._btn_group_plane_type.addButton(self._radio_plane_poly, 1)

        self._radio_rot_joint = QRadioButton("Joint")
        self._radio_rot_aim = QRadioButton("Aim")
        self._radio_rot_manual = QRadioButton("Manual")
        self._radio_rot_joint.setChecked(True)
        self._btn_group_rotation_mode = QButtonGroup(self)
        self._btn_group_rotation_mode.addButton(self._radio_rot_joint, 0)
        self._btn_group_rotation_mode.addButton(self._radio_rot_aim, 1)
        self._btn_group_rotation_mode.addButton(self._radio_rot_manual, 2)

        self._radio_axis_x = QRadioButton("X")
        self._radio_axis_y = QRadioButton("Y")
        self._radio_axis_z = QRadioButton("Z")
        self._radio_axis_y.setChecked(True)
        self._btn_group_axis = QButtonGroup(self)
        self._btn_group_axis.addButton(self._radio_axis_x, 0)
        self._btn_group_axis.addButton(self._radio_axis_y, 1)
        self._btn_group_axis.addButton(self._radio_axis_z, 2)

        grid_radios.addWidget(lbl_plane_type, 0, 0)
        grid_radios.addWidget(self._radio_plane_nurbs, 0, 1)
        grid_radios.addWidget(self._radio_plane_poly, 0, 2)

        grid_radios.addWidget(lbl_axis, 1, 0)
        grid_radios.addWidget(self._radio_axis_x, 1, 1)
        grid_radios.addWidget(self._radio_axis_y, 1, 2)
        grid_radios.addWidget(self._radio_axis_z, 1, 3)

        grid_radios.addWidget(lbl_rotation_mode, 2, 0)
        grid_radios.addWidget(self._radio_rot_joint, 2, 1)
        grid_radios.addWidget(self._radio_rot_aim, 2, 2)
        grid_radios.addWidget(self._radio_rot_manual, 2, 3)

        grid_radios.setColumnStretch(4, 1)
        lay_create.addLayout(grid_radios)

        # Label width for stacked pages (match grid col0 = Rotation Mode label)
        stacked_label_width = lbl_rotation_mode.sizeHint().width()

        # QStackedWidget for rotation mode pages
        self._stack_rotation_mode = QStackedWidget()

        # Page 0: Joint (hint label)
        page_joint = QWidget()
        lay_page_joint = QVBoxLayout(page_joint)
        lay_page_joint.setContentsMargins(0, 0, 0, 0)
        lbl_joint_hint = QLabel("Uses the joint's world rotation.")
        lbl_joint_hint.setEnabled(False)
        lay_page_joint.addWidget(lbl_joint_hint)
        lay_page_joint.addStretch()
        self._stack_rotation_mode.addWidget(page_joint)

        # Page 1: Aim
        page_aim = QWidget()
        lay_page_aim = QVBoxLayout(page_aim)
        lay_page_aim.setContentsMargins(0, 0, 0, 0)

        # Aim Target row
        row_aim_target = QHBoxLayout()
        lbl_aim_target = QLabel("Aim Target:")
        lbl_aim_target.setFixedWidth(stacked_label_width)
        lbl_aim_target.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_aim_target.addWidget(lbl_aim_target)
        self._combo_aim_target = QComboBox()
        self._combo_aim_target.addItems(["Auto", "Parent", "Chain"])
        row_aim_target.addWidget(self._combo_aim_target)
        row_aim_target.addStretch()
        lay_page_aim.addLayout(row_aim_target)

        # Aim Joint row
        row_aim = QHBoxLayout()
        lbl_aim_joint = QLabel("Aim Joint:")
        lbl_aim_joint.setFixedWidth(stacked_label_width)
        lbl_aim_joint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_aim.addWidget(lbl_aim_joint)
        self._line_plane_aim_joint = QLineEdit()
        self._line_plane_aim_joint.setReadOnly(True)
        self._line_plane_aim_joint.setPlaceholderText("(optional: auto-resolved if empty / ignored for multiple joints)")
        row_aim.addWidget(self._line_plane_aim_joint, 1)
        self._btn_set_plane_aim_joint = QPushButton("Set")
        row_aim.addWidget(self._btn_set_plane_aim_joint)
        lay_page_aim.addLayout(row_aim)
        lay_page_aim.addStretch()
        self._stack_rotation_mode.addWidget(page_aim)

        # Page 2: Manual
        page_manual = QWidget()
        lay_page_manual = QVBoxLayout(page_manual)
        lay_page_manual.setContentsMargins(0, 0, 0, 0)
        row_manual = QHBoxLayout()
        lbl_rotation = QLabel("Rotation:")
        lbl_rotation.setFixedWidth(stacked_label_width)
        lbl_rotation.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_manual.addWidget(lbl_rotation)
        rot_validator = QDoubleValidator(-360.0, 360.0, 2, self)
        self._line_rot_x = QLineEdit("0.0")
        self._line_rot_y = QLineEdit("0.0")
        self._line_rot_z = QLineEdit("0.0")
        for line in (self._line_rot_x, self._line_rot_y, self._line_rot_z):
            line.setValidator(rot_validator)
            row_manual.addWidget(line)
        row_manual.addStretch()
        lay_page_manual.addLayout(row_manual)
        lay_page_manual.addStretch()
        self._stack_rotation_mode.addWidget(page_manual)

        lay_create.addWidget(self._stack_rotation_mode)

        # Size Scale
        row_scale = QHBoxLayout()
        lbl_size_scale = QLabel("Size Scale:")
        lbl_size_scale.setFixedWidth(stacked_label_width)
        lbl_size_scale.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_scale.addWidget(lbl_size_scale)
        self._line_size_scale = QLineEdit("1.0")
        self._line_size_scale.setValidator(QDoubleValidator(0.01, 100.0, 2, self))
        row_scale.addWidget(self._line_size_scale)
        row_scale.addStretch()
        lay_create.addLayout(row_scale)

        # Create Plane button
        self._btn_create_plane = QPushButton("Create Plane")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_create_plane.setMinimumHeight(int(height * 0.08))
        lay_create.addWidget(self._btn_create_plane)

        layout.addWidget(grp_create)

        # === Mirror Plane ===
        grp_mirror = QGroupBox("Mirror Plane")
        lay_mirror = QVBoxLayout(grp_mirror)
        lay_mirror.setSpacing(int(spacing * 0.5))

        row_mirror_axis = QHBoxLayout()
        row_mirror_axis.addWidget(QLabel("Mirror Axis:"))
        self._radio_mirror_x = QRadioButton("X")
        self._radio_mirror_y = QRadioButton("Y")
        self._radio_mirror_z = QRadioButton("Z")
        self._radio_mirror_x.setChecked(True)
        self._btn_group_mirror_axis = QButtonGroup(self)
        self._btn_group_mirror_axis.addButton(self._radio_mirror_x, 0)
        self._btn_group_mirror_axis.addButton(self._radio_mirror_y, 1)
        self._btn_group_mirror_axis.addButton(self._radio_mirror_z, 2)
        row_mirror_axis.addWidget(self._radio_mirror_x)
        row_mirror_axis.addWidget(self._radio_mirror_y)
        row_mirror_axis.addWidget(self._radio_mirror_z)
        row_mirror_axis.addStretch()
        lay_mirror.addLayout(row_mirror_axis)

        self._btn_mirror_plane = QPushButton("Mirror")
        self._btn_mirror_plane.setMinimumHeight(int(height * 0.08))
        lay_mirror.addWidget(self._btn_mirror_plane)

        layout.addWidget(grp_mirror)
        layout.addStretch()

        return tab

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        # Cut tab
        self._btn_add_source.clicked.connect(self._on_add_source)
        self._btn_remove_source.clicked.connect(self._on_remove_source)
        self._btn_clear_source.clicked.connect(self._on_clear_source)
        self._radio_by_weights.toggled.connect(lambda checked: self._stack_cut_method.setCurrentIndex(0 if checked else 1))
        self._btn_add_joints.clicked.connect(self._on_add_joints)
        self._btn_remove_joints.clicked.connect(self._on_remove_joints)
        self._btn_select_all_joints.clicked.connect(lambda: self._select_all_items(self._list_joints))
        self._btn_add_cutters.clicked.connect(self._on_add_cutters)
        self._btn_remove_cutters.clicked.connect(self._on_remove_cutters)
        self._btn_select_all_cutters.clicked.connect(lambda: self._select_all_items(self._list_cutters))
        self._btn_cut.clicked.connect(self._on_cut)

        # Assign tab
        self._btn_load_pieces.clicked.connect(self._on_load_pieces)
        self._btn_add_pieces.clicked.connect(self._on_add_pieces)
        self._btn_remove_pieces.clicked.connect(self._on_remove_pieces)
        self._btn_select_all_pieces.clicked.connect(lambda: self._select_all_items(self._list_pieces))
        self._radio_assign_by_weights.toggled.connect(lambda checked: self._stack_assign_method.setCurrentIndex(0 if checked else 1))
        self._btn_set_ref_mesh.clicked.connect(self._on_set_ref_mesh)
        self._btn_add_assign_joints_w.clicked.connect(self._on_add_assign_joints_w)
        self._btn_remove_assign_joints_w.clicked.connect(self._on_remove_assign_joints_w)
        self._btn_select_all_assign_joints_w.clicked.connect(lambda: self._select_all_items(self._list_assign_joints_w))
        self._btn_add_assign_joints_b.clicked.connect(self._on_add_assign_joints_b)
        self._btn_remove_assign_joints_b.clicked.connect(self._on_remove_assign_joints_b)
        self._btn_select_all_assign_joints_b.clicked.connect(lambda: self._select_all_items(self._list_assign_joints_b))
        self._btn_assign.clicked.connect(self._on_assign)

        # Finalize tab
        self._btn_load_finalize_groups.clicked.connect(self._on_load_finalize_groups)
        self._btn_finalize.clicked.connect(self._on_finalize)

        # Plane tab
        self._btn_set_plane_joints.clicked.connect(self._on_set_plane_joints)
        self._btn_set_plane_target_mesh.clicked.connect(self._on_set_plane_target_mesh)
        self._btn_set_plane_aim_joint.clicked.connect(self._on_set_plane_aim_joint)
        self._combo_aim_target.currentIndexChanged.connect(self._on_aim_target_changed)
        self._btn_group_rotation_mode.buttonClicked.connect(
            lambda btn: self._stack_rotation_mode.setCurrentIndex(self._btn_group_rotation_mode.id(btn))
        )
        self._btn_create_plane.clicked.connect(self._on_create_plane)
        self._btn_mirror_plane.clicked.connect(self._on_mirror_plane)

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
        self._list_joints.set_sync_enabled(False)
        for item in reversed(self._list_joints.selectedItems()):
            self._list_joints.takeItem(self._list_joints.row(item))
        self._list_joints.set_sync_enabled(True)

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
        self._list_cutters.set_sync_enabled(False)
        for item in reversed(self._list_cutters.selectedItems()):
            self._list_cutters.takeItem(self._list_cutters.row(item))
        self._list_cutters.set_sync_enabled(True)

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

    # ------------------------------------------------------------------
    # Slots — Assign Joints (Assign tab)
    # ------------------------------------------------------------------

    def _add_joints_to_list(self, list_widget: SceneNodeListWidget) -> None:
        """Add selected joints to the given list widget (skip duplicates)."""
        sel = cmds.ls(selection=True, type="joint")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more joints")
            return
        existing = {list_widget.item(i).text() for i in range(list_widget.count())}
        for joint in sel:
            if joint not in existing:
                list_widget.addItem(joint)

    def _remove_from_list(self, list_widget: SceneNodeListWidget) -> None:
        """Remove selected items from the given list widget."""
        list_widget.set_sync_enabled(False)
        for item in reversed(list_widget.selectedItems()):
            list_widget.takeItem(list_widget.row(item))
        list_widget.set_sync_enabled(True)

    def _select_all_items(self, list_widget: SceneNodeListWidget) -> None:
        """Select all items in the given list widget."""
        list_widget.selectAll()

    def _on_add_assign_joints_w(self) -> None:
        """Add selected joints to the weights joints list."""
        self._add_joints_to_list(self._list_assign_joints_w)

    def _on_remove_assign_joints_w(self) -> None:
        """Remove selected items from the weights joints list."""
        self._remove_from_list(self._list_assign_joints_w)

    def _on_add_assign_joints_b(self) -> None:
        """Add selected joints to the bones joints list."""
        self._add_joints_to_list(self._list_assign_joints_b)

    def _on_remove_assign_joints_b(self) -> None:
        """Remove selected items from the bones joints list."""
        self._remove_from_list(self._list_assign_joints_b)

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
    # Slots — Finalize (Step 3)
    # ------------------------------------------------------------------

    def _on_load_finalize_groups(self) -> None:
        """Load proxy groups from the source group into the groups list."""
        group_name = self._line_finalize_group.text().strip()
        if not group_name or not cmds.objExists(group_name):
            cmds.warning(f"Proxy Builder: Source group '{group_name}' not found")
            return

        self._list_finalize_groups.set_sync_enabled(False)
        self._list_finalize_groups.clear()
        children = cmds.listRelatives(group_name, children=True, type="transform") or []
        for child in children:
            meshes = cmds.listRelatives(child, children=True, type="transform") or []
            mesh_count = sum(1 for m in meshes if cmds.listRelatives(m, shapes=True, type="mesh"))
            item = QListWidgetItem(f"{child}  ({mesh_count} pieces)")
            item.setData(Qt.UserRole, child)
            self._list_finalize_groups.addItem(item)
        self._list_finalize_groups.set_sync_enabled(True)

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
    # Slots — Plane tab
    # ------------------------------------------------------------------

    def _on_set_plane_joints(self) -> None:
        """Set joints from Maya selection."""
        sel = cmds.ls(selection=True, type="joint")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more joints")
            return
        self._line_plane_joints.setText(", ".join(sel))

    def _on_set_plane_target_mesh(self) -> None:
        """Set the target mesh from Maya selection, or clear if nothing is selected."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            self._line_plane_target_mesh.clear()
            return
        mesh = sel[0]
        if not cmds.listRelatives(mesh, shapes=True, type="mesh"):
            cmds.warning(f"Proxy Builder: '{mesh}' is not a mesh transform")
            return
        self._line_plane_target_mesh.setText(mesh)

    def _on_set_plane_aim_joint(self) -> None:
        """Set the aim joint from Maya selection, or clear if nothing is selected."""
        sel = cmds.ls(selection=True, type="joint")
        if not sel:
            self._line_plane_aim_joint.clear()
            return
        self._line_plane_aim_joint.setText(sel[0])

    def _on_aim_target_changed(self, index: int) -> None:
        """Enable/disable aim joint field based on aim target mode.

        Chain mode (index 2) does not use an explicit aim joint,
        so the field and Set button are disabled and cleared.
        """
        is_chain = index == 2
        self._line_plane_aim_joint.setEnabled(not is_chain)
        self._btn_set_plane_aim_joint.setEnabled(not is_chain)
        if is_chain:
            self._line_plane_aim_joint.clear()

    @error_handler
    @undo_chunk("Proxy Builder: Create Plane")
    def _on_create_plane(self) -> None:
        """Create cutting planes at the specified joints."""
        joints_text = self._line_plane_joints.text().strip()
        if not joints_text:
            cmds.warning("Proxy Builder: Set joints first")
            return

        joints = [j.strip() for j in joints_text.split(",") if j.strip()]
        if not joints:
            cmds.warning("Proxy Builder: Set joints first")
            return

        target_mesh = self._line_plane_target_mesh.text().strip() or None
        plane_type = "nurbs" if self._btn_group_plane_type.checkedId() == 0 else "poly"

        rotation_mode_id = self._btn_group_rotation_mode.checkedId()
        rotation_mode_map = {0: "joint", 1: "aim", 2: "manual"}
        rotation_mode = rotation_mode_map[rotation_mode_id]

        # Aim target / aim joint: only used when aim mode
        aim_target_map = {0: "auto", 1: "parent", 2: "chain"}
        aim_target = aim_target_map[self._combo_aim_target.currentIndex()]

        aim_joint = None
        if rotation_mode == "aim" and len(joints) == 1:
            aim_joint = self._line_plane_aim_joint.text().strip() or None

        rotation = None
        if rotation_mode == "manual":
            rotation = (
                float(self._line_rot_x.text() or 0),
                float(self._line_rot_y.text() or 0),
                float(self._line_rot_z.text() or 0),
            )

        size_scale = float(self._line_size_scale.text() or 1.0)

        axis_map = {0: (1, 0, 0), 1: (0, 1, 0), 2: (0, 0, 1)}
        axis = axis_map[self._btn_group_axis.checkedId()]

        results = []
        for joint in joints:
            result = plane.create_plane_at_joint(
                joint=joint,
                target_mesh=target_mesh,
                plane_type=plane_type,
                rotation_mode=rotation_mode,
                aim_joint=aim_joint,
                aim_target=aim_target,
                rotation=rotation,
                size_scale=size_scale,
                axis=axis,
            )
            results.append(result)

        cmds.select(results, replace=True)
        logger.info("Created %d plane(s): %s", len(results), results)

    @error_handler
    @undo_chunk("Proxy Builder: Mirror Plane")
    def _on_mirror_plane(self) -> None:
        """Mirror the selected plane(s) across the chosen axis."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select one or more planes to mirror")
            return

        axis_map = {0: "x", 1: "y", 2: "z"}
        axis = axis_map[self._btn_group_mirror_axis.checkedId()]

        results = []
        for source in sel:
            mirrored = plane.mirror_plane(source=source, axis=axis)
            results.append(mirrored)

        if results:
            cmds.select(results, replace=True)
            logger.info("Mirrored %d plane(s)", len(results))

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
            "assign_method": self._btn_group_assign_method.checkedId(),
            "output_group": self._line_output_group.text(),
            "finalize_group": self._line_finalize_group.text(),
            "finalize_output": self._line_finalize_output.text(),
            "combine_mode": "per_shader" if self._btn_group_combine.checkedId() == 1 else "single",
            "plane_type": self._btn_group_plane_type.checkedId(),
            "rotation_mode": self._btn_group_rotation_mode.checkedId(),
            "aim_target": self._combo_aim_target.currentIndex(),
            "manual_rotation_x": self._line_rot_x.text(),
            "manual_rotation_y": self._line_rot_y.text(),
            "manual_rotation_z": self._line_rot_z.text(),
            "size_scale": self._line_size_scale.text(),
            "plane_axis": self._btn_group_axis.checkedId(),
            "mirror_axis": self._btn_group_mirror_axis.checkedId(),
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

        assign_method = settings_data.get("assign_method", 0)
        if assign_method == 1:
            self._radio_assign_by_bones.setChecked(True)
            self._stack_assign_method.setCurrentIndex(1)
        else:
            self._radio_assign_by_weights.setChecked(True)
            self._stack_assign_method.setCurrentIndex(0)

        self._line_output_group.setText(settings_data.get("output_group", "proxy_grp"))
        self._line_finalize_group.setText(settings_data.get("finalize_group", "proxy_grp"))
        self._line_finalize_output.setText(settings_data.get("finalize_output", "proxy_final_grp"))

        combine_mode = settings_data.get("combine_mode", "single")
        if combine_mode == "per_shader":
            self._radio_per_shader.setChecked(True)
        else:
            self._radio_single.setChecked(True)

        # Plane tab
        plane_type = settings_data.get("plane_type", 0)
        if plane_type == 1:
            self._radio_plane_poly.setChecked(True)
        else:
            self._radio_plane_nurbs.setChecked(True)

        rotation_mode = settings_data.get("rotation_mode", 0)
        rot_radios = {0: self._radio_rot_joint, 1: self._radio_rot_aim, 2: self._radio_rot_manual}
        rot_radios.get(rotation_mode, self._radio_rot_joint).setChecked(True)
        self._stack_rotation_mode.setCurrentIndex(rotation_mode)

        self._combo_aim_target.setCurrentIndex(settings_data.get("aim_target", 0))

        self._line_rot_x.setText(str(settings_data.get("manual_rotation_x", "0.0")))
        self._line_rot_y.setText(str(settings_data.get("manual_rotation_y", "0.0")))
        self._line_rot_z.setText(str(settings_data.get("manual_rotation_z", "0.0")))
        self._line_size_scale.setText(str(settings_data.get("size_scale", "1.0")))

        plane_axis = settings_data.get("plane_axis", 1)
        axis_radios = {0: self._radio_axis_x, 1: self._radio_axis_y, 2: self._radio_axis_z}
        axis_radios.get(plane_axis, self._radio_axis_y).setChecked(True)

        mirror_axis = settings_data.get("mirror_axis", 0)
        mirror_radios = {0: self._radio_mirror_x, 1: self._radio_mirror_y, 2: self._radio_mirror_z}
        mirror_radios.get(mirror_axis, self._radio_mirror_x).setChecked(True)

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
