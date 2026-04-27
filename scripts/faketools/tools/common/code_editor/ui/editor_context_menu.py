"""Right-click context menu for ``PythonEditor``.

Builds a ``QMenu`` populated with the editor's contextual actions: Maya
help (when the cursor is on a recognised ``cmds.*`` call), Inspect
Object / Inspect Help, Reload Module (for valid dotted module names),
and Add to Shelf (when there is a selection).

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
        editor: The ``PythonEditor`` instance receiving the event.
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

    if selected_text and _is_valid_identifier(selected_text):
        menu.addSeparator()

        inspect_action = QAction(f"Inspect Object '{selected_text}'", editor)
        inspect_action.triggered.connect(lambda: editor.inspect_object.emit(selected_text, "dir"))
        menu.addAction(inspect_action)

        inspect_help_action = QAction(f"Inspect Object Help '{selected_text}'", editor)
        inspect_help_action.triggered.connect(lambda: editor.inspect_object.emit(selected_text, "help"))
        menu.addAction(inspect_help_action)

        if _is_valid_module_name(selected_text):
            reload_action = QAction(f"Reload Module '{selected_text}'", editor)
            reload_action.triggered.connect(lambda: _reload_module(editor, selected_text))
            menu.addAction(reload_action)

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


def _reload_module(editor, module_name):
    """Dispatch a reload of ``module_name`` through the execution manager."""
    exec_manager = _find_execution_manager(editor)
    if exec_manager is None:
        return

    reload_code = _build_reload_code(module_name)
    if hasattr(exec_manager, "execute_inspection_code"):
        if exec_manager.output_terminal:
            exec_manager.output_terminal.append_output(f"\n=== Reloading Module: {module_name} ===")
        exec_manager.execute_inspection_code(reload_code)
    else:
        exec_manager.execute_python_code(reload_code)


def _find_attr_in_parents(widget, attr_name):
    """Return the named attribute from the first ancestor that has it."""
    node = widget.parent()
    while node is not None:
        value = getattr(node, attr_name, None)
        if value is not None:
            return value
        node = node.parent() if hasattr(node, "parent") else None
    return None


def _find_execution_manager(widget):
    """Return the main window's ``execution_manager`` if reachable.

    The historical lookup walked one extra ``parent.parent()`` hop because
    the editor sits inside a tab widget which sits inside the main window;
    that contract is preserved here.
    """
    node = widget.parent()
    while node is not None:
        parent = node.parent() if hasattr(node, "parent") else None
        if parent is not None and hasattr(parent, "execution_manager"):
            return parent.execution_manager
        node = parent
    return None


def _is_valid_identifier(text):
    """Return True for a bare Python identifier (no dotted form)."""
    if not text:
        return False
    return text.replace("_", "").replace(".", "").isalnum() and not text[0].isdigit()


def _is_valid_module_name(text):
    """Return True for a dotted module path like ``pkg.sub.module``."""
    if not text:
        return False
    if text.startswith(".") or text.endswith(".") or ".." in text:
        return False
    for part in text.split("."):
        if not part:
            return False
        if not (part.replace("_", "").isalnum() and not part[0].isdigit()):
            return False
    return True


def _build_reload_code(module_name):
    """Render the snippet that ``execute_inspection_code`` will run.

    Tries the dotted form first (``sys.modules[name]``), then falls back
    to ``eval`` so import aliases also work.
    """
    return f"""
import importlib
import sys
import types

try:
    if '{module_name}' in sys.modules:
        importlib.reload(sys.modules['{module_name}'])
        print("Code Editor: Module '{module_name}' reloaded successfully.")
    else:
        _reload_obj = eval('{module_name}')
        if not isinstance(_reload_obj, types.ModuleType):
            print("Code Editor: Error: '{module_name}' is not a module.")
        elif _reload_obj.__name__ not in sys.modules:
            print(f"Code Editor: Error: Module '{{_reload_obj.__name__}}' is not in sys.modules.")
        else:
            importlib.reload(sys.modules[_reload_obj.__name__])
            print(f"Code Editor: Module '{{_reload_obj.__name__}}' reloaded successfully.")
except NameError:
    print("Code Editor: Error: '{module_name}' is not defined.")
except Exception as e:
    print(f"Code Editor: Error reloading module '{module_name}': {{e}}")
"""
