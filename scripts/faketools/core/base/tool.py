"""
Base tool class for FakeTools.

Provides optional base class for tools. Tools are NOT required to inherit from this class.
This is provided as a convenience for tools that want standard metadata support.
"""

from typing import Optional

from ...lib_ui.qt_compat import QWidget


class BaseTool(QWidget):
    """
    Optional base class for FakeTools.

    Provides standard interface for tool metadata and lifecycle.
    Tools can inherit from this for convenience, but it's not required.

    Attributes:
        TOOL_NAME: Display name for the tool
        TOOL_VERSION: Tool version string
        TOOL_DESCRIPTION: Brief description of tool functionality
        TOOL_CATEGORY: Tool category (rig/model/anim/common)
    """

    TOOL_NAME = "Base Tool"
    TOOL_VERSION = "1.0.0"
    TOOL_DESCRIPTION = "Base tool class"
    TOOL_CATEGORY = "common"

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the base tool.

        Args:
            parent: Parent widget (typically Maya main window)
        """
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """
        Setup the tool UI.

        Override this method in subclasses to create the UI.
        """
        pass

    @classmethod
    def get_metadata(cls) -> dict[str, str]:
        """
        Get tool metadata.

        Returns:
            dict[str, str]: Dictionary containing tool metadata
        """
        return {
            "name": cls.TOOL_NAME,
            "version": cls.TOOL_VERSION,
            "description": cls.TOOL_DESCRIPTION,
            "category": cls.TOOL_CATEGORY,
        }

    def closeEvent(self, event):
        """
        Handle window close event.

        Override this method to perform cleanup when window closes.
        """
        super().closeEvent(event)


__all__ = ["BaseTool"]
