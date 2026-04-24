"""
Renderer for structured Python docstrings (numpydoc / Google / RST).

Built on top of :mod:`docstring_parser`. The parser handles format
detection and produces a typed object with ``short_description``,
``long_description``, ``params``, ``returns``, ``raises``, and generic
``meta`` entries for Examples / Notes / etc.

A couple of parser quirks are worked around here:

- numpydoc's Examples section gets split into one meta per doctest
  output block, with the ``>>>`` prompt lines dropped entirely. We
  fall back to :func:`detect.extract_numpydoc_sections` to pull the
  raw Examples text so the prompts survive.
- The parser can emit several meta entries with the same section name
  (notably Examples). We group by section name before rendering so we
  don't produce a duplicate heading per doctest chunk.

If ``docstring_parser`` itself is missing, :data:`AVAILABLE` is False
and the orchestrator falls back to :mod:`.plain`.
"""

from __future__ import annotations

from collections import OrderedDict
import html
from logging import getLogger

from . import blocks, detect

logger = getLogger(__name__)


try:
    import docstring_parser  # type: ignore

    AVAILABLE = True
except Exception as exc:  # pragma: no cover — diagnostic only
    AVAILABLE = False
    logger.debug(f"docstring_parser unavailable, structured parsing disabled: {exc}")


# Section names docstring_parser already models as typed attributes
# (``parsed.params`` / ``.returns`` / ``.raises``). We skip these in
# the generic meta loop so they aren't rendered twice.
HANDLED_META_NAMES = frozenset(
    {
        "param",
        "parameter",
        "parameters",
        "arg",
        "argument",
        "arguments",
        "keyword",
        "kwarg",
        "type",
        "returns",
        "return",
        "rtype",
        "yields",
        "yield",
        "ytype",
        "raises",
        "raise",
        "except",
        "exception",
    }
)


def render(text: str, theme: dict[str, str]) -> str:
    """Render a Python docstring as semantic HTML sections."""
    parts: list[str] = []

    # Peel the leading ``foo(...)`` / ``def foo(...):`` line BEFORE
    # handing to docstring_parser. Otherwise docstring_parser adopts
    # the signature as its ``short_description`` and we'd render it
    # twice — once as highlighted code block, once as bold prose.
    body_text = text.lstrip()
    sig_line, rest_after_sig = detect.extract_signature_line(body_text)
    if sig_line:
        parts.append(blocks.signature(sig_line, theme))
    doc_for_parse = rest_after_sig if sig_line else text

    try:
        parsed = docstring_parser.parse(doc_for_parse)
    except Exception as exc:
        logger.debug(f"docstring_parser failed, falling back to plain: {exc}")
        from . import plain

        return plain.render(text, theme)

    # numpydoc Examples parsing is lossy — pull the raw section bodies
    # so we can use them instead of the parsed meta entries.
    numpydoc_sections = detect.extract_numpydoc_sections(doc_for_parse)

    if parsed.short_description:
        parts.append(f"<p><b>{html.escape(parsed.short_description)}</b></p>")

    if parsed.long_description:
        parts.append(blocks.paragraphs(parsed.long_description, theme))

    if parsed.params:
        parts.append(blocks.section_header("Parameters", theme))
        parts.append(param_list(parsed.params, theme))

    if parsed.returns is not None or getattr(parsed, "many_returns", None):
        parts.append(blocks.section_header("Returns", theme))
        if parsed.returns is not None:
            parts.append(returns(parsed.returns, theme))
        for ret in getattr(parsed, "many_returns", []) or []:
            if ret is parsed.returns:
                continue
            parts.append(returns(ret, theme))

    raises = list(getattr(parsed, "raises", []) or [])
    if raises:
        parts.append(blocks.section_header("Raises", theme, accent=theme["raise_accent"]))
        parts.append(raises_list(raises, theme))

    # Group remaining meta entries by section name so multi-entry
    # sections (numpydoc Examples emits one meta per doctest output
    # block) are rendered under a single header.
    grouped: OrderedDict[str, list] = OrderedDict()
    for meta in getattr(parsed, "meta", []) or []:
        names = getattr(meta, "args", []) or []
        if not names:
            continue
        key = names[0].lower()
        if key in HANDLED_META_NAMES:
            continue
        grouped.setdefault(key, []).append(meta)

    for key, metas in grouped.items():
        title = _title_case(key)
        parts.append(blocks.section_header(title, theme))
        if key == "examples":
            # Prefer the raw numpydoc section text (keeps >>> prompts).
            raw = numpydoc_sections.get("Examples")
            body = raw if raw else _join_meta_descriptions(metas)
            parts.append(blocks.code_block(body or "", theme))
        else:
            body = _join_meta_descriptions(metas)
            parts.append(blocks.paragraphs(body, theme))

    if not parts:
        from . import plain

        return plain.render(rest_after_sig or text, theme)
    return "\n".join(parts)


# --- Parameter / Returns / Raises rows --------------------------------------


def param_list(params, theme: dict[str, str]) -> str:
    """Parameter rows: coloured ``name : type = default``, description indented.

    All three header pieces share the body font + size so
    ``user_id : int`` reads as a single horizontal unit — colour is
    what distinguishes them.
    """
    rows: list[str] = []
    for p in params:
        name = html.escape(p.arg_name or "")
        type_name = html.escape(p.type_name or "")
        default = html.escape(p.default or "")

        header = [f'<span style="color:{theme["param_name"]};">{name}</span>']
        if type_name:
            header.append(f'<span style="color:{theme["muted"]};"> : </span><span style="color:{theme["param_type"]};">{type_name}</span>')
        if default:
            header.append(f'<span style="color:{theme["muted"]};"> = </span><span style="color:{theme["literal"]};">{default}</span>')
        desc = blocks.inline_format(p.description or "", theme).replace("\n", "<br>")
        rows.append(f'<div style="margin:8px 0 0 0;">{"".join(header)}<div style="margin:2px 0 0 20px;">{desc}</div></div>')
    return "\n".join(rows)


def returns(ret, theme: dict[str, str]) -> str:
    """Single Returns row. Handles the numpydoc ``name : type`` shape."""
    type_name = html.escape(ret.return_name or ret.type_name or "")
    desc = blocks.inline_format(ret.description or "", theme).replace("\n", "<br>")
    header = ""
    if type_name:
        if ret.return_name and ret.type_name and ret.return_name != ret.type_name:
            header = (
                f'<span style="color:{theme["param_name"]};">{html.escape(ret.return_name)}</span>'
                f'<span style="color:{theme["muted"]};"> : </span>'
                f'<span style="color:{theme["param_type"]};">{html.escape(ret.type_name)}</span>'
            )
        else:
            header = f'<span style="color:{theme["param_type"]};">{type_name}</span>'
    return f'<div style="margin:8px 0 0 0;">{header}<div style="margin:2px 0 0 20px;">{desc}</div></div>'


def raises_list(raises_iter, theme: dict[str, str]) -> str:
    """Raises rows — exception name in warm accent, description indented."""
    rows: list[str] = []
    for r in raises_iter:
        exc_name = html.escape(r.type_name or "")
        desc = blocks.inline_format(r.description or "", theme).replace("\n", "<br>")
        header = f'<span style="color:{theme["raise_accent"]};">{exc_name}</span>' if exc_name else ""
        rows.append(f'<div style="margin:8px 0 0 0;">{header}<div style="margin:2px 0 0 20px;">{desc}</div></div>')
    return "\n".join(rows)


# --- Helpers ----------------------------------------------------------------


def _join_meta_descriptions(metas) -> str:
    return "\n\n".join((m.description or "").strip() for m in metas if m.description)


def _title_case(name: str) -> str:
    """``'examples'`` → ``'Examples'``; ``'see also'`` → ``'See Also'``."""
    return " ".join(w.title() for w in name.split())


__all__ = [
    "AVAILABLE",
    "HANDLED_META_NAMES",
    "param_list",
    "raises_list",
    "render",
    "returns",
]
