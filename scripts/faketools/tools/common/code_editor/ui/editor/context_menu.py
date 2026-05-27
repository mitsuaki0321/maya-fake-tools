"""Right-click context menu for the editor widget.

Builds a ``QMenu`` populated with the editor's contextual actions:

* **Maya help** — appended when the cursor is on a recognised ``cmds.*``
  call. Python-only: MEL has no equivalent ``cmds.X`` syntax and the
  detector would always come up empty there, so we skip it outright.
* **Language-specific section** — delegated to the active editor's
  :class:`LanguageProfile.context_menu_extender` (e.g. Inspect Object /
  Inspect Help / Reload Module for Python; whatIs / Source File for MEL
  in Phase 1+). Skipped when the language doesn't provide an extender.
* **Insert** — a single action pinned at the *top* of the menu (shortest
  travel from the right click), mirroring the toolbar split-button's
  *current* pick. No submenu: switching which command is the current one
  stays the toolbar's job. Gated on ``supports(language)`` and disabled
  when nothing is selected in Maya.
* **Add to Shelf** — appended when there is a selection and the language
  supports shelf buttons (gating handled by ``maya_shelf.add_to_active_shelf``
  itself).

Kept out of ``code_editor.py`` so the editor widget can stay focused on
text editing concerns; the menu is built fresh on every right click and
the actions are stateless beyond the editor reference they capture.
"""

from __future__ import annotations

from ......lib_ui.qt_compat import QAction, QTextCursor
from ...command.insert_commands import INSERT_COMMANDS, get_insert_command, get_selected_node_names
from ...languages import PYTHON
from ...themes import AppTheme


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
        # The extender (and the executer it dispatches to) handles invalid
        # identifiers by surfacing a friendly message in the terminal, so
        # we don't gate on syntax here.
        extender(menu, editor, selected_text)

    _maybe_add_insert_command(menu, editor, event)

    if editor.textCursor().hasSelection():
        menu.addSeparator()
        shelf_action = QAction("Add to Shelf", editor)
        shelf_action.triggered.connect(lambda: _add_selection_to_shelf(editor))
        menu.addAction(shelf_action)

    return menu


def _maybe_add_insert_command(menu, editor, event):
    """Pin the toolbar's *current* insert command at the top of the menu.

    A single action (no submenu) that mirrors the toolbar split-button's
    current pick, so right-clicking gives the same one-action insert from
    right next to the cursor. Skipped when no command applies to the
    active language; disabled when nothing is selected in Maya.

    Insertion is delegated to the main window's ``insert_named_command``
    (same path as the toolbar). When there is no active selection, the
    caret is first moved to the click position so the text lands where
    the user right-clicked rather than at the old caret.
    """
    command = _current_insert_command(editor)
    if command is None:
        return

    insert = _find_attr_in_parents(editor, "insert_named_command")
    if insert is None:
        return

    click_pos = event.pos()
    action = QAction(f"Insert {command.label}", editor)
    action.setEnabled(bool(get_selected_node_names()))
    action.triggered.connect(lambda checked=False, name=command.name: _run_insert(editor, name, click_pos, insert))

    # Pin to the very top: insert before the first standard action, then a
    # separator, so the order is [Insert, ---, Undo, Redo, …].
    actions = menu.actions()
    if actions:
        menu.insertAction(actions[0], action)
        menu.insertSeparator(actions[0])
    else:
        menu.addAction(action)
        menu.addSeparator()


def _current_insert_command(editor):
    """Resolve the insert command to offer for ``editor``'s language.

    Prefers the toolbar's current pick; falls back to the first registered
    command that supports the language (so a language-incompatible default
    still yields a usable entry). Returns ``None`` when nothing applies.
    """
    language = editor.language

    toolbar = _find_attr_in_parents(editor, "toolbar")
    insert_button = getattr(toolbar, "insert_button", None) if toolbar is not None else None
    if insert_button is not None:
        current = get_insert_command(insert_button.current_name())
        if current is not None and current.supports(language):
            return current

    return next((command for command in INSERT_COMMANDS if command.supports(language)), None)


def _run_insert(editor, name, click_pos, insert):
    """Move the caret to the click position (if unselected) then insert.

    Args:
        editor: The :class:`CodeEditor` receiving the insertion.
        name (str): The :class:`EditorInsertCommand` name to run.
        click_pos: Viewport position of the original right click.
        insert: The main window's ``insert_named_command`` bound method.
    """
    if not editor.textCursor().hasSelection():
        editor.setTextCursor(editor.cursorForPosition(click_pos))
    insert(name)


def _maybe_add_maya_help(menu, editor):
    """Append a Maya help action when a known ``cmds.*`` call is at the cursor.

    Skipped for non-Python tabs: MEL has no ``cmds.X`` form, so the
    detector would scan the whole document for nothing on every right
    click.
    """
    if editor.language is not PYTHON:
        return

    # Lazy import: utils.maya_help_detector pulls Maya-aware helpers and
    # we want the menu code itself importable without that chain at load time.
    from ...utils.maya_help_detector import MayaHelpDetector

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
