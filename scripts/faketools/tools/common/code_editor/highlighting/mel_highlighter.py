"""MEL syntax highlighter for the Code Editor.

Per-block regex state machine — the standard Qt :class:`QSyntaxHighlighter`
pattern. Much simpler than the Python highlighter's full-document
tokenize/cache because MEL syntax has minimal lookahead and the only
multi-line construct is ``/* ... */``, which Qt's
``previousBlockState`` / ``setCurrentBlockState`` mechanism handles
natively.

Token coverage parallels the VSCode MEL extension's ``tmLanguage``
(comments, strings + escape sequences, numbers, ``$variables``,
control keywords, types, ``proc`` declarations, calls), minus the
hardcoded Maya command / node-type lists. Those will plug in via the
``cmds.help("-list", "*")`` query that Phase 4 (autocomplete) builds.
"""

from __future__ import annotations

import re

from .....lib_ui.qt_compat import QFont, QSyntaxHighlighter, QTextCharFormat
from .syntax_config_loader import SyntaxConfigLoader


class MelHighlighter(QSyntaxHighlighter):
    """MEL syntax highlighter (regex state machine)."""

    # Block-state codes used with set/previousBlockState. Qt initialises
    # blocks to -1, which is treated as "not in a block comment".
    _STATE_NORMAL = 0
    _STATE_BLOCK_COMMENT = 1

    # Theme-key mapping. Mirrors the Python highlighter so both languages
    # consume the same ``themes/syntax_colors.json`` palette.
    _KIND_TO_FMTKEY = {
        "comment": "comment",
        "string": "string",
        "escape": "escape_sequence",
        "number": "number",
        "variable": "variable",
        "control_kw": "control_keyword",
        "type": "type_annotation",
        "def_kw": "def_class_keyword",
        "boolean": "boolean",
        "function": "function",
        "method": "method",
        "operator": "operator",
    }

    # Bold for keyword-like tokens. Style flags live here so the loader
    # stays a pure colour-table reader.
    _BOLD_KINDS = frozenset({"control_kw", "def_kw", "type", "boolean"})

    # Rainbow bracket depth keys — same cycle as the Python highlighter.
    _BRACKET_DEPTH_KEYS = ("bracket_1", "bracket_2", "bracket_3")

    # Keyword sets (mirrors the VSCode MEL.tmLanguage).
    _CONTROL_KEYWORDS = frozenset(
        {
            "if", "else", "for", "while", "do", "switch", "case", "default",
            "break", "continue", "return", "in", "source", "catch", "alias",
        }
    )
    _TYPE_KEYWORDS = frozenset({"int", "float", "string", "vector", "matrix", "void"})
    _DEF_KEYWORDS = frozenset({"global", "proc"})
    _BOOLEAN_KEYWORDS = frozenset(
        {"true", "false", "yes", "no", "on", "off", "null", "undefined"}
    )

    # Combined token regex with named groups so we can dispatch by kind.
    # Order in the alternation matters:
    #   * line / block comments must beat ``operator`` (``//`` would
    #     otherwise be parsed as two ``/`` operators).
    #   * strings must beat ``$variable`` so a ``$`` inside a string stays
    #     part of the string.
    #   * multi-char operators must beat single-char ones.
    # The ``string`` alternative tolerates an unterminated literal so a
    # half-typed ``"foo`` doesn't turn the highlighter into a no-op.
    _TOKEN_RE = re.compile(
        r"(?P<line_comment>//[^\n]*)"
        r"|(?P<block_comment_start>/\*)"
        r'|(?P<string>"(?:\\.|[^"\\\n])*(?:"|$))'
        r"|(?P<number>\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)[LlUuFf]*\b)"
        r"|(?P<variable>\$[A-Za-z_]\w*)"
        r"|(?P<identifier>[A-Za-z_]\w*)"
        r"|(?P<bracket>[()\[\]{}])"
        r"|(?P<operator>->|::|==|!=|<=|>=|&&|\|\||<<|>>|\+\+|--|[-+*/%=<>!&|^~?])"
    )

    _BLOCK_COMMENT_END_RE = re.compile(r"\*/")
    _ESCAPE_RE = re.compile(r"\\.")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = SyntaxConfigLoader()
        self._fmt = {kind: self._build_fmt(kind, key) for kind, key in self._KIND_TO_FMTKEY.items()}
        for i, key in enumerate(self._BRACKET_DEPTH_KEYS):
            self._fmt[f"br_d{i}"] = self._cfg.get_format(key)

    def _build_fmt(self, kind: str, fmt_key: str) -> QTextCharFormat:
        """Resolve a format from the loader and apply local style flags.

        ``QTextCharFormat`` is copied before mutation so the loader's cached
        entry stays unmodified — relevant if the loader is ever reloaded or
        shared.
        """
        fmt = self._cfg.get_format(fmt_key)
        if kind in self._BOLD_KINDS:
            fmt = QTextCharFormat(fmt)
            fmt.setFontWeight(QFont.Bold)
        return fmt

    # -------------------- QSyntaxHighlighter hook --------------------

    def highlightBlock(self, text: str) -> None:
        n = len(text)
        pos = 0

        # Resume an open /* */ from the previous block.
        if self.previousBlockState() == self._STATE_BLOCK_COMMENT:
            end_match = self._BLOCK_COMMENT_END_RE.search(text)
            if end_match is None:
                self.setFormat(0, n, self._fmt["comment"])
                self.setCurrentBlockState(self._STATE_BLOCK_COMMENT)
                return
            self.setFormat(0, end_match.end(), self._fmt["comment"])
            pos = end_match.end()

        # Default to normal state; flipped only if a block comment opens
        # and doesn't close on this line.
        self.setCurrentBlockState(self._STATE_NORMAL)

        bracket_depth = 0
        n_bracket_colors = len(self._BRACKET_DEPTH_KEYS)

        # ``proc`` declaration tracking — `proc [returnType] funcName(...)`.
        # The flag lives only within the current line; multi-line proc
        # headers (rare) won't get the function name coloured. Adding a
        # dedicated block state for that case is left for a follow-up.
        after_proc = False
        after_proc_type = False

        while pos < n:
            match = self._TOKEN_RE.search(text, pos)
            if match is None:
                break

            kind = match.lastgroup
            tok_text = match.group()
            tok_start = match.start()
            tok_end = match.end()

            if kind == "line_comment":
                self.setFormat(tok_start, tok_end - tok_start, self._fmt["comment"])
                pos = tok_end
                continue

            if kind == "block_comment_start":
                end_match = self._BLOCK_COMMENT_END_RE.search(text, tok_end)
                if end_match is None:
                    # /* ... continues past EOL — flag the next block.
                    self.setFormat(tok_start, n - tok_start, self._fmt["comment"])
                    self.setCurrentBlockState(self._STATE_BLOCK_COMMENT)
                    return
                self.setFormat(tok_start, end_match.end() - tok_start, self._fmt["comment"])
                pos = end_match.end()
                continue

            if kind == "string":
                self.setFormat(tok_start, tok_end - tok_start, self._fmt["string"])
                # Sub-colour escape sequences (\n, \", \\, ...) inside the literal.
                for esc in self._ESCAPE_RE.finditer(tok_text):
                    self.setFormat(tok_start + esc.start(), esc.end() - esc.start(), self._fmt["escape"])
                pos = tok_end
                continue

            if kind == "number":
                self.setFormat(tok_start, tok_end - tok_start, self._fmt["number"])
                pos = tok_end
                continue

            if kind == "variable":
                self.setFormat(tok_start, tok_end - tok_start, self._fmt["variable"])
                pos = tok_end
                continue

            if kind == "identifier":
                if tok_text in self._CONTROL_KEYWORDS:
                    self.setFormat(tok_start, tok_end - tok_start, self._fmt["control_kw"])
                    after_proc = False
                    after_proc_type = False
                elif tok_text in self._TYPE_KEYWORDS:
                    self.setFormat(tok_start, tok_end - tok_start, self._fmt["type"])
                    if after_proc:
                        # `proc int foo(...)` — name still pending after the type.
                        after_proc_type = True
                        after_proc = False
                    else:
                        after_proc_type = False
                elif tok_text in self._DEF_KEYWORDS:
                    self.setFormat(tok_start, tok_end - tok_start, self._fmt["def_kw"])
                    after_proc = tok_text == "proc"
                    after_proc_type = False
                elif tok_text in self._BOOLEAN_KEYWORDS:
                    self.setFormat(tok_start, tok_end - tok_start, self._fmt["boolean"])
                    after_proc = False
                    after_proc_type = False
                else:
                    if after_proc or after_proc_type:
                        # The name in `proc [type] name`.
                        self.setFormat(tok_start, tok_end - tok_start, self._fmt["function"])
                        after_proc = False
                        after_proc_type = False
                    elif self._next_nonspace(text, tok_end) == "(":
                        # `func(` style call. MEL command-style calls
                        # (`polyCube -w 1`) have no parens and stay default.
                        self.setFormat(tok_start, tok_end - tok_start, self._fmt["method"])
                pos = tok_end
                continue

            if kind == "bracket":
                if tok_text in "([{":
                    fmt = self._fmt[f"br_d{bracket_depth % n_bracket_colors}"]
                    bracket_depth += 1
                else:
                    if bracket_depth > 0:
                        bracket_depth -= 1
                    fmt = self._fmt[f"br_d{bracket_depth % n_bracket_colors}"]
                self.setFormat(tok_start, tok_end - tok_start, fmt)
                pos = tok_end
                continue

            if kind == "operator":
                self.setFormat(tok_start, tok_end - tok_start, self._fmt["operator"])
                pos = tok_end
                continue

            # Unreachable — every named group above is handled.
            pos = tok_end

    @staticmethod
    def _next_nonspace(text: str, pos: int) -> str:
        """Return the next non-blank character at or after ``pos`` (or '')."""
        n = len(text)
        while pos < n and text[pos] in " \t":
            pos += 1
        return text[pos] if pos < n else ""
