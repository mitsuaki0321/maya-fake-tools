"""Side-panel widgets attached to the main window.

Exports the high-level widgets the main window assembles. Internal modules
(e.g. ``maya_terminal``) are loaded by ``output_terminal`` and not re-exported.
"""

from .file_explorer import FileExplorer
from .output_terminal import OutputTerminal

__all__ = ["FileExplorer", "OutputTerminal"]
