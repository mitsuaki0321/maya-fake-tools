"""Side-panel widgets attached to the main window.

Exports the high-level widgets the main window assembles. Internal modules
(e.g. ``maya_terminal``) are loaded by ``output_terminal`` and not re-exported.
"""

from .file_explorer import FileExplorer
from .output_terminal import DEFAULT_FONT_FAMILY, OutputTerminal

__all__ = ["DEFAULT_FONT_FAMILY", "FileExplorer", "OutputTerminal"]
