"""Mesh Fitter main window — thin Qt shell over MeshFitController.

All business logic lives in controller.py; this file only handles
widget creation, layout, and Qt signal wiring.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

import maya.cmds as cmds  # type: ignore[import]

# Check trimesh/rtree/fast-simplification availability
try:
    import fast_simplification  # noqa: F401
    import rtree  # noqa: F401
    import trimesh  # noqa: F401

    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QStatusBar,
    Qt,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import IconButton, IconButtonStyle

if TRIMESH_AVAILABLE:
    from . import command
    from .controller import MeshFitController, SceneMeshListProvider
    from .core.algorithms import SCHEDULES
    from .mesh_bridge import OpenMayaMeshAPI

logger = getLogger(__name__)

_IMAGES_DIR = str(Path(__file__).parent / "images")

_instance = None


class MainWindow(BaseMainWindow):
    """Main GUI window for Mesh Fitter in Maya."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            object_name="MeshFitterMainWindow",
            window_title="Mesh Fitter",
            central_layout="vertical",
        )
        self.setMinimumWidth(380)

        self.settings = ToolSettingsManager(tool_name="mesh_fitter", category="model")

        self._controller = MeshFitController(
            api=OpenMayaMeshAPI(),
            mesh_list_provider=SceneMeshListProvider(),
        )

        self._build_ui()
        self._connect_signals()
        self._connect_controller_callbacks()

        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # --- Meshes ---
        grp_mesh = QGroupBox("Meshes")
        lay_mesh = QVBoxLayout(grp_mesh)

        lbl_source = QLabel("Source:")
        lbl_target = QLabel("Target:")
        lbl_region = QLabel("Region:")
        fm = lbl_source.fontMetrics()
        label_width = max(
            fm.horizontalAdvance("Source:"),
            fm.horizontalAdvance("Target:"),
            fm.horizontalAdvance("Region:"),
        )
        label_width += fm.horizontalAdvance("M")
        lbl_source.setFixedWidth(label_width)
        lbl_target.setFixedWidth(label_width)
        lbl_region.setFixedWidth(label_width)
        lbl_source.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_target.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_region.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        row_src = QHBoxLayout()
        row_src.addWidget(lbl_source)
        self._line_source = QLineEdit()
        self._line_source.setReadOnly(True)
        self._line_source.setPlaceholderText("Select a mesh and click SET")
        row_src.addWidget(self._line_source, 1)
        self._btn_set_source = QPushButton("SET")
        row_src.addWidget(self._btn_set_source)
        lay_mesh.addLayout(row_src)

        row_tgt = QHBoxLayout()
        row_tgt.addWidget(lbl_target)
        self._line_target = QLineEdit()
        self._line_target.setReadOnly(True)
        self._line_target.setPlaceholderText("Select a mesh and click SET")
        row_tgt.addWidget(self._line_target, 1)
        self._btn_set_target = QPushButton("SET")
        row_tgt.addWidget(self._btn_set_target)
        lay_mesh.addLayout(row_tgt)

        row_region = QHBoxLayout()
        row_region.addWidget(lbl_region)
        self._line_region = QLineEdit()
        self._line_region.setReadOnly(True)
        self._line_region.setPlaceholderText("Select target faces and click SET")
        row_region.addWidget(self._line_region, 1)
        self._btn_set_region = QPushButton("SET")
        row_region.addWidget(self._btn_set_region)
        lay_mesh.addLayout(row_region)

        self.central_layout.addWidget(grp_mesh)

        # --- Settings (Tab Widget) ---
        grp_settings = QGroupBox("Settings")
        lay_settings = QVBoxLayout(grp_settings)

        self._tab_settings = QTabWidget()
        lay_settings.addWidget(self._tab_settings)

        # -- Pre tab --
        tab_pre = QWidget()
        lay_pre = QVBoxLayout(tab_pre)
        self._chk_auto_align = QCheckBox("Auto-align source to target")
        self._chk_auto_align.setChecked(True)
        lay_pre.addWidget(self._chk_auto_align)
        lay_pre.addStretch()
        self._tab_settings.addTab(tab_pre, "Align")

        # -- Main tab --
        tab_main = QWidget()
        lay_main = QVBoxLayout(tab_main)

        row_sched = QHBoxLayout()
        row_sched.addWidget(QLabel("Schedule:"))
        self._combo_schedule = QComboBox()
        self._combo_schedule.addItems([k.title() for k in SCHEDULES])
        self._combo_schedule.setCurrentText("Gentle")
        row_sched.addWidget(self._combo_schedule, 1)
        lay_main.addLayout(row_sched)

        # Advanced (nested inside Main tab, under Schedule)
        self._grp_advanced = QGroupBox("Advanced")
        self._grp_advanced.setCheckable(True)
        self._grp_advanced.setChecked(False)
        lay_adv = QVBoxLayout(self._grp_advanced)

        # Compute uniform label width for Advanced sliders
        adv_labels = ["Stiffness:", "Landmark Influence:", "Quality Steps:"]
        fm_adv = self.fontMetrics()
        adv_label_width = max(fm_adv.horizontalAdvance(t) for t in adv_labels)
        adv_label_width += fm_adv.horizontalAdvance("M")

        # Stiffness: 0.01–0.20, step 0.01, default from schedule
        row_stiff = QHBoxLayout()
        lbl_stiff = QLabel("Stiffness:")
        lbl_stiff.setFixedWidth(adv_label_width)
        lbl_stiff.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_stiff.addWidget(lbl_stiff)
        self._slider_stiffness = QSlider(Qt.Horizontal)
        self._slider_stiffness.setRange(1, 20)  # maps to 0.01–0.20
        self._slider_stiffness.setValue(10)
        row_stiff.addWidget(self._slider_stiffness, 1)
        self._spin_stiffness = QDoubleSpinBox()
        self._spin_stiffness.setRange(0.01, 0.20)
        self._spin_stiffness.setSingleStep(0.01)
        self._spin_stiffness.setDecimals(2)
        self._spin_stiffness.setValue(0.10)
        self._spin_stiffness.setFixedWidth(60)
        row_stiff.addWidget(self._spin_stiffness)
        lay_adv.addLayout(row_stiff)

        # Landmark Strength: 0.0–1.0, step 0.05, default 1.0
        row_lm = QHBoxLayout()
        lbl_lm = QLabel("Landmark Influence:")
        lbl_lm.setFixedWidth(adv_label_width)
        lbl_lm.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_lm.addWidget(lbl_lm)
        self._slider_landmark_strength = QSlider(Qt.Horizontal)
        self._slider_landmark_strength.setRange(0, 20)  # maps to 0.0–1.0 (x0.05)
        self._slider_landmark_strength.setValue(20)
        row_lm.addWidget(self._slider_landmark_strength, 1)
        self._spin_landmark_strength = QDoubleSpinBox()
        self._spin_landmark_strength.setRange(0.0, 1.0)
        self._spin_landmark_strength.setSingleStep(0.05)
        self._spin_landmark_strength.setDecimals(2)
        self._spin_landmark_strength.setValue(1.0)
        self._spin_landmark_strength.setFixedWidth(60)
        row_lm.addWidget(self._spin_landmark_strength)
        lay_adv.addLayout(row_lm)

        # Steps: 3–10, default from schedule
        row_steps = QHBoxLayout()
        lbl_steps = QLabel("Quality Steps:")
        lbl_steps.setFixedWidth(adv_label_width)
        lbl_steps.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_steps.addWidget(lbl_steps)
        self._slider_steps = QSlider(Qt.Horizontal)
        self._slider_steps.setRange(3, 10)
        self._slider_steps.setValue(7)
        row_steps.addWidget(self._slider_steps, 1)
        self._spin_steps = QSpinBox()
        self._spin_steps.setRange(3, 10)
        self._spin_steps.setValue(7)
        self._spin_steps.setFixedWidth(60)
        row_steps.addWidget(self._spin_steps)
        lay_adv.addLayout(row_steps)

        self._update_landmark_strength_enabled()
        lay_main.addWidget(self._grp_advanced)

        # Simplify Target: checkbox + ratio spinbox (independent of Advanced)
        row_decimate = QHBoxLayout()
        self._chk_decimate = QCheckBox("Simplify Target")
        row_decimate.addWidget(self._chk_decimate)
        row_decimate.addStretch()
        lbl_ratio = QLabel("Ratio:")
        row_decimate.addWidget(lbl_ratio)
        self._spin_decimate = QDoubleSpinBox()
        self._spin_decimate.setRange(0.05, 1.0)
        self._spin_decimate.setSingleStep(0.05)
        self._spin_decimate.setDecimals(2)
        self._spin_decimate.setValue(0.25)
        self._spin_decimate.setEnabled(False)
        self._spin_decimate.setFixedWidth(60)
        row_decimate.addWidget(self._spin_decimate)
        lay_main.addLayout(row_decimate)

        lay_main.addStretch()
        self._tab_settings.addTab(tab_main, "Fitting")

        # -- Post tab --
        tab_post = QWidget()
        lay_post = QVBoxLayout(tab_post)

        # Checkbox indicator width for indenting child widgets
        indicator_indent = self._chk_auto_align.style().pixelMetric(
            self._chk_auto_align.style().PixelMetric.PM_IndicatorWidth
        ) + self._chk_auto_align.style().pixelMetric(self._chk_auto_align.style().PixelMetric.PM_CheckBoxLabelSpacing)

        self._chk_smooth = QCheckBox("Smooth Result")
        lay_post.addWidget(self._chk_smooth)
        self._spin_smooth = QSpinBox()
        self._spin_smooth.setRange(1, 50)
        self._spin_smooth.setValue(3)
        self._spin_smooth.setEnabled(False)
        self._spin_smooth.setSuffix(" times")
        row_spin_smooth = QHBoxLayout()
        row_spin_smooth.setContentsMargins(indicator_indent, 0, 0, 0)
        row_spin_smooth.addWidget(self._spin_smooth)
        row_spin_smooth.addStretch()
        lay_post.addLayout(row_spin_smooth)

        self._chk_snap = QCheckBox("Snap to Target Surface")
        lay_post.addWidget(self._chk_snap)

        self._chk_symmetrize = QCheckBox("Symmetrize")
        lay_post.addWidget(self._chk_symmetrize)
        self._SYM_DISPLAY = {"By Position": "position", "By Topology": "topology"}
        self._combo_sym_method = QComboBox()
        self._combo_sym_method.addItems(list(self._SYM_DISPLAY.keys()))
        self._combo_sym_method.setEnabled(False)
        row_combo_sym = QHBoxLayout()
        row_combo_sym.setContentsMargins(indicator_indent, 0, 0, 0)
        row_combo_sym.addWidget(self._combo_sym_method)
        row_combo_sym.addStretch()
        lay_post.addLayout(row_combo_sym)

        # Unify width of spin_smooth and combo_sym_method
        post_box_width = max(self._spin_smooth.sizeHint().width(), self._combo_sym_method.sizeHint().width())
        self._spin_smooth.setFixedWidth(post_box_width)
        self._combo_sym_method.setFixedWidth(post_box_width)

        self._chk_duplicate = QCheckBox("Keep Original Mesh")
        self._chk_duplicate.setChecked(True)
        lay_post.addWidget(self._chk_duplicate)

        self._OUTPUT_SPACE_DISPLAY = {"Source": "source", "Target": "target"}
        row_output_space = QHBoxLayout()
        row_output_space.addWidget(QLabel("Output Space:"))
        self._combo_output_space = QComboBox()
        self._combo_output_space.addItems(list(self._OUTPUT_SPACE_DISPLAY.keys()))
        row_output_space.addWidget(self._combo_output_space, 1)
        lay_post.addLayout(row_output_space)

        lay_post.addStretch()
        self._tab_settings.addTab(tab_post, "Finish")

        self.central_layout.addWidget(grp_settings)

        # --- Landmarks ---
        grp_lm = QGroupBox("Landmarks")
        lay_lm = QVBoxLayout(grp_lm)

        self._tree_landmarks = QTreeWidget()
        self._tree_landmarks.setHeaderLabels(["Source", "Target", "", ""])
        self._tree_landmarks.setColumnCount(4)
        self._tree_landmarks.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree_landmarks.setRootIsDecorated(False)
        self._tree_landmarks.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self._tree_landmarks.header()
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setCursor(Qt.PointingHandCursor)
        header.setStyleSheet("QHeaderView::section { background: palette(button); border: none; }QHeaderView::section:hover { background: #707070; }")
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_item = self._tree_landmarks.headerItem()
        header_item.setIcon(2, QIcon(str(Path(_IMAGES_DIR) / "select.svg")))
        header_item.setIcon(3, QIcon(str(Path(_IMAGES_DIR) / "remove.svg")))
        lay_lm.addWidget(self._tree_landmarks)

        self._btn_set_landmarks = QPushButton("Set")
        lay_lm.addWidget(self._btn_set_landmarks)

        self.central_layout.addWidget(grp_lm, 1)

        # --- Run button ---
        self._btn_run = QPushButton("Run Fitting")
        self._btn_run.setMinimumHeight(36)
        self.central_layout.addWidget(self._btn_run)

        # --- Status bar ---
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Ready")
        self.central_layout.addWidget(self._status_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_source.clicked.connect(self._on_set_source)
        self._btn_set_target.clicked.connect(self._on_set_target)
        self._btn_set_region.clicked.connect(self._on_set_region)

        self._combo_schedule.currentTextChanged.connect(self._on_schedule_changed)
        self._chk_auto_align.toggled.connect(self._controller.set_auto_align)
        self._chk_smooth.toggled.connect(self._on_smooth_toggled)
        self._spin_smooth.valueChanged.connect(self._controller.set_smooth_iterations)
        self._chk_snap.toggled.connect(self._controller.set_snap_to_target)
        self._chk_symmetrize.toggled.connect(self._on_symmetrize_toggled)
        self._combo_sym_method.currentTextChanged.connect(self._on_symmetrize_method_changed)
        self._chk_duplicate.toggled.connect(self._controller.set_duplicate_source)
        self._combo_output_space.currentTextChanged.connect(self._on_output_space_changed)

        self._grp_advanced.toggled.connect(self._on_advanced_toggled)
        self._slider_stiffness.valueChanged.connect(self._on_stiffness_slider)
        self._spin_stiffness.valueChanged.connect(self._on_stiffness_spin)
        self._slider_landmark_strength.valueChanged.connect(self._on_landmark_strength_slider)
        self._spin_landmark_strength.valueChanged.connect(self._on_landmark_strength_spin)
        self._slider_steps.valueChanged.connect(self._on_steps_slider)
        self._spin_steps.valueChanged.connect(self._on_steps_spin)
        self._chk_decimate.toggled.connect(self._on_decimate_toggled)
        self._spin_decimate.valueChanged.connect(self._controller.set_decimate_ratio)

        self._tree_landmarks.header().sectionClicked.connect(self._on_landmark_header_clicked)
        self._btn_set_landmarks.clicked.connect(lambda: self._controller.set_landmarks_from_selection())

        self._btn_run.clicked.connect(self._on_run)

    def _connect_controller_callbacks(self) -> None:
        self._controller.on_status = self._status_bar.showMessage
        self._controller.on_error = self._on_error
        self._controller.on_landmarks_changed = self._refresh_landmark_tree
        self._controller.on_fitting_state_changed = self._set_fitting_ui
        self._controller.on_target_region_changed = self._refresh_region_display
        self._controller.on_fitting_complete = self._on_fitting_complete

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_set_source(self) -> None:
        from .scene_ops import get_selected_mesh

        name = get_selected_mesh()
        if name is None:
            self._status_bar.showMessage("Error: Select a mesh transform")
            return
        self._line_source.setText(name.rsplit("|", 1)[-1])
        self._line_source.setToolTip(name)
        self._controller.set_source(name)

    def _on_set_target(self) -> None:
        from .scene_ops import get_selected_mesh

        name = get_selected_mesh()
        if name is None:
            self._status_bar.showMessage("Error: Select a mesh transform")
            return
        self._line_target.setText(name.rsplit("|", 1)[-1])
        self._line_target.setToolTip(name)
        self._controller.set_target(name)

    def _on_set_region(self) -> None:
        """SET clicked: faces selected -> set region, nothing selected -> clear."""
        self._controller.set_target_faces_from_selection()

    def _refresh_region_display(self) -> None:
        """Update the region QLineEdit based on controller state."""
        indices = self._controller.target_face_indices
        if indices is not None:
            self._line_region.setText(f"{len(indices)} faces")
        else:
            self._line_region.clear()

    def _on_error(self, msg: str) -> None:
        logger.error(msg, exc_info=True)
        self._status_bar.showMessage(f"Error: {msg}")

    def _on_smooth_toggled(self, checked: bool) -> None:
        self._controller.set_smooth_result(checked)
        self._spin_smooth.setEnabled(checked)

    def _on_symmetrize_toggled(self, checked: bool) -> None:
        self._controller.set_symmetrize(checked)
        self._combo_sym_method.setEnabled(checked)

    def _on_symmetrize_method_changed(self, text: str) -> None:
        internal = self._SYM_DISPLAY.get(text, "position")
        self._controller.set_symmetry_method(internal)

    def _on_output_space_changed(self, text: str) -> None:
        internal = self._OUTPUT_SPACE_DISPLAY.get(text, "source")
        self._controller.set_output_space(internal)

    def _on_schedule_changed(self, text: str) -> None:
        self._controller.set_schedule(text.lower())
        self._sync_advanced_to_schedule()

    def _sync_advanced_to_schedule(self) -> None:
        """Update advanced sliders/spinboxes to match the current schedule defaults."""
        stiffness, steps = self._controller.schedule_defaults()
        for w in (self._slider_stiffness, self._spin_stiffness, self._slider_steps, self._spin_steps):
            w.blockSignals(True)
        self._slider_stiffness.setValue(round(stiffness * 100))
        self._spin_stiffness.setValue(stiffness)
        self._slider_steps.setValue(steps)
        self._spin_steps.setValue(steps)
        for w in (self._slider_stiffness, self._spin_stiffness, self._slider_steps, self._spin_steps):
            w.blockSignals(False)

    def _on_decimate_toggled(self, checked: bool) -> None:
        self._controller.set_decimate_target(checked)
        self._spin_decimate.setEnabled(checked)

    def _on_advanced_toggled(self, checked: bool) -> None:
        if not checked:
            self._controller.reset_advanced()
            # Reset widgets to schedule defaults
            self._sync_advanced_to_schedule()
            for w in (self._slider_landmark_strength, self._spin_landmark_strength):
                w.blockSignals(True)
            self._slider_landmark_strength.setValue(20)
            self._spin_landmark_strength.setValue(1.0)
            for w in (self._slider_landmark_strength, self._spin_landmark_strength):
                w.blockSignals(False)

    def _on_stiffness_slider(self, value: int) -> None:
        fval = value / 100.0
        self._spin_stiffness.blockSignals(True)
        self._spin_stiffness.setValue(fval)
        self._spin_stiffness.blockSignals(False)
        self._controller.set_stiffness(fval)

    def _on_stiffness_spin(self, value: float) -> None:
        self._slider_stiffness.blockSignals(True)
        self._slider_stiffness.setValue(round(value * 100))
        self._slider_stiffness.blockSignals(False)
        self._controller.set_stiffness(value)

    def _on_landmark_strength_slider(self, value: int) -> None:
        fval = value * 0.05
        self._spin_landmark_strength.blockSignals(True)
        self._spin_landmark_strength.setValue(fval)
        self._spin_landmark_strength.blockSignals(False)
        self._controller.set_landmark_strength(fval)

    def _on_landmark_strength_spin(self, value: float) -> None:
        self._slider_landmark_strength.blockSignals(True)
        self._slider_landmark_strength.setValue(round(value / 0.05))
        self._slider_landmark_strength.blockSignals(False)
        self._controller.set_landmark_strength(value)

    def _on_steps_slider(self, value: int) -> None:
        self._spin_steps.blockSignals(True)
        self._spin_steps.setValue(value)
        self._spin_steps.blockSignals(False)
        self._controller.set_steps(value)

    def _on_steps_spin(self, value: int) -> None:
        self._slider_steps.blockSignals(True)
        self._slider_steps.setValue(value)
        self._slider_steps.blockSignals(False)
        self._controller.set_steps(value)

    def _update_landmark_strength_enabled(self) -> None:
        enabled = self._controller.has_landmarks
        self._slider_landmark_strength.setEnabled(enabled)
        self._spin_landmark_strength.setEnabled(enabled)

    def _refresh_landmark_tree(self) -> None:
        self._tree_landmarks.clear()
        self._update_landmark_strength_enabled()
        for i, (src, tgt) in enumerate(self._controller.landmark_pairs):
            # Show short name (last component of DAG path)
            src_label = src.rsplit("|", 1)[-1]
            tgt_label = tgt.rsplit("|", 1)[-1]
            item = QTreeWidgetItem([src_label, tgt_label])
            self._tree_landmarks.addTopLevelItem(item)

            btn_sel = IconButton(icon_name="select", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_IMAGES_DIR)
            btn_sel.setToolTip("Select pair")
            btn_sel.clicked.connect(lambda _=False, idx=i: self._on_select_pair(idx))
            self._tree_landmarks.setItemWidget(item, 2, btn_sel)

            btn_del = IconButton(icon_name="remove", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_IMAGES_DIR)
            btn_del.setToolTip("Remove pair")
            btn_del.clicked.connect(lambda _=False, idx=i: self._on_remove_pair(idx))
            self._tree_landmarks.setItemWidget(item, 3, btn_del)

    def _on_select_pair(self, index: int) -> None:
        self._controller.select_landmark_pair(index)

    def _on_remove_pair(self, index: int) -> None:
        self._controller.remove_landmark_pair(index)

    def _on_landmark_header_clicked(self, index: int) -> None:
        if index == 0:
            self._controller.select_source_landmarks()
        elif index == 1:
            self._controller.select_target_landmarks()
        elif index == 2:
            self._controller.select_all_landmarks()
        elif index == 3:
            self._controller.clear_all_landmarks()

    @error_handler
    @undo_chunk("Mesh Fitter: Run")
    def _on_run(self) -> None:
        request = self._controller.build_fitting_request()
        if request is None:
            return

        self._controller.on_fitting_started()
        QApplication.processEvents()

        from .scene_ops import wait_cursor

        try:
            wait_cursor(True)
            result = command.run_fitting(
                source_name=request.source_name,
                target_name=request.target_name,
                config=request.config,
                landmarks=request.landmarks,
                duplicate_source=request.duplicate_source,
                output_space=request.output_space,
                target_face_indices=request.target_face_indices,
                on_progress=self._on_fitting_progress,
            )
            self._controller.on_fitting_finished(result)
        except Exception as exc:
            logger.error("Fitting failed", exc_info=True)
            self._controller.on_fitting_error(str(exc))
        finally:
            wait_cursor(False)

    def _on_fitting_progress(self, message: str) -> None:
        self._status_bar.showMessage(message)
        QApplication.processEvents()

    def _on_fitting_complete(self, result) -> None:
        """Select the result mesh in Maya after fitting completes."""
        if result.result_mesh_name:
            from .scene_ops import select_mesh

            select_mesh(result.result_mesh_name)

    def _set_fitting_ui(self, running: bool) -> None:
        """Enable/disable interactive elements during fitting."""
        enabled = not running
        self._btn_run.setEnabled(enabled)
        self._btn_set_source.setEnabled(enabled)
        self._btn_set_target.setEnabled(enabled)
        self._btn_set_region.setEnabled(enabled)
        self._btn_set_landmarks.setEnabled(enabled)
        self._tree_landmarks.setEnabled(enabled)

        self._btn_run.setText("Fitting..." if running else "Run Fitting")

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
            "schedule": self._combo_schedule.currentText().lower(),
            "auto_align": self._chk_auto_align.isChecked(),
            "smooth": self._chk_smooth.isChecked(),
            "smooth_iterations": self._spin_smooth.value(),
            "snap": self._chk_snap.isChecked(),
            "symmetrize": self._chk_symmetrize.isChecked(),
            "symmetry_method": self._SYM_DISPLAY.get(self._combo_sym_method.currentText(), "position"),
            "duplicate": self._chk_duplicate.isChecked(),
            "output_space": self._OUTPUT_SPACE_DISPLAY.get(self._combo_output_space.currentText(), "source"),
            "decimate_target": self._chk_decimate.isChecked(),
            "decimate_ratio": self._spin_decimate.value(),
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict) -> None:
        self._combo_schedule.setCurrentText(settings_data.get("schedule", "gentle").title())
        self._chk_auto_align.setChecked(settings_data.get("auto_align", True))
        self._chk_smooth.setChecked(settings_data.get("smooth", False))
        self._spin_smooth.setValue(settings_data.get("smooth_iterations", 3))
        self._chk_snap.setChecked(settings_data.get("snap", False))
        self._chk_symmetrize.setChecked(settings_data.get("symmetrize", False))
        # Convert internal symmetry method to display name
        sym_internal = settings_data.get("symmetry_method", "position")
        sym_display = next((k for k, v in self._SYM_DISPLAY.items() if v == sym_internal), "By Position")
        self._combo_sym_method.setCurrentText(sym_display)
        self._chk_duplicate.setChecked(settings_data.get("duplicate", True))
        os_internal = settings_data.get("output_space", "source")
        os_display = next((k for k, v in self._OUTPUT_SPACE_DISPLAY.items() if v == os_internal), "Source")
        self._combo_output_space.setCurrentText(os_display)
        self._chk_decimate.setChecked(settings_data.get("decimate_target", False))
        self._spin_decimate.setValue(settings_data.get("decimate_ratio", 0.25))

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
    """Show the Mesh Fitter UI.

    Returns:
        MainWindow: The main window instance, or None if trimesh is not available.
    """
    global _instance

    if not TRIMESH_AVAILABLE:
        cmds.error(
            "Mesh Fitter requires trimesh, rtree and fast-simplification. Please install: mayapy -m pip install trimesh rtree fast-simplification"
        )
        return None

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
