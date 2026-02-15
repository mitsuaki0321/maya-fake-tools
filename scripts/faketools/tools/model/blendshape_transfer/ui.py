"""BS Transfer main window — thin Qt shell over BSTransferController.

All business logic lives in bs_controller.py; this file only handles
widget creation, layout, and Qt signal wiring.
"""

from __future__ import annotations

from logging import getLogger

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler
from ....lib_ui.maya_qt import get_maya_main_window
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ..mesh_fitting.bs_controller import BSTransferController
from ..mesh_fitting.bs_worker import TransferWorker
from ..mesh_fitting.controller import SceneMeshListProvider
from ..mesh_fitting.mesh_bridge import OpenMayaMeshAPI

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

        self._controller = BSTransferController(
            api=OpenMayaMeshAPI(),
            mesh_list_provider=SceneMeshListProvider(),
        )
        self._worker: TransferWorker | None = None

        self._build_ui()
        self._connect_signals()
        self._connect_controller_callbacks()

        # Initial mesh list refresh
        self._controller.refresh_mesh_list()
        self._populate_combos()

        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # --- Meshes ---
        grp_mesh = QGroupBox("Meshes")
        lay_mesh = QVBoxLayout(grp_mesh)

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Source Base:"))
        self._combo_source = QComboBox()
        row_src.addWidget(self._combo_source, 1)
        self._btn_refresh = QPushButton("Refresh")
        row_src.addWidget(self._btn_refresh)
        lay_mesh.addLayout(row_src)

        row_fit = QHBoxLayout()
        row_fit.addWidget(QLabel("Fitted:"))
        self._combo_fitted = QComboBox()
        row_fit.addWidget(self._combo_fitted, 1)
        lay_mesh.addLayout(row_fit)

        self.central_layout.addWidget(grp_mesh)

        # --- Blend Shapes ---
        grp_bs = QGroupBox("Blend Shapes")
        lay_bs = QHBoxLayout(grp_bs)

        # Available list
        lay_avail = QVBoxLayout()
        lay_avail.addWidget(QLabel("Available:"))
        self._list_available = QListWidget()
        self._list_available.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay_avail.addWidget(self._list_available)
        lay_bs.addLayout(lay_avail, 1)

        # Arrow buttons
        lay_arrows = QVBoxLayout()
        lay_arrows.addStretch()
        self._btn_add = QPushButton(">>")
        self._btn_add.setFixedWidth(40)
        lay_arrows.addWidget(self._btn_add)
        self._btn_remove = QPushButton("<<")
        self._btn_remove.setFixedWidth(40)
        lay_arrows.addWidget(self._btn_remove)
        lay_arrows.addStretch()
        lay_bs.addLayout(lay_arrows)

        # Selected list
        lay_sel = QVBoxLayout()
        lay_sel.addWidget(QLabel("Selected:"))
        self._list_selected = QListWidget()
        self._list_selected.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay_sel.addWidget(self._list_selected)
        lay_bs.addLayout(lay_sel, 1)

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
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._combo_source.currentTextChanged.connect(self._on_source_changed)
        self._combo_fitted.currentTextChanged.connect(self._on_fitted_changed)

        self._btn_add.clicked.connect(self._on_add_bs)
        self._btn_remove.clicked.connect(self._on_remove_bs)

        self._btn_transfer.clicked.connect(self._on_transfer)

    def _connect_controller_callbacks(self) -> None:
        self._controller.on_status = self._status_bar.showMessage
        self._controller.on_error = self._on_error
        self._controller.on_progress = self._on_progress
        self._controller.on_transfer_state_changed = self._set_transfer_ui
        self._controller.on_transfer_complete = self._on_complete

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_refresh(self) -> None:
        names = self._controller.refresh_mesh_list()
        self._populate_combos(names)

    def _populate_combos(self, names: list[str] | None = None) -> None:
        if names is None:
            names = self._controller.mesh_names

        for combo in (self._combo_source, self._combo_fitted):
            combo.blockSignals(True)
            prev = combo.currentText()
            combo.clear()
            combo.addItems(names)
            if prev in names:
                combo.setCurrentText(prev)
            combo.blockSignals(False)

        # Sync controller with final combo values (signals were blocked)
        self._controller.set_source_base(self._combo_source.currentText())
        self._controller.set_fitted(self._combo_fitted.currentText())
        self._refresh_bs_lists()

    def _on_source_changed(self, name: str) -> None:
        self._controller.set_source_base(name)
        self._refresh_bs_lists()
        self._update_transfer_button()

    def _on_fitted_changed(self, name: str) -> None:
        self._controller.set_fitted(name)
        self._refresh_bs_lists()
        self._update_transfer_button()

    def _on_add_bs(self) -> None:
        for item in self._list_available.selectedItems():
            self._controller.add_bs(item.text())
        self._refresh_bs_lists()
        self._update_transfer_button()

    def _on_remove_bs(self) -> None:
        for item in self._list_selected.selectedItems():
            self._controller.remove_bs(item.text())
        self._refresh_bs_lists()
        self._update_transfer_button()

    def _on_error(self, msg: str) -> None:
        logger.error(msg, exc_info=True)
        self._status_bar.showMessage(f"Error: {msg}")

    def _on_progress(self, current: int, total: int, name: str) -> None:
        self._status_bar.showMessage(f"Transferring {current}/{total}: {name}")

    def _on_complete(self, count: int, skipped: list) -> None:
        if skipped:
            names = ", ".join(s[0] for s in skipped)
            logger.warning("Skipped: %s", names)

    @error_handler
    def _on_transfer(self) -> None:
        # Validate before building request
        error = self._controller.validate_selection()
        if error is not None:
            self._on_error(error)
            return

        request = self._controller.build_transfer_request()
        if request is None:
            return

        self._controller.on_transfer_started()
        self._worker = TransferWorker(request, parent=self)
        self._worker.finished.connect(self._controller.on_transfer_finished)
        self._worker.error.connect(self._controller.on_transfer_error)
        self._worker.progress.connect(self._controller.on_progress)
        self._worker.start()

    def _refresh_bs_lists(self) -> None:
        """Update the Available and Selected list widgets from controller."""
        self._list_available.clear()
        for name in self._controller.available_bs_names:
            self._list_available.addItem(name)

        self._list_selected.clear()
        for name in self._controller.selected_bs_names:
            self._list_selected.addItem(name)

    def _update_transfer_button(self) -> None:
        self._btn_transfer.setEnabled(self._controller.can_run)

    def _set_transfer_ui(self, running: bool) -> None:
        """Enable/disable interactive elements during transfer."""
        enabled = not running
        self._btn_transfer.setEnabled(enabled and self._controller.can_run)
        self._combo_source.setEnabled(enabled)
        self._combo_fitted.setEnabled(enabled)
        self._btn_refresh.setEnabled(enabled)
        self._btn_add.setEnabled(enabled)
        self._btn_remove.setEnabled(enabled)

        self._btn_transfer.setText("Transferring..." if running else "Transfer Blend Shapes")

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
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
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
