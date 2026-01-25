"""Maya Code Editor - Python code editor with native Maya integration."""

TOOL_CONFIG = {
    "name": "Code Editor",
    "version": "1.0.0",
    "description": "Python code editor with syntax highlighting and Maya integration",
    "menu_label": "Code Editor",
    "menu_order": 10,
    "requires_selection": False,
    "author": "FakeTools",
    "category": "common",
}


def show_ui():
    """Show the Code Editor UI."""
    from .main import show_editor

    show_editor()


__all__ = ["TOOL_CONFIG", "show_ui"]
