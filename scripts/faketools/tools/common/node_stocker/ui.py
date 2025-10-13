"""
Node Stocker Tool.
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_name
from ....lib_ui import maya_decorator, maya_qt, maya_ui, tool_data
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.qt_compat import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QStatusBar, QStyle, Qt, QTabWidget, QVBoxLayout, QWidget
from ....lib_ui.tool_settings import ToolSettingsManager
from ....lib_ui.widgets import extra_widgets
from .button import NodeStockPushButton
from .command import NodeStockFile, NodeStorage
from .widgets import NameReplaceField, NameSpaceBox, StockAreaSwitchButtons, ToolBar

logger = getLogger(__name__)

_instance = None


class MainWindow(BaseMainWindow):
    """Node Stocker Main Window."""

    _stock_file_name = "node"

    def __init__(self, parent=None, object_name="MainWindow", window_title="Main Window", num_areas=7, **kwargs):
        """Constructor.

        Args:
            parent (QWidget): The parent widget.
            object_name (str): The object name.
            window_title (str): The window title.
            num_areas (int): The number of areas (tabs).

        Keyword Args:
            button_size (int): The size of the buttons.
        """
        super().__init__(parent=parent, object_name=object_name, window_title=window_title)

        self.button_size = kwargs.get("button_size", 20)
        num_buttons = 10  # Fixed: 10 buttons per tab
        self.button_grids = []  # Store button references for each tab

        tool_data_manager = tool_data.ToolDataManager("node_stocker", "common")
        tool_data_manager.ensure_data_dir()
        self.node_storage = NodeStorage(tool_data_manager.get_data_dir())
        self.settings = ToolSettingsManager(tool_name="node_stocker", category="common")

        self._current_scene_data = {}

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Stock area switch buttons
        self.switch_buttons = StockAreaSwitchButtons(num_buttons=num_areas)
        self.switch_buttons.set_index(0)
        layout.addWidget(self.switch_buttons)

        # Tool bar
        self.tool_bar = ToolBar()
        layout.addWidget(self.tool_bar)

        self.central_layout.addLayout(layout)

        # Tab Widget (hidden tabs)
        self.tab_widget = QTabWidget()
        self.tab_widget.tabBar().hide()  # Hide tab bar
        self.central_layout.addWidget(self.tab_widget, stretch=1)

        # Create tabs and buttons
        self._create_tabs(num_areas=num_areas, num_buttons=num_buttons)
        self._load_scene_data(0)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # Options
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.name_space_box = NameSpaceBox()
        layout.addWidget(self.name_space_box)

        self.name_replace_field = NameReplaceField()
        layout.addWidget(self.name_replace_field)

        self.central_layout.addLayout(layout)

        separator = extra_widgets.HorizontalSeparator()
        self.central_layout.addWidget(separator)

        # Status bar
        layout = QHBoxLayout()

        # In Maya, the status bar gets destroyed at some point, so this is a workaround
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("QStatusBar::item { border: none; }")
        self.status_bar.setSizeGripEnabled(False)
        layout.addWidget(self.status_bar)

        self.node_length_label = QLabel(f"{self._get_node_length_label(0)}   ")
        self.node_length_label.setFixedWidth(self.node_length_label.sizeHint().width())
        self.status_separator = extra_widgets.VerticalSeparator()
        self.node_names_label = QLabel()

        self.status_bar.addWidget(self.node_length_label)
        self.status_bar.addWidget(self.status_separator)
        self.status_bar.addWidget(self.node_names_label)

        self.central_layout.addLayout(layout)

        # Signals & Slots
        self.switch_buttons.button_selection_changed.connect(self._switch_tab)
        self.tool_bar.refresh_button_clicked.connect(self._refresh_window)

        # For updating the status bar
        style = self.status_bar.style()
        margin = style.pixelMetric(QStyle.PM_LayoutLeftMargin, None, self.status_bar)
        padding = style.pixelMetric(QStyle.PM_LayoutHorizontalSpacing, None, self.status_bar)
        self.font_metrics = self.node_names_label.fontMetrics()
        self.status_bar_spacing = self.node_length_label.width() + self.status_separator.width() + margin + padding

        # Restore settings
        self._restore_settings()

        # Initial window size
        minimum_size = self.minimumSizeHint()
        self.resize(minimum_size.width(), minimum_size.height())

    def _collect_settings(self) -> dict:
        """Collect current UI settings (excluding window geometry).

        Returns:
            dict: Settings data
        """
        return {
            "name_space_enabled": self.name_space_box.is_enabled(),
            "name_replace_enabled": self.name_replace_field.is_enabled(),
            "search_replace": self.name_replace_field.get_search_replace_text(),
            "name_replace_switched": self.name_replace_field.is_switched(),
            "name_replace_re": self.name_replace_field.is_re(),
        }

    def _apply_settings(self, settings_data: dict):
        """Apply settings to UI (excluding window geometry).

        Args:
            settings_data (dict): Settings data to apply
        """
        if "name_space_enabled" in settings_data:
            self.name_space_box.set_enabled(settings_data["name_space_enabled"])
        if "name_replace_enabled" in settings_data:
            self.name_replace_field.set_enabled(settings_data["name_replace_enabled"])
        if "search_replace" in settings_data:
            self.name_replace_field.set_search_replace_text(*settings_data["search_replace"])
        else:
            self.name_replace_field.set_search_replace_text("", "")
        if "name_replace_switched" in settings_data:
            self.name_replace_field.set_switched(settings_data["name_replace_switched"])
        if "name_replace_re" in settings_data:
            self.name_replace_field.set_re(settings_data["name_replace_re"])

    def _switch_tab(self, index: int) -> None:
        """Switch to the specified tab.

        Args:
            index (int): The index of the tab.
        """
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
            self._load_scene_data(index)

    def _create_tabs(self, num_areas: int, num_buttons: int) -> None:
        """Create tabs with button grids.

        Args:
            num_areas (int): Number of tabs.
            num_buttons (int): Number of buttons per tab (fixed at 10).
        """
        for area_index in range(num_areas):
            # Create tab widget with background color
            tab = QWidget()
            tab.setStyleSheet("QWidget { background-color: #2b2b2b; }")
            grid_layout = QGridLayout()
            grid_layout.setSpacing(5)
            grid_layout.setContentsMargins(5, 5, 5, 5)
            tab.setLayout(grid_layout)

            # Create buttons for this tab (2x5 grid)
            buttons = []
            for i in range(num_buttons):
                row = i // 5  # 5 columns
                col = i % 5
                key = str(i)
                label = str(i)

                button = NodeStockPushButton(key, label, tab)
                button.setMinimumSize(self.button_size, self.button_size)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                # Setup PieMenu for middle click (2-way: Register/Unregister)
                button.setup_pie_menu(
                    items=[
                        {"label": "Register", "callback": lambda b=button: self._add_nodes(b)},
                        {"label": "Unregister", "callback": lambda b=button: self._remove_nodes(b)},
                    ],
                    trigger_button=Qt.MouseButton.MiddleButton,
                )

                # Setup PieMenu for right click (4-way: SetKeyframe and future commands)
                button.setup_pie_menu(
                    items=[
                        {"label": "Set Keyframe", "callback": lambda b=button: self._set_keyframe(b)},
                        None,  # Right - empty for future
                        None,  # Down - empty for future
                        None,  # Left - empty for future
                    ],
                    trigger_button=Qt.MouseButton.RightButton,
                )

                # Connect left click for selection
                button.clicked.connect(lambda checked=False, b=button: self._select_nodes(b))

                # Connect hover events
                button.hovered.connect(self.__update_status_bar)
                button.unhovered.connect(self._clear_status_bar)

                grid_layout.addWidget(button, row, col)
                buttons.append(button)

            # Set stretch factors for rows and columns to make buttons expand
            for row_idx in range(2):  # 2 rows
                grid_layout.setRowStretch(row_idx, 1)
            for col_idx in range(5):  # 5 columns
                grid_layout.setColumnStretch(col_idx, 1)

            # Add tab to widget
            self.tab_widget.addTab(tab, f"Area {area_index}")

            # Store buttons for data loading
            self.button_grids.append(buttons)

        logger.debug(f"Created {num_areas} tabs with {num_buttons} buttons each")

    def _load_scene_data(self, index: int) -> None:
        """Load the data for the specified tab.

        Args:
            index (int): The index of the tab.
        """
        if not (0 <= index < len(self.button_grids)):
            return

        scene_file_name = self._get_file_prefix(index)
        storage_file = self.node_storage.get_file(scene_file_name)
        self._current_scene_data = storage_file.get_data()

        # Update button colors based on data
        for button in self.button_grids[index]:
            if button.key in self._current_scene_data and self._current_scene_data[button.key]:
                button.apply_stoked_color()
            else:
                button.reset_stoked_color()

        logger.debug(f"Loaded scene data: {scene_file_name}")

    def _get_file_prefix(self, index: int) -> str:
        """Make the file prefix."""
        return f"{self._stock_file_name}_{index}"

    def _get_node_stock_file(self, button: NodeStockPushButton) -> NodeStockFile:
        """Get the node stock file from the button.

        Args:
            button (NodeStockPushButton): The button.

        Returns:
            NodeStockFile: The node stock file.
        """
        if not isinstance(button, NodeStockPushButton):
            raise TypeError("Button must be an instance of NodeStockPushButton.")

        # Get current tab index
        grid_index = self.tab_widget.currentIndex()
        name = self._get_file_prefix(grid_index)

        return self.node_storage.get_file(name)

    def _refresh_window(self) -> None:
        """Refresh the window."""
        current_index = self.tab_widget.currentIndex()
        self._load_scene_data(current_index)
        self.name_space_box.refresh_name_spaces()

    @staticmethod
    def _get_node_length_label(node_count: int) -> str:
        """Get the node length label.

        Args:
            node_count (int): The number of nodes.

        Returns:
            str: The node length label.
        """
        return f"Nodes: {node_count}"

    def __update_status_bar(self, button: NodeStockPushButton) -> None:
        """Update the status bar with the button's information.

        Args:
            button (NodeStockPushButton): The button.
        """
        nodes = self._current_scene_data.get(button.key, [])
        if not nodes:
            self.node_length_label.setText(self._get_node_length_label(0))
            self.node_names_label.clear()
            return

        node_count = len(nodes)
        node_names = " ".join(nodes)
        max_width = self.status_bar.width() - self.status_bar_spacing - 5
        elided_text = self.font_metrics.elidedText(node_names, Qt.ElideRight, max_width)
        self.node_length_label.setText(self._get_node_length_label(node_count))
        self.node_names_label.setText(elided_text)

    def _clear_status_bar(self) -> None:
        """Clear the status bar."""
        self.node_length_label.setText(self._get_node_length_label(0))
        self.node_names_label.clear()

    def _select_nodes_with_modifier(self, nodes: list[str]) -> None:
        """Select the nodes in the scene.

        Args:
            nodes (list[str]): The nodes to select.
        """
        # Get the replace and name space settings.
        nodes = self._replace_node_names(nodes, echo_error=True)
        nodes = self._name_space_with_nodes(nodes)

        # Validate the nodes.
        not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
        if not_exists_nodes:
            cmds.error(f"No existing nodes to select: {not_exists_nodes}")

        # Select the nodes.
        sel_nodes = cmds.ls(sl=True)
        mod_keys = maya_ui.get_modifiers()
        if not mod_keys:
            cmds.select(nodes, r=True)
            logger.debug(f"Selected new nodes: {nodes}")
        elif mod_keys == ["Shift", "Ctrl"] or "Shift" in mod_keys:
            cmds.select(sel_nodes, r=True)
            cmds.select(nodes, add=True)
            logger.debug(f"Add selected new nodes: {nodes}")
        elif "Ctrl" in mod_keys:
            cmds.select(sel_nodes, r=True)
            cmds.select(nodes, d=True)
            logger.debug(f"Deselect selected new nodes: {nodes}")

    def _replace_node_names(self, nodes: list[str], echo_error: bool = False) -> list[str]:
        """Replace the node names.

        Args:
            nodes (list[str]): The nodes.
            echo_error (bool): If True, output an error.

        Returns:
            list[str]: The replaced nodes.
        """
        if not self.name_replace_field.is_enabled():
            logger.debug("Not enabled name replace field.")
            return nodes

        search_text, replace_text = self.name_replace_field.get_search_replace_text()
        if search_text or replace_text:
            if self.name_replace_field.is_switched():
                search_text, replace_text = replace_text, search_text

            if self.name_replace_field.is_re():
                nodes = lib_name.substitute_names(nodes, search_text, replace_text)
            else:
                if not search_text:
                    if echo_error:
                        cmds.error("Search text is required when not in regular expression mode.")

                    logger.debug("Search text is required when not in regular expression mode.")
                else:
                    nodes = [node.replace(search_text, replace_text) for node in nodes]

            return nodes
        else:
            logger.debug("No search and replace text.")
            return nodes

    def _name_space_with_nodes(self, nodes: list[str]) -> list[str]:
        """Get the name space with the nodes.

        Args:
            nodes (list[str]): The nodes.

        Returns:
            list[str]: The name space with the nodes.
        """
        if not self.name_space_box.is_enabled():
            logger.debug("No name space.")
            return nodes

        name_space = self.name_space_box.get_name_space()
        nodes = lib_name.replace_namespaces(nodes, name_space)

        logger.debug(f"Name spaced nodes: {nodes}")

        return nodes

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Select Nodes")
    def _select_nodes(self, button: NodeStockPushButton) -> None:
        """Select the nodes when the button is clicked."""
        nodes = self._current_scene_data.get(button.key, [])
        if not nodes:
            return

        self._select_nodes_with_modifier(nodes)

        logger.debug(f"Selected nodes: {nodes}")

    @maya_decorator.error_handler
    def _add_nodes(self, button: NodeStockPushButton) -> None:
        """Add the nodes to nodeStorage (called from PieMenu)."""
        sel_nodes = cmds.ls(sl=True)
        if not sel_nodes:
            cmds.warning("No nodes selected.")
            return

        # Add the nodes to the storage file.
        node_stock_file = self._get_node_stock_file(button)
        node_stock_file.add_nodes(button.key, sel_nodes, overwrite=True)

        # Update the current scene data.
        self._current_scene_data[button.key] = sel_nodes

        # Change the button color.
        button.apply_stoked_color()

        logger.debug(f"Added nodes: {sel_nodes}")

    @maya_decorator.error_handler
    def _remove_nodes(self, button: NodeStockPushButton) -> None:
        """Remove the nodes from nodeStorage (called from PieMenu)."""
        # Remove the nodes from the storage file.
        node_stock_file = self._get_node_stock_file(button)
        nodes = node_stock_file.get_nodes(button.key)
        if not nodes:
            logger.debug("No nodes registered to the button.")
            return

        node_stock_file.remove_nodes(button.key)

        # Update the current scene data.
        self._current_scene_data.pop(button.key, None)

        # Change the button color.
        button.reset_stoked_color()

        logger.debug(f"Removed nodes: {nodes}")

    @maya_decorator.error_handler
    @maya_decorator.undo_chunk("Set Keyframe")
    def _set_keyframe(self, button: NodeStockPushButton) -> None:
        """Set keyframe on registered nodes (called from PieMenu).

        Args:
            button (NodeStockPushButton): The button.
        """
        nodes = self._current_scene_data.get(button.key, [])
        if not nodes:
            cmds.warning("No nodes registered to this button.")
            return

        # Apply name replace and namespace processing
        nodes = self._replace_node_names(nodes, echo_error=True)
        nodes = self._name_space_with_nodes(nodes)

        # Validate nodes exist
        not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
        if not_exists_nodes:
            cmds.error(f"No existing nodes to set keyframe: {not_exists_nodes}")

        # Set keyframe on all nodes
        for node in nodes:
            try:
                cmds.setKeyframe(node)
            except Exception as e:
                logger.warning(f"Failed to set keyframe on {node}: {e}")

        cmds.inViewMessage(amg=f"Set keyframe on <hl>{len(nodes)}</hl> nodes", pos="topCenter", fade=True)
        logger.info(f"Set keyframe on nodes: {nodes}")

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        settings_data = self.settings.load_settings("default")
        if settings_data:
            self._apply_settings(settings_data)
        else:
            # Apply default values
            self._apply_settings({})

        logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to preferences."""
        settings_data = self._collect_settings()
        self.settings.save_settings(settings_data, "default")

        logger.debug("UI settings saved")

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """
    Show the Node Stocker UI.

    Creates or raises the main window.

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

    parent = maya_qt.get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
