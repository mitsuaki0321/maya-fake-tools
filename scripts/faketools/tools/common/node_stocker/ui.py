"""
Node Stocker Tool.
"""

from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_name
from ....lib_ui import maya_decorator, maya_qt, maya_ui, tool_data
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QHBoxLayout, QLabel, QStatusBar, QStyle, Qt, QVBoxLayout
from ....lib_ui.widgets import extra_widgets
from . import nodeStock_view
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
            num_areas (int): The number of areas.

        Keyword Args:
            rows (int): The number of button rows.
            cols (int): The number of button columns.
            button_size (int): The size of the buttons.
        """
        super().__init__(parent=parent, object_name=object_name, window_title=window_title)

        rows = kwargs.get("rows", 2)
        cols = kwargs.get("cols", 7)
        button_size = kwargs.get("button_size", 50)

        tool_data_manager = tool_data.ToolDataManager("node_stocker", "common")
        tool_data_manager.ensure_data_dir()
        self.node_storage = NodeStorage(tool_data_manager.get_data_dir())
        self.settings = ToolOptionSettings(__name__)

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

        # Stock area
        self.scenes = [nodeStock_view.NodeStockGraphicsScene() for _ in range(num_areas)]
        self.view = nodeStock_view.NodeStockGraphicsView(self.scenes[0], self)
        self.central_layout.addWidget(self.view, stretch=1)

        self._create_button_grid(rows=rows, cols=cols, button_size=button_size, spacing=5)
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
        self.switch_buttons.button_selection_changed.connect(self._switch_scene)
        self.tool_bar.refresh_button_clicked.connect(self._refresh_window)
        self.view.rubber_band_selection.connect(self._select_nodes_rubber_band)

        # For updating the status bar
        style = self.status_bar.style()
        margin = style.pixelMetric(QStyle.PM_LayoutLeftMargin, None, self.status_bar)
        padding = style.pixelMetric(QStyle.PM_LayoutHorizontalSpacing, None, self.status_bar)
        self.font_metrics = self.node_names_label.fontMetrics()
        self.status_bar_spacing = self.node_length_label.width() + self.status_separator.width() + margin + padding

        # Restore settings
        self._restore_settings()

    def _switch_scene(self, index: int) -> None:
        """Switch the scene in the graphic widget.

        Args:
            index (int): The index of the scene.
        """
        if 0 <= index < len(self.scenes):
            self.view.setScene(self.scenes[index])
            self.view.setAlignment(Qt.AlignCenter)
            self._load_scene_data(index)

    def _create_button_grid(self, rows, cols, button_size, spacing) -> None:
        """Create a grid of buttons in each scene.

        Args:
            rows (int): The number of rows.
            cols (int): The number of columns.
            button_size (int): The size of the buttons.
            spacing (int): The spacing between buttons.
        """
        margin = spacing
        offset = spacing / 2

        for scene in self.scenes:
            total_width = cols * (button_size + spacing) - spacing + margin * 2
            total_height = rows * (button_size + spacing) - spacing + margin * 2
            scene.setSceneRect(0, 0, total_width, total_height)

            for row in range(rows):
                for col in range(cols):
                    x = margin + col * (button_size + spacing) + offset
                    y = margin + row * (button_size + spacing)
                    button = nodeStock_view.NodeStockButton(f"{row}_{col}", x, y, button_size, label=str(row * cols + col))
                    button.left_button_clicked.connect(self._select_nodes)
                    button.middle_button_clicked.connect(self._add_nodes)
                    button.right_button_clicked.connect(self._remove_nodes)
                    button.hovered.connect(self.__update_status_bar)
                    button.unhovered.connect(self._clear_status_bar)
                    scene.addItem(button)

            self.view.setSceneRect(scene.sceneRect())

        logger.debug(f"Created button grid: {rows}x{cols}")

    def _load_scene_data(self, index: int) -> None:
        """Load the data for the specified scene.

        Args:
            index (int): The index of the scene.
        """
        scene_file_name = self._get_file_prefix(index)
        storage_file = self.node_storage.get_file(scene_file_name)
        self._current_scene_data = storage_file.get_data()
        scene = self.scenes[index]
        for button in scene.list_buttons():
            if button.key in self._current_scene_data and self._current_scene_data[button.key]:
                button.apply_stoked_color()
            else:
                button.reset_stoked_color()

        logger.debug(f"Loaded scene data: {scene_file_name}")

    def _get_file_prefix(self, index: int) -> str:
        """Make the file prefix."""
        return f"{self._stock_file_name}_{index}"

    def _get_node_stock_file(self, button: nodeStock_view.NodeStockButton) -> NodeStockFile:
        """Get the node stock file from the button.

        Args:
            button (nodeStock_view.NodeStockButton): The button.

        Returns:
            node_storage.NodeStockFile: The node stock file.
        """
        if not isinstance(button, nodeStock_view.NodeStockButton):
            return TypeError("Button must be an instance of NodeStockButton.")

        scene_index = self.scenes.index(button.scene())
        name = self._get_file_prefix(scene_index)

        return self.node_storage.get_file(name)

    def _refresh_window(self) -> None:
        """Refresh the window."""
        self._load_scene_data(self.switch_buttons.button_group.checkedId())
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

    def __update_status_bar(self, button: nodeStock_view.NodeStockButton) -> None:
        """Update the status bar with the button's information.

        Args:
            button (nodeStock_view.NodeStockButton): The button.
        """
        self.current_button = button
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

    @maya_decorator.undo_chunk("Select Nodes")
    @maya_decorator.error_handler
    def _select_nodes(self, button: nodeStock_view.NodeStockButton) -> None:
        """Select the nodes when the left button is clicked."""
        nodes = self._current_scene_data.get(button.key, [])
        if not nodes:
            return

        self._select_nodes_with_modifier(nodes)

        logger.debug(f"Selected nodes: {nodes}")

    @maya_decorator.undo_chunk("Select Nodes by Rubber Band")
    @maya_decorator.error_handler
    def _select_nodes_rubber_band(self, buttons: list[nodeStock_view.NodeStockButton]) -> None:
        """Select the nodes when the rubber band selection is made."""
        if not buttons:
            logger.debug("No buttons to select.")
            return

        nodes = []
        for button in buttons:
            nodes.extend(self._current_scene_data.get(button.key, []))

        if not nodes:
            logger.debug("No nodes to select.")
            return

        self._select_nodes_with_modifier(nodes)

        logger.debug(f"Selected nodes by rubber band: {nodes}")

    @maya_decorator.error_handler
    def _add_nodes(self, button: nodeStock_view.NodeStockButton) -> None:
        """Add the nodes to nodeStorage when the middle button is clicked."""
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
    def _remove_nodes(self, button: nodeStock_view.NodeStockButton) -> None:
        """Remove the nodes from nodeStorage when the right button is clicked."""
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

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        # Restore window geometry
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])
        else:
            # Default size if no saved geometry
            minimum_size = self.minimumSizeHint()
            width = minimum_size.width() * 1.1
            height = minimum_size.height()
            self.resize(width, height)

        # Restore widget settings
        self.name_space_box.set_enabled(self.settings.read("name_space_enabled", False))
        self.name_replace_field.set_enabled(self.settings.read("name_replace_enabled", False))
        self.name_replace_field.set_search_replace_text(*self.settings.read("search_replace", ("", "")))
        self.name_replace_field.set_switched(self.settings.read("name_replace_switched", False))
        self.name_replace_field.set_re(self.settings.read("name_replace_re", False))

        logger.debug("UI settings restored")

    def _save_settings(self):
        """Save UI settings to preferences."""
        # Save window geometry
        self.settings.set_window_geometry(size=[self.width(), self.height()], position=[self.x(), self.y()])

        # Save widget settings
        self.settings.write("name_space_enabled", self.name_space_box.is_enabled())
        self.settings.write("name_replace_enabled", self.name_replace_field.is_enabled())
        self.settings.write("search_replace", self.name_replace_field.get_search_replace_text())
        self.settings.write("name_replace_switched", self.name_replace_field.is_switched())
        self.settings.write("name_replace_re", self.name_replace_field.is_re())

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
