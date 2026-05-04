"""Python autocomplete-engine factory for the language profile.

Lazy imports so the ``code_editor.languages`` package stays Qt- and
jedi-free at module import time. The shared engine is a process-wide
:class:`JediEngine` -- :func:`get_shared_engine` configures Maya stub
paths on its first call and caches the engine for every subsequent
caller, so opening multiple Python tabs reuses the same instance.
"""

from __future__ import annotations


def python_completion_engine_factory():
    """Return the process-wide :class:`JediEngine` for Python autocomplete."""
    from ...ui.autocomplete import get_shared_engine

    return get_shared_engine()


__all__ = ["python_completion_engine_factory"]
