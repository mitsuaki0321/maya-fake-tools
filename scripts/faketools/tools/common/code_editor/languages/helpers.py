"""Cross-language helpers used by ``LanguageProfile`` action handlers.

These utilities don't belong to any single language — they encapsulate
the editor-side plumbing every language needs when its right-click
actions hand work over to the execution manager.
"""

from __future__ import annotations


def find_execution_manager(widget):
    """Walk up from ``widget`` to the main window and return its execution_manager.

    The historical lookup walked one extra ``parent.parent()`` hop because
    the editor sits inside a tab widget which sits inside the main window;
    that contract is preserved here.
    """
    node = widget.parent()
    while node is not None:
        parent = node.parent() if hasattr(node, "parent") else None
        if parent is not None and hasattr(parent, "execution_manager"):
            return parent.execution_manager
        node = parent
    return None


__all__ = ["find_execution_manager"]
