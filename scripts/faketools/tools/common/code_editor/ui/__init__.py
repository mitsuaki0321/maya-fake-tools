"""UI module for Maya Code Editor."""

# Lazy imports to avoid circular dependencies
# Import these directly when needed instead of from __init__

__all__ = ["CodeEditorWidget", "FileExplorer", "MayaCodeEditor", "OutputTerminal", "ToolBar", "show_ui"]


def show_ui():
    """Show the Code Editor UI.

    This is the FakeTools standard entry point for the menu system.
    """
    from ..main import show_editor

    show_editor()
