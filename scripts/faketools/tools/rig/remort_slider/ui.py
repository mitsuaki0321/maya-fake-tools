"""
Remote attribute slider tool UI layer.
"""

from functools import partial

import maya.cmds as cmds

from ....lib_ui import maya_qt, maya_ui
from ....lib_ui.tool_settings import ToolSettingsManager
from . import command


class RemoteSliderWindow:
    """Remote attribute slider window.

    Limitations:
        - World Relative mode only supports single translate or rotate attributes.
    """

    control_attrs = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ"]
    control_reset_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    preset_values = [0.0, 0.1, 0.5, 1.0, 2.0, 3.0, 30, 45, 90, 120, 140, 160, 180]

    def __init__(self):
        """RemoteSliderWindow class initializer."""
        self.settings = ToolSettingsManager(tool_name="remort_slider", category="rig")

        # UI Names
        self.title = "Remote Float Attr"
        self.window = self.ui_name("window")
        self.node_list = self.ui_name("nodeList")
        self.slider = self.ui_name("slider")
        self.min_field = self.ui_name("minField")
        self.default_field = self.ui_name("defaultField")
        self.max_field = self.ui_name("maxField")
        self.attr_list = self.ui_name("attrList")
        self.mode = self.ui_name("mode")
        self.local_absolute_radio_btn = self.ui_name("localAbsoluteRadioBtn")
        self.local_relative_radio_btn = self.ui_name("localRelativeRadioBtn")
        self.world_relative_radio_btn = self.ui_name("worldRelativeRadioBtn")

        # slider value
        self.node_values = command.DagNodeValues(self.control_attrs)
        self.prev_value = 0.0
        self.validate_ok = False
        self.on_value_changed = False

    def _save_setting(self, key: str, value):
        """Save a single setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        settings_data = self.settings.load_settings("default")
        settings_data[key] = value
        self.settings.save_settings(settings_data, "default")

    def ui_name(self, name) -> str:
        """Get the UI name.

        Args:
            name: UI name.

        Returns:
            UI name.
        """
        return f"{__name__.replace('.', '_')}_{name}"

    def show_ui(self) -> str:
        """Create and show the UI window.

        Returns:
            Window name.
        """
        # Window
        win = self.window
        if cmds.window(win, exists=True):
            cmds.deleteUI(win)

        win = cmds.window(win, title=self.title, mb=True)

        # Menu
        cmds.menu(l="Edit")
        cmds.menuItem(l="Update Reset Values", c=self.update_reset_values)

        cmds.menuItem(l="Mode", divider=True)
        cmds.radioMenuItemCollection()
        cmds.menuItem(self.local_absolute_radio_btn, l="Local Absolute", rb=False, c=self.change_mode)
        cmds.menuItem(self.local_relative_radio_btn, l="Local Relative", rb=True, c=self.change_mode)
        cmds.menuItem(self.world_relative_radio_btn, l="World Relative", rb=False, c=self.change_mode)

        # Main Widgets
        main_layout = cmds.formLayout()

        # Node List
        node_list = cmds.textScrollList(self.node_list, ams=True)

        # Buttons
        minus_button = cmds.button(l="- Step", c=partial(self.step_value, -1.0))
        reset_button = cmds.button(l="Reset", c=self.reset_value)
        plus_button = cmds.button(l="+ Step", c=partial(self.step_value, 1.0))

        # Slider
        slider = cmds.floatSliderGrp(self.slider, v=0.0, min=-90.0, max=90.0, dc=self.change_slider_value, cc=self.changed_slider_value)

        # Min, Default, Max Fields
        min_field = cmds.floatField(self.min_field, v=-90.0, pre=2, cc=self.set_min_value)
        default_field = cmds.floatField(self.default_field, v=0.0, pre=2, cc=self.change_field_value)
        max_field = cmds.floatField(self.max_field, v=90.0, pre=2, cc=self.set_max_value)

        # Attr List
        attr_list = cmds.textScrollList(self.ui_name("attrList"), ams=True, a=self.control_attrs, sii=1, h=130)

        # Popup Menus
        cmds.popupMenu(mm=True, p=self.node_list)
        cmds.menuItem(l="Set Items", rp="N", c=self.set_items)
        cmds.menuItem(l="Remove Items", rp="W", c=self.remove_items)
        cmds.menuItem(l="Select All Items", rp="E", c=self.select_all_items)
        cmds.menuItem(l="Select Nodes", rp="S", c=self.select_nodes)

        # Layout positioning using formLayout
        cmds.formLayout(
            main_layout,
            edit=True,
            attachForm=[
                (node_list, "top", 5),
                (node_list, "left", 5),
                (node_list, "right", 5),
                (slider, "left", 5),
                (slider, "right", 5),
                (attr_list, "left", 5),
                (attr_list, "right", 5),
                (attr_list, "bottom", 5),
            ],
            attachControl=[
                (node_list, "bottom", 5, minus_button),
                (minus_button, "bottom", 5, slider),
                (reset_button, "bottom", 5, slider),
                (plus_button, "bottom", 5, slider),
                (slider, "bottom", 5, min_field),
                (min_field, "bottom", 5, attr_list),
                (max_field, "bottom", 5, attr_list),
                (default_field, "bottom", 5, attr_list),
            ],
            attachPosition=[
                # Buttons configuration
                (minus_button, "left", 5, 0),
                (minus_button, "right", 0, 33),
                (reset_button, "left", 0, 33),
                (reset_button, "right", 0, 66),
                (plus_button, "left", 0, 66),
                (plus_button, "right", 5, 100),
                # Fields configuration
                (min_field, "left", 5, 0),
                (min_field, "right", 0, 33),
                (default_field, "left", 0, 33),
                (default_field, "right", 0, 66),
                (max_field, "left", 0, 66),
                (max_field, "right", 5, 100),
            ],
        )

        # Pop-up menus for min and max fields
        for i, field in zip([-1.0, 1.0], [self.min_field, self.max_field]):
            pop = cmds.popupMenu(p=field)
            for val in self.preset_values:
                cmds.menuItem(l=str(val), c=partial(self.set_preset_value, field, val * i), p=pop)

        # Initialize UI values
        self.initialize_ui()

        # Show Window
        cmds.showWindow()

        return win

    def initialize_ui(self):
        """Initialize the UI values from the option settings."""
        # Load settings
        settings_data = self.settings.load_settings("default")

        # Get option settings with defaults
        mode_settings = settings_data.get("mode", [True, False, False])
        local_relative, local_absolute, world_relative = mode_settings
        min_value = settings_data.get("min_value", -90.0)
        max_value = settings_data.get("max_value", 90.0)
        saved_nodes = settings_data.get("node_list", [])

        # Settings initial values
        cmds.menuItem(self.local_absolute_radio_btn, e=True, rb=local_relative)
        cmds.menuItem(self.local_relative_radio_btn, e=True, rb=local_absolute)
        cmds.menuItem(self.world_relative_radio_btn, e=True, rb=world_relative)

        cmds.floatField(self.min_field, e=True, v=min_value)
        cmds.floatField(self.max_field, e=True, v=max_value)

        # Set slider value
        cmds.floatSliderGrp(self.slider, e=True, min=min_value, max=max_value)

        # Set initial nodes
        initial_nodes = []
        for node in saved_nodes:
            try:
                self.node_values.add_node(node)
                initial_nodes.append(node)
            except Exception as e:
                cmds.warning(str(e))

        if initial_nodes:
            cmds.textScrollList(self.node_list, e=True, a=initial_nodes, sii=1)

    def change_mode(self, *args):
        """Change mode.

        Notes:
            - In World Relative mode, only a single attribute is supported.
        """
        selected_attrs = self._get_attribute_items()

        mode = self._get_mode()
        if mode == "world_relative":
            cmds.textScrollList(self.attr_list, e=True, ams=False)

            if selected_attrs:
                cmds.textScrollList(self.attr_list, e=True, si=selected_attrs[0])
        else:
            cmds.textScrollList(self.attr_list, e=True, ams=True)

            if selected_attrs:
                cmds.textScrollList(self.attr_list, e=True, si=selected_attrs)

        # Save the option settings
        self._save_setting(
            "mode",
            [
                cmds.menuItem(self.local_absolute_radio_btn, q=True, rb=True),
                cmds.menuItem(self.local_relative_radio_btn, q=True, rb=True),
                cmds.menuItem(self.world_relative_radio_btn, q=True, rb=True),
            ],
        )

    def set_items(self, *args):
        """Set items."""
        # Set select items
        sel_nodes = cmds.ls(sl=True, type="transform")
        if not sel_nodes:
            cmds.warning("Please select any dagNodes.")
            return

        current_nodes = cmds.textScrollList(self.node_list, q=True, ai=True) or []
        for node in sel_nodes:
            if node in current_nodes:
                continue

            cmds.textScrollList(self.node_list, e=True, a=node)

            # Add node values for reset
            self.node_values.add_node(node)

        # Save the option settings
        self._save_setting("node_list", self._get_node_items(selected=False))

    def remove_items(self, *args):
        """Remove items."""
        # Remove selected items
        selected_nodes = self._get_node_items(selected=True)
        if not selected_nodes:
            cmds.warning("No items selected on node list.")
            return

        cmds.textScrollList(self.node_list, e=True, ri=selected_nodes)

        # Remove node values for reset
        for node in selected_nodes:
            self.node_values.remove_node(node)

        # Save the option settings
        self._save_setting("node_list", self._get_node_items(selected=False))

    def select_all_items(self, *args):
        """Select all node items."""
        items = self._get_node_items(selected=False)
        if items:
            cmds.textScrollList(self.node_list, e=True, si=items)

    def select_nodes(self, *args):
        """Select maya nodes."""
        selected_nodes = self._get_nodes(selected=True)
        if selected_nodes:
            cmds.select(selected_nodes, r=True)
        else:
            cmds.warning("No nodes to select.")

    def change_slider_value(self, value):
        """Change slider value.

        Args:
            value: Value from the slider.
        """
        # Change default field value
        cmds.floatField(self.default_field, e=True, v=value)

        # Get target elements
        node_attributes = self._get_node_attributes()
        if not node_attributes:
            self.prev_value = value
            return

        # Get mode
        mode = self._get_mode()

        # Validate attributes
        if not self.validate_ok:
            if not command.validate_attributes(mode, node_attributes):
                self.prev_value = value
                return

            self.validate_ok = True

        # Change value
        if not self.on_value_changed:
            cmds.undoInfo(openChunk=True)
            self.on_value_changed = True

        self._change_value(value, mode, node_attributes)

        self.prev_value = value

    def changed_slider_value(self, value):
        """This function is called when the slider value is changed.

        Args:
            value: Value from the slider.
        """
        if self.on_value_changed:
            cmds.undoInfo(closeChunk=True)
            self.on_value_changed = False

        self.prev_value = value

    def change_field_value(self, value):
        """Change field value.

        Args:
            value: Value from the field.
        """
        # Change slider value
        cmds.floatSliderGrp(self.ui_name("slider"), e=True, v=value)

        # Get target elements
        node_attributes = self._get_node_attributes()
        if not node_attributes:
            self.prev_value = value
            return

        # Get mode
        mode = self._get_mode()

        # Validate attributes
        if not command.validate_attributes(mode, node_attributes):
            self.prev_value = value
            return

        # Change value
        self._change_value(value, mode, node_attributes)

        self.prev_value = value

    def _change_value(self, value: float, mode: str, node_attributes: list[str]):
        """Change value by calling command layer functions.

        Args:
            value: Value.
            mode: Operation mode.
            node_attributes: Node attributes list.
        """
        if mode == "local_relative":
            diff_value = value - self.prev_value
            command.change_value_local_relative(node_attributes, diff_value)

        elif mode == "local_absolute":
            command.change_value_local_absolute(node_attributes, value)

        elif mode == "world_relative":
            attr = self._get_attribute_items()[0]
            nodes = self._get_nodes(selected=True)
            diff_value = value - self.prev_value
            command.change_value_world_relative(nodes, attr, diff_value)

    def set_min_value(self, *args):
        """Set min value."""
        min_val = cmds.floatField(self.min_field, q=True, v=True)
        max_val = cmds.floatField(self.max_field, q=True, v=True)

        if max_val <= min_val:
            cmds.warning("Min value must be less than max value.")
            return

        cmds.floatSliderGrp(self.ui_name("slider"), e=True, min=min_val)

        # Save the option settings
        self._save_setting("min_value", min_val)

    def set_max_value(self, *args):
        """Set max value."""
        min_val = cmds.floatField(self.min_field, q=True, v=True)
        max_val = cmds.floatField(self.max_field, q=True, v=True)

        if max_val <= min_val:
            cmds.warning("Max value must be greater than min value.")
            return

        cmds.floatSliderGrp(self.ui_name("slider"), e=True, max=max_val)

        # Save the option settings
        self._save_setting("max_value", max_val)

    def reset_value(self, *args):
        """Reset value."""
        connect_elements = self._get_node_attributes()
        if not connect_elements:
            cmds.error("Failed to connect to node attribute.Check details in the script editor.")

        mode = self._get_mode()

        # Update node values
        # Check all nodes first as non-existent nodes may be added later
        if mode in ["local_relative", "world_relative"]:
            nodes = self._get_nodes(selected=True)
            for node in nodes:
                if not self.node_values.has_node(node):
                    self.node_values.add_node(node)

        absolute_only_scale = False
        if mode == "local_relative":
            absolute_only_scale = command.reset_value_local_relative(connect_elements, self.node_values)

        elif mode == "local_absolute":
            absolute_only_scale = command.reset_value_local_absolute(connect_elements, self.control_attrs, self.control_reset_values)

        elif mode == "world_relative":
            attr = self._get_attribute_items()[0]
            absolute_only_scale = command.reset_value_world_relative(connect_elements, attr, self.node_values)

        # Update slider and default field value
        if absolute_only_scale:
            cmds.floatSliderGrp(self.ui_name("slider"), e=True, v=1.0)
            cmds.floatField(self.default_field, e=True, v=1.0)
            self.prev_value = 1.0
        else:
            cmds.floatSliderGrp(self.ui_name("slider"), e=True, v=0.0)
            cmds.floatField(self.default_field, e=True, v=0.0)
            self.prev_value = 0.0

    def update_reset_values(self, *args):
        """Update reset values."""
        selected_nodes = self._get_nodes(selected=False)
        if not selected_nodes:
            cmds.warning("No nodes in node list.")
            return

        for node in selected_nodes:
            self.node_values.update_node(node)

    def step_value(self, step_value, *args):
        """Set value.

        Args:
            step_value: Value.
        """
        # Get target elements
        node_attributes = self._get_node_attributes()
        if not node_attributes:
            return

        # Get mode
        mode = self._get_mode()

        # Validate attributes
        if not command.validate_attributes(mode, node_attributes):
            return

        # Get step value
        mods = maya_ui.get_modifiers()
        if "Shift" in mods:
            step_value *= 10
        if "Ctrl" in mods:
            step_value /= 10

        # Change value
        if mode == "local_relative":
            command.step_value_local_relative(node_attributes, step_value)

        elif mode == "local_absolute":
            current_slider_value = cmds.floatSliderGrp(self.ui_name("slider"), q=True, v=True)
            command.step_value_local_absolute(node_attributes, current_slider_value, step_value)

        elif mode == "world_relative":
            attribute = self._get_attribute_items()[0]
            nodes = self._get_nodes(selected=True)
            command.step_value_world_relative(nodes, attribute, step_value)

        # Update slider and default field value
        slider_value = cmds.floatSliderGrp(self.ui_name("slider"), q=True, v=True) + step_value
        cmds.floatSliderGrp(self.ui_name("slider"), e=True, v=slider_value)
        cmds.floatField(self.default_field, e=True, v=slider_value)

        self.prev_value = slider_value

    def set_preset_value(self, field, value, *args):
        """Set preset value for min and max fields.

        Args:
            field: Field name.
            value: Value.
        """
        if field == self.min_field:
            cmds.floatField(self.min_field, e=True, v=value)
            self.set_min_value()
        elif field == self.max_field:
            cmds.floatField(self.max_field, e=True, v=value)
            self.set_max_value()

    def _get_nodes(self, selected: bool = True) -> list[str]:
        """Get nodes from the node list.

        Args:
            selected: Get selected nodes. Defaults to True.

        Returns:
            Nodes.
        """
        nodes = self._get_node_items(selected=selected)

        if not nodes:
            return []

        result_nodes = []
        for item in nodes:
            if cmds.objExists(item):
                result_nodes.append(item)
            else:
                cmds.warning(f"Node does not exist: {item}")

        return result_nodes

    def _get_node_items(self, selected: bool = True) -> list[str]:
        """Get node items.

        Args:
            selected: Get selected nodes. Defaults to True.

        Returns:
            Nodes.
        """
        if selected:
            nodes = cmds.textScrollList(self.node_list, q=True, si=True) or []
        else:
            nodes = cmds.textScrollList(self.node_list, q=True, ai=True) or []

        return nodes

    def _get_attribute_items(self, selected: bool = True) -> list[str]:
        """Get attribute items.

        Args:
            selected: Get selected attributes. Defaults to True.

        Returns:
            Attributes.
        """
        if selected:
            attrs = cmds.textScrollList(self.attr_list, q=True, si=True) or []
        else:
            attrs = cmds.textScrollList(self.attr_list, q=True, ai=True) or []

        return attrs

    def _get_node_attributes(self) -> list[str]:
        """Get connect to node attributes from the this tool.

        Returns:
            Connect node attributes.
        """
        selected_nodes = self._get_nodes(selected=True)
        if not selected_nodes:
            cmds.warning("No nodes selected in node list.")
            return []

        selected_attrs = self._get_attribute_items() or []
        if not selected_attrs:
            cmds.warning("No attributes selected in attribute list.")
            return []

        connect_node_attrs = []
        for node in selected_nodes:
            for attr in selected_attrs:
                connect_node_attrs.append(f"{node}.{attr}")

        return connect_node_attrs

    def _get_mode(self) -> str:
        """Get the mode.

        Returns:
            Mode.
        """
        if cmds.menuItem(self.local_absolute_radio_btn, q=True, rb=True):
            return "local_absolute"
        elif cmds.menuItem(self.local_relative_radio_btn, q=True, rb=True):
            return "local_relative"
        elif cmds.menuItem(self.world_relative_radio_btn, q=True, rb=True):
            return "world_relative"


def show_ui():
    """Show the UI."""
    remote_slider = RemoteSliderWindow()
    win = remote_slider.show_ui()

    # Resize window to fit the minimum size
    qt_win = maya_qt.qt_widget_from_maya_window(win)
    minimum_size_hint = qt_win.minimumSizeHint()
    cmds.window(win, e=True, w=minimum_size_hint.width(), h=minimum_size_hint.height())
