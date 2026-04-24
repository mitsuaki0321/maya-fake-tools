"""Compare ``jedi.Name.docstring(raw=True)`` vs ``raw=False``.

Run from Maya's Script Editor to inspect what the help popup would
receive for any dotted expression:

    import faketools.module_cleaner
    faketools.module_cleaner.clean()  # optional reload helper

    from scripts.debug import jedi_docstring_diff
    jedi_docstring_diff.show("numpy.absolute")
    jedi_docstring_diff.show("str.join")
    jedi_docstring_diff.show("cmds.polyCube")      # auto-prefixes via the shim
    jedi_docstring_diff.show("om.MFnMesh.getPoints")

Or, for a custom source + cursor position:

    jedi_docstring_diff.show_at(\"\"\"
    import numpy as np
    np.linalg.inv
    \"\"\", line=3, column=13)

``show`` wraps the expression in the editor's Maya shim (``import
maya.cmds as cmds`` etc.) so bare ``cmds.*`` / ``om.*`` names resolve
against bundled stubs, matching the Code Editor flow.
"""

from __future__ import annotations

from typing import Optional

try:
    import jedi  # type: ignore
except ImportError:
    jedi = None  # type: ignore


_MAYA_SHIM = (
    "import maya.cmds as cmds\n"
    "import maya.api.OpenMaya as om\n"
    "import maya.api.OpenMayaAnim as oma\n"
    "import maya.api.OpenMayaRender as omr\n"
    "import maya.api.OpenMayaUI as omui\n"
)


_SHIM_BINDINGS = {"cmds", "om", "oma", "omr", "omui"}


def _builtin_roots() -> frozenset[str]:
    # ``__builtins__`` is a module in ``__main__`` but a dict inside
    # imported modules, so fetch the canonical module directly.
    import builtins

    return frozenset(dir(builtins))


_BUILTIN_ROOTS = _builtin_roots()


def show(expression: str) -> None:
    """Print both docstring forms for ``expression`` (e.g. ``"numpy.absolute"``)."""
    root = expression.split(".", 1)[0]
    extra_import = ""
    if root and root not in _SHIM_BINDINGS and root not in _BUILTIN_ROOTS and not expression.startswith("builtins."):
        # Cover ``numpy.absolute``, ``collections.OrderedDict``, etc. —
        # jedi needs the top-level name to be bound before it can follow
        # the dotted chain. Builtins (``str``, ``dict``…) are already
        # bound, so skip the import — ``import str`` would be a parse
        # error that breaks the whole Script.
        extra_import = f"import {root}\n"
    source = _MAYA_SHIM + extra_import + expression + "\n"
    line = source.count("\n")
    column = len(expression)
    show_at(source, line, column, label=expression)


def show_at(source: str, line: int, column: int, *, label: Optional[str] = None) -> None:
    """Print both docstring forms for the symbol at ``(line, column)`` of ``source``."""
    if jedi is None:
        print("jedi is not importable in this environment.")
        return

    script = jedi.Script(source)
    try:
        names = script.help(line, column)
    except Exception as exc:
        print(f"[error] jedi.help failed: {exc}")
        return

    header = label or f"line={line}, column={column}"
    print("=" * 78)
    print(f"TARGET: {header}")
    print(f"names:  {[(n.name, n.full_name) for n in names]}")
    print("=" * 78)

    if not names:
        print("(no names resolved)")
        return

    for idx, name in enumerate(names):
        print(f"\n--- [{idx}] {name.full_name or name.name} ---")
        _print_section("raw=True ", _safe_doc(name, raw=True))
        _print_section("raw=False", _safe_doc(name, raw=False))


def _safe_doc(name, *, raw: bool) -> str:
    try:
        return name.docstring(raw=raw) or ""
    except Exception as exc:
        return f"(docstring(raw={raw}) raised: {exc})"


def _print_section(title: str, body: str) -> None:
    stripped = body.strip()
    if not stripped:
        print(f"[{title}] (empty)")
        return
    print(f"[{title}] ({len(body)} chars)")
    for line in body.splitlines():
        print(f"    {line}")


__all__ = ["show", "show_at"]
