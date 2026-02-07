"""Skin Weights Transfer UI layer."""

from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_skinCluster
from ....lib_ui import BaseMainWindow, error_handler, get_margins, get_maya_main_window, get_spacing, undo_chunk
from ....lib_ui.qt_compat import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
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
        sc_layout.addWidget(self._sc_field, 1)

        sc_set_button = QPushButton("SET")
        sc_set_button.clicked.connect(self._on_set_skin_cluster)
        sc_layout.addWidget(sc_set_button)

        self.central_layout.addLayout(sc_layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # --- Influence Filter ---
        self._inf_filter = QLineEdit()
        self._inf_filter.setPlaceholderText("Filter (space-separated)...")
        self._inf_filter.setClearButtonEnabled(True)
        self._inf_filter.textChanged.connect(self._on_filter_changed)
        self.central_layout.addWidget(self._inf_filter)

        # --- Influence Lists Section ---
        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(spacing)

        # Source (left)
        src_layout = QVBoxLayout()
        src_label = QLabel("Source (from)")
        src_label.setAlignment(Qt.AlignCenter)
        src_layout.addWidget(src_label)

        self._src_list = QListWidget()
        self._src_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        src_layout.addWidget(self._src_list)

        lists_layout.addLayout(src_layout)

        # Target (right)
        tgt_layout = QVBoxLayout()
        tgt_label = QLabel("Target (to)")
        tgt_label.setAlignment(Qt.AlignCenter)
        tgt_layout.addWidget(tgt_label)

        self._tgt_list = QListWidget()
        self._tgt_list.setSelectionMode(QAbstractItemView.SingleSelection)
        tgt_layout.addWidget(self._tgt_list)

        lists_layout.addLayout(tgt_layout)

        self.central_layout.addLayout(lists_layout, 1)

        separator2 = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator2)

        # --- Mode / Amount Section ---
        options_layout = QGridLayout()
        options_layout.setSpacing(int(spacing * 0.5))

        mode_label = QLabel("Mode:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        options_layout.addWidget(mode_label, 0, 0)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Percentage", "Value"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        options_layout.addWidget(self._mode_combo, 0, 1)

        amount_label = QLabel("Amount:", alignment=Qt.AlignRight | Qt.AlignVCenter)
        options_layout.addWidget(amount_label, 1, 0)

        self._amount_widget = FieldSliderWidget(min_value=0, max_value=100, default_value=100, value_type="int")
        options_layout.addWidget(self._amount_widget, 1, 1)

        options_layout.setColumnStretch(1, 1)
        self.central_layout.addLayout(options_layout)

        separator3 = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator3)

        # --- Execute Button ---
        execute_button = QPushButton("Move Weights")
        execute_button.clicked.connect(self._on_execute)
        self.central_layout.addWidget(execute_button)

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
        keywords = text.lower().split()
        for list_widget in (self._src_list, self._tgt_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item_text = item.text().lower()
                hidden = bool(keywords) and not any(kw in item_text for kw in keywords)
                item.setHidden(hidden)

    def _on_mode_changed(self, index: int):
        """Rebuild the amount widget when mode changes.

        Args:
            index (int): ComboBox index (0=Percentage, 1=Value).
        """
        # Remove old widget
        self._amount_widget.setParent(None)
        self._amount_widget.deleteLater()

        # Create new widget based on mode
        if index == 0:  # Percentage
            self._amount_widget = FieldSliderWidget(min_value=0, max_value=100, default_value=100, value_type="int")
        else:  # Value
            self._amount_widget = FieldSliderWidget(min_value=0.0, max_value=1.0, default_value=1.0, decimals=2, value_type="float")

        # Find the grid layout and replace (row 1, col 1)
        grid = self.central_layout.itemAt(self._get_options_layout_index()).layout()
        if grid is not None:
            grid.addWidget(self._amount_widget, 1, 1)

    def _get_options_layout_index(self) -> int:
        """Find the index of the options grid layout within central_layout.

        Returns:
            int: Layout index.
        """
        for i in range(self.central_layout.count()):
            item = self.central_layout.itemAt(i)
            if item.layout() is not None and isinstance(item.layout(), QGridLayout):
                return i
        return -1

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

        # Get mode and amount
        mode = "percentage" if self._mode_combo.currentIndex() == 0 else "value"
        amount = self._amount_widget.value()

        count = command.move_skin_weights(
            skin_cluster=self._skin_cluster,
            src_infs=src_infs,
            tgt_inf=tgt_inf,
            components=components,
            mode=mode,
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
        if "mode" in settings_data:
            mode_index = settings_data["mode"]
            if isinstance(mode_index, int) and 0 <= mode_index <= 1:
                self._mode_combo.setCurrentIndex(mode_index)

        if "amount" in settings_data:
            amount = settings_data["amount"]
            if amount is not None and amount != "":
                try:
                    if self._mode_combo.currentIndex() == 0:
                        self._amount_widget.setValue(int(amount))
                    else:
                        self._amount_widget.setValue(float(amount))
                except (ValueError, TypeError):
                    pass

    def _collect_settings(self) -> dict:
        """Collect current widget settings.

        Returns:
            dict: Current settings data.
        """
        return {
            "mode": self._mode_combo.currentIndex(),
            "amount": self._amount_widget.value(),
        }

    def _save_settings(self):
        """Save current settings."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

    def closeEvent(self, event):
        """Save settings on close."""
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
