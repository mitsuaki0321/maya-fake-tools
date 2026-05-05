"""Themed dialog widgets for the Code Editor.

Public exports:

* :class:`CodeEditorDialog`, :class:`CodeEditorMessageBox`,
  :class:`CodeEditorInputDialog`, :class:`CodeEditorFileDialog` --
  themed wrappers from :mod:`.base` that drop the dialog over the
  editor window and apply the standard palette / fonts.
* :class:`FindReplaceDialog` -- the search/replace dialog from
  :mod:`.find_replace`.

Consumers should import from this package (``from .dialogs import
CodeEditorMessageBox``) rather than reaching into individual modules.
"""

from __future__ import annotations

from .base import (
    CodeEditorDialog,
    CodeEditorFileDialog,
    CodeEditorInputDialog,
    CodeEditorMessageBox,
    DialogPositioner,
)
from .find_replace import (
    FindReplaceDialog,
    find_next,
    find_previous,
    show_find_dialog,
    show_replace_dialog,
)

__all__ = [
    "CodeEditorDialog",
    "CodeEditorFileDialog",
    "CodeEditorInputDialog",
    "CodeEditorMessageBox",
    "DialogPositioner",
    "FindReplaceDialog",
    "find_next",
    "find_previous",
    "show_find_dialog",
    "show_replace_dialog",
]
