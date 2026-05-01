"""
Main window for Code Editor.
Provides the primary UI layout and coordinates between components.
"""

from logging import getLogger
import os

from .....lib_ui.qt_compat import QWidget
from ..command import maya_shelf, os_launcher
from ..command.execution import build_exec_globals
from ..languages import PYTHON
from ..settings import SettingsManager
from .dialog_base import CodeEditorMessageBox
from .execution_manager import ExecutionManager
from .file_operations_controller import FileOperationsController
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

        # Persistent execution environment (like Maya Script Editor)
        self.exec_globals = build_exec_globals()
        self.toolbar = None

        # Initialize execution manager
        self.execution_manager = ExecutionManager(self)

        # File-operation coordinator (open/save/new/rename/delete/execute)
        self.file_ops = FileOperationsController(self)

        # Initialize shortcut handler
        self.shortcut_handler = ShortcutHandler(self)

        # Initialize UI layout manager
        self.layout_manager = UILayoutManager(self)

        # Initialize session manager
        self.session_manager = UISessionManager(self)

        self.layout_manager.init_ui()
        self.layout_manager.apply_theme()
        self.layout_manager.connect_signals()
        self.shortcut_handler.setup_shortcuts()
        self.layout_manager.apply_font_settings()
        self.setup_workspace()
        self.layout_manager.restore_settings()

    def get_current_editor(self):
        """Get the currently active editor widget."""
        if self.code_editor:
            return self.code_editor.currentWidget()
        return None

    def fold_all(self):
        """Fold all foldable regions in the current editor."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, "fold_manager"):
            editor.fold_manager.fold_all()

    def unfold_all(self):
        """Unfold all folded regions in the current editor."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, "fold_manager"):
            editor.fold_manager.unfold_all()

    def add_to_shelf(self):
        """Add currently selected code to the active Maya shelf."""
        # Get selected text from current editor
        editor = self.get_current_editor()
        if not editor:
            return

        selected_text = editor.textCursor().selectedText()
        if not selected_text:
            CodeEditorMessageBox.information(self, "Add to Shelf", "Please select the code you want to add to the shelf.")
            return

        # QTextCursor uses Unicode paragraph separator (U+2029) for line breaks
        code = selected_text.replace("\u2029", "\n")
        language = getattr(editor, "language", PYTHON)

        ok, info = maya_shelf.add_to_active_shelf(code, language=language)
        if not ok:
            CodeEditorMessageBox.warning(self, "Add to Shelf", f"Failed to add code to shelf:\n{info}")

    def open_workspace_directory(self):
        """Open the workspace directory in the host OS file manager."""
        if hasattr(self.file_explorer, "root_path") and self.file_explorer.root_path:
            workspace_dir = self.file_explorer.root_path
        else:
            workspace_dir = self.settings_manager.get_workspace_directory()

        ok, error = os_launcher.open_directory(workspace_dir)
        if ok:
            self.output_terminal.append_output(f"Opened workspace directory: {workspace_dir}")
        else:
            self.output_terminal.append_error(error)

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

    def closeEvent(self, event):
        """Handle main window close event."""
        # Save current session state
        self.session_manager.save_session_state()

        # Save settings before closing
        self.layout_manager.save_settings()

        # Close find/replace dialog if open
        if hasattr(self, "shortcut_handler") and self.shortcut_handler.find_replace_dialog:
            self.shortcut_handler.find_replace_dialog.close()

        # Cleanup every cached execution bridge (one per language) so each
        # hidden Maya window is deleted.
        if hasattr(self, "execution_manager"):
            self.execution_manager.cleanup_bridges()

        super().closeEvent(event)

    def resizeEvent(self, event):
        """Handle resize events to ensure proper layout."""
        super().resizeEvent(event)

    def showEvent(self, event):
        """Handle show events to ensure proper initial layout."""
        super().showEvent(event)

        # Force a layout update when shown in Maya
        self.updateGeometry()
