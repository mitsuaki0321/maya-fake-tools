"""VP Compositor main UI — layer panel window."""

from __future__ import annotations

import contextlib
from logging import getLogger
import os

import maya.api.OpenMayaRender as omr  # type: ignore
import maya.cmds as cmds  # type: ignore

from .....lib_ui.maya_qt import get_maya_main_window
from .....lib_ui.qt_compat import (
    QCheckBox,
    QComboBox,
    QCursor,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ..core.builder import OVERRIDE_NAME, build_override
from ..core.model import (
    CameraLayer,
    ImageLayer,
    LayerStack,
    SequenceLayer,
)
from ..core.scene_queries import (
    add_set_members,
    create_object_set,
    get_selection,
    list_model_panels,
    make_set_name,
    query_panel_camera,
    remove_set_members,
)
from ..core.sequence_detect import detect_sequence
from ..core.serialization import export_stack, import_stack, stack_from_dicts
from .colors import (
    ICON_DELETE,
    ICON_MUTED,
    LAYER_TYPE_CAMERA,
    LAYER_TYPE_IMAGE,
    LAYER_TYPE_SEQUENCE,
)
from .dialogs import IMAGE_FILTER, AddCameraDialog, AddImageDialog, AddSequenceDialog
from .layer_model import ROLE_STACK_IDX, ROLE_VISIBLE, LayerModel
from .layer_view import LayerView
from .resource_utils import load_qss, load_svg_icon, make_separator

logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_OBJECT_NAME = "vpcompMainWindow"
WINDOW_TITLE = "VP Compositor"
VP2_RENDERER = "vp2Renderer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _panel_label(panel: str) -> str:
    """Return 'modelPanel4 (persp)' style label."""
    try:
        cam = query_panel_camera(panel)
        return f"{panel} ({cam})"
    except Exception:
        return panel


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class VpcompWindow(QMainWindow):
    """VP Compositor main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(0, 500)

        self._stack = LayerStack()
        self._override_obj = None
        self._applied_panel: str | None = None

        self._build_ui()
        self._refresh_panels()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(load_qss())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Menu bar ──
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Export Layers...").triggered.connect(self._export_layers)
        file_menu.addAction("Import Layers...").triggered.connect(self._import_layers)
        edit_menu = menu_bar.addMenu("Edit")
        playblast_action = edit_menu.addAction("to playblast...")
        playblast_action.triggered.connect(self._open_playblast)

        # ── Panel row ──
        panel_w = QWidget()
        pl = QHBoxLayout(panel_w)
        pl.setContentsMargins(8, 6, 8, 6)
        pl.setSpacing(6)

        lbl = QLabel("PANEL")
        lbl.setObjectName("panelLabel")
        pl.addWidget(lbl)

        self._panel_combo = QComboBox()
        pl.addWidget(self._panel_combo, 1)

        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("iconBtn")
        self._refresh_btn.setIcon(load_svg_icon("refresh", ICON_MUTED))
        self._refresh_btn.setToolTip("Refresh panels")
        self._refresh_btn.clicked.connect(self._refresh_panels)
        pl.addWidget(self._refresh_btn)

        root.addWidget(panel_w)
        root.addWidget(make_separator())

        # ── Layers header ──
        lh_w = QWidget()
        lh = QHBoxLayout(lh_w)
        lh.setContentsMargins(8, 5, 8, 5)
        lh.setSpacing(4)

        header_lbl = QLabel("LAYERS")
        header_lbl.setObjectName("layersHeader")
        lh.addWidget(header_lbl)
        lh.addStretch()
        root.addWidget(lh_w)

        # ── Layer view ──
        self._layer_model = LayerModel(self)
        self._layer_view = LayerView(self)
        self._layer_view.setModel(self._layer_model)
        self._layer_view.setMinimumHeight(240)

        # Context menu on right-click
        self._layer_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._layer_view.customContextMenuRequested.connect(self._on_context_menu)

        # Signals
        self._layer_view.visibility_changed.connect(self._on_visibility_changed)
        self._layer_view.menu_requested.connect(self._on_menu_requested)
        self._layer_view.order_changed.connect(self._on_order_changed)
        self._layer_model.dataChanged.connect(self._on_model_data_changed)

        root.addWidget(self._layer_view, 1)
        root.addWidget(make_separator())

        # ── Add / Delete row ──
        add_w = QWidget()
        al = QHBoxLayout(add_w)
        al.setContentsMargins(8, 6, 8, 6)
        al.setSpacing(4)

        self._add_cam_btn = QPushButton()
        self._add_cam_btn.setObjectName("iconBtn")
        self._add_cam_btn.setIcon(load_svg_icon("add_cam", LAYER_TYPE_CAMERA))
        self._add_cam_btn.setToolTip("Add Camera layer")
        self._add_img_btn = QPushButton()
        self._add_img_btn.setObjectName("iconBtn")
        self._add_img_btn.setIcon(load_svg_icon("add_img", LAYER_TYPE_IMAGE))
        self._add_img_btn.setToolTip("Add Image layer")
        self._add_seq_btn = QPushButton()
        self._add_seq_btn.setObjectName("iconBtn")
        self._add_seq_btn.setIcon(load_svg_icon("add_seq", LAYER_TYPE_SEQUENCE))
        self._add_seq_btn.setToolTip("Add Sequence layer")

        self._add_cam_btn.clicked.connect(self._add_camera)
        self._add_img_btn.clicked.connect(self._add_image)
        self._add_seq_btn.clicked.connect(self._add_sequence)

        self._del_btn = QPushButton()
        self._del_btn.setObjectName("deleteBtn")
        self._del_btn.setIcon(load_svg_icon("trash", ICON_DELETE))
        self._del_btn.setToolTip("Delete selected layer")
        self._del_btn.clicked.connect(self._delete_layer)

        al.addWidget(self._add_cam_btn)
        al.addWidget(self._add_img_btn)
        al.addWidget(self._add_seq_btn)
        al.addStretch()
        al.addWidget(self._del_btn)
        root.addWidget(add_w)
        root.addWidget(make_separator())

        # ── Footer ──
        footer_w = QWidget()
        fl = QHBoxLayout(footer_w)
        fl.setContentsMargins(8, 6, 8, 6)
        fl.setSpacing(6)

        self._auto_cb = QCheckBox("Auto Update")
        fl.addWidget(self._auto_cb)
        fl.addStretch()

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setObjectName("applyBtn")
        self._remove_btn = QPushButton("Remove")

        self._apply_btn.clicked.connect(self._apply_override)
        self._remove_btn.clicked.connect(self._remove_override)

        fl.addWidget(self._apply_btn)
        fl.addWidget(self._remove_btn)
        root.addWidget(footer_w)

    # -- Panel selector -----------------------------------------------------

    def _refresh_panels(self):
        self._panel_combo.clear()
        panels = list_model_panels()
        panels.sort(key=lambda p: 0 if query_panel_camera(p) == "persp" else 1)
        for panel in panels:
            self._panel_combo.addItem(_panel_label(panel), panel)

    def _current_panel(self) -> str | None:
        return self._panel_combo.currentData()

    # -- Layer list sync ----------------------------------------------------

    def _sync_list(self):
        """Rebuild LayerModel from the LayerStack."""
        sel_indexes = self._layer_view.selectedIndexes()
        sel_row = sel_indexes[0].row() if sel_indexes else -1

        self._layer_model.rebuild(self._stack)

        if 0 <= sel_row < self._layer_model.rowCount():
            idx = self._layer_model.index(sel_row, 0)
            self._layer_view.setCurrentIndex(idx)

    def _selected_stack_index(self) -> int | None:
        indexes = self._layer_view.selectedIndexes()
        if not indexes:
            return None
        return indexes[0].data(ROLE_STACK_IDX)

    # -- Visibility ---------------------------------------------------------

    def _on_visibility_changed(self, stack_idx: int, visible: bool):
        if stack_idx < len(self._stack):
            self._stack[stack_idx].visible = visible
            self._auto_rebuild()

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        if ROLE_VISIBLE in roles:
            stack_idx = top_left.data(ROLE_STACK_IDX)
            visible = top_left.data(ROLE_VISIBLE)
            self._on_visibility_changed(stack_idx, visible)

    # -- DnD order change ---------------------------------------------------

    def _on_order_changed(self):
        self._layer_model.rows_moved_to_stack(self._stack)
        self._auto_rebuild()

    # -- Add layers ---------------------------------------------------------

    def _add_camera(self):
        dlg = AddCameraDialog(self._stack.cameras_in_use(), self)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_camera:
            return
        cam = dlg.selected_camera
        set_name = make_set_name(cam)
        create_object_set(set_name)
        layer = CameraLayer(name=cam, camera=cam, object_set=set_name)
        try:
            self._stack.add(layer)
        except (ValueError, RuntimeError) as exc:
            logger.warning("Cannot add camera layer: %s", exc)
            return
        self._sync_list()
        self._auto_rebuild()

    def _add_image(self):
        dlg = AddImageDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_path:
            return
        name = os.path.basename(dlg.selected_path)
        layer = ImageLayer(name=name, file_path=dlg.selected_path, fit_mode=dlg.selected_fit)
        try:
            self._stack.add(layer)
        except RuntimeError as exc:
            logger.warning("Cannot add image layer: %s", exc)
            return
        self._sync_list()
        self._auto_rebuild()

    def _add_sequence(self):
        dlg = AddSequenceDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.seq_info:
            return
        info = dlg.seq_info
        name = os.path.basename(info.file_pattern % info.frame_start)
        layer = SequenceLayer(
            name=name,
            file_pattern=info.file_pattern,
            frame_start=info.frame_start,
            frame_end=info.frame_end,
            fit_mode=dlg.selected_fit,
        )
        try:
            self._stack.add(layer)
        except RuntimeError as exc:
            logger.warning("Cannot add sequence layer: %s", exc)
            return
        self._sync_list()
        self._auto_rebuild()

    def _delete_layer(self):
        idx = self._selected_stack_index()
        if idx is None:
            return
        self._stack.remove(idx)
        self._sync_list()
        self._auto_rebuild()

    # -- Context menu -------------------------------------------------------

    def _on_menu_requested(self, row: int):
        item = self._layer_model.item(row)
        if item is None:
            return
        stack_idx = item.data(ROLE_STACK_IDX)
        if stack_idx is None or stack_idx >= len(self._stack):
            return
        self._show_context_menu_for(stack_idx)

    def _on_context_menu(self, pos):
        index = self._layer_view.indexAt(pos)
        if index.isValid():
            self._show_context_menu_for(index.data(ROLE_STACK_IDX))

    def _show_context_menu_for(self, stack_idx: int):
        layer = self._stack[stack_idx]
        menu = QMenu(self)

        if isinstance(layer, CameraLayer):
            act_add = menu.addAction("Add Members")
            act_remove = menu.addAction("Remove Members")
            menu.addSeparator()
            act_select = menu.addAction("Select Set")
            action = menu.exec_(QCursor.pos())
            if action == act_add:
                self._ctx_add_members(layer)
            elif action == act_remove:
                self._ctx_remove_members(layer)
            elif action == act_select:
                self._ctx_select_set(layer)

        elif isinstance(layer, ImageLayer):
            act_change = menu.addAction("Change Image…")
            if menu.exec_(QCursor.pos()) == act_change:
                self._ctx_change_image(layer)

        elif isinstance(layer, SequenceLayer):
            act_change = menu.addAction("Change Sequence…")
            if menu.exec_(QCursor.pos()) == act_change:
                self._ctx_change_sequence(layer)

    def _ctx_add_members(self, layer: CameraLayer):
        sel = get_selection()
        if not sel:
            logger.info("No selection to add")
            return
        add_set_members(layer.object_set, sel)
        logger.info("Added %d node(s) to %s", len(sel), layer.object_set)
        self._auto_rebuild()

    def _ctx_remove_members(self, layer: CameraLayer):
        sel = get_selection()
        if not sel:
            logger.info("No selection to remove")
            return
        remove_set_members(layer.object_set, sel)
        logger.info("Removed %d node(s) from %s", len(sel), layer.object_set)
        self._auto_rebuild()

    def _ctx_select_set(self, layer: CameraLayer):
        if cmds.objExists(layer.object_set):
            cmds.select(layer.object_set, replace=True)

    def _ctx_change_image(self, layer: ImageLayer):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", IMAGE_FILTER)
        if path:
            layer.file_path = path
            layer.name = os.path.basename(path)
            self._sync_list()
            self._auto_rebuild()

    def _ctx_change_sequence(self, layer: SequenceLayer):
        path, _ = QFileDialog.getOpenFileName(self, "Select Sequence File", "", IMAGE_FILTER)
        if not path:
            return
        info = detect_sequence(path)
        if info is None:
            logger.warning("No sequence pattern detected from: %s", path)
            return
        layer.file_pattern = info.file_pattern
        layer.frame_start = info.frame_start
        layer.frame_end = info.frame_end
        layer.name = os.path.basename(info.file_pattern)
        self._sync_list()
        self._auto_rebuild()

    # -- Export / Import ----------------------------------------------------

    _LAYER_FILE_FILTER = "VP Compositor Layers (*.vpcomp.json)"

    def _export_layers(self):
        if len(self._stack) == 0:
            QMessageBox.warning(self, "Export", "No layers to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Layers",
            "",
            self._LAYER_FILE_FILTER,
        )
        if not path:
            return
        try:
            export_stack(self._stack, path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return
        logger.info("Layers exported to %s", path)

    @staticmethod
    def _validate_imported_layers(
        parsed_layers: list,
        warnings: list[str],
    ) -> list:
        """Validate parsed layers against the live Maya scene.

        Returns the list of valid layers. Invalid layers are skipped and
        their issues appended to *warnings*.
        """
        valid: list = []
        for layer in parsed_layers:
            if isinstance(layer, CameraLayer):
                if not cmds.objExists(layer.camera):
                    warnings.append(f"Camera not found: {layer.camera}")
                    continue
                if not cmds.objExists(layer.object_set):
                    try:
                        create_object_set(layer.object_set)
                        logger.info("Auto-created objectSet: %s", layer.object_set)
                    except Exception as exc:
                        warnings.append(f"Failed to create objectSet {layer.object_set}: {exc}")
                        continue
            elif isinstance(layer, ImageLayer):
                if not os.path.isfile(layer.file_path):
                    warnings.append(f"Image not found: {layer.file_path}")
                    continue
            elif isinstance(layer, SequenceLayer):
                found = any(os.path.isfile(layer.file_pattern % f) for f in range(layer.frame_start, layer.frame_end + 1))
                if not found:
                    warnings.append(f"No frames found: {layer.file_pattern}")
                    continue
            valid.append(layer)
        return valid

    def _import_layers(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Layers",
            "",
            f"{self._LAYER_FILE_FILTER};;All Files (*)",
        )
        if not path:
            return

        data, err = import_stack(path)
        if data is None:
            QMessageBox.critical(self, "Import Error", err)
            return

        try:
            parsed_layers, warnings = stack_from_dicts(data)
        except ValueError as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return

        valid_layers = self._validate_imported_layers(parsed_layers, warnings)

        if self._applied_panel:
            self._remove_override()

        self._stack.clear()
        for layer in valid_layers:
            try:
                self._stack.add(layer)
            except (ValueError, RuntimeError) as exc:
                warnings.append(f"Skipped {layer.name}: {exc}")

        self._sync_list()
        self._show_import_report(len(parsed_layers), len(self._stack), warnings)

    def _show_import_report(
        self,
        total: int,
        imported: int,
        warnings: list[str],
    ):
        detail = "\n".join(warnings) if warnings else ""
        if imported == total and not warnings:
            QMessageBox.information(
                self,
                "Import",
                f"Imported {imported} layer(s).",
            )
        elif imported > 0:
            QMessageBox.warning(
                self,
                "Import",
                f"Imported {imported} of {total} layer(s).\n\n{detail}",
            )
        else:
            QMessageBox.warning(
                self,
                "Import",
                f"No valid layers found.\n\n{detail}",
            )

    # -- Playblast ----------------------------------------------------------

    def _open_playblast(self):
        if len(self._stack) == 0:
            logger.warning("No layers to playblast")
            return

        from .playblast_ui import PlayblastWindow

        panel = self._current_panel()
        if not panel:
            logger.warning("No panel selected")
            return
        dlg = PlayblastWindow(self._stack, panel, parent=self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.Window)
        dlg.show()

    def _update_layer_buttons(self) -> None:
        """Enable/disable add/delete buttons based on override state."""
        enabled = self._applied_panel is None
        self._add_cam_btn.setEnabled(enabled)
        self._add_img_btn.setEnabled(enabled)
        self._add_seq_btn.setEnabled(enabled)
        self._del_btn.setEnabled(enabled)

    # -- Override lifecycle -------------------------------------------------

    def _apply_override(self):
        panel = self._current_panel()
        if not panel:
            logger.warning("No panel selected")
            return

        errors = self._stack.validate_all()
        if errors:
            for idx, msgs in errors.items():
                for msg in msgs:
                    logger.warning("Layer %d: %s", idx, msg)
            return

        if len(self._stack) == 0:
            logger.warning("No layers to apply")
            return

        self._remove_override()

        try:
            override = build_override(self._stack, panel=panel)
        except RuntimeError as exc:
            logger.error("Build failed: %s", exc)
            return

        self._override_obj = override
        omr.MRenderer.registerOverride(override)
        cmds.modelEditor(
            panel,
            e=True,
            rendererName=VP2_RENDERER,
            rendererOverrideName=OVERRIDE_NAME,
        )
        self._applied_panel = panel
        self._update_layer_buttons()
        logger.info("Override applied to %s", panel)

    def _remove_override(self):
        if self._applied_panel:
            with contextlib.suppress(Exception):
                cmds.modelEditor(self._applied_panel, e=True, rendererOverrideName="")
            logger.info("Override removed from %s", self._applied_panel)
            self._applied_panel = None
        if self._override_obj:
            with contextlib.suppress(Exception):
                omr.MRenderer.deregisterOverride(self._override_obj)
            self._override_obj = None
        self._update_layer_buttons()

    def _auto_rebuild(self):
        """Re-apply override if Auto Update is checked and override is active."""
        if not self._auto_cb.isChecked():
            return
        if self._applied_panel is None:
            return
        self._apply_override()
        cmds.refresh()

    # -- Cleanup ------------------------------------------------------------

    def closeEvent(self, event):
        self._remove_override()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_instance: VpcompWindow | None = None


def show():
    """Show the VP Compositor window (singleton)."""
    global _instance

    # Close existing instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except Exception:
            pass
        _instance = None

    parent = get_maya_main_window()
    win = VpcompWindow(parent)
    win.setWindowFlags(win.windowFlags() | Qt.Window)
    win.show()
    _instance = win
    return win
