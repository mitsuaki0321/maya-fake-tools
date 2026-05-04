"""Tab widget that hosts one editor per open file.

Public exports:

* :class:`CodeEditorWidget` -- the ``QTabWidget`` subclass that owns
  per-tab editor lifecycle (new / open / close / preview / save).
* :class:`EditableTabBar` -- the custom tab bar that paints the
  language accent strip on top of every tab.
* :class:`UISessionManager` -- saves / restores the open-tab list
  through :class:`SettingsManager` so the editor reopens with the
  same tabs the user had last time.

Internals (the per-tab session-state book-keeping in
:mod:`.session_manager`, the custom tab bar paint logic in
:mod:`.tab_bar`) live as sibling modules; the ``CodeEditorWidget``
class wires them together.
"""

from __future__ import annotations

from .session_manager import UISessionManager
from .tab_bar import EditableTabBar
from .widget import CodeEditorWidget

__all__ = ["CodeEditorWidget", "EditableTabBar", "UISessionManager"]
