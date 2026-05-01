"""Python right-click menu actions and the inspection-code templates they run.

Split out of :mod:`languages.python` so the profile module stays small and
focused on assembling :class:`LanguageProfile`. This module owns:

* The Python ``dir`` / ``help`` snippet templates and the
  :func:`python_inspection_snippets` mapper consumed via
  :attr:`LanguageProfile.inspection_snippets`.
* The Python module reload pipeline (:func:`_build_reload_code` +
  :func:`_reload_module`).
* :func:`python_context_menu_extender` — the
  :attr:`LanguageProfile.context_menu_extender` callback that adds Inspect
  Object / Inspect Help / Reload Module entries to the editor's right-click
  menu.

Qt classes are imported lazily inside the extender so this module stays
Qt-free at import time (smoke tests, lint runs).
"""

from __future__ import annotations

from typing import Optional

from .helpers import find_execution_manager


def _build_reload_code(module_name: str) -> str:
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
    print("Code Editor: '{module_name}' is not defined.")
except Exception as e:
    print(f"Code Editor: Error reloading module '{module_name}': {{e}}")
"""


def _reload_module(editor, module_name: str) -> None:
    """Dispatch a Python module reload through the editor's execution manager."""
    exec_manager = find_execution_manager(editor)
    if exec_manager is None:
        return

    reload_code = _build_reload_code(module_name)
    if hasattr(exec_manager, "execute_inspection_code"):
        if exec_manager.output_terminal:
            exec_manager.output_terminal.append_output(f"\n=== Reloading Module: {module_name} ===")
        exec_manager.execute_inspection_code(reload_code)
    else:
        exec_manager.execute_python_code(reload_code)


def python_context_menu_extender(menu, editor, identifier: str) -> None:
    """Append Inspect Object / Inspect Help / Reload Module to the right-click menu.

    Items are added unconditionally. The Inspect / Reload code runs through
    Maya's executer with try/except wrappers (NameError, "not a module",
    etc.), so invalid selections surface a friendly message in the terminal
    instead of breaking the editor — no syntactic gating needed here.

    Qt classes are imported lazily so :mod:`languages.python_actions` itself
    stays Qt-free at import time (smoke tests, lint runs).
    """
    from .....lib_ui.qt_compat import QAction

    menu.addSeparator()

    inspect_action = QAction(f"Inspect Object '{identifier}'", editor)
    inspect_action.triggered.connect(lambda: editor.inspect_object.emit(identifier, "dir"))
    menu.addAction(inspect_action)

    inspect_help_action = QAction(f"Inspect Object Help '{identifier}'", editor)
    inspect_help_action.triggered.connect(lambda: editor.inspect_object.emit(identifier, "help"))
    menu.addAction(inspect_help_action)

    reload_action = QAction(f"Reload Module '{identifier}'", editor)
    reload_action.triggered.connect(lambda: _reload_module(editor, identifier))
    menu.addAction(reload_action)


_PYTHON_DIR_TEMPLATE = """
try:
    _obj = OBJECT_NAME_PLACEHOLDER
    _attrs = dir(_obj)
    print("Object type: " + str(type(_obj)))
    print("Number of attributes: " + str(len(_attrs)))
    print("Attributes:")
    for _attr in _attrs:
        print("  " + _attr)
except NameError:
    print("Code Editor: 'OBJECT_NAME_PLACEHOLDER' is not defined")
except Exception as _inspect_err:
    print("Code Editor: Error inspecting 'OBJECT_NAME_PLACEHOLDER' - " + str(_inspect_err))
"""


_PYTHON_HELP_TEMPLATE = """
try:
    _obj = OBJECT_NAME_PLACEHOLDER
    # Try to get help for the object itself
    import pydoc
    _help_text = pydoc.getdoc(_obj)
    if _help_text and _help_text != 'no documentation found':
        help(_obj)
    else:
        # If no documentation, show help for the type
        print(f"Variable '{object_name}' is of type: {type(_obj).__name__}")
        print(f"Value: {repr(_obj)}")
        print("-" * 40)
        help(type(_obj))
except NameError:
    print("Code Editor: 'OBJECT_NAME_PLACEHOLDER' is not defined")
except Exception as _help_err:
    print("Code Editor: Error getting help for 'OBJECT_NAME_PLACEHOLDER' - " + str(_help_err))
"""


def python_inspection_snippets(inspection_type: str, object_name: str) -> Optional[str]:
    """Return the Python code that performs the requested inspection.

    Recognised types: ``"dir"`` (attribute listing) and ``"help"`` (pydoc).
    Other types return ``None`` so the consumer can short-circuit.
    """
    if inspection_type == "dir":
        return _PYTHON_DIR_TEMPLATE.replace("OBJECT_NAME_PLACEHOLDER", object_name)
    if inspection_type == "help":
        return _PYTHON_HELP_TEMPLATE.replace("OBJECT_NAME_PLACEHOLDER", object_name).replace("object_name", f"'{object_name}'")
    return None


__all__ = ["python_context_menu_extender", "python_inspection_snippets"]
