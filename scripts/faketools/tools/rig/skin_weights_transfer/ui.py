"""Skin Weights Transfer UI layer."""

import contextlib
from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_skinCluster
from ....lib_ui import BaseMainWindow, error_handler, get_margins, get_maya_main_window, get_spacing, undo_chunk
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import FieldSliderWidget, extra_widgets
from . import command

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Skin Weights Transfer main window."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="SkinWeightsTransferMainWindow",
            window_title="Skin Weights Transfer",
            central_layout="vertical",
        )
        self.settings = ToolSettingsManager(tool_name="skin_weights_transfer", category="rig")
        self._skin_cluster = ""
        self._hilite_nodes = []
        self._affected_infs = None
        self._script_job_id = None
        self._setup_ui()
        self._restore_settings()

    def _setup_ui(self):
        """Build the user interface."""
        spacing = get_spacing(self)
        margins = get_margins(self)
        self.central_layout.setSpacing(spacing)
        self.central_layout.setContentsMargins(*margins)

        # --- SkinCluster Section ---
        sc_layout = QHBoxLayout()
        sc_layout.setSpacing(int(spacing * 0.5))

        sc_label = QLabel("SkinCluster:")
        sc_layout.addWidget(sc_label)

        self._sc_field = QLineEdit()
        self._sc_field.setReadOnly(True)
        self._sc_field.setPlaceholderText("Select a mesh and click SET")
        self._sc_field.setToolTip("The skinCluster node to operate on")
        sc_layout.addWidget(self._sc_field, 1)

        sc_set_button = QPushButton("SET")
        sc_set_button.setToolTip("Set skinCluster from the selected mesh or components")
        sc_set_button.clicked.connect(self._on_set_skin_cluster)
        sc_layout.addWidget(sc_set_button)

        self.central_layout.addLayout(sc_layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # --- Influence Filter ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(int(spacing * 0.5))

        self._inf_filter = QLineEdit()
        self._inf_filter.setPlaceholderText("Filter (space-separated)...")
        self._inf_filter.setClearButtonEnabled(True)
        self._inf_filter.setToolTip("Filter influences by name (space-separated keywords, OR logic)")
        self._inf_filter.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._inf_filter, 1)

        self._affected_checkbox = QCheckBox("Affected Only")
        self._affected_checkbox.setToolTip("Show only influences with non-zero weights on selected components")
        self._affected_checkbox.toggled.connect(self._on_affected_toggled)
        filter_layout.addWidget(self._affected_checkbox)

        self.central_layout.addLayout(filter_layout)

        # --- Influence Lists Section ---
        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(spacing)

        # Source (left)
        src_layout = QVBoxLayout()
        src_layout.setSpacing(int(spacing * 0.25))
        self._src_label = QLabel("Source (from)")
        self._src_label.setAlignment(Qt.AlignCenter)
        src_layout.addWidget(self._src_label)

        self._src_list = QListWidget()
        self._src_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._src_list.setToolTip("Multi-select: Ctrl+click / Shift+click")
        self._src_list.itemSelectionChanged.connect(self._on_influence_selection_changed)
        src_layout.addWidget(self._src_list)

        lists_layout.addLayout(src_layout)

        # Target (right)
        tgt_layout = QVBoxLayout()
        tgt_layout.setSpacing(int(spacing * 0.25))
        self._tgt_label = QLabel("Target (to)")
        self._tgt_label.setAlignment(Qt.AlignCenter)
        tgt_layout.addWidget(self._tgt_label)

        self._tgt_list = QListWidget()
        self._tgt_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tgt_list.setToolTip("Single-select: click to choose target influence")
        self._tgt_list.itemSelectionChanged.connect(self._on_influence_selection_changed)
        tgt_layout.addWidget(self._tgt_list)

        lists_layout.addLayout(tgt_layout)

        self.central_layout.addLayout(lists_layout, 1)

        # --- Amount + Execute Row ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(int(spacing * 0.5))

        amount_label = QLabel("Amount:")
        bottom_layout.addWidget(amount_label)

        self._amount_widget = FieldSliderWidget(min_value=0, max_value=100, default_value=100, value_type="int")
        self._amount_widget.setToolTip("Percentage of weight to transfer (0-100%)")
        bottom_layout.addWidget(self._amount_widget, 1)

        execute_button = QPushButton("Move Weights")
        execute_button.setToolTip("Transfer weights from source to target influences on selected components")
        execute_button.clicked.connect(self._on_execute)
        bottom_layout.addWidget(execute_button)

        self.central_layout.addLayout(bottom_layout)

        # --- ScriptJob ---
        self._script_job_id = cmds.scriptJob(event=["SelectionChanged", self._on_selection_changed])

    # --- Slots ---

    @error_handler
    def _on_set_skin_cluster(self):
        """Set skinCluster from the currently selected mesh or components."""
        sel = cmds.ls(selection=True, objectsOnly=True)
        if not sel:
            cmds.warning("Select a mesh or components to set the skinCluster.")
            return

        node = sel[0]
        if "deformableShape" in (cmds.nodeType(node, inherited=True) or []):
            # Component selection: objectsOnly returns the shape directly
            shape = node
        else:
            # Transform selection: get the shape from the transform
            shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                cmds.warning(f"No shape found under: {node}")
                return
            shape = shapes[0]

        sc = lib_skinCluster.get_skinCluster(shape)
        if not sc:
            cmds.warning(f"No skinCluster found on: {node}")
            return

        self._skin_cluster = sc
        self._sc_field.setText(sc)
        self._populate_influence_lists()

    def _populate_influence_lists(self):
        """Populate both influence lists from the current skinCluster."""
        self._src_list.clear()
        self._tgt_list.clear()

        if not self._skin_cluster:
            return

        infs = lib_skinCluster.get_influences_from_skinCluster([self._skin_cluster])
        for inf in infs:
            self._src_list.addItem(inf)
            self._tgt_list.addItem(inf)

        self._inf_filter.clear()

    def _on_filter_changed(self, text: str):
        """Filter both influence lists by text (case-insensitive).

        Args:
            text (str): Filter text.
        """
        self._apply_filters()

    def _on_selection_changed(self):
        """Handle Maya selection change for affected-only filtering."""
        if not self._affected_checkbox.isChecked():
            return
        self._update_affected_influences()
        self._apply_filters()

    def _on_affected_toggled(self, checked: bool):
        """Handle affected-only checkbox toggle.

        Args:
            checked (bool): Checkbox state.
        """
        if checked:
            self._update_affected_influences()
        else:
            self._affected_infs = None
        self._apply_filters()

    def _update_affected_influences(self):
        """Query affected influences from the current component selection."""
        if not self._skin_cluster or not cmds.objExists(self._skin_cluster):
            self._affected_infs = None
            return

        components = cmds.filterExpand(selectionMask=[28, 31, 46]) or []
        if not components:
            self._affected_infs = None
            return

        affected = command.get_affected_influences(
            skin_cluster=self._skin_cluster,
            components=components,
        )
        self._affected_infs = set(affected)

    def _apply_filters(self):
        """Apply combined text and affected-only filters to both lists."""
        keywords = self._inf_filter.text().lower().split()
        use_affected = self._affected_checkbox.isChecked() and self._affected_infs is not None

        for list_widget in (self._src_list, self._tgt_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item_text = item.text()

                text_hidden = bool(keywords) and not any(kw in item_text.lower() for kw in keywords)
                affected_hidden = use_affected and item_text not in self._affected_infs

                item.setHidden(text_hidden or affected_hidden)

    def _on_influence_selection_changed(self):
        """Highlight the chosen influences in Maya viewport using cmds.hilite."""
        # Update selection count labels
        src_count = len(self._src_list.selectedItems())
        tgt_count = len(self._tgt_list.selectedItems())
        self._src_label.setText(f"Source (from) [{src_count}]" if src_count else "Source (from)")
        self._tgt_label.setText(f"Target (to) [{tgt_count}]" if tgt_count else "Target (to)")

        # Unhighlight previous
        if self._hilite_nodes:
            cmds.hilite(self._hilite_nodes, u=True)
            self._hilite_nodes = []

        # Collect selected influences from both lists
        infs = set()
        for item in self._src_list.selectedItems():
            infs.add(item.text())
        for item in self._tgt_list.selectedItems():
            infs.add(item.text())

        existing = [inf for inf in infs if cmds.objExists(inf)]
        if existing:
            cmds.hilite(existing)
            self._hilite_nodes = existing

    @error_handler
    @undo_chunk("Skin Weights Transfer: Move Weights")
    def _on_execute(self):
        """Execute the weight transfer."""
        # Validate skinCluster
        if not self._skin_cluster or not cmds.objExists(self._skin_cluster):
            cmds.warning("Set a valid skinCluster first.")
            return

        # Validate source selection
        src_items = self._src_list.selectedItems()
        if not src_items:
            cmds.warning("Select at least one source influence.")
            return

        # Validate target selection
        tgt_items = self._tgt_list.selectedItems()
        if not tgt_items:
            cmds.warning("Select a target influence.")
            return

        src_infs = [item.text() for item in src_items]
        tgt_inf = tgt_items[0].text()

        # Check source != target
        if len(src_infs) == 1 and src_infs[0] == tgt_inf:
            cmds.warning("Source and target must be different.")
            return

        # Get selected components
        components = cmds.filterExpand(selectionMask=[28, 31, 46]) or []
        if not components:
            cmds.warning("Select vertices, CVs, or lattice points.")
            return

        # Validate components belong to the skinCluster's geometry
        comp_shapes = list(set(cmds.ls(components, objectsOnly=True)))
        sc_geos = cmds.skinCluster(self._skin_cluster, query=True, geometry=True) or []
        for shape in comp_shapes:
            if shape not in sc_geos:
                cmds.warning(f"Selected components do not belong to the skinCluster's geometry: {shape}")
                return

        amount = self._amount_widget.value()

        count = command.move_skin_weights(
            skin_cluster=self._skin_cluster,
            src_infs=src_infs,
            tgt_inf=tgt_inf,
            components=components,
            amount=float(amount),
        )

        logger.info(f"Transferred weights on {count} components")

    # --- Settings ---

    def _restore_settings(self):
        """Restore saved settings."""
        settings_data = self.settings.load_settings("default")
        if not settings_data:
            return
        self._apply_settings(settings_data)

    def _apply_settings(self, settings_data: dict):
        """Apply settings data to widgets.

        Args:
            settings_data (dict): Settings to apply.
        """
        if "amount" in settings_data:
            amount = settings_data["amount"]
            if amount is not None and amount != "":
                with contextlib.suppress(ValueError, TypeError):
                    self._amount_widget.setValue(int(amount))
        if "affected_only" in settings_data:
            self._affected_checkbox.setChecked(bool(settings_data["affected_only"]))

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Current settings data.
        """
        return {
            "amount": self._amount_widget.value(),
            "affected_only": self._affected_checkbox.isChecked(),
        }

    def _save_settings(self):
        """Save current settings."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def closeEvent(self, event):
        """Save settings, kill scriptJob, and clear hilite on close."""
        if self._script_job_id is not None:
            with contextlib.suppress(RuntimeError):
                cmds.scriptJob(kill=self._script_job_id, force=True)
            self._script_job_id = None
        if self._hilite_nodes:
            cmds.hilite(self._hilite_nodes, u=True)
            self._hilite_nodes = []
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the Skin Weights Transfer window."""
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
