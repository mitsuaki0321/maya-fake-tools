"""
Main window for Maya Code Editor.
Provides the primary UI layout and coordinates between components.
"""

from logging import getLogger
import os

from .....lib_ui.qt_compat import QWidget
from ..settings import SettingsManager
from ..utils.autosave_manager import AutoSaveManager  # Direct import to avoid circular dependency
from .dialog_base import CodeEditorInputDialog, CodeEditorMessageBox
from .execution_manager import ExecutionManager
from .shortcut_handler import ShortcutHandler
from .ui_layout_manager import UILayoutManager
from .ui_session_manager import UISessionManager

logger = getLogger(__name__)


class MayaCodeEditor(QWidget):
    """Main code editor widget for Maya integration."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_explorer = None
        self.code_editor = None
        self.output_terminal = None

        # Initialize settings manager
        self.settings_manager = SettingsManager()

        # Initialize auto-save manager
        self.autosave_manager = AutoSaveManager(self.settings_manager, self)

        # Persistent execution environment (like Maya Script Editor)
        self.exec_globals = {
            "__name__": "__main__",
        }
        self.setup_exec_environment()
        self.toolbar = None

        # Initialize execution manager
        self.execution_manager = ExecutionManager(self)

        # Initialize shortcut handler
        self.shortcut_handler = ShortcutHandler(self)

        # Initialize UI layout manager
        self.layout_manager = UILayoutManager(self)

        # Initialize execution manager (uses properties for lazy access)
        self.execution_manager = ExecutionManager(self)

        # Initialize session manager
        self.session_manager = UISessionManager(self)

        self.layout_manager.init_ui()
        self.layout_manager.apply_theme()
        self.layout_manager.connect_signals()
        self.shortcut_handler.setup_shortcuts()
        self.layout_manager.apply_font_settings()
        self.setup_workspace()
        self.layout_manager.restore_settings()

    def setup_exec_environment(self):
        """Setup persistent execution environment with Maya imports."""
        try:
            import maya.api.OpenMaya as om2  # type: ignore
            import maya.cmds as cmds  # type: ignore

            # Add Maya modules to persistent environment
            self.exec_globals.update(
                {
                    "cmds": cmds,
                    "om2": om2,
                    "om": om2,  # Alias for backward compatibility
                },
            )

        except ImportError:
            # Maya not available
            pass

    def get_current_editor(self):
        """Get the currently active editor widget."""
        if self.code_editor:
            return self.code_editor.currentWidget()
        return None

    def open_file_permanent(self, file_path: str):
        """Open a file in permanent mode (fixed tab)."""
        if self.code_editor:
            # First check if this file is currently in preview mode
            self.code_editor.make_preview_permanent(file_path)

            success = self.code_editor.open_file_permanent(file_path)
            if success:
                # Add to recent files and save settings
                self.settings_manager.add_recent_file(file_path)
                self.settings_manager.save_settings()

                # Register file with auto-save manager
                current_editor = self.code_editor.get_current_editor()
                if current_editor:
                    content = current_editor.toPlainText()
                    self.autosave_manager.register_file(file_path, content)

    def open_file_preview(self, file_path: str):
        """Open a file in preview mode."""
        if self.code_editor:
            success = self.code_editor.open_file_preview(file_path)
            if success:
                # Add to recent files
                self.settings_manager.add_recent_file(file_path)
                self.settings_manager.save_settings()

    def save_current_file(self):
        """Save the currently active file."""
        if self.code_editor:
            success = self.code_editor.save_current_file()
            if success:
                self.output_terminal.append_output("File saved successfully.")
                # Get the current editor to add to recent files
                current_editor = self.get_current_editor()
                if current_editor and current_editor.file_path:
                    self.settings_manager.add_recent_file(current_editor.file_path)
            else:
                self.output_terminal.append_output("Failed to save file.")

    def save_all_files(self):
        """Save all open files."""
        if not self.code_editor:
            return

        saved_count = 0
        failed_count = 0

        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            if isinstance(editor, type(self.code_editor.get_current_editor())):
                try:
                    # Skip Draft tab
                    if hasattr(editor, "is_draft") and editor.is_draft:
                        continue

                    if hasattr(editor, "file_path") and editor.file_path:
                        # Save file with existing path
                        with open(editor.file_path, "w", encoding="utf-8") as f:
                            f.write(editor.toPlainText())
                        saved_count += 1

                        # Update autosave manager
                        content = editor.toPlainText()
                        self.autosave_manager.register_file(editor.file_path, content)

                        # Mark as unmodified (both custom property and QTextDocument)
                        editor.is_modified = False
                        editor.document().setModified(False)

                        # Update tab title to remove asterisk
                        self.code_editor.update_tab_title(editor)

                    else:
                        # Skip untitled files
                        self.output_terminal.append_output(f"Skipped untitled file in tab {i + 1}")

                except Exception as e:
                    failed_count += 1
                    self.output_terminal.append_output(f"Failed to save tab {i + 1}: {e!s}")

        if saved_count > 0:
            self.output_terminal.append_output(f"Saved {saved_count} file(s)")
        if failed_count > 0:
            self.output_terminal.append_output(f"Failed to save {failed_count} file(s)")
        if saved_count == 0 and failed_count == 0:
            self.output_terminal.append_output("No files to save")

    def handle_file_renamed(self, old_path: str, new_path: str):
        """Handle file rename event and update corresponding tabs."""
        if not self.code_editor:
            return

        # Normalize paths to use forward slashes for comparison
        old_path_normalized = old_path.replace("\\", "/")
        new_path_normalized = new_path.replace("\\", "/")

        new_filename = os.path.basename(new_path)
        old_filename = os.path.basename(old_path)
        tabs_updated = 0

        # Find ALL tabs with the old file path and update them
        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            editor_path = getattr(editor, "file_path", None)

            # Normalize editor path for comparison
            if editor_path:
                editor_path_normalized = editor_path.replace("\\", "/")
            else:
                editor_path_normalized = None

            if hasattr(editor, "file_path") and editor_path and editor_path_normalized == old_path_normalized:
                # Update the editor's file path (use normalized path for consistency)
                editor.file_path = new_path_normalized

                # Get current tab text to check if it's a preview tab
                current_tab_text = self.code_editor.tabText(i)

                # Update tab title based on whether it's a preview tab or not
                if " (Preview)" in current_tab_text:
                    # Maintain preview status
                    self.code_editor.setTabText(i, new_filename + " (Preview)")
                else:
                    # Regular tab
                    self.code_editor.setTabText(i, new_filename)

                # Update autosave manager
                if hasattr(self, "autosave_manager"):
                    content = editor.toPlainText()
                    self.autosave_manager.unregister_file(old_path)  # Remove old registration
                    self.autosave_manager.register_file(new_path, content)  # Add new registration

                tabs_updated += 1

        # Update recent files if the file was in the list
        if tabs_updated > 0:
            self.settings_manager.update_recent_file_path(old_path, new_path)
            self.output_terminal.append_output(f"File renamed: {old_filename} → {new_filename}")

    def handle_folder_renamed(self, old_folder_path: str, new_folder_path: str):
        """Handle folder rename event and update all files within the folder."""
        if not self.code_editor:
            return

        updated_count = 0

        # Find all tabs with files inside the renamed folder
        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            if hasattr(editor, "file_path") and editor.file_path and editor.file_path.startswith(old_folder_path + os.sep):
                # Calculate the new path
                relative_path = editor.file_path[len(old_folder_path) + 1 :]
                new_file_path = os.path.join(new_folder_path, relative_path)

                # Update the editor's file path
                old_file_path = editor.file_path
                editor.file_path = new_file_path

                # Update tab title (filename shouldn't change)
                filename = os.path.basename(new_file_path)
                self.code_editor.setTabText(i, filename)

                # Update autosave manager
                if hasattr(self, "autosave_manager"):
                    content = editor.toPlainText()
                    self.autosave_manager.unregister_file(old_file_path)
                    self.autosave_manager.register_file(new_file_path, content)

                # Update recent files
                self.settings_manager.update_recent_file_path(old_file_path, new_file_path)

                updated_count += 1

        if updated_count > 0:
            folder_name = os.path.basename(new_folder_path)
            self.output_terminal.append_output(f"Updated {updated_count} file(s) in renamed folder: {folder_name}")

    def handle_file_deleted(self, deleted_file_path: str):
        """Handle file deletion and close corresponding tab."""
        if not self.code_editor:
            return

        # Find and close tab with the deleted file
        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            if hasattr(editor, "file_path") and editor.file_path == deleted_file_path:
                # Close the tab
                self.code_editor.removeTab(i)

                # Unregister from autosave manager
                if hasattr(self, "autosave_manager"):
                    self.autosave_manager.unregister_file(deleted_file_path)

                # Remove from recent files
                recent_files = self.settings_manager.get("recent_files", [])
                if deleted_file_path in recent_files:
                    recent_files.remove(deleted_file_path)
                    self.settings_manager.set("recent_files", recent_files)
                    self.settings_manager.save_settings()

                filename = os.path.basename(deleted_file_path)
                self.output_terminal.append_output(f"Closed tab for deleted file: {filename}")
                break

    def handle_folder_deleted(self, deleted_folder_path: str):
        """Handle folder deletion and close all tabs within the folder."""
        if not self.code_editor:
            return

        closed_count = 0
        tabs_to_remove = []

        # Find all tabs with files inside the deleted folder
        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            if hasattr(editor, "file_path") and editor.file_path and editor.file_path.startswith(deleted_folder_path + os.sep):
                tabs_to_remove.append((i, editor.file_path))

        # Remove tabs in reverse order to maintain indices
        for i, file_path in reversed(tabs_to_remove):
            self.code_editor.removeTab(i)

            # Unregister from autosave manager
            if hasattr(self, "autosave_manager"):
                self.autosave_manager.unregister_file(file_path)

            # Remove from recent files
            recent_files = self.settings_manager.get("recent_files", [])
            if file_path in recent_files:
                recent_files.remove(file_path)
                self.settings_manager.set("recent_files", recent_files)

            closed_count += 1

        # Save settings if any files were removed from recent files
        if closed_count > 0:
            self.settings_manager.save_settings()
            folder_name = os.path.basename(deleted_folder_path)
            self.output_terminal.append_output(f"Closed {closed_count} tab(s) from deleted folder: {folder_name}")

    def new_file(self):
        """Create a new file in the workspace directory."""
        # Get workspace directory
        workspace_dir = self.settings_manager.get_workspace_directory()
        if not workspace_dir or not os.path.exists(workspace_dir):
            CodeEditorMessageBox.warning(self, "Error", "Workspace directory not found.")
            return

        # Ask user for filename
        filename, ok = CodeEditorInputDialog.getText(self, "New File", "Enter filename (with .py extension):", text="new_script.py")

        if not ok or not filename.strip():
            return

        filename = filename.strip()

        # Ensure .py extension
        if not filename.endswith(".py"):
            filename += ".py"

        # Create full path
        file_path = os.path.join(workspace_dir, filename)

        # Check if file already exists
        if os.path.exists(file_path):
            reply = CodeEditorMessageBox.question(
                self,
                "File Exists",
                f"File '{filename}' already exists. Do you want to overwrite it?",
                CodeEditorMessageBox.Yes | CodeEditorMessageBox.No,
                CodeEditorMessageBox.No,
            )
            if reply != CodeEditorMessageBox.Yes:
                return

        try:
            # Create the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# New Python script\n\n")

            # Refresh file explorer to show the new file
            if self.file_explorer:
                self.file_explorer.refresh()

            # Automatically open the new file in code editor
            self.open_file_permanent(file_path)

            self.output_terminal.append_output(f"Created new file: {filename}")

        except Exception as e:
            CodeEditorMessageBox.critical(self, "Error", f"Failed to create file: {e!s}")

    def clear_terminal(self):
        """Clear the output terminal."""
        if self.output_terminal:
            self.output_terminal.clear()

    def execute_file_directly(self, file_path: str):
        """Execute a Python file directly without opening it in the editor."""
        if not os.path.exists(file_path):
            CodeEditorMessageBox.warning(self, "File Not Found", f"File does not exist: {file_path}")
            return

        try:
            # Read the file contents
            with open(file_path, encoding="utf-8") as f:
                code = f.read()

            # Display file being executed in terminal
            file_name = os.path.basename(file_path)
            self.output_terminal.append_output(f"\n# Executing: {file_name}")
            self.output_terminal.append_output("-" * 40)

            # Execute the code through the execution manager
            if self.execution_manager:
                self.execution_manager.execute_code(code)

        except Exception as e:
            self.output_terminal.append_output(f"Error executing file: {e!s}")

    def manual_save_session(self):
        """Manually save session state for testing."""
        self.session_manager.save_session_state()

    def open_workspace_directory(self):
        """Open maya_code_editor_workspace directory in file explorer."""
        import platform
        import subprocess

        # Get the directory that file explorer is currently using
        if hasattr(self.file_explorer, "root_path") and self.file_explorer.root_path:
            workspace_dir = self.file_explorer.root_path
        else:
            # Fallback to settings manager
            workspace_dir = self.settings_manager.get_workspace_directory()

        # Normalize the path for the current platform
        workspace_dir = os.path.normpath(workspace_dir)
        workspace_dir = os.path.abspath(workspace_dir)

        # Create directory if it doesn't exist
        if not os.path.exists(workspace_dir):
            try:
                os.makedirs(workspace_dir, exist_ok=True)
                self.output_terminal.append_success(f"Created workspace directory: {workspace_dir}")
            except Exception as e:
                self.output_terminal.append_error(f"Failed to create workspace directory: {e!s}")
                return

        # Open directory in system file manager
        try:
            system = platform.system()
            if system == "Windows":
                # Use os.startfile for more reliable Windows behavior
                os.startfile(workspace_dir)
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", workspace_dir])
            elif system == "Linux":
                subprocess.Popen(["xdg-open", workspace_dir])
            else:
                self.output_terminal.append_warning(f"Unsupported platform: {system}")
                return

            self.output_terminal.append_output(f"Opened workspace directory: {workspace_dir}")
        except Exception as e:
            self.output_terminal.append_error(f"Failed to open workspace directory: {e!s}")

    def show_syntax_errors_in_terminal(self, errors):
        """Show syntax errors in the output terminal."""
        if not self.output_terminal:
            return

        self.output_terminal.append_output("=== Syntax Errors ===")
        for error in errors:
            error_msg = "Line " + str(error.line) + ", Column " + str(error.column) + ": " + error.message
            self.output_terminal.append_error(error_msg)

        self.output_terminal.append_output("=" * 30)

    def set_working_directory(self, path: str):
        """Set the working directory for the file explorer."""
        if self.file_explorer:
            self.file_explorer.set_root_path(path)

    def setup_workspace(self):
        """Setup workspace directory and Python path."""
        # Add workspace to Python path
        self.settings_manager.add_workspace_to_python_path()

        # Set file explorer root to workspace directory
        workspace_dir = self.settings_manager.get_workspace_directory()

        if workspace_dir and os.path.exists(workspace_dir):
            # Workspace directory exists, use it
            self.set_working_directory(workspace_dir)
        elif workspace_dir:
            # Workspace directory configured but doesn't exist yet
            # Create it and set as root
            try:
                os.makedirs(workspace_dir, exist_ok=True)
                self.set_working_directory(workspace_dir)
                logger.info(f"Created workspace directory: {workspace_dir}")
            except Exception as e:
                logger.error(f"Failed to create workspace directory: {e}")
                # Fallback to home directory
                self._setup_fallback_directory()
        else:
            # No workspace configured, use fallback
            self._setup_fallback_directory()

    def _setup_fallback_directory(self):
        """Setup fallback directory when workspace is not available."""
        from .....lib_ui.qt_compat import QDir

        # Try home directory as fallback
        home_path = QDir.homePath()
        if home_path and os.path.exists(home_path):
            self.set_working_directory(home_path)
            logger.info(f"Using fallback directory: {home_path}")
        else:
            logger.warning("No valid directory found for file explorer")

    def toggle_file_explorer(self):
        """Toggle the visibility of the file explorer panel."""
        if not self.file_explorer or not hasattr(self, "main_splitter"):
            return

        if self.file_explorer.isVisible():
            # Save current width before hiding
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[0] > 0:
                self.settings_manager.set("layout.explorer_width", sizes[0])
            # Hide the explorer
            self.file_explorer.hide()
            self.settings_manager.set("layout.explorer_visible", False)
        else:
            # Show the explorer
            self.file_explorer.show()
            self.settings_manager.set("layout.explorer_visible", True)
            # Restore saved width
            saved_width = self.settings_manager.get("layout.explorer_width", 200)
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2:
                total = sum(sizes)
                self.main_splitter.setSizes([saved_width, total - saved_width])
        # Save settings
        self.settings_manager.save_settings()

    def closeEvent(self, event):
        """Handle main window close event."""
        # Save current content to auto-save before closing
        if self.autosave_manager:
            self.autosave_manager.flush_backups()  # Flush any pending backups first
            self.autosave_manager.auto_save_all()
            self.autosave_manager.stop_auto_save()

        # Save current session state
        self.session_manager.save_session_state()

        # Save settings before closing
        self.layout_manager.save_settings()

        # Close find/replace dialog if open
        if hasattr(self, "shortcut_handler") and self.shortcut_handler.find_replace_dialog:
            self.shortcut_handler.find_replace_dialog.close()

        # Cleanup native execution bridge if exists
        if hasattr(self, "execution_manager") and self.execution_manager.native_bridge:
            self.execution_manager.native_bridge.cleanup()

        super().closeEvent(event)

    def resizeEvent(self, event):
        """Handle resize events to ensure proper layout."""
        super().resizeEvent(event)

    def showEvent(self, event):
        """Handle show events to ensure proper initial layout."""
        super().showEvent(event)

        # Force a layout update when shown in Maya
        self.updateGeometry()
