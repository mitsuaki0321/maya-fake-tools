"""
Format detection and lightweight text extraction helpers.

No HTML generation here — everything returns plain strings / dicts.
The orchestrator in ``__init__`` uses these to pick a renderer, and
the renderers themselves use them to peel off signature lines or
re-extract numpydoc sections that ``docstring_parser`` mangles.
"""

from __future__ import annotations

import re

# Markers we look for at the top of a docstring to decide it's Maya's
# ``cmds.help(...)`` output. ``Synopsis:`` is the distinctive header;
# ``Flags:`` comes right after it and helps on edge cases where the
# first line is a blank / command summary.
MAYA_HELP_MARKERS = ("Synopsis:", "Flags:")


def looks_like_maya_help(text: str) -> bool:
    """Heuristic: does ``text`` look like ``cmds.help(name)`` output?

    Scans the first 400 characters for one of :data:`MAYA_HELP_MARKERS`.
    False positives fall back to the generic plain renderer which still
    produces a reasonable result, so we don't need to be precise.
    """
    head = text[:400]
    return any(marker in head for marker in MAYA_HELP_MARKERS)


# numpydoc sections look like::
#
#     Examples
#     --------
#     body...
#
# The regex matches the heading + the ``---`` underline, captures the
# section title and the body until the next same-shape heading or the
# end of the string.
NUMPYDOC_SECTION_RE = re.compile(
    r"^([A-Z][A-Za-z ]+)\n-{3,}[ \t]*\n(.*?)(?=\n[A-Z][A-Za-z ]+\n-{3,}|\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_numpydoc_sections(text: str) -> dict[str, str]:
    """Parse numpydoc ``Section\\n---------`` blocks into ``{name: body}``.

    Used to work around ``docstring_parser``'s numpydoc Examples
    parsing, which strips the ``>>>`` prompt lines and emits one meta
    entry per doctest output block. Pulling the body directly from the
    source text keeps the prompts and preserves whitespace.
    """
    return {m[0].strip(): m[1].rstrip() for m in NUMPYDOC_SECTION_RE.findall(text)}


# Matches a leading ``foo(`` / ``def foo(`` — the regex intentionally
# stops at the opening paren; completion of the signature (including
# multi-line cases) is handled by :func:`extract_signature_line`.
SIGNATURE_RE = re.compile(r"^\s*(?:def\s+)?([A-Za-z_][\w.]*)\s*\(")


def extract_signature_line(text: str) -> tuple[str, str]:
    """Peel off the leading ``foo(...)`` signature line.

    Returns ``(signature, remaining_text)``. The signature is an empty
    string when the input doesn't start with a signature-like pattern
    — numpy-style docs often open with a prose summary instead of a
    signature, and we don't want to force one.

    Handles multi-line signatures by accumulating lines until the paren
    depth balances.
    """
    if not text:
        return "", text
    stripped = text.lstrip("\n")
    first_line, _sep, rest_after_first = stripped.partition("\n")
    if not SIGNATURE_RE.match(first_line):
        return "", text

    if first_line.count("(") <= first_line.count(")"):
        return first_line.strip(), rest_after_first

    # Multi-line signature: accumulate until parens balance.
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
