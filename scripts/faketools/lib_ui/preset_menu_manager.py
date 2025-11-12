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
from .qt_compat import QMenu, QTimer, shiboken
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

    MENU_TITLE = "Preset"

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

    def _is_widget_alive(self, widget) -> bool:
        """Return True if the Qt object still has a valid C++ instance."""
        return widget is not None and shiboken.isValid(widget)

    def _remove_existing_menu_entry(self, menu_bar):
        """Remove an orphaned Preset menu entry before rebuilding.

        Returns the QAction that originally followed the Preset menu so the
        recreated menu can be inserted at the same position.
        """
        actions = menu_bar.actions()
        for index, action in enumerate(actions):
            # Strip mnemonic markers (&) when comparing titles
            if (action.text() or "").replace("&", "") == self.MENU_TITLE:
                next_action = actions[index + 1] if index + 1 < len(actions) else None
                menu_bar.removeAction(action)
                action.deleteLater()
                return next_action

        return None

    def _create_preset_menu(self):
        """Create the preset menu structure (static actions + separator)."""
        if not self._is_widget_alive(self.window):
            logger.warning("Cannot create preset menu because parent window no longer exists.")
            self.preset_menu = None
            return None

        menu_bar = self.window.menuBar()
        insert_before = self._remove_existing_menu_entry(menu_bar)

        self.preset_menu = QMenu(self.MENU_TITLE, menu_bar)
        if insert_before and self._is_widget_alive(insert_before):
            menu_bar.insertMenu(insert_before, self.preset_menu)
        else:
            menu_bar.addMenu(self.preset_menu)

        action = self.preset_menu.addAction("Save Settings...")
        action.triggered.connect(self._on_save_preset)

        action = self.preset_menu.addAction("Edit Settings...")
        action.triggered.connect(self._on_edit_presets)

        action = self.preset_menu.addAction("Reset Settings...")
        action.triggered.connect(self._on_reset_settings)

        self.preset_menu.addSeparator()
        return self.preset_menu

    def _ensure_menu(self):
        """Ensure we have a live QMenu reference, rebuilding if needed."""
        if not self._is_widget_alive(self.window):
            return None

        if not self._is_widget_alive(self.preset_menu):
            logger.debug("Preset menu was deleted; recreating menu entry.")
            self._create_preset_menu()

        return self.preset_menu

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
        if self._create_preset_menu() is None:
            return

        # Populate preset list
        self._update_preset_menu()

        logger.debug("Preset menu added to window")

    def _update_preset_menu(self):
        """
        Update the preset menu with current presets.

        Refreshes the list of available presets in the menu.
        Protected against RuntimeError when menu object is deleted.
        """
        preset_menu = self._ensure_menu()
        if preset_menu is None:
            logger.debug("Skipping preset menu update because menu is unavailable.")
            return

        try:
            # Remove all actions after the separator
            actions = preset_menu.actions()
            separator_index = -1
            for i, action in enumerate(actions):
                if action.isSeparator():
                    separator_index = i
                    break

            # Remove preset actions (everything after separator)
            if separator_index >= 0:
                for action in actions[separator_index + 1 :]:
                    preset_menu.removeAction(action)

            # Add preset actions
            presets = self.settings_manager.list_presets()

            # Ensure "default" is always first
            if "default" in presets:
                presets.remove("default")
                presets.insert(0, "default")

            for preset_name in presets:
                action = preset_menu.addAction(preset_name)
                action.triggered.connect(partial(self._on_load_preset, preset_name))

            logger.debug(f"Updated preset menu with {len(presets)} presets")

        except RuntimeError as e:
            # Menu object may have been deleted (C++ object destroyed)
            logger.warning(f"Could not update preset menu: {e}")
            # Drop invalid reference so next attempt can rebuild cleanly
            self.preset_menu = None

    def _on_save_preset(self):
        """Handle Save Settings menu action."""
        dialog = PresetSaveDialog(self.settings_manager, parent=self.window)
        # Connect to preset_saved signal to update menu immediately when preset is saved
        dialog.preset_saved.connect(lambda name: self._update_preset_menu())
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
        # Connect to presets_changed signal to update menu immediately when presets are deleted
        dialog.presets_changed.connect(self._update_preset_menu)
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
