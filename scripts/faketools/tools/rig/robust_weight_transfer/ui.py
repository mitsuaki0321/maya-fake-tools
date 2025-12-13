"""Robust Weight Transfer UI layer.

This module provides the user interface for the Robust Weight Transfer tool.
Based on the SIGGRAPH Asia 2023 paper "Robust Skin Weights Transfer via Weight Inpainting".
"""

import logging
from typing import Optional

import maya.cmds as cmds

from ....lib_ui import (
    BaseMainWindow,
    PresetMenuManager,
    ToolSettingsManager,
    error_handler,
    get_maya_main_window,
    get_spacing,
    undo_chunk,
)
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QColor,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from . import command
from .widgets import (
    DeformOptionsSection,
    SeamAveragingSection,
    SettingsSection,
    SmoothingSection,
)

logger = logging.getLogger(__name__)

_instance = None


class TargetItem:
    """Class to hold target mesh/vertex information."""

    def __init__(self, mesh_name: str, vertex_indices: Optional[set[int]] = None):
        """Initialize target item.

        Args:
            mesh_name: Mesh node name.
            vertex_indices: Set of vertex indices. None means all vertices.
        """
        self.mesh_name = mesh_name
        self.vertex_indices = vertex_indices  # None = all vertices

    @property
    def is_partial(self) -> bool:
        """Whether this is a partial vertex selection."""
        return self.vertex_indices is not None

    @property
    def vertex_count(self) -> int:
        """Get vertex count."""
        if self.vertex_indices is not None:
            return len(self.vertex_indices)
        else:
            return command.get_mesh_vertex_count(self.mesh_name)

    def get_display_text(self) -> str:
        """Get text for list display."""
        if self.is_partial:
            return f"{self.mesh_name} [{len(self.vertex_indices)} vtx]"
        else:
            return f"{self.mesh_name} ({self.vertex_count} verts)"

    def select_in_maya(self) -> None:
        """Select this target in Maya viewport."""
        if self.is_partial:
            vtx_list = [f"{self.mesh_name}.vtx[{i}]" for i in sorted(self.vertex_indices)]
            cmds.select(vtx_list, replace=True)
        else:
            cmds.select(self.mesh_name, replace=True)

    def merge_vertices(self, other_indices: set[int]) -> None:
        """Merge additional vertex indices.

        Args:
            other_indices: Set of vertex indices to merge.
        """
        if self.vertex_indices is None:
            # Already all vertices, do nothing
            return
        self.vertex_indices = self.vertex_indices | other_indices

    def set_all_vertices(self) -> None:
        """Set to all vertices (remove partial selection)."""
        self.vertex_indices = None


class MainWindow(BaseMainWindow):
    """Robust Weight Transfer main UI window."""

    WINDOW_TITLE = "Robust Weight Transfer"
    WINDOW_NAME = "robustWeightTransferMainWindow"

    # Default values for settings
    DEFAULT_SETTINGS = {
        "distance_ratio": 0.05,
        "angle_degrees": 30.0,
        "flip_normals": False,
        "use_kdtree": False,
        "use_deformed_source": False,
        "use_deformed_target": False,
        "enable_smoothing": True,
        "smooth_iterations": 10,
        "smooth_alpha": 0.2,
        "seam_average": False,
        "seam_internal": True,
        "seam_tolerance": 0.0001,
    }

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent: Parent widget.
        """
        super().__init__(
            parent=parent,
            object_name=self.WINDOW_NAME,
            window_title=self.WINDOW_TITLE,
            central_layout="vertical",
        )

        # Target list data
        self._targets: dict[str, TargetItem] = {}

        # Match status data
        self._matched_indices: dict[str, list] = {}
        self._unmatched_indices: dict[str, list] = {}

        # Settings managers
        self.settings = ToolSettingsManager("robust_weight_transfer", "rig")

        self._setup_ui()
        self._connect_signals()

        # Setup preset menu
        self.preset_manager = PresetMenuManager(
            window=self,
            settings_manager=self.settings,
            collect_callback=self._collect_settings,
            apply_callback=self._apply_settings,
        )
        self.preset_manager.add_menu()

        # Restore settings
        self._restore_settings()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        spacing = get_spacing(self, direction="vertical")

        # === Source ===
        self._setup_source_section(spacing)

        # === Targets ===
        self._setup_targets_section(spacing)

        # === Settings ===
        self.settings_section = SettingsSection(self.DEFAULT_SETTINGS)
        self.central_layout.addWidget(self.settings_section)

        # === Deform Options ===
        self.deform_section = DeformOptionsSection(self.DEFAULT_SETTINGS)
        self.central_layout.addWidget(self.deform_section)

        # === Smoothing ===
        self.smoothing_section = SmoothingSection(self.DEFAULT_SETTINGS)
        self.central_layout.addWidget(self.smoothing_section)

        # === Seam Averaging ===
        self.seam_section = SeamAveragingSection(self.DEFAULT_SETTINGS)
        self.central_layout.addWidget(self.seam_section)

        # === Status ===
        self._setup_status_section(spacing)

        # === Action Buttons ===
        self._setup_action_buttons(spacing)

    def _setup_source_section(self, spacing: int) -> None:
        """Setup source mesh section.

        Args:
            spacing: Layout spacing value.
        """
        source_group = QGroupBox("Source")
        source_layout = QHBoxLayout(source_group)
        source_layout.setSpacing(spacing)

        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setPlaceholderText("Select skinned mesh...")
        source_layout.addWidget(self.source_edit)

        self.source_btn = QPushButton("Set")
        source_layout.addWidget(self.source_btn)

        self.central_layout.addWidget(source_group)

    def _setup_targets_section(self, spacing: int) -> None:
        """Setup targets list section.

        Args:
            spacing: Layout spacing value.
        """
        targets_group = QGroupBox("Targets")
        targets_layout = QVBoxLayout(targets_group)
        targets_layout.setSpacing(spacing)

        # Target list
        self.target_list = QListWidget()
        self.target_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        targets_layout.addWidget(self.target_list)

        # Target buttons
        target_btn_layout = QHBoxLayout()
        target_btn_layout.setSpacing(spacing)

        self.add_target_btn = QPushButton("Add Selected")
        self.add_target_btn.setToolTip("Add selected mesh(es) or vertices to targets")
        target_btn_layout.addWidget(self.add_target_btn)

        self.remove_target_btn = QPushButton("Remove")
        self.remove_target_btn.setToolTip("Remove selected items from list")
        target_btn_layout.addWidget(self.remove_target_btn)

        self.clear_targets_btn = QPushButton("Clear")
        self.clear_targets_btn.setToolTip("Clear all targets")
        target_btn_layout.addWidget(self.clear_targets_btn)

        self.select_target_btn = QPushButton("Select")
        self.select_target_btn.setToolTip("Select target in Maya viewport")
        target_btn_layout.addWidget(self.select_target_btn)

        targets_layout.addLayout(target_btn_layout)

        # Stretch factor 1 to make targets list expand when window is resized
        self.central_layout.addWidget(targets_group, 1)

    def _setup_status_section(self, spacing: int) -> None:
        """Setup status display section.

        Args:
            spacing: Layout spacing value.
        """
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(spacing)

        status_layout.addWidget(QLabel("Matched:"))
        self.matched_label = QLabel("0 (0%)")
        self.matched_label.setStyleSheet("font-weight: bold; color: green;")
        status_layout.addWidget(self.matched_label)

        status_layout.addWidget(QLabel("Unmatched:"))
        self.unmatched_label = QLabel("0 (0%)")
        self.unmatched_label.setStyleSheet("font-weight: bold; color: orange;")
        status_layout.addWidget(self.unmatched_label)

        status_layout.addStretch()

        self.central_layout.addWidget(status_group)

    def _setup_action_buttons(self, spacing: int) -> None:
        """Setup action buttons section.

        Args:
            spacing: Layout spacing value.
        """
        button_layout = QHBoxLayout()
        button_layout.setSpacing(spacing)

        self.search_btn = QPushButton("Search")
        self.search_btn.setToolTip("Find matching vertices")
        button_layout.addWidget(self.search_btn)

        self.select_btn = QPushButton("Select Unmatched")
        self.select_btn.setToolTip("Select unmatched vertices in viewport")
        button_layout.addWidget(self.select_btn)

        self.transfer_btn = QPushButton("Transfer")
        self.transfer_btn.setToolTip("Transfer and inpaint weights")
        self.transfer_btn.setStyleSheet("background-color: #4a7c4e; font-weight: bold;")
        button_layout.addWidget(self.transfer_btn)

        self.central_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.central_layout.addWidget(self.progress_bar)

    def _connect_signals(self) -> None:
        """Connect UI signals to slots."""
        self.source_btn.clicked.connect(self._on_set_source)
        self.add_target_btn.clicked.connect(self._on_add_targets)
        self.remove_target_btn.clicked.connect(self._on_remove_targets)
        self.clear_targets_btn.clicked.connect(self._on_clear_targets)
        self.select_target_btn.clicked.connect(self._on_select_targets)
        self.search_btn.clicked.connect(self._on_search)
        self.select_btn.clicked.connect(self._on_select_unmatched)
        self.transfer_btn.clicked.connect(self._on_transfer)

    def _collect_settings(self) -> dict:
        """Collect current UI settings for preset save.

        Returns:
            Dictionary of settings values.
        """
        settings = {}
        settings.update(self.settings_section.collect_settings())
        settings.update(self.deform_section.collect_settings())
        settings.update(self.smoothing_section.collect_settings())
        settings.update(self.seam_section.collect_settings())
        return settings

    def _apply_settings(self, settings_data: dict) -> None:
        """Apply settings from preset to UI.

        Args:
            settings_data: Dictionary of settings values.
        """
        self.settings_section.apply_settings(settings_data)
        self.deform_section.apply_settings(settings_data)
        self.smoothing_section.apply_settings(settings_data)
        self.seam_section.apply_settings(settings_data)

    def _restore_settings(self) -> None:
        """Restore settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)

    def _save_settings(self) -> None:
        """Save current settings to default preset."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def showEvent(self, event):
        """Handle window show event."""
        super().showEvent(event)
        # Set minimum height on first show
        if not event.spontaneous():
            self.resize(self.width(), self.minimumSizeHint().height())

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)

    def _reset_status(self) -> None:
        """Reset status display."""
        self._matched_indices = {}
        self._unmatched_indices = {}
        self.matched_label.setText("0 (0%)")
        self.unmatched_label.setText("0 (0%)")

    def _update_status(self, matched_count: int, unmatched_count: int) -> None:
        """Update status display with vertex counts.

        Args:
            matched_count: Number of matched vertices.
            unmatched_count: Number of unmatched vertices.
        """
        total = matched_count + unmatched_count
        if total > 0:
            matched_pct = matched_count / total * 100
            unmatched_pct = unmatched_count / total * 100
        else:
            matched_pct = 0
            unmatched_pct = 0

        self.matched_label.setText(f"{matched_count} ({matched_pct:.1f}%)")
        self.unmatched_label.setText(f"{unmatched_count} ({unmatched_pct:.1f}%)")

    def _update_target_list(self) -> None:
        """Update target list UI from internal data."""
        self.target_list.clear()

        for mesh_name, target in self._targets.items():
            item = QListWidgetItem(target.get_display_text())
            item.setData(Qt.UserRole, mesh_name)

            # Different color for partial selection
            if target.is_partial:
                item.setForeground(QColor("#5599ff"))

            self.target_list.addItem(item)

    @error_handler
    def _on_set_source(self) -> None:
        """Set source mesh from Maya selection."""
        selection = cmds.ls(selection=True, objectsOnly=True)
        if not selection:
            cmds.warning("Nothing selected")
            return

        mesh = selection[0]

        # Validate source mesh
        is_valid, error_msg = command.validate_source_mesh(mesh)
        if not is_valid:
            cmds.warning(error_msg)
            return

        self.source_edit.setText(mesh)
        self._reset_status()

    @error_handler
    def _on_add_targets(self) -> None:
        """Add Maya selection to target list."""
        parsed = command.parse_selection()

        if not parsed:
            cmds.warning("No valid mesh or vertices selected")
            return

        source = self.source_edit.text()

        for mesh_name, vertex_indices in parsed.items():
            # Don't add same mesh as source
            if mesh_name == source:
                cmds.warning(f"Skipping {mesh_name}: same as source")
                continue

            # Validate target
            is_valid, error_msg = command.validate_target_mesh(mesh_name, source)
            if not is_valid:
                cmds.warning(error_msg)
                continue

            if mesh_name in self._targets:
                # Update existing entry
                existing = self._targets[mesh_name]
                if vertex_indices is None:
                    # Overwrite to all vertices
                    existing.set_all_vertices()
                elif existing.vertex_indices is not None:
                    # Merge vertices
                    existing.merge_vertices(vertex_indices)
                # If already all vertices, do nothing
            else:
                # Add new
                self._targets[mesh_name] = TargetItem(mesh_name, vertex_indices)

        self._update_target_list()
        self._reset_status()

    @error_handler
    def _on_remove_targets(self) -> None:
        """Remove selected targets from list."""
        selected_items = self.target_list.selectedItems()

        if not selected_items:
            cmds.warning("No target selected in list")
            return

        for item in selected_items:
            mesh_name = item.data(Qt.UserRole)
            if mesh_name in self._targets:
                del self._targets[mesh_name]

        self._update_target_list()
        self._reset_status()

    @error_handler
    def _on_clear_targets(self) -> None:
        """Clear all targets from list."""
        self._targets.clear()
        self._update_target_list()
        self._reset_status()

    @error_handler
    def _on_select_targets(self) -> None:
        """Select targets in Maya viewport."""
        selected_items = self.target_list.selectedItems()

        if not selected_items:
            cmds.warning("No target selected in list")
            return

        cmds.select(clear=True)

        for item in selected_items:
            mesh_name = item.data(Qt.UserRole)
            if mesh_name in self._targets:
                self._targets[mesh_name].select_in_maya()
                # For multiple selection, add to selection
                if len(selected_items) > 1:
                    cmds.select(cmds.ls(selection=True), add=True)

    @error_handler
    def _on_search(self) -> None:
        """Execute search for matching vertices."""
        source = self.source_edit.text()

        if not source:
            cmds.warning("Please set source mesh")
            return

        if not self._targets:
            cmds.warning("Please add target mesh(es)")
            return

        settings = self._collect_settings()
        self._matched_indices = {}
        self._unmatched_indices = {}

        total_matched = 0
        total_unmatched = 0

        for mesh_name, target in self._targets.items():
            # Get vertex indices for partial selection
            vertex_indices = sorted(target.vertex_indices) if target.is_partial else None

            matched, unmatched = command.search_matches(
                source_mesh=source,
                target_mesh=mesh_name,
                vertex_indices=vertex_indices,
                distance_ratio=settings["distance_ratio"],
                angle_degrees=settings["angle_degrees"],
                flip_normals=settings["flip_normals"],
                use_kdtree=settings["use_kdtree"],
                use_deformed_source=settings["use_deformed_source"],
                use_deformed_target=settings["use_deformed_target"],
            )

            self._matched_indices[mesh_name] = matched
            self._unmatched_indices[mesh_name] = unmatched

            total_matched += len(matched)
            total_unmatched += len(unmatched)

        self._update_status(total_matched, total_unmatched)

        total = total_matched + total_unmatched
        unmatched_pct = total_unmatched / total * 100 if total > 0 else 0
        cmds.inViewMessage(
            amg=f"Found {total_matched} matched, {total_unmatched} unmatched ({unmatched_pct:.1f}%)",
            pos="topCenter",
            fade=True,
        )

    @error_handler
    def _on_select_unmatched(self) -> None:
        """Select unmatched vertices in Maya viewport."""
        if not self._unmatched_indices:
            cmds.warning("No unmatched vertices. Run Search first.")
            return

        cmds.select(clear=True)

        total_count = 0
        for mesh_name, indices in self._unmatched_indices.items():
            if indices:
                total_count += command.select_vertices(mesh_name, indices)

        cmds.inViewMessage(
            amg=f"Selected {total_count} unmatched vertices",
            pos="topCenter",
            fade=True,
        )

    @error_handler
    @undo_chunk("Robust Weight Transfer")
    def _on_transfer(self) -> None:
        """Execute weight transfer."""
        source = self.source_edit.text()

        if not source:
            cmds.warning("Please set source mesh")
            return

        if not self._targets:
            cmds.warning("Please add target mesh(es)")
            return

        settings = self._collect_settings()

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        total_targets = len(self._targets)
        total_matched = 0
        total_unmatched = 0
        total_verts = 0

        try:
            from ....lib_ui.qt_compat import QApplication

            for idx, (mesh_name, target) in enumerate(self._targets.items()):

                def progress_callback(message: str, percent: int, idx=idx, mesh_name=mesh_name) -> None:
                    # Calculate overall progress
                    overall = int((idx / total_targets + percent / 100 / total_targets) * 100)
                    self.progress_bar.setValue(overall)
                    self.progress_bar.setFormat(f"{mesh_name}: {message} ({overall}%)")
                    QApplication.processEvents()

                # Get vertex indices (for partial selection)
                vertex_indices = sorted(target.vertex_indices) if target.is_partial else None

                result = command.transfer_weights(
                    source_mesh=source,
                    target_mesh=mesh_name,
                    vertex_indices=vertex_indices,
                    distance_ratio=settings["distance_ratio"],
                    angle_degrees=settings["angle_degrees"],
                    flip_normals=settings["flip_normals"],
                    use_kdtree=settings["use_kdtree"],
                    use_deformed_source=settings["use_deformed_source"],
                    use_deformed_target=settings["use_deformed_target"],
                    enable_smoothing=settings["enable_smoothing"],
                    smooth_iterations=settings["smooth_iterations"],
                    smooth_alpha=settings["smooth_alpha"],
                    progress_callback=progress_callback,
                )

                total_matched += result["matched_count"]
                total_unmatched += result["unmatched_count"]
                total_verts += result["total_vertices"]

            # Seam averaging post-process
            seam_message = ""
            # Run seam averaging if enabled and either:
            # - Multiple targets (cross-mesh seams)
            # - Internal seams enabled (single mesh seams)
            if settings["seam_average"] and (len(self._targets) >= 2 or settings["seam_internal"]):
                from ....lib_ui.qt_compat import QApplication

                self.progress_bar.setFormat("Averaging seam weights...")
                self.progress_bar.setValue(95)
                QApplication.processEvents()

                seam_result = command.average_seam_weights(
                    meshes=list(self._targets.keys()),
                    position_tolerance=settings["seam_tolerance"],
                    include_internal_seams=settings["seam_internal"],
                )

                if seam_result["success"] and seam_result["seam_groups"] > 0:
                    seam_message = f", {seam_result['vertices_averaged']} seam verts averaged"

            self._update_status(total_matched, total_unmatched)

            unmatched_pct = total_unmatched / total_verts * 100 if total_verts > 0 else 0
            cmds.inViewMessage(
                amg=f"Transfer complete: {total_matched}/{total_verts} matched ({unmatched_pct:.1f}% inpainted){seam_message}",
                pos="topCenter",
                fade=True,
            )

        finally:
            self.progress_bar.setVisible(False)


def show_ui():
    """Show the tool UI (entry point).

    Returns:
        MainWindow: The window instance.
    """
    global _instance

    # Close existing instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    # Create new instance
    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
