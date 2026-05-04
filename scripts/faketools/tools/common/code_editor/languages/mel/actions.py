"""MEL right-click menu actions.

Currently provides the **What Is** family of actions, which classifies
an identifier via Maya's ``whatIs`` MEL command and reports the result
in the editor's terminal.

Two menu entries:

* ``What Is 'X'`` -- runs the classifier and prints a descriptive
  message. Read-only: the editor state is not touched.
* ``What Is 'X' (Open Source)`` -- same classification, plus opens the
  source file in the **OS-default application** when ``whatIs`` returns
  a path. The OS handler (Notepad, Finder preview, ``xdg-open``, ...)
  is preferred over loading the file as a Code Editor tab because the
  paths typically point at Maya bundled scripts or third-party MEL
  libraries that the user should not be editing.

Qt classes are imported lazily inside the extender so this module
stays Qt-free at import time (smoke tests, lint runs).
"""

from __future__ import annotations

from logging import getLogger
import os
import re
import sys
from typing import Optional

from ..editor_helpers import find_execution_manager

logger = getLogger(__name__)


# Path-bearing whatIs results. The path may be absent for a procedure
# defined inline (no source file recorded), so the capture group is
# optional.
_MEL_PROC_RE = re.compile(r"^Mel procedure(?:\s+found in:\s*(.+?))?\s*$")
_SCRIPT_RE = re.compile(r"^Script(?:\s+found in:\s*(.+?))?\s*$")
# Variable result, e.g. ``int[] variable`` / ``string variable``.
_VARIABLE_RE = re.compile(r"^(.+?)\s+variable$")


def _eval_whatis(identifier: str) -> Optional[str]:
    """Return the ``whatIs`` result string for ``identifier``, or ``None`` on failure.

    ``whatIs`` is a MEL-only command (no ``cmds.whatIs`` wrapper), so the
    call goes through ``maya.mel.eval``. Backslashes and double quotes
    in the identifier are escaped so a pasted Windows path or a
    quoted name doesn't break the MEL string literal.
    """
    try:
        import maya.mel as mel  # type: ignore
    except ImportError:
        return None
    escaped = identifier.replace("\\", "\\\\").replace('"', '\\"')
    try:
        return mel.eval(f'whatIs "{escaped}";')
    except Exception as exc:
        logger.debug(f"whatIs failed for {identifier!r}: {exc}")
        return None


def _query_runtime_command_body(identifier: str) -> Optional[str]:
    """Return the body of a runtimeCommand, or ``None`` if not retrievable."""
    try:
        import maya.cmds as cmds  # type: ignore
    except ImportError:
        return None
    try:
        return cmds.runTimeCommand(identifier, query=True, command=True)
    except Exception as exc:
        logger.debug(f"runTimeCommand query failed for {identifier!r}: {exc}")
        return None


def _classify(identifier: str, what_is_result: str) -> tuple[list[str], Optional[str]]:
    """Translate the raw ``whatIs`` string into terminal lines + an optional path.

    Returns:
        (lines, source_path):
            lines: messages to print, already prefixed with ``// `` so they
                   read as MEL comments in the terminal.
            source_path: extracted source path if the result carried one,
                   else ``None``.
    """
    lines: list[str] = []
    source_path: Optional[str] = None

    if what_is_result == "Command":
        lines.append(f"// What Is '{identifier}': Built-in Maya command")
        lines.append("//   This is a Maya command compiled into the application -- no MEL source file exists.")
        return lines, None

    if what_is_result == "Run Time Command":
        lines.append(f"// What Is '{identifier}': Runtime command (registered via runTimeCommand)")
        body = _query_runtime_command_body(identifier)
        if body:
            lines.append("// ----- runTimeCommand body -----")
            lines.extend(body.splitlines() or [""])
            lines.append("// -------------------------------")
        else:
            lines.append("//   (body not retrievable)")
        return lines, None

    if what_is_result == "Unknown":
        lines.append(f"// What Is '{identifier}': Unknown identifier")
        lines.append("//   This name doesn't match any known command, procedure, script, or global variable.")
        return lines, None

    proc_match = _MEL_PROC_RE.match(what_is_result)
    if proc_match:
        source_path = proc_match.group(1)
        if source_path:
            lines.append(f"// What Is '{identifier}': MEL procedure")
            lines.append(f"//   Source: {source_path}")
            lines.append(f"//   Use \"What Is '{identifier}' (Open Source)\" to open this file in your OS default editor.")
        else:
            lines.append(f"// What Is '{identifier}': MEL procedure (no source file recorded -- defined inline)")
        return lines, source_path

    script_match = _SCRIPT_RE.match(what_is_result)
    if script_match:
        source_path = script_match.group(1)
        if source_path:
            lines.append(f"// What Is '{identifier}': MEL script (uncompiled)")
            lines.append(f"//   Source: {source_path}")
            lines.append(f"//   Use \"What Is '{identifier}' (Open Source)\" to open this file in your OS default editor.")
        else:
            lines.append(f"// What Is '{identifier}': MEL script (no source path returned)")
        return lines, source_path

    var_match = _VARIABLE_RE.match(what_is_result)
    if var_match:
        var_type = var_match.group(1).strip()
        lines.append(f"// What Is '{identifier}': MEL variable (type: {var_type})")
        return lines, None

    # Unknown shape from whatIs -- surface it raw rather than guess.
    lines.append(f"// What Is '{identifier}': {what_is_result}")
    return lines, None


def _print_to_terminal(editor, lines: list[str]) -> None:
    """Append ``lines`` to the host window's output terminal."""
    exec_manager = find_execution_manager(editor)
    if exec_manager is None or exec_manager.output_terminal is None:
        return
    for line in lines:
        exec_manager.output_terminal.append_output(line)


def _open_in_os_default(path: str) -> bool:
    """Hand ``path`` to a text-viewing application. Returns True on success.

    Strategy per platform:

    * Windows: try ``os.startfile`` first so a user-configured ``.mel``
      association wins; fall back to ``notepad.exe`` when no
      association is registered (the common case -- ``.mel`` has no
      default Windows handler).
    * macOS: ``open -t`` opens in the default text editor (TextEdit by
      default), bypassing any "run the file" association.
    * Linux: ``xdg-open`` -- distros generally route unknown text
      extensions to the user's chosen text editor.

    Picking a text-editor flow rather than the unconditional default
    matters here because the source files surfaced by ``whatIs`` are
    typically Maya bundled scripts or third-party MEL libraries -- the
    user wants to *read* them, not execute them.
    """
    import subprocess

    try:
        if sys.platform == "win32":
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except OSError as exc:
                # No registered association (typical for .mel) -- fall
                # back to notepad, always present on Windows.
                logger.debug(f"os.startfile({path!r}) failed ({exc}); falling back to notepad")
                subprocess.Popen(["notepad.exe", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-t", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception as exc:
        logger.warning(f"Failed to open {path!r} in OS default app: {exc}")
        return False


def mel_whatis(editor, identifier: str, *, open_source: bool = False) -> None:
    """Run ``whatIs`` for ``identifier`` and print the classified result.

    When ``open_source=True`` and the classifier extracted a source
    path, the file is additionally handed to the OS-default application
    (notepad / Quick Look / xdg-open). For results without a path
    (``Command`` / ``Variable`` / ``Run Time Command`` / ``Unknown``), an
    explanatory line is appended saying nothing was opened.
    """
    identifier = identifier.strip()
    if not identifier:
        return

    result = _eval_whatis(identifier)
    if result is None:
        _print_to_terminal(
            editor,
            [f"// What Is '{identifier}': failed to evaluate (Maya unavailable?)"],
        )
        return

    lines, source_path = _classify(identifier, result)

    if open_source:
        if source_path is None:
            lines.append("//   (no source file to open)")
        elif _open_in_os_default(source_path):
            lines.append("//   Opening source file in OS default application...")
        else:
            lines.append("//   Failed to open source file in OS default application -- see log.")

    _print_to_terminal(editor, lines)


def mel_context_menu_extender(menu, editor, identifier: str) -> None:
    """Append the **What Is** action pair to the right-click menu.

    Both entries are added unconditionally; ``whatIs`` itself handles
    every identifier shape (commands, procedures, variables, unknowns)
    so no pre-validation is needed here.
    """
    from ......lib_ui.qt_compat import QAction

    menu.addSeparator()

    whatis_action = QAction(f"What Is '{identifier}'", editor)
    whatis_action.triggered.connect(lambda: mel_whatis(editor, identifier, open_source=False))
    menu.addAction(whatis_action)

    whatis_open_action = QAction(f"What Is '{identifier}' (Open Source)", editor)
    whatis_open_action.triggered.connect(lambda: mel_whatis(editor, identifier, open_source=True))
    menu.addAction(whatis_open_action)


__all__ = ["mel_context_menu_extender", "mel_whatis"]
