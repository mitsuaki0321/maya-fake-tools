"""BS Transfer main window — thin Qt shell over BSTransferController.

All business logic lives in bs_controller.py; this file only handles
widget creation, layout, and Qt signal wiring.
"""

from __future__ import annotations

from logging import getLogger

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStatusBar,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ..mesh_fitter.bs_controller import BSTransferController
from ..mesh_fitter.mesh_bridge import OpenMayaMeshAPI

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """GUI window for blend shape transfer in Maya."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            object_name="BSTransferMainWindow",
            window_title="BS Transfer",
            central_layout="vertical",
        )
        self.setMinimumWidth(420)

        self.settings = ToolSettingsManager(tool_name="blendshape_transfer", category="model")

        self._api = OpenMayaMeshAPI()
        self._controller = BSTransferController(api=self._api)

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

        lbl_source = QLabel("Source Base:")
        lbl_fitted = QLabel("Fitted:")
        fm = lbl_source.fontMetrics()
        label_width = max(fm.horizontalAdvance(lbl_source.text()), fm.horizontalAdvance(lbl_fitted.text()))
        label_width += fm.horizontalAdvance("M")
        lbl_source.setFixedWidth(label_width)
        lbl_fitted.setFixedWidth(label_width)
        lbl_source.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_fitted.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        row_src = QHBoxLayout()
        row_src.addWidget(lbl_source)
        self._line_source = QLineEdit()
        self._line_source.setReadOnly(True)
        self._line_source.setPlaceholderText("Select a mesh and click SET")
        row_src.addWidget(self._line_source, 1)
        self._btn_set_source = QPushButton("SET")
        row_src.addWidget(self._btn_set_source)
        lay_mesh.addLayout(row_src)

        row_fit = QHBoxLayout()
        row_fit.addWidget(lbl_fitted)
        self._line_fitted = QLineEdit()
        self._line_fitted.setReadOnly(True)
        self._line_fitted.setPlaceholderText("Select a mesh and click SET")
        row_fit.addWidget(self._line_fitted, 1)
        self._btn_set_fitted = QPushButton("SET")
        row_fit.addWidget(self._btn_set_fitted)
        lay_mesh.addLayout(row_fit)

        self.central_layout.addWidget(grp_mesh)

        # --- Blend Shapes ---
        grp_bs = QGroupBox("Blend Shapes")
        lay_bs = QVBoxLayout(grp_bs)

        row_bs_header = QHBoxLayout()
        row_bs_header.addStretch()
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.setEnabled(False)
        row_bs_header.addWidget(self._btn_refresh)
        lay_bs.addLayout(row_bs_header)

        self._list_bs = QListWidget()
        self._list_bs.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay_bs.addWidget(self._list_bs)

        self.central_layout.addWidget(grp_bs)

        # --- Transfer button ---
        self._btn_transfer = QPushButton("Transfer Blend Shapes")
        self._btn_transfer.setMinimumHeight(36)
        self.central_layout.addWidget(self._btn_transfer)

        # --- Status bar ---
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Ready")
        self.central_layout.addWidget(self._status_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_source.clicked.connect(self._on_set_source)
        self._btn_set_fitted.clicked.connect(self._on_set_fitted)
        self._btn_refresh.clicked.connect(self._on_refresh)

        self._list_bs.itemSelectionChanged.connect(self._on_bs_selection_changed)

        self._btn_transfer.clicked.connect(self._on_transfer)

    def _connect_controller_callbacks(self) -> None:
        self._controller.on_status = self._status_bar.showMessage
        self._controller.on_error = self._on_error

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_set_source(self) -> None:
        from ..mesh_fitter.scene_ops import get_selected_mesh

        name = get_selected_mesh()
        if name is None:
            self._status_bar.showMessage("Error: Select a mesh transform")
            return
        self._line_source.setText(name.rsplit("|", 1)[-1])
        self._line_source.setToolTip(name)
        self._controller.set_source_base(name)
        self._btn_refresh.setEnabled(True)
        self._on_refresh()

    def _on_set_fitted(self) -> None:
        from ..mesh_fitter.scene_ops import get_selected_mesh

        name = get_selected_mesh()
        if name is None:
            self._status_bar.showMessage("Error: Select a mesh transform")
            return
        self._line_fitted.setText(name.rsplit("|", 1)[-1])
        self._line_fitted.setToolTip(name)
        self._controller.set_fitted(name)
        self._update_transfer_button()

    def _on_refresh(self) -> None:
        self._controller.refresh_bs_list()
        self._refresh_bs_lists()
        self._update_transfer_button()

    def _on_bs_selection_changed(self) -> None:
        names = [item.text() for item in self._list_bs.selectedItems()]
        self._controller.set_selected_bs(names)
        self._update_transfer_button()

    def _on_error(self, msg: str) -> None:
        logger.error(msg, exc_info=True)
        self._status_bar.showMessage(f"Error: {msg}")

    @error_handler
    @undo_chunk("BS Transfer")
    def _on_transfer(self) -> None:
        import maya.cmds as cmds  # type: ignore[import]

        from ..mesh_fitter.scene_ops import duplicate_mesh
        from ..mesh_fitter.transfer.delta_transfer import transfer_batch

        error = self._controller.validate_selection()
        if error is not None:
            self._on_error(error)
            return

        request = self._controller.build_transfer_request()
        if request is None:
            return

        # Read vertex data
        source_base_verts = self._api.get_vertex_positions(request.source_base_name)
        fitted_verts = self._api.get_vertex_positions(request.fitted_name)

        bs_list = []
        for name in request.bs_names:
            verts = self._api.get_vertex_positions(name)
            bs_list.append((name, verts))

        # Compute deltas
        batch_result = transfer_batch(source_base_verts, fitted_verts, bs_list)

        # Write results to scene
        created = []
        for tr in batch_result.results:
            new_name = f"{tr.name}_transfer"
            dup_name = duplicate_mesh(request.fitted_name, new_name)
            self._api.set_vertex_positions(dup_name, tr.vertices)
            cmds.setAttr(f"{dup_name}.visibility", True)
            created.append(dup_name)
        if created:
            cmds.select(created, replace=True)

        if batch_result.skipped:
            names = ", ".join(s[0] for s in batch_result.skipped)
            logger.warning("Skipped: %s", names)

        count = len(batch_result.results)
        msg = f"Transfer complete: {count} blend shape{'s' if count != 1 else ''} created"
        if batch_result.skipped:
            msg += f", {len(batch_result.skipped)} skipped"
        self._status_bar.showMessage(msg)

    def _refresh_bs_lists(self) -> None:
        """Update the blend shape list widget from controller."""
        previously_selected = set(self._controller.selected_bs_names)
        self._list_bs.blockSignals(True)
        self._list_bs.clear()
        for name in self._controller.available_bs_names:
            self._list_bs.addItem(name)
        # Restore previous selection
        for i in range(self._list_bs.count()):
            item = self._list_bs.item(i)
            if item.text() in previously_selected:
                item.setSelected(True)
        self._list_bs.blockSignals(False)
        # Sync controller with actual selection state
        names = [item.text() for item in self._list_bs.selectedItems()]
        self._controller.set_selected_bs(names)

    def _update_transfer_button(self) -> None:
        self._btn_transfer.setEnabled(self._controller.can_run)

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
            "window_geometry": {
                "size": [self.width(), self.height()],
                "position": [self.x(), self.y()],
            },
        }

    def _apply_settings(self, settings_data: dict) -> None:
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
    """Show the BlendShape Transfer UI.

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
