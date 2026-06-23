"""UI module for Code Editor."""

# Lazy imports to avoid circular dependencies
# Import these directly when needed instead of from __init__

__all__ = ["CodeEditorWidget", "FileExplorer", "MayaCodeEditor", "OutputTerminal", "ToolBar", "show_ui"]


def show_ui(floating: bool = False):
    """Show the Code Editor UI.

    This is the FakeTools standard entry point for the menu system.

    Args:
        floating (bool): If True, show as a floating window instead of docked (Maya only).
    """
    from ..main import show_editor

    show_editor(floating=floating)
