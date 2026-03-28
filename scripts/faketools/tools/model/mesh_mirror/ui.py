"""Mesh Mirror UI layer."""

from logging import getLogger

import maya.cmds as cmds

from ....lib_ui import maya_decorator
from ....lib_ui.base_window import BaseMainWindow, get_spacing
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from . import command

logger = getLogger(__name__)

_instance = None


# =====================================================================
# Helpers
# =====================================================================


def _align_label_widths(labels: list[QLabel]) -> None:
    """Set all labels to the same fixed width based on the widest one."""
    max_width = 0
    for label in labels:
        width = label.fontMetrics().boundingRect(label.text()).width()
        if width > max_width:
            max_width = width
    # Add padding for alignment
    max_width += label.fontMetrics().averageCharWidth() * 2
    for label in labels:
        label.setFixedWidth(max_width)


# =====================================================================
# Mesh Input Widget
# =====================================================================


class _MeshFieldWidget(QWidget):
    """A single mesh input field with a 'Set' button."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent=parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._line = QLineEdit()
        self._line.setReadOnly(True)
        self._btn = QPushButton("Set")
        self._btn.clicked.connect(self._on_set)

        layout.addWidget(self._label)
        layout.addWidget(self._line, 1)
        layout.addWidget(self._btn)
        self.setLayout(layout)

    @property
    def label_widget(self) -> QLabel:
        """Access the label widget for external width alignment."""
        return self._label

    def _on_set(self):
        """Set mesh from current selection."""
        import maya.cmds as cmds

        sel = cmds.ls(sl=True, type="transform") or []
        if not sel:
            return
        try:
            command.validate_mesh(sel[0])
            self._line.setText(sel[0])
        except ValueError as e:
            logger.warning(str(e))

    def get_mesh(self) -> str:
        return self._line.text()

    def set_mesh(self, name: str):
        self._line.setText(name)


class _MeshListWidget(QWidget):
    """A mesh input field that accepts multiple meshes from selection."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent=parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._line = QLineEdit()
        self._line.setReadOnly(True)
        self._btn = QPushButton("Set")
        self._btn.clicked.connect(self._on_set)
        self._meshes: list[str] = []

        layout.addWidget(self._label)
        layout.addWidget(self._line, 1)
        layout.addWidget(self._btn)
        self.setLayout(layout)

    @property
    def label_widget(self) -> QLabel:
        """Access the label widget for external width alignment."""
        return self._label

    def _on_set(self):
        """Set meshes from current selection."""
        import maya.cmds as cmds

        sel = cmds.ls(sl=True, type="transform") or []
        valid: list[str] = []
        for s in sel:
            try:
                command.validate_mesh(s)
                valid.append(s)
            except ValueError:
                pass
        self._meshes = valid
        self._update_display()

    def _update_display(self):
        if not self._meshes:
            self._line.setText("")
            self._line.setToolTip("")
        elif len(self._meshes) == 1:
            self._line.setText(self._meshes[0])
            self._line.setToolTip(self._meshes[0])
        else:
            self._line.setText(f"{len(self._meshes)} meshes")
            self._line.setToolTip("\n".join(self._meshes))

    def get_meshes(self) -> list[str]:
        return list(self._meshes)


# =====================================================================
# Main Window
# =====================================================================


class MainWindow(BaseMainWindow):
    """Mesh Mirror Main Window."""

    _MODES = ("Single Mesh", "Dual Mesh")
    _SINGLE_METHODS = ("position", "topology")
    _DUAL_METHODS = ("position", "topology", "index")
    _DIRECTIONS_SINGLE = ("+X → -X", "-X → +X")
    _DIRECTIONS_DUAL = ("A → B", "B → A")

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="MeshMirrorMainWindow",
            window_title="Mesh Mirror",
            central_layout="vertical",
        )

        self.settings = ToolSettingsManager(tool_name="mesh_mirror", category="model")

        # State
        self._table = None  # SymmetryResult or CorrespondenceResult
        self._check_result = None  # CheckResult

        self._build_ui()
        self._restore_settings()
        self._on_mode_changed(self.mode_combo.currentText())

    def _build_ui(self):
        # ---- Mode ----
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_label = QLabel("Mode:")
        mode_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_layout.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self._MODES)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo, 1)
        self.central_layout.addLayout(mode_layout)

        # ---- Mesh Input ----
        input_group = QGroupBox("Mesh Input")
        input_layout = QVBoxLayout()
        input_spacing = int(get_spacing(input_group, direction="vertical") * 0.5)
        input_layout.setSpacing(input_spacing)

        # Single mesh fields
        self.single_widget = QWidget()
        single_layout = QVBoxLayout()
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(input_spacing)
        self.base_field = _MeshFieldWidget("Base:")
        self.target_list = _MeshListWidget("Target:")
        single_layout.addWidget(self.base_field)
        single_layout.addWidget(self.target_list)
        self.single_widget.setLayout(single_layout)
        input_layout.addWidget(self.single_widget)

        # Dual mesh fields
        self.dual_widget = QWidget()
        dual_layout = QVBoxLayout()
        dual_layout.setContentsMargins(0, 0, 0, 0)
        dual_layout.setSpacing(input_spacing)
        self.base_a_field = _MeshFieldWidget("Base A:")
        self.base_b_field = _MeshFieldWidget("Base B:")
        self.target_a_list = _MeshListWidget("Target A:")
        self.target_b_list = _MeshListWidget("Target B:")
        dual_layout.addWidget(self.base_a_field)
        dual_layout.addWidget(self.base_b_field)
        dual_layout.addWidget(self.target_a_list)
        dual_layout.addWidget(self.target_b_list)
        self.dual_widget.setLayout(dual_layout)
        input_layout.addWidget(self.dual_widget)

        # Align all mesh input label widths
        all_input_widgets = [
            self.base_field,
            self.target_list,
            self.base_a_field,
            self.base_b_field,
            self.target_a_list,
            self.target_b_list,
        ]
        _align_label_widths([w.label_widget for w in all_input_widgets])

        input_group.setLayout(input_layout)
        self.central_layout.addWidget(input_group)

        # ---- Symmetry Check ----
        check_group = QGroupBox("Symmetry Check")
        check_layout = QVBoxLayout()

        method_layout = QHBoxLayout()
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_label = QLabel("Method:")
        method_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        method_layout.addWidget(method_label)
        self.method_combo = QComboBox()
        method_layout.addWidget(self.method_combo, 1)
        check_layout.addLayout(method_layout)

        threshold_layout = QHBoxLayout()
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_label = QLabel("Threshold:")
        threshold_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        threshold_layout.addWidget(threshold_label)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0001, 100.0)
        self.threshold_spin.setDecimals(4)
        self.threshold_spin.setValue(0.001)
        self.threshold_spin.setSingleStep(0.001)
        threshold_layout.addWidget(self.threshold_spin, 1)
        check_layout.addLayout(threshold_layout)

        # Align check section label widths
        _align_label_widths([method_label, threshold_label])

        self.check_btn = QPushButton("Build Table && Check")
        self.check_btn.clicked.connect(self._on_check)
        check_layout.addWidget(self.check_btn)

        self.check_result_label = QLabel("\n")
        self.check_result_label.setMinimumHeight(self.check_result_label.sizeHint().height())
        self.check_result_label.setText("")
        check_layout.addWidget(self.check_result_label)

        self.select_failed_btn = QPushButton("Select Failed Vertices")
        self.select_failed_btn.clicked.connect(self._on_select_failed)
        self.select_failed_btn.setEnabled(False)
        check_layout.addWidget(self.select_failed_btn)

        check_group.setLayout(check_layout)
        self.central_layout.addWidget(check_group)

        # ---- Apply ----
        apply_group = QGroupBox("Apply")
        apply_layout = QVBoxLayout()

        dir_layout = QHBoxLayout()
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_label = QLabel("Direction:")
        dir_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dir_layout.addWidget(dir_label)
        self.dir_radio_0 = QRadioButton()
        self.dir_radio_1 = QRadioButton()
        self.dir_radio_0.setChecked(True)
        dir_layout.addWidget(self.dir_radio_0)
        dir_layout.addWidget(self.dir_radio_1)
        dir_layout.addStretch(1)
        apply_layout.addLayout(dir_layout)

        fallback_layout = QHBoxLayout()
        fallback_layout.setContentsMargins(0, 0, 0, 0)
        fallback_label = QLabel("Fallback:")
        fallback_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        fallback_layout.addWidget(fallback_label)
        self.fallback_combo = QComboBox()
        self.fallback_combo.addItems(["closest_point", "laplacian"])
        fallback_layout.addWidget(self.fallback_combo, 1)
        apply_layout.addLayout(fallback_layout)

        # Align apply labels (including spacer for checkbox indentation)
        copy_spacer = QLabel("")
        _align_label_widths([dir_label, fallback_label, copy_spacer])

        copy_layout = QHBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.addWidget(copy_spacer)
        self.create_copy_check = QCheckBox("Create Copy")
        copy_layout.addWidget(self.create_copy_check)
        copy_layout.addStretch(1)
        apply_layout.addLayout(copy_layout)

        btn_layout = QHBoxLayout()
        self.mirror_btn = QPushButton("Mirror")
        self.mirror_btn.clicked.connect(self._on_mirror)
        self.mirror_btn.setEnabled(False)
        btn_layout.addWidget(self.mirror_btn)

        self.flip_btn = QPushButton("Flip")
        self.flip_btn.clicked.connect(self._on_flip)
        btn_layout.addWidget(self.flip_btn)

        apply_layout.addLayout(btn_layout)

        apply_group.setLayout(apply_layout)
        self.central_layout.addWidget(apply_group)

        # Push all content to the top; absorb extra space at the bottom
        self.central_layout.addStretch(1)

    # -----------------------------------------------------------------
    # Mode switching
    # -----------------------------------------------------------------

    def _on_mode_changed(self, mode: str):
        is_single = mode == "Single Mesh"

        self.single_widget.setVisible(is_single)
        self.dual_widget.setVisible(not is_single)

        # Update method options
        self.method_combo.clear()
        methods = self._SINGLE_METHODS if is_single else self._DUAL_METHODS
        self.method_combo.addItems(methods)

        # Update direction labels
        directions = self._DIRECTIONS_SINGLE if is_single else self._DIRECTIONS_DUAL
        self.dir_radio_0.setText(directions[0])
        self.dir_radio_1.setText(directions[1])

        # Reset table
        self._table = None
        self._update_table_state()

    # -----------------------------------------------------------------
    # Symmetry Check
    # -----------------------------------------------------------------

    @maya_decorator.error_handler
    def _on_check(self):
        method = self.method_combo.currentText()
        threshold = self.threshold_spin.value()

        if self._is_single_mode():
            base = self.base_field.get_mesh()
            if not base:
                raise ValueError("Base mesh is not set.")
            self._table = command.build_single_table(base, method, threshold)
            self._check_result = command.get_check_result_single(base, self._table, threshold)
        else:
            base_a = self.base_a_field.get_mesh()
            base_b = self.base_b_field.get_mesh()
            if not base_a or not base_b:
                raise ValueError("Base meshes are not set.")
            self._table = command.build_dual_table(base_a, base_b, method, threshold)
            self._check_result = command.get_check_result_dual(base_a, base_b, self._table, threshold)

        r = self._check_result
        self.check_result_label.setText(
            f"Matched: {r.matched_count}  |  Center: {r.center_count}\nFailed: {r.failed_count}  |  Asymmetric: {r.asymmetric_count}"
        )
        self._update_table_state()
        self.select_failed_btn.setEnabled(r.failed_count > 0 or r.asymmetric_count > 0)

    @maya_decorator.error_handler
    def _on_select_failed(self):
        if self._check_result is None:
            return

        # Combine failed + asymmetric indices
        indices = list(set(self._check_result.failed_indices + self._check_result.asymmetric_indices))
        if not indices:
            return

        if self._is_single_mode():
            mesh = self.base_field.get_mesh()
        else:
            mesh = self.base_a_field.get_mesh()

        if mesh:
            command.select_failed_vertices(mesh, indices)

    def _update_table_state(self):
        has_table = self._table is not None
        self.mirror_btn.setEnabled(has_table)
        self.flip_btn.setEnabled(has_table)

    # -----------------------------------------------------------------
    # Apply
    # -----------------------------------------------------------------

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Mesh Mirror")
    def _on_mirror(self):
        if self._table is None:
            raise ValueError("Build table first.")

        fallback = self.fallback_combo.currentText()
        create_copy = self.create_copy_check.isChecked()

        if self._is_single_mode():
            targets = self.target_list.get_meshes()
            base = self.base_field.get_mesh()
            if not targets or not base:
                raise ValueError("Target and Base meshes are not set.")
            self._validate_targets_topology(base, targets)

            direction = "+x" if self.dir_radio_0.isChecked() else "-x"
            result_meshes = []
            for target in targets:
                actual = command.duplicate_mesh(target, "_mirror") if create_copy else target
                op = command.SingleMeshOperation(actual, base, self._table)
                op.mirror(direction, fallback=fallback)
                result_meshes.append(actual)
            cmds.select(result_meshes, r=True)
        else:
            targets_a = self.target_a_list.get_meshes()
            targets_b = self.target_b_list.get_meshes()
            base_a = self.base_a_field.get_mesh()
            base_b = self.base_b_field.get_mesh()
            if not targets_a or not targets_b or not base_a or not base_b:
                raise ValueError("All meshes must be set.")
            if len(targets_a) != len(targets_b):
                raise ValueError(f"Target count mismatch: A={len(targets_a)}, B={len(targets_b)}")
            self._validate_targets_topology(base_a, targets_a)
            self._validate_targets_topology(base_b, targets_b)

            direction = "a_to_b" if self.dir_radio_0.isChecked() else "b_to_a"
            result_meshes = []
            for ta, tb in zip(targets_a, targets_b):
                actual_a = command.duplicate_mesh(ta, "_mirror") if create_copy else ta
                actual_b = command.duplicate_mesh(tb, "_mirror") if create_copy else tb
                op = command.DualMeshOperation(actual_a, actual_b, base_a, base_b, self._table)
                op.mirror(direction, fallback=fallback)
                result_meshes.extend([actual_a, actual_b])
            cmds.select(result_meshes, r=True)

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Mesh Flip")
    def _on_flip(self):
        if self._table is None:
            raise ValueError("Build table first.")

        fallback = self.fallback_combo.currentText()
        create_copy = self.create_copy_check.isChecked()

        if self._is_single_mode():
            targets = self.target_list.get_meshes()
            base = self.base_field.get_mesh()
            if not targets or not base:
                raise ValueError("Target and Base meshes are not set.")
            self._validate_targets_topology(base, targets)

            result_meshes = []
            for target in targets:
                actual = command.duplicate_mesh(target, "_flip") if create_copy else target
                op = command.SingleMeshOperation(actual, base, self._table)
                op.flip(fallback=fallback)
                result_meshes.append(actual)
            cmds.select(result_meshes, r=True)
        else:
            targets_a = self.target_a_list.get_meshes()
            targets_b = self.target_b_list.get_meshes()
            base_a = self.base_a_field.get_mesh()
            base_b = self.base_b_field.get_mesh()
            if not targets_a or not targets_b or not base_a or not base_b:
                raise ValueError("All meshes must be set.")
            if len(targets_a) != len(targets_b):
                raise ValueError(f"Target count mismatch: A={len(targets_a)}, B={len(targets_b)}")
            self._validate_targets_topology(base_a, targets_a)
            self._validate_targets_topology(base_b, targets_b)

            result_meshes = []
            for ta, tb in zip(targets_a, targets_b):
                actual_a = command.duplicate_mesh(ta, "_flip") if create_copy else ta
                actual_b = command.duplicate_mesh(tb, "_flip") if create_copy else tb
                op = command.DualMeshOperation(actual_a, actual_b, base_a, base_b, self._table)
                op.flip(fallback=fallback)
                result_meshes.extend([actual_a, actual_b])
            cmds.select(result_meshes, r=True)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _is_single_mode(self) -> bool:
        return self.mode_combo.currentText() == "Single Mesh"

    @staticmethod
    def _validate_targets_topology(base: str, targets: list[str]) -> None:
        """Validate that all targets have the same topology as the base mesh.

        Checks all targets and reports all mismatches at once.
        """
        mismatched = [t for t in targets if not command.validate_same_topology(base, t)]
        if mismatched:
            names = ", ".join(mismatched)
            raise ValueError(f"Topology mismatch with {base}: {names}")

    # -----------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------

    def _restore_settings(self):
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

        # Compute minimum height from Dual Mesh mode (the taller layout),
        # then allow the user to resize freely above that minimum.
        self.single_widget.setVisible(False)
        self.dual_widget.setVisible(True)
        self.adjustSize()
        self.setMinimumHeight(self.sizeHint().height())

        # Now apply actual visibility
        self._on_mode_changed(self.mode_combo.currentText())

    def _save_settings(self):
        self.settings.save_settings(self._collect_settings(), "default")

    def _collect_settings(self) -> dict:
        return {
            "mode": self.mode_combo.currentText(),
            "method": self.method_combo.currentText(),
            "threshold": self.threshold_spin.value(),
            "direction_index": 0 if self.dir_radio_0.isChecked() else 1,
            "fallback": self.fallback_combo.currentText(),
            "create_copy": self.create_copy_check.isChecked(),
        }

    def _apply_settings(self, data: dict):
        if "mode" in data:
            self.mode_combo.setCurrentText(data["mode"])
        if "method" in data:
            self.method_combo.setCurrentText(data["method"])
        if "threshold" in data:
            self.threshold_spin.setValue(data["threshold"])
        if "direction_index" in data:
            if data["direction_index"] == 0:
                self.dir_radio_0.setChecked(True)
            else:
                self.dir_radio_1.setChecked(True)
        if "fallback" in data:
            self.fallback_combo.setCurrentText(data["fallback"])
        if "create_copy" in data:
            self.create_copy_check.setChecked(data["create_copy"])

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)


# =====================================================================
# show_ui
# =====================================================================


def show_ui():
    """Show the Mesh Mirror UI."""
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
