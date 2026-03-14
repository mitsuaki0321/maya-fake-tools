"""vpcomp.ui — Qt-based layer panel UI for VP Compositor."""

__all__ = ["show_ui"]


def show_ui():
    """Show the VP Compositor UI."""
    from .layer_ui import show_ui

    show_ui()
