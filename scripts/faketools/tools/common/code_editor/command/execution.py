"""
Execution command layer for the Code Editor.

Owns the Maya-side execution primitives:
- ``build_exec_globals`` constructs the persistent globals dict (with Maya
  modules merged in when available) used by the editor's exec sandbox.
- ``NativeExecutionBridge`` drives Maya's hidden ``cmdScrollFieldExecuter`` so
  executed code integrates with Maya's native output and undo behaviour.

UI code should never import ``maya.cmds`` directly; it should go through this
module so that non-Maya environments (tests, linting) remain importable.
"""

from __future__ import annotations

from logging import getLogger
from typing import Optional

logger = getLogger(__name__)

try:
    import maya.cmds as cmds  # type: ignore

    MAYA_AVAILABLE = True
except ImportError:
    cmds = None  # type: ignore[assignment]
    MAYA_AVAILABLE = False
    logger.debug("Maya commands not available")


_HIDDEN_WINDOW_NAME = "hiddenNativeExecuter"


def build_exec_globals(base: Optional[dict] = None) -> dict:
    """Build the persistent execution globals dict used by the editor.

    Starts from ``base`` (or a fresh dict with ``__name__`` set to ``__main__``)
    and layers in Maya modules when Maya is importable. Safe to call in a
    non-Maya interpreter — the Maya merge is skipped silently.
    """
    env: dict = dict(base) if base else {"__name__": "__main__"}
    try:
        import maya.api.OpenMaya as om2  # type: ignore
        import maya.cmds as _cmds  # type: ignore
    except ImportError:
        return env

    env.update(
        {
            "cmds": _cmds,
            "om2": om2,
            "om": om2,  # Alias kept for backward compatibility
        },
    )
    return env


def _sync_main_to_globals(exec_globals: dict) -> None:
    """Copy user-defined names from __main__ into ``exec_globals`` (skip modules and builtins)."""
    import __main__

    for key in dir(__main__):
        if key.startswith("__"):
            continue
        try:
            value = getattr(__main__, key)
        except Exception as e:
            logger.debug(f"Failed to read __main__.{key}: {e}")
            continue
        if hasattr(value, "__module__") and value.__module__ in ("builtins", "__builtin__"):
            continue
        exec_globals[key] = value


def _sync_globals_to_main(exec_globals: dict) -> None:
    """Push names from ``exec_globals`` into ``__main__`` so Maya's executer sees them."""
    import __main__

    for key, value in exec_globals.items():
        if key.startswith("__"):
            continue
        setattr(__main__, key, value)


class NativeExecutionBridge:
    """Executes Python via Maya's hidden ``cmdScrollFieldExecuter``.

    Using the native executer (rather than ``exec``) makes printed output, undo
    chunks, and error traceback formatting match Maya's built-in Script Editor.
    """

    def __init__(self):
        self.hidden_window = None
        self.python_executer = None
        self._setup_executer()

    def _setup_executer(self):
        if not MAYA_AVAILABLE:
            return

        if cmds.window(_HIDDEN_WINDOW_NAME, exists=True):
            cmds.deleteUI(_HIDDEN_WINDOW_NAME)

        self.hidden_window = cmds.window(_HIDDEN_WINDOW_NAME, visible=False, retain=True)

        cmds.setParent(self.hidden_window)
        layout = cmds.columnLayout()

        self.python_executer = cmds.cmdScrollFieldExecuter(
            parent=layout,
            sourceType="python",
            width=100,
            height=100,
        )

    def execute_code(self, code, mode="all", selection_range=None, exec_globals=None) -> bool:
        """Execute ``code`` through the native executer.

        Args:
            code: Python code to execute.
            mode: ``"all"``, ``"selected"``, or ``"range"``.
            selection_range: ``(start, end)`` character offsets when ``mode == "range"``.
            exec_globals: Optional shared globals dict; synced to/from ``__main__``
                around execution so the editor sees Maya-side state changes.
        """
        if not MAYA_AVAILABLE or not self.python_executer:
            return False

        try:
            if exec_globals is not None:
                _sync_main_to_globals(exec_globals)
                _sync_globals_to_main(exec_globals)

            cmds.cmdScrollFieldExecuter(self.python_executer, edit=True, text=code)

            if mode == "all":
                cmds.cmdScrollFieldExecuter(self.python_executer, edit=True, executeAll=True)
            elif mode == "range" and selection_range:
                start, end = selection_range
                cmds.cmdScrollFieldExecuter(self.python_executer, edit=True, select=[start, end])
                cmds.cmdScrollFieldExecuter(self.python_executer, edit=True, execute=True)
            else:  # "selected" or unknown → execute selected/current line
                cmds.cmdScrollFieldExecuter(self.python_executer, edit=True, execute=True)

            if exec_globals is not None:
                _sync_main_to_globals(exec_globals)

            return True
        except Exception as e:
            logger.error(f"Failed to execute code: {e}")
            return False

    def execute_silent(self, code: str, exec_globals: Optional[dict] = None) -> bool:
        """Execute ``code`` via ``cmds.python`` without echoing it to Maya's terminal.

        Used for introspection helpers (dir/help) where the user shouldn't see
        the wrapping code. Falls back to ``execute_code`` if ``cmds.python``
        isn't usable, and finally to a plain ``exec`` outside of Maya.
        """
        if MAYA_AVAILABLE:
            try:
                if exec_globals is not None:
                    _sync_globals_to_main(exec_globals)

                cmds.python(code)

                if exec_globals is not None:
                    _sync_main_to_globals(exec_globals)
                return True
            except Exception as e:
                logger.debug(f"Maya python command failed: {e}, falling back to native bridge")
                if self.python_executer:
                    return self.execute_code(code, mode="all", exec_globals=exec_globals)

        try:
            exec(code, exec_globals if exec_globals is not None else {})
            return True
        except Exception:
            import traceback

            traceback.print_exc()
            return False

    def cleanup(self):
        """Remove the hidden executer window."""
        if MAYA_AVAILABLE and self.hidden_window and cmds.window(self.hidden_window, exists=True):
            cmds.deleteUI(self.hidden_window)
