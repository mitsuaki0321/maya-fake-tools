"""
UI Layout Manager for Code Editor.
Handles UI initialization, theming, and layout management.
"""

import contextlib
from logging import getLogger

from .....lib_ui.qt_compat import QSplitter, Qt, QTimer, QVBoxLayout, QWidget
from ..themes import AppTheme
from .code_editor import CodeEditorWidget
from .panels import FileExplorer, OutputTerminal
from .toolbar import ToolBar

logger = getLogger(__name__)


class UILayoutManager:
    """Manages UI layout, initialization, and theming for the main window."""

    def __init__(self, main_window):
        """Initialize the UILayoutManager with a reference to the main window.

        Args:
            main_window: The main MayaCodeEditor instance
        """
        self.main_window = main_window
        # Load layout orientation from user settings
        self.terminal_at_bottom = self.main_window.settings_manager.get("layout.terminal_at_bottom", True)

    def init_ui(self):
        """Initialize the user interface."""
        self.main_window.setWindowTitle("Code Editor")
        self.main_window.setMinimumSize(600, 400)  # Reduced minimum size for flexibility

        # Create main layout
        main_layout = QVBoxLayout(self.main_window)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Create toolbar
        self.main_window.toolbar = ToolBar(self.main_window)
        main_layout.addWidget(self.main_window.toolbar)

        # Create horizontal splitter for explorer and editor
        self.main_window.main_splitter = QSplitter(Qt.Horizontal)
        # Disable opaque resize for better performance on low-spec machines
        self.main_window.main_splitter.setOpaqueResize(False)

        # Create file explorer (no snippet panel anymore)
        self.main_window.file_explorer = FileExplorer(self.main_window)

        # Add file explorer directly to main horizontal splitter
        self.main_window.main_splitter.addWidget(self.main_window.file_explorer)

        # Create vertical splitter for editor and terminal
        self.main_window.v_splitter = QSplitter(Qt.Vertical)
        # Disable opaque resize for better performance on low-spec machines
        self.main_window.v_splitter.setOpaqueResize(False)

        # Create a container widget for editor and variable bar
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # Create code editor
        self.main_window.code_editor = CodeEditorWidget(self.main_window)
        editor_layout.addWidget(self.main_window.code_editor)

        # Create output terminal
        self.main_window.output_terminal = OutputTerminal(self.main_window)

        # Add widgets based on layout orientation setting
        if self.terminal_at_bottom:
            # Standard layout: editor on top, terminal on bottom
            self.main_window.v_splitter.addWidget(editor_container)
            self.main_window.v_splitter.addWidget(self.main_window.output_terminal)
        else:
            # Swapped layout: terminal on top, editor on bottom
            self.main_window.v_splitter.addWidget(self.main_window.output_terminal)
            self.main_window.v_splitter.addWidget(editor_container)

        # Set splitter proportions
        self.main_window.v_splitter.setSizes([400, 150])  # Editor larger than terminal
        # Allow terminal to be collapsed but keep editor visible
        self.main_window.v_splitter.setCollapsible(0, False)  # Editor cannot be collapsed
        self.main_window.v_splitter.setCollapsible(1, True)  # Terminal can be collapsed
        if self.main_window.code_editor:
            self.main_window.code_editor.setMinimumHeight(100)
        if self.main_window.output_terminal:
            self.main_window.output_terminal.setMinimumHeight(20)  # Lower minimum for collapsing

        self.main_window.main_splitter.addWidget(self.main_window.v_splitter)
        self.main_window.main_splitter.setSizes([200, 600])  # Explorer smaller than editor area

        # Set stretch factors: explorer stays fixed (0), editor area stretches (1)
        self.main_window.main_splitter.setStretchFactor(0, 0)  # File explorer - fixed width
        self.main_window.main_splitter.setStretchFactor(1, 1)  # Editor area - stretches

        # Connect splitter signals for settings save
        self.main_window.main_splitter.splitterMoved.connect(self.on_splitter_moved)
        self.main_window.v_splitter.splitterMoved.connect(self.on_splitter_moved)

        main_layout.addWidget(self.main_window.main_splitter)

    def apply_theme(self):
        """Apply application theme to all UI components."""
        # Apply main window theme
        self.main_window.setStyleSheet(AppTheme.get_main_window_stylesheet())

        # Apply editor theme
        if self.main_window.code_editor:
            editor_style = AppTheme.get_editor_stylesheet()
            tab_style = AppTheme.get_tab_widget_stylesheet()
            self.main_window.code_editor.setStyleSheet(tab_style)

            # Apply to all editor instances
            for i in range(self.main_window.code_editor.count()):
                editor = self.main_window.code_editor.widget(i)
                if editor:
                    editor.setStyleSheet(editor_style)
                    editor.highlight_current_line()

        # Apply terminal theme
        # Only apply stylesheet if using QTextEdit (not Maya native terminal)
        if (
            self.main_window.output_terminal
            and hasattr(self.main_window.output_terminal, "output_display")
            and self.main_window.output_terminal.output_display
        ):
            terminal_style = AppTheme.get_terminal_stylesheet()
            self.main_window.output_terminal.output_display.setStyleSheet(terminal_style)

        # Apply file explorer theme
        if self.main_window.file_explorer:
            explorer_style = AppTheme.get_file_explorer_stylesheet()
            self.main_window.file_explorer.setStyleSheet(explorer_style)

        # ToolBar styles itself in its own init_ui (it's a QWidget, not a
        # QToolBar, so AppTheme's QToolBar-targeted rules wouldn't match).

    def connect_signals(self):
        """Connect signals between components."""
        mw = self.main_window
        file_ops = mw.file_ops

        if mw.toolbar:
            mw.toolbar.toggle_explorer_clicked.connect(self.toggle_file_explorer)
            mw.toolbar.refresh_explorer_clicked.connect(self._refresh_file_explorer)
            mw.toolbar.run_clicked.connect(mw.execution_manager.run_current_script)
            mw.toolbar.save_clicked.connect(file_ops.save_current_file)
            mw.toolbar.save_all_clicked.connect(file_ops.save_all_files)
            mw.toolbar.new_clicked.connect(file_ops.new_file)
            mw.toolbar.clear_clicked.connect(self.clear_terminal)
            mw.toolbar.workspace_clicked.connect(mw.open_workspace_directory)
            mw.toolbar.swap_layout_clicked.connect(self.swap_editor_terminal_layout)
            mw.toolbar.terminal_toggled.connect(self.toggle_terminal)
            mw.toolbar.echo_all_toggled.connect(self.toggle_echo_all)
            mw.toolbar.word_wrap_toggled.connect(self.toggle_word_wrap)
            mw.toolbar.fold_all_clicked.connect(mw.fold_all)
            mw.toolbar.unfold_all_clicked.connect(mw.unfold_all)
            mw.toolbar.add_to_shelf_clicked.connect(mw.add_to_shelf)
            mw.toolbar.autocomplete_toggled.connect(self.toggle_autocomplete)

        if mw.file_explorer:
            mw.file_explorer.file_selected.connect(file_ops.open_file_permanent)
            mw.file_explorer.file_preview.connect(file_ops.open_file_preview)
            mw.file_explorer.file_executed.connect(file_ops.execute_file_directly)
            mw.file_explorer.file_renamed.connect(file_ops.handle_file_renamed)
            mw.file_explorer.folder_renamed.connect(file_ops.handle_folder_renamed)
            mw.file_explorer.file_deleted.connect(file_ops.handle_file_deleted)
            mw.file_explorer.folder_deleted.connect(file_ops.handle_folder_deleted)

        if self.main_window.code_editor:
            self._connect_editor_focus_signals()

    def _connect_editor_focus_signals(self):
        """Wire ``focus_lost`` on every editor to ``save_session_state``.

        Focus-out is the primary trigger for session.json persistence: a save
        fires whenever the user moves focus away from the code area (other
        tab, explorer, terminal, another window).
        """
        if not self.main_window.code_editor:
            return

        for i in range(self.main_window.code_editor.count()):
            editor = self.main_window.code_editor.widget(i)
            if editor and hasattr(editor, "focus_lost"):
                self._wire_focus_lost(editor)

        # Late-created tabs need the same wiring; piggyback on currentChanged.
        self.main_window.code_editor.currentChanged.connect(self._on_tab_changed_connect_focus)

    def _on_tab_changed_connect_focus(self, index):
        """Re-wire ``focus_lost`` when the active tab changes."""
        if index < 0 or not self.main_window.code_editor:
            return

        editor = self.main_window.code_editor.widget(index)
        if editor and hasattr(editor, "focus_lost"):
            self._wire_focus_lost(editor)

    def _wire_focus_lost(self, editor):
        """Connect ``focus_lost`` to session save (idempotent)."""
        save = self.main_window.session_manager.save_session_state

        with contextlib.suppress(Exception):
            editor.focus_lost.disconnect(save)
        with contextlib.suppress(Exception):
            editor.focus_lost.connect(save)

    def apply_font_settings(self):
        """Apply default font settings from settings.json to editors and terminal."""
        # Get editor font size
        editor_font_size = self.main_window.settings_manager.get("editor.font_size", 10)

        # Apply to code editor tabs
        if self.main_window.code_editor:
            for i in range(self.main_window.code_editor.count()):
                editor = self.main_window.code_editor.widget(i)
                if hasattr(editor, "set_default_font_size"):
                    editor.set_default_font_size(editor_font_size)

        # Apply to output terminal
        terminal_font_size = self.main_window.settings_manager.get("terminal.font_size", 9)
        if self.main_window.output_terminal and hasattr(self.main_window.output_terminal, "set_default_font_size"):
            self.main_window.output_terminal.set_default_font_size(terminal_font_size)

        # Restore word wrap setting
        word_wrap_enabled = self.main_window.settings_manager.get("editor.word_wrap", True)
        if self.main_window.code_editor:
            self.main_window.code_editor.set_word_wrap_all(word_wrap_enabled)
        # Sync toolbar toggle button state
        if self.main_window.toolbar and hasattr(self.main_window.toolbar, "word_wrap_button"):
            self.main_window.toolbar.word_wrap_button.set_active(word_wrap_enabled)

        # Restore autocomplete setting. Auto-disable + gray out the toolbar
        # button when jedi isn't importable so the user can see why toggling
        # does nothing.
        from ..command.autocomplete import JEDI_AVAILABLE

        autocomplete_enabled = self.main_window.settings_manager.get("autocomplete.enabled", True) and JEDI_AVAILABLE
        if self.main_window.code_editor and hasattr(self.main_window.code_editor, "set_autocomplete_enabled"):
            self.main_window.code_editor.set_autocomplete_enabled(autocomplete_enabled)
        if self.main_window.toolbar and hasattr(self.main_window.toolbar, "autocomplete_button"):
            button = self.main_window.toolbar.autocomplete_button
            button.set_active(autocomplete_enabled)
            if not JEDI_AVAILABLE:
                button.setEnabled(False)
                button.setToolTip("Autocomplete unavailable (install jedi to enable)")

    def restore_settings(self):
        """Restore window settings from saved preferences."""
        # Restore window geometry
        window_settings = self.main_window.settings_manager.get_window_geometry()

        if window_settings:
            self.main_window.resize(window_settings.get("width", 800), window_settings.get("height", 600))
            self.main_window.move(window_settings.get("x", 100), window_settings.get("y", 100))

            if window_settings.get("maximized", False):
                self.main_window.showMaximized()

        # Restore splitter sizes
        if hasattr(self.main_window, "main_splitter"):
            h_sizes = self.main_window.settings_manager.get_splitter_sizes("horizontal")
            if h_sizes:
                self.main_window.main_splitter.setSizes(h_sizes)

        # Restore file explorer visibility
        if hasattr(self.main_window, "file_explorer") and self.main_window.file_explorer:
            explorer_visible = self.main_window.settings_manager.get("layout.explorer_visible", True)
            if not explorer_visible:
                self.main_window.file_explorer.hide()
            # Sync refresh button enabled state
            if self.main_window.toolbar and hasattr(self.main_window.toolbar, "refresh_explorer_button"):
                self.main_window.toolbar.refresh_explorer_button.setEnabled(explorer_visible)

        if hasattr(self.main_window, "v_splitter"):
            v_sizes = self.main_window.settings_manager.get_splitter_sizes("vertical")
            if v_sizes:
                self.main_window.v_splitter.setSizes(v_sizes)

        # Restore terminal visibility
        if hasattr(self.main_window, "output_terminal") and self.main_window.output_terminal:
            terminal_visible = self.main_window.settings_manager.get("layout.terminal_visible", True)
            if not terminal_visible:
                self.main_window.output_terminal.hide()
            if self.main_window.toolbar and hasattr(self.main_window.toolbar, "terminal_toggle_button"):
                self.main_window.toolbar.terminal_toggle_button.set_active(terminal_visible)

        # No longer need left_splitter settings

        # Restore session after UI is set up (with slight delay to ensure everything is ready)
        def delayed_restore():
            self.main_window.session_manager.restore_session_state()

        QTimer.singleShot(100, delayed_restore)  # 100ms delay

    def save_settings(self):
        """Save current window settings."""
        # Save window geometry
        if not self.main_window.isMaximized():
            self.main_window.settings_manager.set_window_geometry(
                self.main_window.x(),
                self.main_window.y(),
                self.main_window.width(),
                self.main_window.height(),
                False,
            )
        else:
            self.main_window.settings_manager.set_window_geometry(
                self.main_window.x(),
                self.main_window.y(),
                self.main_window.width(),
                self.main_window.height(),
                True,
            )

        # Save splitter sizes
        if hasattr(self.main_window, "main_splitter"):
            self.main_window.settings_manager.set_splitter_sizes("horizontal", self.main_window.main_splitter.sizes())

        if hasattr(self.main_window, "v_splitter"):
            self.main_window.settings_manager.set_splitter_sizes("vertical", self.main_window.v_splitter.sizes())

        # No longer need to save left_splitter settings

        # Save to file
        self.main_window.settings_manager.save_settings()

    def _refresh_file_explorer(self):
        """Refresh the file explorer tree."""
        if self.main_window.file_explorer and self.main_window.file_explorer.isVisible():
            self.main_window.file_explorer.refresh()

    def on_splitter_moved(self):
        """Handle splitter movement - save settings with delay."""
        # Save settings when splitter is moved
        self.save_settings()

    def swap_editor_terminal_layout(self):
        """Swap the positions of editor and terminal in the vertical splitter."""
        if not hasattr(self.main_window, "v_splitter"):
            return

        # Get the count of widgets in splitter
        widget_count = self.main_window.v_splitter.count()
        if widget_count != 2:
            logger.warning(f"Expected 2 widgets in v_splitter, found {widget_count}")
            return

        # Get current sizes before swapping
        current_sizes = self.main_window.v_splitter.sizes()

        # Store references to the widgets based on current layout
        if self.terminal_at_bottom:
            # Currently: editor at top (index 0), terminal at bottom (index 1)
            top_widget = self.main_window.v_splitter.widget(0)
            bottom_widget = self.main_window.v_splitter.widget(1)
        else:
            # Currently: terminal at top (index 0), editor at bottom (index 1)
            top_widget = self.main_window.v_splitter.widget(0)
            bottom_widget = self.main_window.v_splitter.widget(1)

        if not top_widget or not bottom_widget:
            return

        # Preserve pre-swap visibility (terminal may be toggled off by the user)
        top_was_visible = top_widget.isVisible()
        bottom_was_visible = bottom_widget.isVisible()

        # Hide both widgets temporarily to prevent flicker
        top_widget.hide()
        bottom_widget.hide()

        # Remove widgets from splitter (this doesn't delete them)
        # Important: Always remove from the end to avoid index shifting
        self.main_window.v_splitter.widget(1).setParent(None)
        self.main_window.v_splitter.widget(0).setParent(None)

        # Add them back in swapped order
        self.main_window.v_splitter.addWidget(bottom_widget)
        self.main_window.v_splitter.addWidget(top_widget)

        # Swap sizes to maintain proportions
        if len(current_sizes) == 2:
            self.main_window.v_splitter.setSizes([current_sizes[1], current_sizes[0]])

        # Restore visibility
        if bottom_was_visible:
            bottom_widget.show()
        if top_was_visible:
            top_widget.show()

        # Toggle the state
        self.terminal_at_bottom = not self.terminal_at_bottom

        # Save the new layout orientation to user settings
        self.main_window.settings_manager.set("layout.terminal_at_bottom", self.terminal_at_bottom)
        self.main_window.settings_manager.save_settings()

        # Update collapsible settings based on new positions
        self.main_window.v_splitter.setCollapsible(0, False)  # Top widget cannot be collapsed
        self.main_window.v_splitter.setCollapsible(1, True)  # Bottom widget can be collapsed

    # -------------------- Panel toggles --------------------

    def toggle_file_explorer(self):
        """Show or hide the file explorer panel and persist its width."""
        mw = self.main_window
        if not mw.file_explorer or not hasattr(mw, "main_splitter"):
            return

        if mw.file_explorer.isVisible():
            sizes = mw.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[0] > 0:
                mw.settings_manager.set("layout.explorer_width", sizes[0])
            mw.file_explorer.hide()
            mw.settings_manager.set("layout.explorer_visible", False)
        else:
            mw.file_explorer.show()
            mw.settings_manager.set("layout.explorer_visible", True)
            saved_width = mw.settings_manager.get("layout.explorer_width", 200)
            sizes = mw.main_splitter.sizes()
            if len(sizes) >= 2:
                total = sum(sizes)
                mw.main_splitter.setSizes([saved_width, total - saved_width])

        if mw.toolbar and hasattr(mw.toolbar, "refresh_explorer_button"):
            mw.toolbar.refresh_explorer_button.setEnabled(mw.file_explorer.isVisible())

        mw.settings_manager.save_settings()

    def toggle_terminal(self):
        """Show or hide the output terminal panel and persist its height."""
        mw = self.main_window
        if not mw.output_terminal or not hasattr(mw, "v_splitter"):
            return

        terminal_idx = mw.v_splitter.indexOf(mw.output_terminal)
        if terminal_idx < 0:
            return

        if mw.output_terminal.isVisible():
            sizes = mw.v_splitter.sizes()
            if terminal_idx < len(sizes) and sizes[terminal_idx] > 0:
                mw.settings_manager.set("layout.terminal_height", sizes[terminal_idx])
            mw.output_terminal.hide()
            mw.settings_manager.set("layout.terminal_visible", False)
        else:
            mw.output_terminal.show()
            mw.settings_manager.set("layout.terminal_visible", True)
            saved_height = mw.settings_manager.get("layout.terminal_height", 150)
            sizes = mw.v_splitter.sizes()
            if len(sizes) == 2:
                other_idx = 1 - terminal_idx
                total = sum(sizes)
                new_sizes = [0, 0]
                new_sizes[terminal_idx] = saved_height
                new_sizes[other_idx] = max(100, total - saved_height)
                mw.v_splitter.setSizes(new_sizes)

        mw.settings_manager.save_settings()

    # -------------------- View-state toggles --------------------

    def toggle_word_wrap(self, enabled):
        """Apply word wrap to every editor tab and persist the choice."""
        mw = self.main_window
        if mw.code_editor:
            mw.code_editor.set_word_wrap_all(enabled)
        mw.settings_manager.set("editor.word_wrap", enabled)
        mw.settings_manager.save_settings()

    def toggle_echo_all(self, enabled):
        """Mirror Maya's ``echoAllCommands`` setting onto the output terminal."""
        if self.main_window.output_terminal:
            self.main_window.output_terminal.set_echo_all(enabled)

    def toggle_autocomplete(self, enabled: bool):
        """Enable/disable jedi autocomplete across all tabs and persist."""
        mw = self.main_window
        if mw.code_editor and hasattr(mw.code_editor, "set_autocomplete_enabled"):
            mw.code_editor.set_autocomplete_enabled(enabled)
        mw.settings_manager.set("autocomplete.enabled", enabled)
        mw.settings_manager.save_settings()

    def clear_terminal(self):
        """Clear the output terminal."""
        if self.main_window.output_terminal:
            self.main_window.output_terminal.clear()
