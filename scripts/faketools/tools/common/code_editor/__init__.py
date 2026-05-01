"""Code Editor — multi-language code editor with native Maya integration.

Python is the only registered language at the moment; the editor's
behaviour (highlighting, run target, comment toggle, ``Add to Shelf``,
context menu) is driven by ``LanguageProfile`` instances under
``languages/`` so additional languages plug in without touching the
editor widgets themselves.
"""

TOOL_CONFIG = {
    "name": "Code Editor",
    "version": "1.0.0",
    "description": "Multi-language code editor with syntax highlighting and Maya integration",
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
