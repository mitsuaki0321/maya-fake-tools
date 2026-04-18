"""Proxy Builder — Plane tab (cutting plane creation and mirroring)."""

from __future__ import annotations

from logging import getLogger

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.base_window import get_spacing
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_dialog import show_info_dialog, show_warning_dialog
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QComboBox,
    QDoubleValidator,
    QFileDialog,
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
from . import plane_command, plane_io
from .plane_io import PlaneSpec

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
        lbl_target_mesh = QLabel("Target Mesh:")
        lbl_target_mesh.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lbl_rotation_mode = QLabel("Rotation Mode:")
        lbl_axis = QLabel("Axis:")
        for lbl in (lbl_rotation_mode, lbl_axis):
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Target Mesh
        row_target = QHBoxLayout()
        self._lbl_target_mesh = lbl_target_mesh
        row_target.addWidget(self._lbl_target_mesh)
        self._line_plane_target_mesh = QLineEdit()
        self._line_plane_target_mesh.setReadOnly(True)
        self._line_plane_target_mesh.setPlaceholderText("(optional, for auto-size)")
        row_target.addWidget(self._line_plane_target_mesh, 1)
        self._btn_set_plane_target_mesh = QPushButton("Set")
        row_target.addWidget(self._btn_set_plane_target_mesh)
        self._btn_toggle_target_mesh = QPushButton("ON")
        self._btn_toggle_target_mesh.setCheckable(True)
        self._btn_toggle_target_mesh.setChecked(True)
        self._btn_toggle_target_mesh.setFixedWidth(self._btn_set_plane_target_mesh.sizeHint().width())
        row_target.addWidget(self._btn_toggle_target_mesh)
        lay_create.addLayout(row_target)

        lay_create.addWidget(HorizontalSeparator())

        # Axis / Rotation Mode (grid for vertical alignment)
        grid_radios = QGridLayout()
        grid_radios.setContentsMargins(0, 0, 0, 0)

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

        grid_radios.addWidget(lbl_axis, 0, 0)
        grid_radios.addWidget(self._radio_axis_x, 0, 1)
        grid_radios.addWidget(self._radio_axis_y, 0, 2)
        grid_radios.addWidget(self._radio_axis_z, 0, 3)

        grid_radios.addWidget(lbl_rotation_mode, 1, 0)
        grid_radios.addWidget(self._radio_rot_joint, 1, 1)
        grid_radios.addWidget(self._radio_rot_aim, 1, 2)
        grid_radios.addWidget(self._radio_rot_manual, 1, 3)

        grid_radios.setColumnStretch(4, 1)
        lay_create.addLayout(grid_radios)

        # Label width for stacked pages (match grid col0 = Rotation Mode label)
        stacked_label_width = lbl_rotation_mode.sizeHint().width()
        self._lbl_target_mesh.setFixedWidth(stacked_label_width)

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
        self._combo_aim_target.addItems(["Auto", "Parent", "Parent > Child"])
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
        self._line_size_scale.setToolTip(
            "With Target Mesh ON: multiplier on the auto-raycasted size.\nWith Target Mesh OFF: used directly as the plane edge length."
        )
        row_scale.addWidget(self._line_size_scale)
        row_scale.addStretch()
        lay_create.addLayout(row_scale)

        # Size Ratio Limit (outlier rejection for raycast auto-size)
        row_ratio = QHBoxLayout()
        self._lbl_size_ratio = QLabel("Size Ratio Limit:")
        self._lbl_size_ratio.setFixedWidth(stacked_label_width)
        self._lbl_size_ratio.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_ratio.addWidget(self._lbl_size_ratio)
        self._line_size_ratio = QLineEdit("3.0")
        self._line_size_ratio.setValidator(QDoubleValidator(1.0, 100.0, 2, self))
        self._line_size_ratio.setToolTip(
            "When opposite raycasts along an axis have a length ratio above this value,\n"
            "the longer one is treated as an internal-penetration outlier and the shorter\n"
            "distance is used symmetrically instead."
        )
        row_ratio.addWidget(self._line_size_ratio)
        row_ratio.addStretch()
        lay_create.addLayout(row_ratio)

        lay_create.addWidget(HorizontalSeparator())

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

        lay_mirror.addWidget(HorizontalSeparator())

        self._btn_mirror_plane = QPushButton("Mirror")
        self._btn_mirror_plane.setMinimumHeight(int(height * 0.08))
        lay_mirror.addWidget(self._btn_mirror_plane)

        layout.addWidget(grp_mirror)

        # === Export / Import ===
        grp_io = QGroupBox("Export / Import")
        lay_io = QVBoxLayout(grp_io)
        lay_io.setSpacing(int(spacing * 0.5))

        row_io_buttons = QHBoxLayout()
        self._btn_export_planes = QPushButton("Export Planes...")
        self._btn_export_planes.setToolTip("Export every plane carrying proxyBuilderMetadata to a JSON file.")
        self._btn_export_planes.setMinimumHeight(int(height * 0.08))
        self._btn_import_planes = QPushButton("Import Planes...")
        self._btn_import_planes.setToolTip("Recreate planes from a previously exported JSON file.\nUses the Target Mesh field below.")
        self._btn_import_planes.setMinimumHeight(int(height * 0.08))
        row_io_buttons.addWidget(self._btn_export_planes)
        row_io_buttons.addWidget(self._btn_import_planes)
        lay_io.addLayout(row_io_buttons)

        # Optional target_mesh override for import
        row_tm = QHBoxLayout()
        lbl_import_tm = QLabel("Target Mesh:")
        lbl_import_tm.setFixedWidth(stacked_label_width)
        lbl_import_tm.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_tm.addWidget(lbl_import_tm)
        self._line_import_target_mesh = QLineEdit()
        self._line_import_target_mesh.setReadOnly(True)
        self._line_import_target_mesh.setPlaceholderText("(optional, overrides the stored target mesh)")
        self._line_import_target_mesh.setToolTip(
            "When set, every imported plane uses this mesh as Target Mesh,\n"
            "replacing whatever was stored in the JSON. Useful when the target\n"
            "scene's body mesh has a different name than the source scene's."
        )
        row_tm.addWidget(self._line_import_target_mesh, 1)
        self._btn_set_import_target_mesh = QPushButton("Set")
        row_tm.addWidget(self._btn_set_import_target_mesh)
        lay_io.addLayout(row_tm)

        layout.addWidget(grp_io)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_plane_target_mesh.clicked.connect(self._on_set_plane_target_mesh)
        self._btn_toggle_target_mesh.toggled.connect(self._on_toggle_target_mesh)
        self._btn_set_plane_aim_joint.clicked.connect(self._on_set_plane_aim_joint)
        self._combo_aim_target.currentIndexChanged.connect(self._on_aim_target_changed)
        self._btn_group_rotation_mode.buttonClicked.connect(
            lambda btn: self._stack_rotation_mode.setCurrentIndex(self._btn_group_rotation_mode.id(btn))
        )
        self._btn_create_plane.clicked.connect(self._on_create_plane)
        self._btn_mirror_plane.clicked.connect(self._on_mirror_plane)
        self._btn_export_planes.clicked.connect(self._on_export_planes)
        self._btn_import_planes.clicked.connect(self._on_import_planes)
        self._btn_set_import_target_mesh.clicked.connect(self._on_set_import_target_mesh)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_toggle_target_mesh(self, checked: bool) -> None:
        """Enable or disable the target mesh field based on the toggle state."""
        self._lbl_target_mesh.setEnabled(checked)
        self._line_plane_target_mesh.setEnabled(checked)
        self._btn_set_plane_target_mesh.setEnabled(checked)
        self._btn_toggle_target_mesh.setText("ON" if checked else "OFF")
        self._lbl_size_ratio.setEnabled(checked)
        self._line_size_ratio.setEnabled(checked)

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
        """Create cutting planes at the selected joints."""
        joints = cmds.ls(selection=True, type="joint")
        if not joints:
            cmds.warning("Proxy Builder: Select one or more joints")
            return

        target_mesh = self._line_plane_target_mesh.text().strip() or None
        if not self._btn_toggle_target_mesh.isChecked():
            target_mesh = None

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
        size_ratio_threshold = float(self._line_size_ratio.text() or 3.0)

        axis_map = {0: (1, 0, 0), 1: (0, 1, 0), 2: (0, 0, 1)}
        axis = axis_map[self._btn_group_axis.checkedId()]

        results = []
        for joint in joints:
            spec = PlaneSpec(
                joint=joint,
                target_mesh=target_mesh,
                rotation_mode=rotation_mode,
                aim_joint=aim_joint,
                aim_target=aim_target,
                rotation=rotation,
                size_scale=size_scale,
                size_ratio_threshold=size_ratio_threshold,
                axis=axis,
            )
            result = plane_command.create_plane_at_joint(spec)
            results.append(result)

        cmds.select(results, replace=True)
        logger.info("Created %d plane(s): %s", len(results), results)

    def _on_set_import_target_mesh(self) -> None:
        """Set the import target mesh override from Maya selection, or clear if nothing is selected."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            self._line_import_target_mesh.clear()
            return
        mesh = sel[0]
        if not cmds.listRelatives(mesh, shapes=True, type="mesh"):
            cmds.warning(f"Proxy Builder: '{mesh}' is not a mesh transform")
            return
        self._line_import_target_mesh.setText(mesh)

    @error_handler
    def _on_export_planes(self) -> None:
        """Export every managed plane in the scene to a user-chosen JSON file."""
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("JSON Files (*.json)")
        file_dialog.setDefaultSuffix("json")
        if file_dialog.exec_() != QFileDialog.Accepted:
            return

        path = file_dialog.selectedFiles()[0]
        exported = plane_io.export_planes_to_file(path)
        if not exported:
            show_warning_dialog(
                "Export Planes",
                "No planes with Proxy Builder metadata were found in the scene.\nNothing was written.",
            )
            return

        logger.info("Exported %d plane(s) to %s", len(exported), path)
        show_info_dialog("Export Planes", f"Exported {len(exported)} plane(s) to:\n{path}")

    @error_handler
    @undo_chunk("Proxy Builder: Import Planes")
    def _on_import_planes(self) -> None:
        """Recreate planes from a JSON file produced by Export Planes."""
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
        file_dialog.setNameFilter("JSON Files (*.json)")
        if file_dialog.exec_() != QFileDialog.Accepted:
            return

        path = file_dialog.selectedFiles()[0]
        target_mesh_override = self._line_import_target_mesh.text().strip() or None

        created = plane_io.import_planes_from_file(path, target_mesh_override=target_mesh_override)
        if not created:
            show_warning_dialog(
                "Import Planes",
                "No planes were created.\nAll entries were skipped (missing joints or duplicate planes).",
            )
            return

        cmds.select(created, replace=True)
        logger.info("Imported %d plane(s) from %s", len(created), path)

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
            "use_target_mesh": self._btn_toggle_target_mesh.isChecked(),
            "rotation_mode": self._btn_group_rotation_mode.checkedId(),
            "aim_target": self._combo_aim_target.currentIndex(),
            "manual_rotation_x": self._line_rot_x.text(),
            "manual_rotation_y": self._line_rot_y.text(),
            "manual_rotation_z": self._line_rot_z.text(),
            "size_scale": self._line_size_scale.text(),
            "size_ratio_threshold": self._line_size_ratio.text(),
            "plane_axis": self._btn_group_axis.checkedId(),
            "mirror_axis": self._btn_group_mirror_axis.checkedId(),
            "import_target_mesh": self._line_import_target_mesh.text(),
        }

    def _apply_settings(self, data: dict) -> None:
        use_target_mesh = data.get("use_target_mesh", True)
        self._btn_toggle_target_mesh.setChecked(use_target_mesh)

        rotation_mode = data.get("rotation_mode", 0)
        rot_radios = {0: self._radio_rot_joint, 1: self._radio_rot_aim, 2: self._radio_rot_manual}
        rot_radios.get(rotation_mode, self._radio_rot_joint).setChecked(True)
        self._stack_rotation_mode.setCurrentIndex(rotation_mode)

        self._combo_aim_target.setCurrentIndex(data.get("aim_target", 0))

        self._line_rot_x.setText(str(data.get("manual_rotation_x", "0.0")))
        self._line_rot_y.setText(str(data.get("manual_rotation_y", "0.0")))
        self._line_rot_z.setText(str(data.get("manual_rotation_z", "0.0")))
        self._line_size_scale.setText(str(data.get("size_scale", "1.0")))
        self._line_size_ratio.setText(str(data.get("size_ratio_threshold", "3.0")))

        plane_axis = data.get("plane_axis", 1)
        axis_radios = {0: self._radio_axis_x, 1: self._radio_axis_y, 2: self._radio_axis_z}
        axis_radios.get(plane_axis, self._radio_axis_y).setChecked(True)

        mirror_axis = data.get("mirror_axis", 0)
        mirror_radios = {0: self._radio_mirror_x, 1: self._radio_mirror_y, 2: self._radio_mirror_z}
        mirror_radios.get(mirror_axis, self._radio_mirror_x).setChecked(True)

        self._line_import_target_mesh.setText(str(data.get("import_target_mesh", "")))
