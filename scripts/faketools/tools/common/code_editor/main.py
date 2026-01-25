"""
Main entry point for Maya Code Editor.
Handles initialization and Maya integration.
"""

from logging import getLogger
import sys

from .ui.qt_compat import QApplication, Qt

logger = getLogger(__name__)

# Import Maya modules
try:
    import maya.cmds as cmds  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    logger.info("Maya not available - running in standalone mode")

from .integration.maya_dock import MayaDock  # noqa: E402
from .ui.main_window import MayaCodeEditor  # noqa: E402

# Global reference to keep the editor alive
_editor_instance = None
_dock_instance = None


def show_editor(floating=False):
    """Show the Maya Code Editor.

    Args:
        floating: If True, show as floating window instead of docked (Maya only)
    """
    global _editor_instance, _dock_instance

    if MAYA_AVAILABLE:
        # Maya integration mode
        # Check if C++ object is still valid
        try:
            if _editor_instance is not None:
                _editor_instance.isVisible()
        except RuntimeError:
            # C++ object was deleted, reset instances
            _editor_instance = None
            _dock_instance = None

        if floating:
            # Hide workspace control if it exists (don't close/delete)
            if _dock_instance:
                _dock_instance.hide()
                # Don't delete the dock instance, we might need it later

            # Create new floating instance if needed
            if _editor_instance is None:
                _editor_instance = MayaCodeEditor()
                _setup_maya_callbacks(_editor_instance)

            # Get Maya main window as parent for floating window
            maya_main_window = None
            try:
                import maya.OpenMayaUI as omui

                from .ui.qt_compat import QWidget, shiboken

                maya_main_ptr = omui.MQtUtil.mainWindow()
                if maya_main_ptr:
                    maya_main_window = shiboken.wrapInstance(int(maya_main_ptr), QWidget)
            except Exception:
                pass

            # Important: Set Maya main window as parent for floating window
            if maya_main_window:
                _editor_instance.setParent(maya_main_window)
            else:
                _editor_instance.setParent(None)

            # Show as floating window
            _editor_instance.setWindowFlags(Qt.Window)
            _editor_instance.resize(1000, 700)
            _editor_instance.show()
        else:
            # Docked mode
            # Check if we need to create a new instance
            try:
                if _editor_instance is not None:
                    _editor_instance.isVisible()
            except RuntimeError:
                # C++ object was deleted, need to recreate
                _editor_instance = None
                _dock_instance = None

            if _editor_instance is None:
                _editor_instance = MayaCodeEditor()
                _dock_instance = MayaDock(_editor_instance)
                _setup_maya_callbacks(_editor_instance)
                # Create docked widget immediately
                _dock_instance.create_docked_widget()
            else:
                # Editor exists, check if we need to switch from floating to docked
                if _editor_instance.windowFlags() & Qt.Window:
                    # Currently floating, need to dock it
                    _editor_instance.hide()
                    # Reset window flags for docking
                    _editor_instance.setWindowFlags(Qt.Widget)

                    # Create or recreate dock instance
                    if _dock_instance is None:
                        _dock_instance = MayaDock(_editor_instance)

                    # Create the docked widget
                    _dock_instance.create_docked_widget()
                else:
                    # Already docked, just show it
                    if _dock_instance is None:
                        _dock_instance = MayaDock(_editor_instance)
                        _dock_instance.create_docked_widget()
                    else:
                        # Check if workspace exists and is floating
                        if _dock_instance.workspace_control and cmds.workspaceControl(_dock_instance.workspace_control, exists=True):
                            is_floating = cmds.workspaceControl(
                                _dock_instance.workspace_control,
                                query=True,
                                floating=True,
                            )
                            if is_floating:
                                # If floating, recreate to force docking
                                _dock_instance.create_docked_widget()
                            else:
                                _dock_instance.show()
                        else:
                            _dock_instance.show()

        # Working directory will be set by workspace setup in main window

    else:
        # Standalone mode for testing
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        _editor_instance = MayaCodeEditor()
        _editor_instance.show()

        if app is not None:
            app.exec_()


def _setup_maya_callbacks(editor_instance):
    """Setup Maya callbacks for automatic session saving."""
    if not MAYA_AVAILABLE:
        return

    try:
        import maya.api.OpenMaya as om2  # type: ignore

        def save_session_callback(client_data):
            """Callback to save session state."""
            if editor_instance and hasattr(editor_instance, "session_manager"):
                editor_instance.session_manager.save_session_state()

        # Register callback for Maya exit
        callback_id = om2.MSceneMessage.addCallback(om2.MSceneMessage.kMayaExiting, save_session_callback)

        # Store callback ID for cleanup if needed
        if not hasattr(editor_instance, "_maya_callbacks"):
            editor_instance._maya_callbacks = []
        editor_instance._maya_callbacks.append(callback_id)

    except Exception as e:
        logger.error(f"Failed to setup Maya callbacks: {e}")


def hide_editor():
    """Hide the Maya Code Editor."""
    global _dock_instance

    if _dock_instance:
        _dock_instance.hide()


def close_editor():
    """Close the Maya Code Editor."""
    global _editor_instance, _dock_instance

    if _dock_instance:
        _dock_instance.close()

    _editor_instance = None
    _dock_instance = None


def get_editor():
    """Get the current editor instance."""
    return _editor_instance


def reload_editor_dev():
    """
    Reload the editor for development purposes.

    This function clears all maya_code_editor modules from memory
    and reloads the editor. Useful during development to apply changes
    without restarting Maya.
    """
    try:
        # Use the module cleaner to clean up
        from . import module_cleaner

        module_cleaner.cleanup()

        # Reload editor (show_editor is defined in this module)
        show_editor()
        logger.info("Maya Code Editor reloaded successfully!")
    except Exception as e:
        logger.error(f"Failed to reload editor: {str(e)}")


def show_ui():
    """Show the Code Editor UI.

    This is the FakeTools standard entry point for the menu system.
    """
    show_editor()
