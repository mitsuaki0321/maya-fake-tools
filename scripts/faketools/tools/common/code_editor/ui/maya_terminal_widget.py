"""
Maya Native Terminal Widget using cmdScrollFieldReporter.
Provides authentic Maya Script Editor-like output display.
"""

from logging import getLogger

try:
    import maya.cmds as cmds
    import maya.OpenMayaUI as omui

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False

from .....lib_ui.qt_compat import QAction, QMenu, QSizePolicy, Qt, QVBoxLayout, QWidget

logger = getLogger(__name__)

if MAYA_AVAILABLE:
    try:
        from shiboken6 import wrapInstance
    except ImportError:
        from shiboken2 import wrapInstance


class MayaTerminalWidget(QWidget):
    """
    Maya native terminal widget using cmdScrollFieldReporter.
    Provides the same output display as Maya's Script Editor.
    """

    def __init__(self, parent=None):
        """Initialize the Maya terminal widget."""
        super().__init__(parent)

        self.history_reporter = None
        self.hidden_window = None
        self.qt_widget = None
        self._is_initialized = False
        self._context_menu_connected = False

        # Setup layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Initialize Maya terminal
        if MAYA_AVAILABLE:
            self.setup_maya_terminal()

    def setup_maya_terminal(self):
        """
        Create and embed Maya's native cmdScrollFieldReporter.
        This provides the same output as Maya's Script Editor.
        """
        if not MAYA_AVAILABLE:
            return False

        try:
            # Create unique window name to avoid conflicts
            window_name = f"codeEditorReporter_{id(self)}"

            # Delete existing window if it exists
            if cmds.window(window_name, exists=True):
                cmds.deleteUI(window_name)

            # Create hidden window to host the reporter
            self.hidden_window = cmds.window(
                window_name,
                visible=False,
                retain=True,  # Prevent auto-deletion
                title="Code Editor Reporter",
            )

            # Add layout to window
            maya_layout = cmds.columnLayout(adjustableColumn=True)

            # Create Maya native reporter with smaller initial size
            self.history_reporter = cmds.cmdScrollFieldReporter(
                parent=maya_layout,
                width=400,  # Reduced from 800
                height=150,  # Reduced from 400
                # Output settings - match Script Editor behavior
                echoAllCommands=False,  # Don't echo all commands
                suppressErrors=False,  # Show errors
                suppressWarnings=False,  # Show warnings
                suppressInfo=False,  # Show info messages
                suppressResults=False,  # Show command results
                suppressStackTrace=False,  # Show stack traces
                lineNumbers=False,  # No line numbers (cleaner output)
                stackTrace=True,  # Enable stack trace for errors
                filterSourceType="",  # No filtering
            )

            # Get Qt widget from Maya control
            ptr = omui.MQtUtil.findControl(self.history_reporter)
            if ptr:
                self.qt_widget = wrapInstance(int(ptr), QWidget)

                # Override minimum size constraints
                self.qt_widget.setMinimumSize(100, 50)  # Allow much smaller minimum size
                self.qt_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                # Add to our layout
                self.layout.addWidget(self.qt_widget)

                # Make visible
                self.qt_widget.setVisible(True)

                self._is_initialized = True

                # Setup context menu after initialization
                self._setup_context_menu()

                # Initial message
                print("# Maya Code Editor Terminal")
                print("# " + "=" * 50)

                return True
            else:
                logger.error("Failed to get Maya terminal widget pointer")
                return False

        except Exception as e:
            logger.error(f"Error setting up Maya terminal: {e}")
            return False

    def is_available(self):
        """Check if Maya terminal is available and initialized."""
        return MAYA_AVAILABLE and self._is_initialized

    def _get_valid_widget(self):
        """Get a valid reference to the Qt widget, recreating if necessary."""
        if not self.history_reporter:
            return None

        # Try to use existing widget reference
        if self.qt_widget:
            try:
                # Test if widget is still valid
                self.qt_widget.isVisible()
                return self.qt_widget
            except RuntimeError:
                # Widget reference is invalid
                self.qt_widget = None

        # Try to recreate widget reference from Maya control
        try:
            ptr = omui.MQtUtil.findControl(self.history_reporter)
            if ptr:
                self.qt_widget = wrapInstance(int(ptr), QWidget)
                return self.qt_widget
        except Exception:
            pass

        return None

    def clear(self):
        """Clear the terminal output."""
        if self.history_reporter:
            try:
                # Check if the Maya control still exists
                if cmds.cmdScrollFieldReporter(self.history_reporter, exists=True):
                    cmds.cmdScrollFieldReporter(self.history_reporter, edit=True, clear=True)
                    print("# Terminal cleared")
                else:
                    logger.error("Terminal reporter no longer exists")
            except Exception as e:
                logger.error(f"Error clearing terminal: {e}")

    def append_output(self, text, prefix=""):
        """
        Append text to the terminal.
        Since we're using Maya's native reporter, we just print to stdout.

        Args:
            text: Text to display
            prefix: Optional prefix for the message
        """
        if not text:
            return

        if prefix:
            print(f"{prefix} {text}")
        else:
            print(text)

    def append_error(self, text):
        """Display error message."""
        # Maya will automatically format errors in red
        print(f"# Error: {text}")

    def append_warning(self, text):
        """Display warning message."""
        # Maya will automatically format warnings in yellow
        print(f"# Warning: {text}")

    def append_success(self, text):
        """Display success message."""
        print(f"# Success: {text}")

    def append_command(self, command):
        """Display executed command."""
        # Show command without prefix
        print(command)

    def append_result(self, result):
        """Display execution result."""
        if result is not None:
            print(f"# Result: {result}")

    def save_output(self, file_path):
        """
        Save terminal output to file.

        Args:
            file_path: Path to save the output

        Returns:
            bool: Success status
        """
        if not self.history_reporter:
            return False

        try:
            # Get text from reporter
            text = cmds.cmdScrollFieldReporter(self.history_reporter, query=True, text=True)

            # Write to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)

            self.append_success(f"Output saved to: {file_path}")
            return True

        except Exception as e:
            self.append_error(f"Failed to save output: {e}")
            return False

    def get_output_text(self):
        """
        Get all text from the terminal.

        Returns:
            str: Terminal text content
        """
        if not self.history_reporter:
            return ""

        try:
            return cmds.cmdScrollFieldReporter(self.history_reporter, query=True, text=True) or ""
        except Exception:
            return ""

    def cleanup(self):
        """Clean up Maya resources when widget is destroyed."""
        if self.hidden_window:
            try:
                if cmds.window(self.hidden_window, exists=True):
                    cmds.deleteUI(self.hidden_window)
            except Exception:
                pass

        self.history_reporter = None
        self.hidden_window = None
        self.qt_widget = None
        self._is_initialized = False

    def closeEvent(self, event):
        """Handle widget close event."""
        self.cleanup()
        super().closeEvent(event)

    def _setup_context_menu(self):
        """Setup context menu for the terminal."""
        if not self._context_menu_connected:
            try:
                if self.qt_widget:
                    # Test if widget is valid
                    self.qt_widget.isVisible()
                    # Enable custom context menu
                    self.qt_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                    self.qt_widget.customContextMenuRequested.connect(self._show_context_menu)
                    self._context_menu_connected = True
            except RuntimeError:
                # Widget reference is invalid, try to recreate it
                if self.history_reporter:
                    try:
                        ptr = omui.MQtUtil.findControl(self.history_reporter)
                        if ptr:
                            self.qt_widget = wrapInstance(int(ptr), QWidget)
                            self.qt_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                            self.qt_widget.customContextMenuRequested.connect(self._show_context_menu)
                            self._context_menu_connected = True
                    except Exception:
                        pass

    def _show_context_menu(self, position):
        """Show context menu at position."""
        # Check if qt_widget is still valid
        if not self.qt_widget:
            return

        try:
            # Test if widget is still valid by accessing a property
            self.qt_widget.isVisible()
        except RuntimeError:
            # Widget has been deleted, recreate reference
            if self.history_reporter:
                try:
                    ptr = omui.MQtUtil.findControl(self.history_reporter)
                    if ptr:
                        self.qt_widget = wrapInstance(int(ptr), QWidget)
                    else:
                        return
                except Exception:
                    return
            else:
                return

        # Create context menu with self as parent instead of qt_widget
        menu = QMenu(self)

        # Apply theme from AppTheme
        try:
            from ..themes.app_theme import AppTheme

            menu.setStyleSheet(AppTheme.get_menu_stylesheet())
        except Exception:
            pass

        # Copy action
        copy_action = QAction("Copy", menu)
        copy_action.triggered.connect(self._copy_selection)
        menu.addAction(copy_action)

        # Clear terminal action
        menu.addSeparator()
        clear_action = QAction("Clear Terminal", menu)
        clear_action.triggered.connect(self.clear)
        menu.addAction(clear_action)

        # Show menu at cursor position
        try:
            # Map position to global coordinates
            global_pos = self.qt_widget.mapToGlobal(position)
            menu.exec_(global_pos)
        except RuntimeError:
            # Fallback if widget reference is invalid
            menu.exec_(self.mapToGlobal(position))

    def _copy_selection(self):
        """Copy selected text to clipboard."""
        if not self.history_reporter:
            return

        try:
            # Check if the Maya control still exists
            if not cmds.cmdScrollFieldReporter(self.history_reporter, exists=True):
                print("# Error: Terminal reporter no longer exists")
                return

            # Use Maya's copySelection command
            cmds.cmdScrollFieldReporter(self.history_reporter, edit=True, copySelection=True)
        except Exception as e:
            logger.error(f"Error copying selection: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
