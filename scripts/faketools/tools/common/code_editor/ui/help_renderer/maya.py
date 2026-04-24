"""
Renderer for Maya ``cmds.help(...)`` output.

Maya's help has a fixed layout driven by section headings that end in
a colon:

- Synopsis:     ``polyCube [flags] [String]``
- Flags:        two-column flag table + a type column
- Return value: single type + description
- Modes:        one line per mode with ``(-e)`` / ``(-q)`` annotations
- Examples:     Python snippet

Each known section gets its own specialised renderer below so the
output looks like a doc page rather than a raw dump. Unknown sections
fall through to a preserved-whitespace code block.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from . import blocks


def render(text: str, theme: dict[str, str]) -> str:
    """Dispatch each ``Section:`` block to its specialised renderer."""
    parts: list[str] = []
    heading_re = re.compile(r"^([A-Z][A-Za-z ]*):\s*(.*)$")
    current_title: Optional[str] = None
    current_body: list[str] = []

    def flush() -> None:
        if current_title is None and not current_body:
            return
        if current_title is not None:
            parts.append(blocks.section_header(current_title, theme))
        body = "\n".join(current_body).rstrip()
        if not body:
            return
        key = (current_title or "").strip().lower()
        if key == "synopsis":
            parts.append(synopsis(body, theme))
        elif key == "flags":
            parts.append(flags_table(body, theme))
        elif key == "return value":
            parts.append(return_value(body, theme))
        elif key == "modes":
            parts.append(modes(body, theme))
        elif key == "examples":
            parts.append(blocks.code_block(body, theme, highlight_python=True))
        else:
            parts.append(blocks.code_block(body, theme))

    for line in text.splitlines():
        m = heading_re.match(line)
        if m and line[0] != " ":
            flush()
            current_title = m.group(1)
            current_body = []
            trailing = m.group(2)
            if trailing:
                current_body.append(trailing)
        else:
            current_body.append(line)
    flush()

    if not parts:
        # No headings found at all — let plain.render have a go.
        from . import plain

        return plain.render(text, theme)
    return "\n".join(parts)


# --- Section-specific renderers ---------------------------------------------


def synopsis(body: str, theme: dict[str, str]) -> str:
    """Colour the command name and ``[placeholder]`` tokens.

    First non-placeholder word is the command itself (``polyCube``);
    tokens wrapped in square brackets (``[flags]``, ``[String]``) are
    placeholders.
    """
    pieces: list[str] = []
    seen_command = False
    for token in body.split():
        if token.startswith("[") and token.endswith("]"):
            pieces.append(f'<span style="color:{theme["param_type"]};">{html.escape(token)}</span>')
        elif not seen_command:
            # The command reads better in the "function" colour than
            # the variable colour ``param_name`` now carries.
            pieces.append(f'<span style="color:{theme["function"]};">{html.escape(token)}</span>')
            seen_command = True
        else:
            pieces.append(html.escape(token))
    return blocks.wrap_code_block(" ".join(pieces), theme)


_FLAG_ROW_RE = re.compile(r"^\s*(-[A-Za-z]\S*)\s+(-[A-Za-z]\S*)\s*(.*)$")


def flags_table(body: str, theme: dict[str, str]) -> str:
    """Three-column HTML table for the flag list.

    Columns:
        short flag (``-ax``)       → muted grey
        long flag (``-axis``)       → ``param_type`` green
        type (``Float Float Float``) → ``param_type`` green

    Lines that don't match the ``-sh -long type`` pattern fall back to
    a plain preserved-whitespace row so we never drop content on weird
    flag definitions.
    """
    rows: list[str] = []
    for raw_line in body.splitlines():
        if not raw_line.strip():
            continue
        m = _FLAG_ROW_RE.match(raw_line)
        if not m:
            rows.append(f'<tr><td colspan="3" style="padding:1px 0;">{html.escape(raw_line)}</td></tr>')
            continue
        short, long_flag, type_info = m.group(1), m.group(2), m.group(3).strip()
        rows.append(
            "<tr>"
            f'<td style="color:{theme["muted"]};padding:1px 16px 1px 0;">{html.escape(short)}</td>'
            f'<td style="color:{theme["param_type"]};padding:1px 24px 1px 0;">{html.escape(long_flag)}</td>'
            f'<td style="color:{theme["param_type"]};padding:1px 0;">{html.escape(type_info)}</td>'
            "</tr>"
        )
    body_html = "\n".join(rows)
    return (
        f'<table cellpadding="0" cellspacing="0" '
        f'style="font-family:{theme["font_family_mono"]};'
        f"margin:4px 0 10px 0;"
        f'border-collapse:collapse;">{body_html}</table>'
    )


_RETURN_TYPE_RE = re.compile(r"^(\s*)(\S+)(\s+)(.*)$")


def return_value(body: str, theme: dict[str, str]) -> str:
    """Colour the leading type token; leave the description plain.

    Typical input: ``    String[]    Object name and node name``. Only
    the first non-whitespace token is touched; multi-line bodies fall
    back to preserved text.
    """
    first_line, _sep, rest = body.partition("\n")
    m = _RETURN_TYPE_RE.match(first_line)
    if not m:
        return blocks.wrap_code_block(html.escape(body), theme)
    _lead, type_tok, gap, tail = m.group(1), m.group(2), m.group(3), m.group(4)
    inner = f'<span style="color:{theme["param_type"]};">{html.escape(type_tok)}</span>{html.escape(gap)}{html.escape(tail)}'
    if rest.strip():
        inner = inner + "\n" + html.escape(rest)
    return blocks.wrap_code_block(inner, theme)


_MODE_FLAG_RE = re.compile(r"\(([^)]+)\)")


def modes(body: str, theme: dict[str, str]) -> str:
    """Colour ``(-e)`` / ``(-q)`` flag annotations and ``(default)``.

    Anything starting with ``-`` inside parens is treated as a CLI
    flag and gets the ``literal`` colour; anything else (e.g.
    ``(default)``) gets the muted colour because it's just a note.
    """
    rows: list[str] = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        def replace(m: re.Match) -> str:
            content = m.group(1)
            colour = theme["literal"] if content.startswith("-") else theme["muted"]
            return f'<span style="color:{colour};">({html.escape(content)})</span>'

        # html.escape doesn't touch parens, so the regex still matches.
        escaped = html.escape(stripped)
        decorated = _MODE_FLAG_RE.sub(replace, escaped)
        rows.append(f'<div style="margin:2px 0;">{decorated}</div>')
    return "\n".join(rows)


__all__ = ["flags_table", "modes", "render", "return_value", "synopsis"]
