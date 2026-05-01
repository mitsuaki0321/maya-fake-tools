"""Right-click context menu for the editor widget.

Builds a ``QMenu`` populated with the editor's contextual actions:

* **Maya help** — appended when the cursor is on a recognised ``cmds.*``
  call. Language-agnostic.
* **Language-specific section** — delegated to the active editor's
  :class:`LanguageProfile.context_menu_extender` (e.g. Inspect Object /
  Inspect Help / Reload Module for Python; whatIs / Source File for MEL
  in Phase 1+). Skipped when the language doesn't provide an extender.
* **Add to Shelf** — appended when there is a selection and the language
  supports shelf buttons (gating handled by ``maya_shelf.add_to_active_shelf``
  itself).

Kept out of ``code_editor.py`` so the editor widget can stay focused on
text editing concerns; the menu is built fresh on every right click and
the actions are stateless beyond the editor reference they capture.
"""

from __future__ import annotations

from .....lib_ui.qt_compat import QAction, QTextCursor
from ..themes import AppTheme


def build_context_menu(editor, event):
    """Construct the populated right-click menu for ``editor``.

    Args:
        editor: The :class:`CodeEditor` instance receiving the event.
        event: The Qt ``QContextMenuEvent``.

    Returns:
        QMenu: A themed menu ready to be ``exec_()``-ed by the caller.
    """
    menu = editor.createStandardContextMenu()
    menu.setStyleSheet(AppTheme.get_menu_stylesheet())

    _maybe_add_maya_help(menu, editor)

    selected_text = editor.textCursor().selectedText().strip()
    if not selected_text:
        cursor = editor.cursorForPosition(event.pos())
        cursor.select(QTextCursor.WordUnderCursor)
        selected_text = cursor.selectedText().strip()

    extender = editor.language.context_menu_extender
    if selected_text and extender is not None:
        validator = editor.language.identifier_validator
        if validator is None or validator(selected_text):
            extender(menu, editor, selected_text)

    if editor.textCursor().hasSelection():
        menu.addSeparator()
        shelf_action = QAction("Add to Shelf", editor)
        shelf_action.triggered.connect(lambda: _add_selection_to_shelf(editor))
        menu.addAction(shelf_action)

    return menu


def _maybe_add_maya_help(menu, editor):
    """Append a Maya help action when a known ``cmds.*`` call is at the cursor."""
    # Lazy import: utils.maya_help_detector pulls Maya-aware helpers and
    # we want the menu code itself importable without that chain at load time.
    from ..utils.maya_help_detector import MayaHelpDetector

    settings_manager = _find_attr_in_parents(editor, "settings_manager")
    detector = MayaHelpDetector(settings_manager)

    cursor_position = editor.textCursor().position()
    text_content = editor.toPlainText()
    maya_command = detector.detect_maya_command_at_cursor(text_content, cursor_position)
    if not maya_command:
        return

    alias, command, _full_match = maya_command
    menu.addSeparator()
    help_text = detector.get_help_menu_text(alias, command)
    action = QAction(help_text, editor)
    action.triggered.connect(lambda: detector.open_help_url(alias, command))
    menu.addAction(action)


def _add_selection_to_shelf(editor):
    """Walk up to the main window and call ``add_to_shelf``."""
    target = _find_attr_in_parents(editor, "add_to_shelf")
    if target is None:
        return
    # _find_attr_in_parents returns the attribute value when it's a
    # callable bound method, so calling it directly is correct.
    target()


def _find_attr_in_parents(widget, attr_name):
    """Return the named attribute from the first ancestor that has it."""
    node = widget.parent()
    while node is not None:
        value = getattr(node, attr_name, None)
        if value is not None:
            return value
        node = node.parent() if hasattr(node, "parent") else None
    return None
