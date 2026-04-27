"""Autocomplete (jedi-backed) for the editor.

The controller in :mod:`.controller` is the public entry point. The worker is
exposed too because the help popup submits its own ``DocstringRunnable`` to
the same thread pool. :func:`get_shared_engine` returns the process-wide
:class:`JediEngine`, configuring Maya stub paths on first use.
"""

from ._stubs import get_shared_engine
from .controller import AutocompleteController
from .worker import CompletionRunnable, DocstringRunnable

__all__ = ["AutocompleteController", "CompletionRunnable", "DocstringRunnable", "get_shared_engine"]
