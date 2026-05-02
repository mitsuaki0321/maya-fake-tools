"""Auto-indent entry point invoked by the editor's ``handle_return_key``.

Delegates the actual algorithm to :class:`IndentResolver` (in
``languages/indent_resolver.py``), which each language profile can
subclass via :attr:`LanguageProfile.indent_resolver`. When no profile
is supplied (or its resolver is ``None``), a default
:class:`IndentResolver` instance is used -- it implements the
bracket-based rules without any language-specific Rule 0.
"""

from __future__ import annotations

from typing import Optional

from ..languages import LanguageProfile
from ..languages.indent_resolver import IndentResolver

# Single shared fallback. Stateless, so reusing across calls is safe.
_DEFAULT_RESOLVER = IndentResolver()


def compute_indent(
    document,
    block_number: int,
    current_line: str,
    text_before_cursor: str,
    language: Optional[LanguageProfile] = None,
) -> str:
    """Decide the indent string for a new line inserted at the cursor.

    Args:
        document: Active ``QTextDocument``.
        block_number (int): Block index of the line being split.
        current_line (str): Full text of the line being split.
        text_before_cursor (str): Text on that line up to the cursor.
        language (Optional[LanguageProfile]): Profile whose
            ``indent_resolver`` drives the computation. When ``None`` (or
            its resolver is ``None``) the default resolver is used --
            language-specific Rule 0 is skipped, but the bracket-based
            rules still run.

    Returns:
        str: Whitespace (or, for bullet-style languages, leading prefix)
            to insert immediately after the newline.
    """
    resolver = language.indent_resolver if (language is not None and language.indent_resolver is not None) else _DEFAULT_RESOLVER
    return resolver.compute(document, block_number, current_line, text_before_cursor)
