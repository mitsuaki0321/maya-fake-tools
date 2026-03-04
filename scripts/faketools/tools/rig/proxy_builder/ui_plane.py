"""Proxy Builder — Plane tab (cutting plane creation and mirroring)."""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QComboBox,
    QDoubleValidator,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.extra_widgets import HorizontalSeparator
from . import plane_command

logger = getLogger(__name__)


class PlaneTab(QWidget):
    """Plane tab widget for creating and mirroring cutting planes."""

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

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
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
    # Slots
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
            result = plane_command.create_plane_at_joint(
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
            mirrored = plane_command.mirror_plane(source=source, axis=axis)
            results.append(mirrored)

        if results:
            cmds.select(results, replace=True)
            logger.info("Mirrored %d plane(s)", len(results))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "plane_type": self._btn_group_plane_type.checkedId(),
            "rotation_mode": self._btn_group_rotation_mode.checkedId(),
            "aim_target": self._combo_aim_target.currentIndex(),
            "manual_rotation_x": self._line_rot_x.text(),
            "manual_rotation_y": self._line_rot_y.text(),
            "manual_rotation_z": self._line_rot_z.text(),
            "size_scale": self._line_size_scale.text(),
            "plane_axis": self._btn_group_axis.checkedId(),
            "mirror_axis": self._btn_group_mirror_axis.checkedId(),
        }

    def _apply_settings(self, data: dict) -> None:
        plane_type = data.get("plane_type", 0)
        if plane_type == 1:
            self._radio_plane_poly.setChecked(True)
        else:
            self._radio_plane_nurbs.setChecked(True)

        rotation_mode = data.get("rotation_mode", 0)
        rot_radios = {0: self._radio_rot_joint, 1: self._radio_rot_aim, 2: self._radio_rot_manual}
        rot_radios.get(rotation_mode, self._radio_rot_joint).setChecked(True)
        self._stack_rotation_mode.setCurrentIndex(rotation_mode)

        self._combo_aim_target.setCurrentIndex(data.get("aim_target", 0))

        self._line_rot_x.setText(str(data.get("manual_rotation_x", "0.0")))
        self._line_rot_y.setText(str(data.get("manual_rotation_y", "0.0")))
        self._line_rot_z.setText(str(data.get("manual_rotation_z", "0.0")))
        self._line_size_scale.setText(str(data.get("size_scale", "1.0")))

        plane_axis = data.get("plane_axis", 1)
        axis_radios = {0: self._radio_axis_x, 1: self._radio_axis_y, 2: self._radio_axis_z}
        axis_radios.get(plane_axis, self._radio_axis_y).setChecked(True)

        mirror_axis = data.get("mirror_axis", 0)
        mirror_radios = {0: self._radio_mirror_x, 1: self._radio_mirror_y, 2: self._radio_mirror_z}
        mirror_radios.get(mirror_axis, self._radio_mirror_x).setChecked(True)
