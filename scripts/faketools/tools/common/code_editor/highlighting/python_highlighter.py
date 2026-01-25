"""
Python syntax highlighter for the Maya Code Editor.

Provides comprehensive Python syntax highlighting with support for:
- Comments, strings (including multiline), numbers, operators, brackets
- Keywords (for, in, return, etc.), def/class keywords, definition names
- True/False/None constants
- Import statements with uncolored identifiers
- Decorators, type annotations, keyword arguments (configurable)
- Method calls (obj.method(), pkg.mod.func()) and bare function calls
- Capitalized class constructors (Name())

Uses single tokenization per document revision for efficiency.
"""

from collections import defaultdict
import io
import keyword
import token as _token
import tokenize as _tokenize

from ..ui.qt_compat import QSyntaxHighlighter
from .syntax_config_loader import SyntaxConfigLoader


class PythonHighlighter(QSyntaxHighlighter):
    """
    Advanced Python syntax highlighter with configurable features.

    Features:
        - Comments, strings (multiline support), numbers, operators, brackets
        - Keywords (for, in, return, etc.) and def/class keywords with definition names
        - True/False/None as boolean colors
        - Import/from statement identifiers remain uncolored (white)
        - Decorators, type annotations in function signatures, kwarg names (toggleable)
        - Dotted method calls (self.foo(), pkg.mod.func()) -> method color
        - Bare function calls (func()) -> method color
        - Capitalized bare calls (Name()) -> class color (toggleable)

    Re-tokenization occurs once per document revision with differential application in highlightBlock.
    """

    # Feature toggles (set to False to disable)
    ENABLE_DECORATOR = True
    ENABLE_TYPE_ANNOT = True
    ENABLE_KWARG = True
    ENABLE_METHOD_TAIL = True  # Color obj.method() / pkg.mod.Func() / bare call 'name()'
    ENABLE_CAPITAL_CALL = True  # Color bare 'Name(' as class

    # Token type -> theme key mapping (colors retrieved from SyntaxConfigLoader)
    _KIND_TO_FMTKEY = {
        # Core features
        "kw": "control_keyword",
        "defk": "def_class_keyword",
        "defname": "function",  # Function name after def
        "classname": "class",  # Class name after class / inferred class calls
        "str": "string",
        "cmt": "comment",
        "num": "number",
        "br": "bracket",
        "op": "operator",
        # Extended features
        "decorator": "decorator",
        "type": "type_annotation",
        "kwarg": "variable",
        "const": "boolean",  # True / False / None
        "method": "method",  # Method/function calls & bare calls
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = SyntaxConfigLoader()
        self._fmt = {k: self._cfg.get_format(v) for k, v in self._KIND_TO_FMTKEY.items()}
        self._spans = {}
        self._rev = -1
        self._kw = set(keyword.kwlist)

    # -------------------- Safe tokenization (handles incomplete code) --------------------

    def _safe_tokenize(self, text: str):
        """Apply newline/bracket/triple-quote completion before tokenizing."""
        patched = text
        if not patched.endswith("\n"):
            patched += "\n"
        patched = self._balance_brackets(patched)
        patched = self._close_unfinished_triple_quotes(patched)
        try:
            rd = io.StringIO(patched).readline
            return list(_tokenize.generate_tokens(rd))
        except (_tokenize.TokenError, IndentationError, SyntaxError):
            # Handle tokenization errors gracefully
            return []

    def _balance_brackets(self, text: str) -> str:
        """Add closing brackets to match unbalanced opening brackets."""
        opens = {"(": ")", "[": "]", "{": "}"}
        closes = {")": "(", "]": "[", "}": "{"}
        stack = []
        for ch in text:
            if ch in opens:
                stack.append(ch)
            elif ch in closes and stack and stack[-1] == closes[ch]:
                stack.pop()
        suffix = "".join(opens[ch] for ch in reversed(stack))
        return text + suffix

    def _close_unfinished_triple_quotes(self, text: str) -> str:
        """Close unfinished triple quotes."""
        dq = text.count('"""')
        sq = text.count("'''")
        if dq % 2 == 1:
            text += '"""'
        if sq % 2 == 1:
            text += "'''"
        return text

    # -------------------- Token utilities --------------------

    def _next_meaningful(self, tokens, j):
        """Skip NL/NEWLINE/INDENT/DEDENT tokens and return next meaningful token index."""
        n = len(tokens)
        while j < n and tokens[j].type in (_tokenize.NL, _tokenize.NEWLINE, _tokenize.INDENT, _tokenize.DEDENT):
            j += 1
        return j

    def _highlight_dotted_name(self, tokens, j, add_token, kind):
        """Highlight tokens[j] (assumed to be NAME) and following '. NAME' chain with given kind."""
        n = len(tokens)
        if j < n and tokens[j].type == _tokenize.NAME:
            add_token(tokens[j], kind)
            j += 1
            while j + 1 < n and tokens[j].type == _tokenize.OP and tokens[j].string == "." and tokens[j + 1].type == _tokenize.NAME:
                add_token(tokens[j + 1], kind)
                j += 2
        return j

    # -------------------- Full tokenization -> line-based spans construction --------------------

    def _build_spans(self, text: str):
        spans = defaultdict(list)
        lines = text.splitlines()
        tokens = self._safe_tokenize(text)
        n = len(tokens)

        def add_span(row0: int, c1: int, c2: int, kind: str):
            if row0 < 0:
                return
            if row0 >= len(lines):
                return
            if c2 <= c1:
                return
            spans[row0].append((c1, c2, kind))

        def add_token(tok, kind: str):
            (sr, sc), (er, ec) = tok.start, tok.end
            sr0 = sr - 1
            er0 = er - 1
            if sr0 == er0:
                add_span(sr0, sc, ec, kind)
            else:
                if 0 <= sr0 < len(lines):
                    add_span(sr0, sc, len(lines[sr0]), kind)
                row = sr0 + 1
                while row < er0:
                    if 0 <= row < len(lines):
                        add_span(row, 0, len(lines[row]), kind)
                    row += 1
                if 0 <= er0 < len(lines):
                    add_span(er0, 0, ec, kind)

        after_def = False
        after_class = False
        waiting_def_params = False  # After function name, waiting for '('
        in_def_params = False  # Inside def (...) parameters
        def_paren_depth = 0

        paren_depth = 0  # Overall () depth for kwarg detection
        pending_type_after_colon = False
        pending_type_after_arrow = False

        in_def_signature = False  # Inside def header (until ':')
        in_import_stmt = False  # Inside import/from statement (until newline)

        i = 0
        while i < n:
            tok = tokens[i]
            ttype = tok.type
            tstr = tok.string

            # Clear import statement flag at logical line end
            if ttype == _tokenize.NEWLINE and in_import_stmt and paren_depth == 0:
                in_import_stmt = False

            # Track parentheses depth
            if ttype == _tokenize.OP:
                exact = _tokenize.EXACT_TOKEN_TYPES.get(tstr)
                if exact == _token.LPAR:
                    paren_depth += 1
                    if waiting_def_params:
                        in_def_params = True
                        def_paren_depth = 1
                        waiting_def_params = False
                    elif in_def_params:
                        def_paren_depth += 1
                elif exact == _token.RPAR:
                    if paren_depth > 0:
                        paren_depth -= 1
                    if in_def_params:
                        if def_paren_depth > 0:
                            def_paren_depth -= 1
                        if def_paren_depth == 0:
                            in_def_params = False

            # Decorators (suppressed during import statements)
            if self.ENABLE_DECORATOR and not in_import_stmt and ttype == _tokenize.OP and tstr == "@":
                j = i + 1
                j = self._next_meaningful(tokens, j)
                if j < n and tokens[j].type == _tokenize.NAME:
                    self._highlight_dotted_name(tokens, j, add_token, "decorator")

            # Pending type annotations (after ':' or '->') - suppressed during import
            if self.ENABLE_TYPE_ANNOT and not in_import_stmt and ttype == _tokenize.NAME and (pending_type_after_colon or pending_type_after_arrow):
                self._highlight_dotted_name(tokens, i, add_token, "type")
                pending_type_after_colon = False
                pending_type_after_arrow = False

            # Keyword arguments (kwarg): suppressed during import
            if self.ENABLE_KWARG and not in_import_stmt and ttype == _tokenize.NAME:
                j = self._next_meaningful(tokens, i + 1)
                if j < n and tokens[j].type == _tokenize.OP and tokens[j].string == "=" and paren_depth > 0:
                    add_token(tok, "kwarg")

            # --- Main syntax coloring ---
            if ttype == _tokenize.COMMENT:
                add_token(tok, "cmt")

            elif ttype == _tokenize.STRING:
                add_token(tok, "str")

            elif ttype == _tokenize.NUMBER:
                add_token(tok, "num")

            elif ttype == _tokenize.NAME:
                # True/False/None get boolean color
                if tstr in ("True", "False", "None"):
                    add_token(tok, "const")
                    after_def = False
                    after_class = False

                elif tstr in self._kw:
                    if tstr == "def":
                        add_token(tok, "defk")
                        after_def = True
                        after_class = False
                        in_def_signature = True

                    elif tstr == "class":
                        add_token(tok, "defk")
                        after_class = True
                        after_def = False

                    elif tstr in ("import", "from"):
                        # Color the keyword itself, then suppress other coloring for import statement
                        add_token(tok, "kw")
                        in_import_stmt = True
                        after_def = False
                        after_class = False

                    else:
                        add_token(tok, "kw")
                        after_def = False
                        after_class = False

                else:
                    if after_def:
                        add_token(tok, "defname")
                        waiting_def_params = True
                        after_def = False
                    elif after_class:
                        add_token(tok, "classname")
                        after_class = False
                    else:
                        # Dotted method calls (obj.method() / pkg.mod.Func())
                        if self.ENABLE_METHOD_TAIL and not in_import_stmt:
                            j = i
                            last_tok = tok
                            had_dot = False

                            # Follow forward .name chain to get the final NAME
                            while (
                                j + 2 < n
                                and tokens[j + 1].type == _tokenize.OP
                                and tokens[j + 1].string == "."
                                and tokens[j + 2].type == _tokenize.NAME
                            ):
                                had_dot = True
                                last_tok = tokens[j + 2]
                                j += 2

                            # Case where previous token is '.' (e.g., super().foo)
                            if not had_dot and i > 0 and tokens[i - 1].type == _tokenize.OP and tokens[i - 1].string == ".":
                                had_dot = True
                                last_tok = tok

                            # If next meaningful token is '(' then it's a call
                            k = self._next_meaningful(tokens, j + 1)
                            if had_dot and k < n and tokens[k].type == _tokenize.OP and tokens[k].string == "(":
                                name_str = last_tok.string
                                if name_str and name_str[:1].isupper():
                                    add_token(last_tok, "classname")
                                else:
                                    add_token(last_tok, "method")

                        # Bare 'Name(' with capital first letter gets class color
                        if self.ENABLE_CAPITAL_CALL and not in_import_stmt:
                            j2 = self._next_meaningful(tokens, i + 1)
                            if j2 < n and tokens[j2].type == _tokenize.OP and tokens[j2].string == "(":
                                if tstr[:1].isupper():
                                    add_token(tok, "classname")

                        # Bare function calls 'name(' also get method color
                        if self.ENABLE_METHOD_TAIL and not in_import_stmt:
                            j3 = self._next_meaningful(tokens, i + 1)
                            is_call = j3 < n and tokens[j3].type == _tokenize.OP and tokens[j3].string == "("
                            prev_is_dot = i > 0 and tokens[i - 1].type == _tokenize.OP and tokens[i - 1].string == "."
                            if is_call and not prev_is_dot:
                                # Let capital 'Name(' be handled by class color if enabled
                                if not (self.ENABLE_CAPITAL_CALL and tstr[:1].isupper()):
                                    add_token(tok, "method")
                        # Regular NAMEs remain uncolored

            elif ttype == _tokenize.OP:
                exact = _tokenize.EXACT_TOKEN_TYPES.get(tstr)

                # Type annotation triggers (suppressed during import)
                if self.ENABLE_TYPE_ANNOT and not in_import_stmt:
                    if tstr == ":":
                        if in_def_params:
                            pending_type_after_colon = True
                        # Header-ending ':' (paren_depth==0) ends header
                        if in_def_signature and paren_depth == 0:
                            in_def_signature = False
                    elif tstr == "->" and in_def_signature:
                        # Return type annotation only in function header
                        pending_type_after_arrow = True

                # Brackets get bracket color, punctuation stays uncolored, rest get operator color
                if exact in (_token.LPAR, _token.RPAR, _token.LSQB, _token.RSQB, _token.LBRACE, _token.RBRACE):
                    add_token(tok, "br")
                elif tstr in (":", ",", ".", ";"):
                    pass
                else:
                    add_token(tok, "op")

            i += 1

        for row in spans:
            spans[row].sort(key=lambda x: x[0])
        return dict(spans)

    # -------------------- QSyntaxHighlighter hooks --------------------

    def highlightBlock(self, text: str):
        doc = self.document()
        if not self._spans or self._rev != doc.revision():
            self._spans = self._build_spans(doc.toPlainText())
            self._rev = doc.revision()

        row = self.currentBlock().blockNumber()
        for c1, c2, kind in self._spans.get(row, ()):
            fmt = self._fmt.get(kind)
            if fmt is not None and 0 <= c1 < c2 <= len(text):
                self.setFormat(c1, c2 - c1, fmt)
