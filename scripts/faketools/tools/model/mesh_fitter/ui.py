"""Mesh Fitter main window — thin Qt shell over MeshFitController.

All business logic lives in controller.py; this file only handles
widget creation, layout, and Qt signal wiring.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import IconButton, IconButtonStyle
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
        fm = lbl_source.fontMetrics()
        label_width = max(fm.horizontalAdvance(lbl_source.text()), fm.horizontalAdvance(lbl_target.text()))
        label_width += fm.horizontalAdvance("M")
        lbl_source.setFixedWidth(label_width)
        lbl_target.setFixedWidth(label_width)
        lbl_source.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_target.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

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

        self.central_layout.addWidget(grp_mesh)

        # --- Settings ---
        grp_settings = QGroupBox("Settings")
        lay_settings = QVBoxLayout(grp_settings)

        row_sched = QHBoxLayout()
        row_sched.addWidget(QLabel("Schedule:"))
        self._combo_schedule = QComboBox()
        self._combo_schedule.addItems(list(SCHEDULES.keys()))
        self._combo_schedule.setCurrentText("gentle")
        row_sched.addWidget(self._combo_schedule, 1)
        lay_settings.addLayout(row_sched)

        self._chk_auto_align = QCheckBox("Auto-align (Procrustes + ICP)")
        self._chk_auto_align.setChecked(True)
        lay_settings.addWidget(self._chk_auto_align)

        row_smooth = QHBoxLayout()
        self._chk_smooth = QCheckBox("Smooth result (Taubin)  iterations:")
        row_smooth.addWidget(self._chk_smooth)
        self._spin_smooth = QSpinBox()
        self._spin_smooth.setRange(1, 50)
        self._spin_smooth.setValue(3)
        self._spin_smooth.setEnabled(False)
        row_smooth.addWidget(self._spin_smooth)
        lay_settings.addLayout(row_smooth)

        self._chk_snap = QCheckBox("Snap to target (progressive)")
        lay_settings.addWidget(self._chk_snap)

        row_sym = QHBoxLayout()
        self._chk_symmetrize = QCheckBox("Symmetrize")
        row_sym.addWidget(self._chk_symmetrize)
        self._combo_sym_method = QComboBox()
        self._combo_sym_method.addItems(["position", "topology"])
        self._combo_sym_method.setEnabled(False)
        row_sym.addWidget(self._combo_sym_method)
        lay_settings.addLayout(row_sym)

        self._chk_duplicate = QCheckBox("Duplicate source (preserve original)")
        self._chk_duplicate.setChecked(True)
        lay_settings.addWidget(self._chk_duplicate)

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
        self._tree_landmarks.setMaximumHeight(150)
        header = self._tree_landmarks.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        lay_lm.addWidget(self._tree_landmarks)

        self._btn_set_landmarks = QPushButton("Set")
        lay_lm.addWidget(self._btn_set_landmarks)

        self.central_layout.addWidget(grp_lm)

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

        self._combo_schedule.currentTextChanged.connect(self._controller.set_schedule)
        self._chk_auto_align.toggled.connect(self._controller.set_auto_align)
        self._chk_smooth.toggled.connect(self._on_smooth_toggled)
        self._spin_smooth.valueChanged.connect(self._controller.set_smooth_iterations)
        self._chk_snap.toggled.connect(self._controller.set_snap_to_target)
        self._chk_symmetrize.toggled.connect(self._on_symmetrize_toggled)
        self._combo_sym_method.currentTextChanged.connect(self._controller.set_symmetry_method)
        self._chk_duplicate.toggled.connect(self._controller.set_duplicate_source)

        self._btn_set_landmarks.clicked.connect(lambda: self._controller.set_landmarks_from_selection())

        self._btn_run.clicked.connect(self._on_run)

    def _connect_controller_callbacks(self) -> None:
        self._controller.on_status = self._status_bar.showMessage
        self._controller.on_error = self._on_error
        self._controller.on_landmarks_changed = self._refresh_landmark_tree
        self._controller.on_fitting_state_changed = self._set_fitting_ui
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

    def _on_error(self, msg: str) -> None:
        logger.error(msg, exc_info=True)
        self._status_bar.showMessage(f"Error: {msg}")

    def _on_smooth_toggled(self, checked: bool) -> None:
        self._controller.set_smooth_result(checked)
        self._spin_smooth.setEnabled(checked)

    def _on_symmetrize_toggled(self, checked: bool) -> None:
        self._controller.set_symmetrize(checked)
        self._combo_sym_method.setEnabled(checked)

    def _refresh_landmark_tree(self) -> None:
        self._tree_landmarks.clear()
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
            "schedule": self._combo_schedule.currentText(),
            "auto_align": self._chk_auto_align.isChecked(),
            "smooth": self._chk_smooth.isChecked(),
            "smooth_iterations": self._spin_smooth.value(),
            "snap": self._chk_snap.isChecked(),
            "symmetrize": self._chk_symmetrize.isChecked(),
            "symmetry_method": self._combo_sym_method.currentText(),
            "duplicate": self._chk_duplicate.isChecked(),
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict) -> None:
        self._combo_schedule.setCurrentText(settings_data.get("schedule", "gentle"))
        self._chk_auto_align.setChecked(settings_data.get("auto_align", True))
        self._chk_smooth.setChecked(settings_data.get("smooth", False))
        self._spin_smooth.setValue(settings_data.get("smooth_iterations", 3))
        self._chk_snap.setChecked(settings_data.get("snap", False))
        self._chk_symmetrize.setChecked(settings_data.get("symmetrize", False))
        self._combo_sym_method.setCurrentText(settings_data.get("symmetry_method", "position"))
        self._chk_duplicate.setChecked(settings_data.get("duplicate", True))

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
        MainWindow: The main window instance
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
