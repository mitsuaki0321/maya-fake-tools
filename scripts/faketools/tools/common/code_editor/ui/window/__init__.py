"""Window-level UI: the top-level widget plus its layout / toolbar / shortcuts.

Public exports:

* :class:`MayaCodeEditor` -- the main ``QWidget`` that hosts the
  whole editor (file explorer, tab widget, output terminal,
  toolbar). Constructed by :mod:`code_editor.main` and docked into
  Maya by :mod:`code_editor.integration.maya_dock`.
* :class:`UILayoutManager` -- builds the splitter / panel layout and
  wires every signal the toolbar / file-explorer / shortcut handler
  emit to its target controller.
* :class:`ToolBar` -- VSCode-style toolbar widget (toggle explorer,
  Run, Save, New File per language, etc.).
* :class:`ShortcutHandler` -- window-scoped ``QShortcut`` bindings
  (Ctrl+N / Ctrl+S / Ctrl+F / Ctrl+/ / Ctrl+Enter / ...).
"""

from __future__ import annotations

from .layout_manager import UILayoutManager
from .main import MayaCodeEditor
from .shortcut_handler import ShortcutHandler
from .toolbar import ToolBar

__all__ = ["MayaCodeEditor", "ShortcutHandler", "ToolBar", "UILayoutManager"]
