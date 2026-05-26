"""Editor insert commands — text snippets injected at the cursor.

Each command is a small subclass of :class:`EditorInsertCommand`. It owns
two things: whether it is available for a given language (:meth:`supports`)
and the text it produces (:meth:`build_text`). The actual cursor insertion
and any user notification live in the UI layer; this module stays
Qt-independent (Maya API calls are allowed).

Adding a new insert command = write a subclass and append an instance to
:data:`INSERT_COMMANDS`. The toolbar split-button enumerates that list
automatically, so no UI code needs to change.

Language-specific formatting (e.g. Python ``["a", "b"]`` vs a future MEL
``{"a", "b"}``) is delegated to ``LanguageProfile.format_string_*`` hooks,
so a command's :meth:`build_text` never branches on language itself. A
command is simply unavailable for languages whose profile leaves those
hooks unset (``supports`` returns ``False``).
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional

from ..languages import LanguageProfile

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    cmds = None  # type: ignore[assignment]
    MAYA_AVAILABLE = False
    logger.debug("Maya commands not available")


def get_selected_node_names() -> list[str]:
    """Return the names of the currently selected nodes.

    Uses ``cmds.ls(selection=True)`` so the names are Maya's shortest
    unique form (the same strings shown in the outliner / channel box).

    Returns:
        list[str]: Selected node names, or an empty list when nothing is
        selected or Maya is unavailable.
    """
    if not MAYA_AVAILABLE:
        return []
    return cmds.ls(selection=True) or []


class EditorInsertCommand:
    """Base class for a command that inserts text at the editor cursor.

    Attributes:
        name (str): Stable identifier used as a settings key and as the
            payload emitted by the toolbar.
        label (str): Human-readable text shown in the toolbar menu.
    """

    name: str = ""
    label: str = ""

    def supports(self, language: LanguageProfile) -> bool:
        """Return whether this command is usable for ``language``.

        Args:
            language (LanguageProfile): The active tab's language profile.

        Returns:
            bool: ``True`` when the command can produce text for the
            language. Subclasses typically gate on the presence of the
            ``LanguageProfile.format_string_*`` hooks they rely on.
        """
        raise NotImplementedError

    def build_text(self, language: LanguageProfile) -> Optional[str]:
        """Build the text to insert, formatted for ``language``.

        Args:
            language (LanguageProfile): The active tab's language profile,
                used for literal formatting.

        Returns:
            Optional[str]: The text to insert, or ``None`` when there is
            nothing to insert (e.g. no selection) so the UI can notify
            instead of inserting an empty value.
        """
        raise NotImplementedError


class InsertSelectedNodeName(EditorInsertCommand):
    """Insert the first selected node's name as a single string literal."""

    name = "insert_selected_node_name"
    label = "Selected Node Name"

    def supports(self, language: LanguageProfile) -> bool:
        return language is not None and language.format_string_literal is not None

    def build_text(self, language: LanguageProfile) -> Optional[str]:
        names = get_selected_node_names()
        if not names:
            return None
        return language.format_string_literal(names[0])


class InsertSelectedNodeNames(EditorInsertCommand):
    """Insert all selected node names as a language-native list literal."""

    name = "insert_selected_node_names"
    label = "Selected Node Names (List)"

    def supports(self, language: LanguageProfile) -> bool:
        return language is not None and language.format_string_list is not None

    def build_text(self, language: LanguageProfile) -> Optional[str]:
        names = get_selected_node_names()
        if not names:
            return None
        return language.format_string_list(names)


# Registry — order defines the toolbar menu order and the first entry is the
# initial default. Append a subclass instance here to expose a new command.
INSERT_COMMANDS: list[EditorInsertCommand] = [
    InsertSelectedNodeName(),
    InsertSelectedNodeNames(),
]


def get_insert_command(name: str) -> Optional[EditorInsertCommand]:
    """Look up a registered insert command by its ``name``.

    Args:
        name (str): The command's stable identifier.

    Returns:
        Optional[EditorInsertCommand]: The matching command, or ``None``.
    """
    for command in INSERT_COMMANDS:
        if command.name == name:
            return command
    return None


__all__ = [
    "EditorInsertCommand",
    "InsertSelectedNodeName",
    "InsertSelectedNodeNames",
    "INSERT_COMMANDS",
    "get_insert_command",
    "get_selected_node_names",
]
