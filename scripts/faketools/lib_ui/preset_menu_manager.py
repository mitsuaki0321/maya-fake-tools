"""
Preset menu manager for tool windows.

Provides preset menu functionality using composition pattern instead of inheritance.
Handles preset saving, loading, editing, and menu updates with RuntimeError protection.

Example:
    >>> class MainWindow(BaseMainWindow):
    ...     def __init__(self, parent=None):
    ...         super().__init__(...)
    ...         self.settings = ToolSettingsManager(...)
    ...
    ...         # Create preset manager using composition
    ...         self.preset_manager = PresetMenuManager(
    ...             window=self,
    ...             settings_manager=self.settings,
    ...             collect_callback=self._collect_settings,
    ...             apply_callback=self._apply_settings
    ...         )
    ...         self.preset_manager.add_menu()
    ...
    ...         self.setup_ui()
    ...         self._restore_settings()
    ...
    ...     def _collect_settings(self) -> dict:
    ...         return {"option": self.checkbox.isChecked()}
    ...
    ...     def _apply_settings(self, settings_data: dict):
    ...         self.checkbox.setChecked(settings_data.get("option", False))
"""

from functools import partial
import logging
from typing import Callable

from .maya_dialog import confirm_dialog, show_info_dialog
from .preset_edit_dialog import PresetEditDialog
from .preset_save_dialog import PresetSaveDialog
from .qt_compat import QTimer
from .tool_settings import ToolSettingsManager

logger = logging.getLogger(__name__)


class PresetMenuManager:
    """
    Manages preset menu for tool windows using composition pattern.

    Provides preset save/load/edit functionality without requiring inheritance.
    Handles menu creation, updates, and RuntimeError protection for menu operations.

    Attributes:
        window: The window instance (must have menuBar() method)
        settings_manager (ToolSettingsManager): Settings manager instance
        collect_callback: Function that collects current UI settings as dict
        apply_callback: Function that applies settings dict to UI
        preset_menu: The Qt menu object for presets
    """

    def __init__(
        self,
        window,
        settings_manager: ToolSettingsManager,
        collect_callback: Callable[[], dict],
        apply_callback: Callable[[dict], None],
    ):
        """
        Initialize the preset menu manager.

        Args:
            window: Window instance with menuBar() method (e.g., QMainWindow)
            settings_manager (ToolSettingsManager): Settings manager instance
            collect_callback: Function that returns current UI settings as dict
            apply_callback: Function that applies settings dict to UI

        Example:
            >>> manager = PresetMenuManager(
            ...     window=self,
            ...     settings_manager=self.settings,
            ...     collect_callback=self._collect_settings,
            ...     apply_callback=self._apply_settings
            ... )
        """
        self.window = window
        self.settings_manager = settings_manager
        self.collect_callback = collect_callback
        self.apply_callback = apply_callback
        self.preset_menu = None

    def add_menu(self):
        """
        Add preset menu to window's menu bar.

        Creates a "Preset" menu with:
        - Save Settings...
        - Edit Settings...
        - Reset Settings...
        - (separator)
        - List of saved presets

        Example:
            >>> manager = PresetMenuManager(...)
            >>> manager.add_menu()
        """
        # Get menu bar from window
        menu_bar = self.window.menuBar()

        # Create Preset menu
        self.preset_menu = menu_bar.addMenu("Preset")

        # Add menu actions
        action = self.preset_menu.addAction("Save Settings...")
        action.triggered.connect(self._on_save_preset)

        action = self.preset_menu.addAction("Edit Settings...")
        action.triggered.connect(self._on_edit_presets)

        action = self.preset_menu.addAction("Reset Settings...")
        action.triggered.connect(self._on_reset_settings)

        self.preset_menu.addSeparator()

        # Populate preset list
        self._update_preset_menu()

        logger.debug("Preset menu added to window")

    def _update_preset_menu(self):
        """
        Update the preset menu with current presets.

        Refreshes the list of available presets in the menu.
        Protected against RuntimeError when menu object is deleted.
        """
        try:
            # Remove all actions after the separator
            actions = self.preset_menu.actions()
            separator_index = -1
            for i, action in enumerate(actions):
                if action.isSeparator():
                    separator_index = i
                    break

            # Remove preset actions (everything after separator)
            if separator_index >= 0:
                for action in actions[separator_index + 1 :]:
                    self.preset_menu.removeAction(action)

            # Add preset actions
            presets = self.settings_manager.list_presets()

            # Ensure "default" is always first
            if "default" in presets:
                presets.remove("default")
                presets.insert(0, "default")

            for preset_name in presets:
                action = self.preset_menu.addAction(preset_name)
                action.triggered.connect(partial(self._on_load_preset, preset_name))

            logger.debug(f"Updated preset menu with {len(presets)} presets")

        except RuntimeError as e:
            # Menu object may have been deleted (C++ object destroyed)
            logger.warning(f"Could not update preset menu: {e}")

    def _on_save_preset(self):
        """Handle Save Settings menu action."""
        dialog = PresetSaveDialog(self.settings_manager, parent=self.window)
        if dialog.exec():
            preset_name = dialog.get_preset_name()
            if preset_name:
                # Collect settings from UI
                settings_data = self.collect_callback()
                self.settings_manager.save_settings(settings_data, preset_name)
                # Defer menu update to avoid RuntimeError with deleted C++ object
                QTimer.singleShot(0, self._update_preset_menu)
                show_info_dialog("Preset Saved", f"Settings saved to preset '{preset_name}'")
                logger.info(f"Saved preset: {preset_name}")

    def _on_edit_presets(self):
        """Handle Edit Settings menu action."""
        dialog = PresetEditDialog(self.settings_manager, parent=self.window)
        dialog.exec()
        # Defer menu update to avoid RuntimeError with deleted C++ object
        QTimer.singleShot(0, self._update_preset_menu)

    def _on_reset_settings(self):
        """Handle Reset Settings menu action."""
        result = confirm_dialog(title="Reset Settings", message="Reset all settings to default values?")

        if result:
            # Apply empty settings to reset to defaults
            self.apply_callback({})
            logger.info("Settings reset to defaults")

    def _on_load_preset(self, preset_name: str):
        """
        Handle preset menu action.

        Args:
            preset_name (str): Name of the preset to load
        """
        settings_data = self.settings_manager.load_settings(preset_name)
        if settings_data:
            self.apply_callback(settings_data)
            logger.info(f"Loaded preset: {preset_name}")


__all__ = ["PresetMenuManager"]
