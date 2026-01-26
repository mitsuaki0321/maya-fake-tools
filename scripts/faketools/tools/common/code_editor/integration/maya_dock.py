"""
Maya docking integration for the code editor.
Handles WorkspaceControl creation and Maya UI integration.
"""

import contextlib

try:
    import maya.cmds as cmds  # type: ignore
    import maya.OpenMayaUI as omui  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    # Maya not available - this module won't be used outside Maya
    MAYA_AVAILABLE = False
    cmds = None
    omui = None

from .....lib_ui.qt_compat import QVBoxLayout, QWidget, shiboken


class MayaDock:
    """Manages Maya WorkspaceControl for docking the code editor."""

    CONTROL_NAME = "MayaCodeEditorWorkspaceControl"
    WINDOW_TITLE = "Maya Code Editor"

    def __init__(self, widget: QWidget):  # type: ignore
        self.widget = widget
        self.workspace_control = None

    def create_docked_widget(self):
        """Create and dock the widget in Maya's UI."""
        if not MAYA_AVAILABLE:
            return None

        # Delete existing control if it exists
        if cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            # First unparent the widget to prevent deletion
            if self.widget and self.widget.parent():
                self.widget.setParent(None)
            cmds.deleteUI(self.CONTROL_NAME)

        # Also check with the instance variable name
        if self.workspace_control and self.workspace_control != self.CONTROL_NAME and cmds.workspaceControl(self.workspace_control, exists=True):
            cmds.deleteUI(self.workspace_control)

        # Reset workspace control state by deleting preferences if needed
        with contextlib.suppress(Exception):
            # Try to reset the workspace state to ensure it doesn't retain floating state
            cmds.workspaceControlState(self.CONTROL_NAME, remove=True)

        # Create new WorkspaceControl
        self.workspace_control = cmds.workspaceControl(
            self.CONTROL_NAME,
            label=self.WINDOW_TITLE,
            dockToControl=["ChannelBoxLayerEditor", "left"],  # Dock to left of Channel Box
            initialWidth=900,
            initialHeight=600,
            minimumWidth=600,  # Increased minimum width to prevent clipping
            widthProperty="free",  # Allow free resizing
            heightProperty="free",  # Allow free resizing
            retain=False,  # Don't retain position between sessions
            floating=False,  # Start docked
            loadImmediately=True,
            visible=True,  # Make it visible immediately
        )

        # Check if it was actually created as docked
        if cmds.workspaceControl(self.workspace_control, exists=True):
            actual_floating = cmds.workspaceControl(self.workspace_control, query=True, floating=True)

            # If Maya created it as floating despite our request, force it to dock
            if actual_floating:
                # Delete and recreate with a different approach
                cmds.deleteUI(self.workspace_control)

                # Create with dockToMainWindow to force docking
                self.workspace_control = cmds.workspaceControl(
                    self.CONTROL_NAME,
                    label=self.WINDOW_TITLE,
                    dockToMainWindow=("right", 1),  # Dock to right side of main window
                    initialWidth=900,
                    initialHeight=600,
                    minimumWidth=600,
                    widthProperty="free",
                    heightProperty="free",
                    retain=False,
                    floating=False,
                    loadImmediately=True,
                    visible=True,
                )

        # Get the WorkspaceControl's widget pointer
        control_widget = omui.MQtUtil.findControl(self.CONTROL_NAME)
        if control_widget:
            control_widget_ptr = int(control_widget)
            # Convert to QWidget and add our widget
            if shiboken:
                maya_widget = shiboken.wrapInstance(control_widget_ptr, QWidget)
            else:
                raise RuntimeError("shiboken not available for Maya integration")

            # Check if widget is still valid before parenting
            try:
                if self.widget:
                    self.widget.isVisible()  # Test if C++ object is still valid

                    # Set our widget as the central widget
                    self.widget.setParent(maya_widget)

                    # Create layout for the Maya widget if it doesn't exist
                    if not maya_widget.layout():
                        layout = QVBoxLayout(maya_widget)
                        layout.setContentsMargins(0, 0, 0, 0)
                        layout.addWidget(self.widget)
                    else:
                        maya_widget.layout().addWidget(self.widget)

                    # Ensure widget is visible
                    self.widget.show()
                    maya_widget.show()
            except RuntimeError as e:
                # Widget was deleted, can't parent it
                raise RuntimeError("Widget is no longer valid - please recreate the editor") from e

        # After creating, ensure the workspace is visible and selected
        if self.workspace_control:
            cmds.workspaceControl(self.workspace_control, edit=True, visible=True)
            cmds.workspaceControl(self.workspace_control, edit=True, restore=True)
            # Try to select the tab
            with contextlib.suppress(Exception):
                cmds.workspaceControl(self.workspace_control, edit=True, selectTab=True)

        return self.workspace_control

    def show(self):
        """Show the docked widget."""
        if not MAYA_AVAILABLE:
            return
        # Check both the class constant name and the instance variable
        workspace_exists = False
        actual_workspace_name = None

        if cmds.workspaceControl(self.CONTROL_NAME, exists=True):
            workspace_exists = True
            actual_workspace_name = self.CONTROL_NAME
        elif self.workspace_control and cmds.workspaceControl(self.workspace_control, exists=True):
            workspace_exists = True
            actual_workspace_name = self.workspace_control

        if workspace_exists and actual_workspace_name:
            # Check if workspace is currently floating
            is_floating = cmds.workspaceControl(actual_workspace_name, query=True, floating=True)

            if is_floating:
                # First unparent the widget
                if self.widget and self.widget.parent():
                    self.widget.setParent(None)
                # Delete the floating workspace
                cmds.deleteUI(actual_workspace_name)
                self.workspace_control = None
                # Recreate as docked
                self.create_docked_widget()
                return

            # Show the workspace
            cmds.workspaceControl(actual_workspace_name, edit=True, visible=True)
            cmds.workspaceControl(actual_workspace_name, edit=True, restore=True)

            # Force the workspace to be selected/active
            with contextlib.suppress(Exception):
                # Try to make it the active tab in its dock area
                cmds.workspaceControl(actual_workspace_name, edit=True, selectTab=True)

            # Ensure the widget is visible
            if self.widget:
                self.widget.show()
        else:
            # Create new workspace if it doesn't exist
            self.create_docked_widget()

    def hide(self):
        """Hide the docked widget."""
        if not MAYA_AVAILABLE:
            return
        if self.workspace_control and cmds.workspaceControl(self.workspace_control, exists=True):
            cmds.workspaceControl(self.workspace_control, edit=True, visible=False)

    def close(self):
        """Close and cleanup the docked widget."""
        if not MAYA_AVAILABLE:
            return
        if self.workspace_control and cmds.workspaceControl(self.workspace_control, exists=True):
            cmds.deleteUI(self.workspace_control)
