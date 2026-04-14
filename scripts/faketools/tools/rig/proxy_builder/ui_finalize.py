"""Proxy Builder — Finalize tab (Step 3)."""

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
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ....lib_ui.ui_utils import get_relative_size
from ....lib_ui.widgets.extra_widgets import HorizontalSeparator
from . import finalize_command
from .ui_common import SceneNodeListWidget

logger = getLogger(__name__)


class FinalizeTab(QWidget):
    """Finalize tab widget for combining proxy pieces."""

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

        # --- Source Group ---
        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Source Group:"))
        self._line_finalize_group = QLineEdit("proxy_grp")
        row_src.addWidget(self._line_finalize_group, 1)
        self._btn_set_finalize_group = QPushButton("Set")
        row_src.addWidget(self._btn_set_finalize_group)
        self._btn_load_finalize_groups = QPushButton("Load")
        row_src.addWidget(self._btn_load_finalize_groups)

        # Match Set / Load button widths to each other
        src_btn_width = max(
            self._btn_set_finalize_group.sizeHint().width(),
            self._btn_load_finalize_groups.sizeHint().width(),
        )
        self._btn_set_finalize_group.setFixedWidth(src_btn_width)
        self._btn_load_finalize_groups.setFixedWidth(src_btn_width)

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

        layout.addWidget(HorizontalSeparator())

        # --- Finalize button ---
        self._btn_finalize = QPushButton("Finalize")
        _, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
        self._btn_finalize.setMinimumHeight(int(height * 0.08))
        layout.addWidget(self._btn_finalize)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._btn_set_finalize_group.clicked.connect(self._on_set_finalize_group)
        self._btn_load_finalize_groups.clicked.connect(self._on_load_finalize_groups)
        self._btn_finalize.clicked.connect(self._on_finalize)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_set_finalize_group(self) -> None:
        """Set the source group from Maya selection."""
        sel = cmds.ls(selection=True, type="transform")
        if not sel:
            cmds.warning("Proxy Builder: Select a group transform")
            return
        self._line_finalize_group.setText(sel[0])

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
    # Settings
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "finalize_group": self._line_finalize_group.text(),
            "finalize_output": self._line_finalize_output.text(),
            "combine_mode": "per_shader" if self._btn_group_combine.checkedId() == 1 else "single",
        }

    def _apply_settings(self, data: dict) -> None:
        self._line_finalize_group.setText(data.get("finalize_group", "proxy_grp"))
        self._line_finalize_output.setText(data.get("finalize_output", "proxy_final_grp"))

        combine_mode = data.get("combine_mode", "single")
        if combine_mode == "per_shader":
            self._radio_per_shader.setChecked(True)
        else:
            self._radio_single.setChecked(True)
