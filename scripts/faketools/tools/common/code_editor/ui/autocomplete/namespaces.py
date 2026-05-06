"""Resolve live execution namespaces for jedi.Interpreter.

Two sources are merged in priority order:

1. The editor's own ``exec_globals`` (populated by
   :func:`build_exec_globals` with ``cmds`` / ``om2`` / ``om`` and
   whatever the user's Run has added since). Discovered by walking the
   editor's parent chain — the dict lives on a host widget further up.
2. Maya's ``__main__.__dict__``. This catches modules the user imported
   in Maya's Script Editor but never executed inside our editor —
   without it, ``import eST3`` done at the Maya prompt would be
   invisible to the popup until the user ran *any* code through our
   Run button (which syncs ``__main__`` into ``exec_globals``).
"""

from logging import getLogger

logger = getLogger(__name__)


def collect_exec_namespaces(editor) -> list[dict]:
    """Return the dicts jedi.Interpreter should consult for ``editor``.

    The caller is expected to invoke this fresh on every completion
    dispatch — ``exec_globals`` and ``__main__`` both mutate while the
    user types, and caching would freeze the popup against a snapshot
    the user can no longer see.
    """
    namespaces: list[dict] = []
    node = editor.parent()
    while node is not None:
        exec_globals = getattr(node, "exec_globals", None)
        if isinstance(exec_globals, dict):
            namespaces.append(exec_globals)
            break
        node = node.parent() if hasattr(node, "parent") else None

    try:
        import __main__

        main_dict = getattr(__main__, "__dict__", None)
        # Identity check, not ``in`` — value comparison would compare every
        # key/value pair across exec_globals and __main__.__dict__, which
        # both can be large in a Maya session and which gets called on every
        # autocomplete dispatch.
        if isinstance(main_dict, dict) and all(d is not main_dict for d in namespaces):
            namespaces.append(main_dict)
    except Exception as exc:
        logger.debug(f"failed to attach __main__ to namespaces: {exc}")

    return namespaces


__all__ = ["collect_exec_namespaces"]
