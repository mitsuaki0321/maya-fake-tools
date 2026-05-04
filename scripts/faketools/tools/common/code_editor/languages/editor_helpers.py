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


def dispatch_inspection(editor, header: str, code: str) -> None:
    """Run a language-specific inspection snippet against the editor's executer.

    Resolves the host window's ``execution_manager`` from ``editor``, prints
    ``header`` to its output terminal (when set), and feeds ``code`` to
    ``execute_inspection_code`` so the snippet runs silently in Maya without
    echoing into the user-visible code stream.

    Args:
        editor: The :class:`CodeEditor` whose ancestor chain hosts the
            execution manager.
        header (str): Line written verbatim to the output terminal before the
            snippet runs (e.g. ``"\\n=== myObj ==="``). Pass an empty string
            to skip the header.
        code (str): Source to execute through
            :meth:`ExecutionManager.execute_inspection_code`.
    """
    exec_manager = find_execution_manager(editor)
    if exec_manager is None:
        return
    if header and exec_manager.output_terminal:
        exec_manager.output_terminal.append_output(header)
    exec_manager.execute_inspection_code(code)


__all__ = ["dispatch_inspection", "find_execution_manager"]
