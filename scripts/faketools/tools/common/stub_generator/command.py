"""
Maya stub generation for autocomplete.

Two outputs, both UTF-8 ``.pyi`` files placed under the tool's data dir:

- ``maya/cmds.pyi``       — every command from ``dir(cmds)`` with its flag
  names expanded as keyword arguments so popups can suggest them inside
  ``cmds.polyCube(|)``. Flags are harvested by parsing ``cmds.help(name)``.
- ``maya/api/OpenMaya.pyi`` — every attribute on ``maya.api.OpenMaya``;
  classes emit a nested block of member stubs via ``dir()``.

The pyi files are per-Maya-version (stubs for 2023 and 2025 live in
different folders) because flag sets shift between releases. The UI layer
calls :func:`generate_all` with a progress callback; this module owns no
Qt imports and can run headlessly in ``mayapy`` too.
"""

from __future__ import annotations

import inspect
from logging import getLogger
from pathlib import Path
import re
from typing import Callable, Optional

logger = getLogger(__name__)

# Flag name extractor: grabs every ``-name`` token in the "Flags:" section.
# Intentionally lenient — it'll pick up meta flags (-q, -e) too, which is
# fine because those are valid on the commands they appear in.
_FLAG_TOKEN_RE = re.compile(r"-([a-zA-Z_][\w]*)")

# Header of the flag table in ``cmds.help(name)`` output.
_FLAGS_HEADER = "Flags:"

# Lines that terminate the flag section. ``help()`` output varies a bit
# across Maya versions; these cover the headings we've seen.
_FLAG_TERMINATORS = (
    "Return value:",
    "Modes:",
    "Examples:",
    "Synopsis:",
)


def get_bundled_stubs_root() -> Path:
    """Return the repo-bundled stub root: ``faketools/resources/maya_stubs/``.

    This is the location checked by the autocomplete engine and the target
    of :func:`generate_bundled`. Committing pre-generated stubs here means
    end users never have to run the generator themselves.
    """
    # ``command.py`` lives at ``faketools/tools/common/stub_generator/command.py``
    # — four ``parent`` hops get us to the ``faketools`` package root.
    return Path(__file__).resolve().parents[3] / "resources" / "maya_stubs"


def get_stubs_root(maya_version: str, data_root: Optional[Path] = None) -> Path:
    """Return the versioned stub root: ``{root}/maya{ver}/``.

    When ``data_root`` is omitted we default to the bundled resources
    directory, so callers inside Maya can regenerate straight into the
    committed location with zero configuration.
    """
    if data_root is None:
        data_root = get_bundled_stubs_root()
    return data_root / f"maya{maya_version}"


def get_package_root(maya_version: str, data_root: Optional[Path] = None) -> Path:
    """Return the path to add to ``sys.path`` so ``import maya.cmds`` resolves to the stub."""
    return get_stubs_root(maya_version, data_root)


# -------------------- cmds --------------------


def _parse_flag_names(help_text: str) -> list[str]:
    """Extract unique flag names from the ``Flags:`` section of ``cmds.help()``.

    The returned list preserves first-seen order so the generated signature
    lists short and long names in the order Maya presents them.
    """
    names: list[str] = []
    seen: set[str] = set()
    in_flags = False

    for line in help_text.splitlines():
        stripped = line.strip()
        if not in_flags:
            if stripped.startswith(_FLAGS_HEADER):
                in_flags = True
            continue

        # Stop if we've walked off the flag table into another section.
        if any(stripped.startswith(term) for term in _FLAG_TERMINATORS):
            break

        for match in _FLAG_TOKEN_RE.finditer(line):
            name = match.group(1)
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    return names


def _is_valid_py_identifier(name: str) -> bool:
    """Guard: a few cmds flags ship with non-identifier names in edge cases."""
    return name.isidentifier() and not _is_reserved(name)


# Python reserved words can't be used as kwargs; we skip these even if Maya
# exposes them as flag aliases.
_RESERVED = frozenset(
    [
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    ]
)


def _is_reserved(name: str) -> bool:
    return name in _RESERVED


def _format_cmds_signature(name: str, flags: list[str]) -> str:
    """Emit the ``def`` line for a command with flags as keyword args."""
    kwargs = [f for f in flags if _is_valid_py_identifier(f)]
    if not kwargs:
        return f"def {name}(*args: Any, **kwargs: Any) -> Any: ..."

    # Keep lines under a reasonable width for readability of the stub.
    pieces = ", ".join(f"{k}: Any = ..." for k in kwargs)
    return f"def {name}(*args: Any, {pieces}, **kwargs: Any) -> Any: ..."


def generate_cmds_stub(progress: Optional[Callable[[int, int, str], None]] = None) -> str:
    """Build the full text of ``cmds.pyi`` from the currently-loaded ``maya.cmds``."""
    import maya.cmds as cmds  # type: ignore

    lines: list[str] = [
        '"""Auto-generated stub for maya.cmds. Do not edit."""',
        "",
        "from typing import Any",
        "",
    ]

    names = sorted(n for n in dir(cmds) if not n.startswith("_"))
    total = len(names)

    for i, name in enumerate(names):
        try:
            obj = getattr(cmds, name)
        except Exception as exc:
            logger.debug(f"cmds.{name}: getattr failed ({exc})")
            continue

        if not callable(obj):
            lines.append(f"{name}: Any = ...")
            continue

        try:
            help_text = cmds.help(name) or ""
        except Exception:
            help_text = ""

        flags = _parse_flag_names(help_text)
        lines.append(_format_cmds_signature(name, flags))

        if progress is not None and (i % 50 == 0 or i == total - 1):
            progress(i + 1, total, name)

    lines.append("")
    return "\n".join(lines)


# -------------------- OpenMaya --------------------


def _emit_class_stub(class_name: str, cls: type) -> list[str]:
    """Produce indented stub lines for one Boost.Python / native class."""
    lines = [f"class {class_name}:"]
    # ``dir()`` gives us class members without the noise of inherited object
    # machinery. We do keep ``__init__`` because it surfaces constructor
    # parameter hints when available.
    members = sorted(n for n in dir(cls) if (not n.startswith("_") or n == "__init__"))
    if not members:
        lines.append("    ...")
        return lines

    for member in members:
        try:
            attr = inspect.getattr_static(cls, member)
        except AttributeError:
            continue
        except Exception:
            lines.append(f"    {member}: Any = ...")
            continue

        if inspect.isroutine(attr) or callable(attr):
            lines.append(f"    def {member}(self, *args: Any, **kwargs: Any) -> Any: ...")
        else:
            lines.append(f"    {member}: Any = ...")

    return lines


def generate_openmaya_stub(progress: Optional[Callable[[int, int, str], None]] = None) -> str:
    """Build the full text of ``maya/api/OpenMaya.pyi``."""
    import maya.api.OpenMaya as om2  # type: ignore

    lines: list[str] = [
        '"""Auto-generated stub for maya.api.OpenMaya. Do not edit."""',
        "",
        "from typing import Any",
        "",
    ]

    names = sorted(n for n in dir(om2) if not n.startswith("_"))
    total = len(names)

    for i, name in enumerate(names):
        try:
            obj = getattr(om2, name)
        except Exception:
            lines.append(f"{name}: Any = ...")
            lines.append("")
            continue

        if isinstance(obj, type):
            lines.extend(_emit_class_stub(name, obj))
        elif callable(obj):
            lines.append(f"def {name}(*args: Any, **kwargs: Any) -> Any: ...")
        else:
            lines.append(f"{name}: Any = ...")
        lines.append("")

        if progress is not None and (i % 20 == 0 or i == total - 1):
            progress(i + 1, total, name)

    return "\n".join(lines)


# -------------------- Top-level driver --------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info(f"stub written: {path}")


def generate_all(
    maya_version: str,
    data_root: Optional[Path] = None,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
    """Generate cmds + OpenMaya stubs for ``maya_version``.

    Writes the package layout under ``{stubs_root}/maya{version}/``:

    ::

        maya/
            __init__.pyi
            cmds.pyi
            api/
                __init__.pyi
                OpenMaya.pyi

    Returns the directory path to add to ``sys.path`` so the stubs can be
    imported as ``maya.cmds`` / ``maya.api.OpenMaya``.
    """
    stubs_root = get_stubs_root(maya_version, data_root)
    maya_pkg = stubs_root / "maya"
    api_pkg = maya_pkg / "api"

    # Package markers so jedi treats these as importable packages.
    _write(maya_pkg / "__init__.pyi", "")
    _write(api_pkg / "__init__.pyi", "")

    if progress is not None:
        progress(0, 2, "cmds")
    cmds_text = generate_cmds_stub(progress=progress)
    _write(maya_pkg / "cmds.pyi", cmds_text)

    if progress is not None:
        progress(1, 2, "OpenMaya")
    om2_text = generate_openmaya_stub(progress=progress)
    _write(api_pkg / "OpenMaya.pyi", om2_text)

    if progress is not None:
        progress(2, 2, "done")
    return stubs_root


def stubs_exist(maya_version: str, data_root: Optional[Path] = None) -> bool:
    """Quick probe used by the autocomplete engine: do we have stubs yet?"""
    root = get_stubs_root(maya_version, data_root)
    return (root / "maya" / "cmds.pyi").exists()


def generate_bundled(progress: Optional[Callable[[int, int, str], None]] = None) -> Path:
    """Maintainer entry point: regenerate stubs for the running Maya into the repo.

    Meant to be invoked from Maya's Script Editor with the target Maya
    version loaded:

    >>> from faketools.tools.common.stub_generator import command
    >>> command.generate_bundled()

    The ``.pyi`` files are written under
    ``scripts/faketools/resources/maya_stubs/maya{version}/`` so they can be
    committed alongside the source. End users don't run this — they just
    get the committed stubs.
    """
    import maya.cmds as cmds  # type: ignore

    maya_version = str(cmds.about(version=True))
    return generate_all(maya_version=maya_version, data_root=None, progress=progress)


__all__ = [
    "generate_all",
    "generate_bundled",
    "generate_cmds_stub",
    "generate_openmaya_stub",
    "get_bundled_stubs_root",
    "get_package_root",
    "get_stubs_root",
    "stubs_exist",
]
