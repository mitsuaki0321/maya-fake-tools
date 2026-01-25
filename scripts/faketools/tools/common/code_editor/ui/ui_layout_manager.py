"""
UI Layout Manager for Maya Code Editor.
Handles UI initialization, theming, and layout management.
"""

from logging import getLogger

from ..themes import AppTheme
from .code_editor import CodeEditorWidget
from .file_explorer import FileExplorer
from .output_terminal import OutputTerminal
from .qt_compat import QColor, QSplitter, Qt, QTextCharFormat, QTextEdit, QTimer, QVBoxLayout, QWidget
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
        self.main_window.setWindowTitle("Maya Code Editor")
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

                    # Update current line highlight color
                    selection = QTextEdit.ExtraSelection()
                    line_color = QColor(AppTheme.CURRENT_LINE)
                    selection.format.setBackground(line_color)
                    selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
                    selection.cursor = editor.textCursor()
                    selection.cursor.clearSelection()
                    editor.setExtraSelections([selection])

        # Apply terminal theme
        if self.main_window.output_terminal:
            # Only apply stylesheet if using QTextEdit (not Maya native terminal)
            if hasattr(self.main_window.output_terminal, "output_display") and self.main_window.output_terminal.output_display:
                terminal_style = AppTheme.get_terminal_stylesheet()
                self.main_window.output_terminal.output_display.setStyleSheet(terminal_style)

        # Apply file explorer theme
        if self.main_window.file_explorer:
            explorer_style = AppTheme.get_file_explorer_stylesheet()
            self.main_window.file_explorer.setStyleSheet(explorer_style)

        # Apply toolbar theme
        if self.main_window.toolbar:
            toolbar_style = AppTheme.get_toolbar_stylesheet()
            self.main_window.toolbar.setStyleSheet(toolbar_style)

        # Snippet panel theme removed - no longer needed

    def connect_signals(self):
        """Connect signals between components."""
        if self.main_window.toolbar:
            self.main_window.toolbar.toggle_explorer_clicked.connect(self.main_window.toggle_file_explorer)
            self.main_window.toolbar.run_clicked.connect(self.main_window.execution_manager.run_current_script)
            self.main_window.toolbar.save_clicked.connect(self.main_window.save_current_file)
            self.main_window.toolbar.save_all_clicked.connect(self.main_window.save_all_files)
            self.main_window.toolbar.new_clicked.connect(self.main_window.new_file)
            self.main_window.toolbar.clear_clicked.connect(self.main_window.clear_terminal)
            self.main_window.toolbar.workspace_clicked.connect(self.main_window.open_workspace_directory)
            self.main_window.toolbar.swap_layout_clicked.connect(self.swap_editor_terminal_layout)
            self.main_window.toolbar.show_help_clicked.connect(self.main_window.show_user_guide)

        if self.main_window.file_explorer:
            self.main_window.file_explorer.file_selected.connect(self.main_window.open_file_permanent)
            self.main_window.file_explorer.file_preview.connect(self.main_window.open_file_preview)
            self.main_window.file_explorer.file_executed.connect(self.main_window.execute_file_directly)
            self.main_window.file_explorer.file_renamed.connect(self.main_window.handle_file_renamed)
            self.main_window.file_explorer.folder_renamed.connect(self.main_window.handle_folder_renamed)
            self.main_window.file_explorer.file_deleted.connect(self.main_window.handle_file_deleted)
            self.main_window.file_explorer.folder_deleted.connect(self.main_window.handle_folder_deleted)

        if self.main_window.code_editor:
            self.main_window.code_editor.inspect_object.connect(self.main_window.execution_manager.handle_object_inspection)
            self.main_window.code_editor.textChanged.connect(self.main_window.session_manager.on_editor_text_changed)

            # Connect focus_lost signal from editors to flush backups (network HDD performance)
            self._connect_editor_focus_signals()

    def _connect_editor_focus_signals(self):
        """Connect focus_lost signals from all editors to flush backups."""
        if not self.main_window.code_editor or not self.main_window.autosave_manager:
            return

        # Connect existing editors
        for i in range(self.main_window.code_editor.count()):
            editor = self.main_window.code_editor.widget(i)
            if editor and hasattr(editor, "focus_lost"):
                try:
                    editor.focus_lost.connect(self.main_window.autosave_manager.flush_backups)
                except Exception:
                    pass  # Already connected or invalid

        # Connect signal for new tabs to auto-connect their focus_lost signal
        self.main_window.code_editor.currentChanged.connect(self._on_tab_changed_connect_focus)

    def _on_tab_changed_connect_focus(self, index):
        """Connect focus_lost signal when switching to a new tab."""
        if index < 0 or not self.main_window.code_editor or not self.main_window.autosave_manager:
            return

        editor = self.main_window.code_editor.widget(index)
        if editor and hasattr(editor, "focus_lost"):
            try:
                # Disconnect first to avoid duplicate connections
                try:
                    editor.focus_lost.disconnect(self.main_window.autosave_manager.flush_backups)
                except Exception:
                    pass
                editor.focus_lost.connect(self.main_window.autosave_manager.flush_backups)
            except Exception:
                pass

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

        if hasattr(self.main_window, "v_splitter"):
            v_sizes = self.main_window.settings_manager.get_splitter_sizes("vertical")
            if v_sizes:
                self.main_window.v_splitter.setSizes(v_sizes)

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
                self.main_window.x(), self.main_window.y(), self.main_window.width(), self.main_window.height(), False
            )
        else:
            self.main_window.settings_manager.set_window_geometry(
                self.main_window.x(), self.main_window.y(), self.main_window.width(), self.main_window.height(), True
            )

        # Save splitter sizes
        if hasattr(self.main_window, "main_splitter"):
            self.main_window.settings_manager.set_splitter_sizes("horizontal", self.main_window.main_splitter.sizes())

        if hasattr(self.main_window, "v_splitter"):
            self.main_window.settings_manager.set_splitter_sizes("vertical", self.main_window.v_splitter.sizes())

        # No longer need to save left_splitter settings

        # Save to file
        self.main_window.settings_manager.save_settings()

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

        # Show both widgets again
        bottom_widget.show()
        top_widget.show()

        # Toggle the state
        self.terminal_at_bottom = not self.terminal_at_bottom

        # Save the new layout orientation to user settings
        self.main_window.settings_manager.set("layout.terminal_at_bottom", self.terminal_at_bottom)
        self.main_window.settings_manager.save_settings()

        # Update collapsible settings based on new positions
        self.main_window.v_splitter.setCollapsible(0, False)  # Top widget cannot be collapsed
        self.main_window.v_splitter.setCollapsible(1, True)  # Bottom widget can be collapsed
