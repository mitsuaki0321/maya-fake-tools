"""Format detection and text extraction helpers (plain strings / dicts only, no HTML).

The only Maya-help heuristic (:func:`looks_like_maya_help`) is
language-agnostic; everything else assumes Python source / docstring
shapes because the help popup is Python-only (see
:mod:`..__init__` for context).
"""

from __future__ import annotations

import re

MAYA_HELP_MARKERS = ("Synopsis:", "Flags:")


def looks_like_maya_help(text: str) -> bool:
    """Heuristic: does ``text`` look like ``cmds.help(name)`` output?"""
    head = text[:400]
    return any(marker in head for marker in MAYA_HELP_MARKERS)


# numpydoc: ``Heading\n---------\nbody...`` up to the next same-shape heading.
NUMPYDOC_SECTION_RE = re.compile(
    r"^([A-Z][A-Za-z ]+)\n-{3,}[ \t]*\n(.*?)(?=\n[A-Z][A-Za-z ]+\n-{3,}|\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_numpydoc_sections(text: str) -> dict[str, str]:
    """Parse numpydoc ``Section\\n---`` blocks → ``{name: body}``.

    Workaround for ``docstring_parser`` stripping ``>>>`` prompts from
    numpydoc Examples.
    """
    return {m[0].strip(): m[1].rstrip() for m in NUMPYDOC_SECTION_RE.findall(text)}


SIGNATURE_RE = re.compile(r"^\s*(?:def\s+)?([A-Za-z_][\w.]*)\s*\(")


def extract_signature_line(text: str) -> tuple[str, str]:
    """Peel off a leading ``foo(...)`` signature. Returns ``(signature, remaining_text)``.

    Signature is empty string when the input doesn't start with one.
    Handles multi-line signatures by accumulating until parens balance.
    """
    if not text:
        return "", text
    stripped = text.lstrip("\n")
    first_line, _sep, rest_after_first = stripped.partition("\n")
    if not SIGNATURE_RE.match(first_line):
        return "", text

    if first_line.count("(") <= first_line.count(")"):
        return first_line.strip(), rest_after_first

    acc = [first_line]
    depth = first_line.count("(") - first_line.count(")")
    remaining_lines = rest_after_first.splitlines(keepends=True)
    consumed = 0
    for line in remaining_lines:
        acc.append(line)
        depth += line.count("(") - line.count(")")
        consumed += 1
        if depth <= 0:
            break
    sig = "".join(acc).strip()
    remaining = "".join(remaining_lines[consumed:])
    return sig, remaining


__all__ = [
    "MAYA_HELP_MARKERS",
    "NUMPYDOC_SECTION_RE",
    "SIGNATURE_RE",
    "extract_numpydoc_sections",
    "extract_signature_line",
    "looks_like_maya_help",
]
