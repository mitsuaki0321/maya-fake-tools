"""
Autocomplete debug harness — feeds jedi the same cursor states the Code
Editor would, then prints what comes back.

Meant to be run from Maya's Script Editor (so we pick up the same ``jedi``
version the editor uses):

    exec(open(r"D:/claude/maya-fake-tools/scripts/debug/autocomplete_probe.py", encoding="utf-8").read())

Outside Maya it also works if ``jedi`` is importable and the bundled
``maya-stubs`` for the requested version exist — the MVector case needs a
live Maya for the Interpreter leg to produce anything meaningful.
"""

from __future__ import annotations

from pathlib import Path
from pprint import pformat
import sys

try:
    import jedi  # type: ignore
except ImportError:
    print("[probe] jedi not importable — install it into this Python or run from Maya.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Path setup — mirror what engine._build_project does so completions resolve
# against the bundled stubs exactly like the editor would.
# ---------------------------------------------------------------------------

# ``__file__`` isn't defined when this script is run via
# ``exec(open(...).read())`` from Maya's Script Editor, so fall back to the
# repo path the harness was authored in. Override ``_REPO`` before running
# if the checkout lives elsewhere.
_THIS_FILE = globals().get("__file__")
if _THIS_FILE:
    _REPO = Path(_THIS_FILE).resolve().parents[2]
else:
    _REPO = Path(r"D:/claude/maya-fake-tools")


def _discover_stubs_root() -> Path | None:
    """Pick the maya{ver} stubs dir, falling back to maya2025 if detection fails."""
    try:
        import maya.cmds as _cmds  # type: ignore

        version = str(_cmds.about(version=True))
    except Exception:
        version = "2025"
    candidate = _REPO / "scripts/faketools/resources/maya_stubs" / f"maya{version}"
    if candidate.exists():
        return candidate
    fallback = _REPO / "scripts/faketools/resources/maya_stubs/maya2025"
    return fallback if fallback.exists() else None


_STUBS_ROOT = _discover_stubs_root()
if _STUBS_ROOT and str(_STUBS_ROOT) not in sys.path:
    sys.path.insert(0, str(_STUBS_ROOT))


def _project() -> jedi.Project | None:
    if _STUBS_ROOT is None:
        return None
    return jedi.Project(
        path=".",
        sys_path=[str(_STUBS_ROOT), *sys.path],
        smart_sys_path=False,
    )


# ---------------------------------------------------------------------------
# Probe runner
# ---------------------------------------------------------------------------


def _print_code(code: str, line: int, column: int) -> None:
    print("    source:")
    for i, ln in enumerate(code.splitlines() or [""], 1):
        marker = f"   <-- cursor @ col {column}" if i == line else ""
        print(f"     {i:2d}| {ln}{marker}")


def _run(label: str, code: str, line: int, column: int, *, mode: str) -> None:
    print(f"\n=== {label} [mode={mode}] ===")
    _print_code(code, line, column)

    project = _project()
    try:
        if mode == "Script":
            script = jedi.Script(code=code, project=project)
        elif mode == "Interpreter":
            namespaces: list[dict] = [{"__name__": "__main__"}]
            try:
                import maya.api.OpenMaya as _om  # type: ignore

                namespaces[0]["om"] = _om
            except ImportError:
                pass
            script = jedi.Interpreter(code, namespaces=namespaces, project=project)
        else:
            raise ValueError(f"unknown mode {mode!r}")
        completions = script.complete(line, column)
    except Exception as exc:
        print(f"    ERROR: {type(exc).__name__}: {exc}")
        return

    print(f"    {len(completions)} completion(s). First 10:")
    if not completions:
        print("      (none)")
    for c in completions[:10]:
        print(f"      {c.type:10s} {c.name}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

print(f"\n[probe] stubs_root = {_STUBS_ROOT}")
print(f"[probe] jedi = {jedi.__version__}")

# --- E-num-5: '"abc".|' ---
STR_LIT_CODE = '"abc".'
STR_VAR_CODE = 'x = "abc"\nx.'

_run("E-num-5 a: string literal dot", STR_LIT_CODE, 1, len(STR_LIT_CODE), mode="Script")
_run("E-num-5 b: string literal dot", STR_LIT_CODE, 1, len(STR_LIT_CODE), mode="Interpreter")
_run("E-num-5 c: control (str via variable)", STR_VAR_CODE, 2, 2, mode="Script")
_run("E-num-5 d: control (str via variable)", STR_VAR_CODE, 2, 2, mode="Interpreter")

# --- E-num-4: 'vec.x.|' ---
VEC_CODE = "from maya.api import OpenMaya as om\nvec = om.MVector([0., 0., 0.])\nvec.x."

_run("E-num-4 a: MVector attribute dot (Script + stubs)", VEC_CODE, 3, 6, mode="Script")
_run("E-num-4 b: MVector attribute dot (Interpreter, needs live Maya)", VEC_CODE, 3, 6, mode="Interpreter")

# --- Extra: float literal ensures our trigger suppression is doing the right thing
#     at jedi level (should still return something — our editor just hides popup). ---
_run("float literal (what jedi thinks about '0.')", "0.", 1, 2, mode="Script")
_run("float literal '1.5' after cursor", "1.5", 1, 3, mode="Script")

print("\n[probe] done.")
print("[probe] If 'E-num-5 a' is empty but 'E-num-5 c' is not,")
print("        jedi.Script rejects orphan-literal completions — we'd need")
print("        a workaround (wrap literal in parens, or route to Interpreter).")
print(f"\n[probe] sys.path[0:3] = \n{pformat(sys.path[:3])}")
