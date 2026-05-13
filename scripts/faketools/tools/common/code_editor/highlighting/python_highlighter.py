"""
Python syntax highlighter for the Code Editor.

Provides comprehensive Python syntax highlighting with support for:
- Comments, strings (including multiline), numbers, operators, brackets
- Keywords (for, in, return, etc.), def/class keywords, definition names
- True/False/None constants
- Import statements with uncolored identifiers
- Decorators, type annotations, keyword arguments (configurable)
- Method calls (obj.method(), pkg.mod.func()) and bare function calls
- Capitalized class constructors (Name())

Rebuilds span cache at most once per debounce window while typing; re-uses
stale spans in between so keystrokes never trigger a full tokenize pass.
"""

from collections import defaultdict
import io
import keyword
import token as _token
import tokenize as _tokenize

from .....lib_ui.qt_compat import QFont, QSyntaxHighlighter, QTextCharFormat, QTimer
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

    Re-tokenization is debounced: character-only edits reuse the previous span
    cache and schedule a single rebuild after _REBUILD_DELAY_MS of typing, while
    edits that change the block count rebuild synchronously to avoid stale spans
    being misaligned against shifted block numbers.
    """

    # Debounce window (ms) between last keystroke and full re-tokenize.
    # Short enough that users don't perceive color lag, long enough that bursts
    # of typing collapse into a single rebuild instead of one per character.
    _REBUILD_DELAY_MS = 30

    # Feature toggles (set to False to disable)
    ENABLE_DECORATOR = True
    ENABLE_TYPE_ANNOT = True
    ENABLE_KWARG = True
    ENABLE_METHOD_TAIL = True  # Color obj.method() / pkg.mod.Func() / bare call 'name()'
    ENABLE_CAPITAL_CALL = True  # Color bare 'Name(' as class

    # Bracket depth colors cycle through these theme keys (rainbow brackets).
    _BRACKET_DEPTH_KEYS = ("bracket_1", "bracket_2", "bracket_3")

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
        "op": "operator",
        # Extended features
        "decorator": "decorator",
        "type": "type_annotation",
        "kwarg": "variable",
        "const": "boolean",  # True / False / None
        "method": "method",  # Method/function calls & bare calls
    }

    # Kinds rendered in bold. Style attributes live here so the loader stays
    # a pure colour-table reader.
    _BOLD_KINDS = frozenset({"kw", "defk", "const", "classname", "decorator"})

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = SyntaxConfigLoader()
        self._fmt = {k: self._build_fmt(k, v) for k, v in self._KIND_TO_FMTKEY.items()}
        # Per-depth bracket formats (kind name: "br_d{i}" for cycle index i).
        for i, key in enumerate(self._BRACKET_DEPTH_KEYS):
            self._fmt[f"br_d{i}"] = self._cfg.get_format(key)
        self._spans = {}
        self._rev = -1
        self._last_block_count = 0
        self._kw = set(keyword.kwlist)

        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.timeout.connect(self._on_rebuild_timer)

    def _build_fmt(self, kind: str, fmt_key: str) -> "QTextCharFormat":
        """Resolve a colour from the loader and apply local style flags.

        ``QTextCharFormat`` is copied before mutation so the loader's
        cached entry stays unmodified — relevant if the loader is ever
        reloaded or shared.
        """
        fmt = self._cfg.get_format(fmt_key)
        if kind in self._BOLD_KINDS:
            fmt = QTextCharFormat(fmt)
            fmt.setFontWeight(QFont.Bold)
        return fmt

    # -------------------- Safe tokenization (handles incomplete code) --------------------

    def _safe_tokenize(self, text: str):
        """Apply newline/bracket/triple-quote completion before tokenizing."""
        patched = text
        if not patched.endswith("\n"):
            patched += "\n"
        patched = self._close_unfinished_structures(patched)
        try:
            rd = io.StringIO(patched).readline
            return list(_tokenize.generate_tokens(rd))
        except (_tokenize.TokenError, IndentationError, SyntaxError):
            # Handle tokenization errors gracefully
            return []

    def _close_unfinished_structures(self, text: str) -> str:
        """Append closing brackets and triple quotes for any unfinished structures.

        Walks the text with a small state machine so brackets and quote chars
        inside comments or strings are ignored — naive char counting was wrong
        for cases like ``# foo'''`` (unbalanced ``'''`` inside a comment) which
        used to make ``tokenize`` fail and leave the document uncolored.

        Single-line strings unterminated at a newline are closed in place by
        inserting the matching quote just before the newline; otherwise
        ``tokenize`` raises ``TokenError`` for the literal and the whole
        document falls back to empty spans (no colouring anywhere), which is
        what users see the instant they delete a closing quote mid-edit.
        """
        opens = {"(": ")", "[": "]", "{": "}"}
        closes = {")": "(", "]": "[", "}": "{"}
        NORMAL, LCOMMENT, S_STR, D_STR, S_TRI, D_TRI = range(6)
        state = NORMAL
        stack: list[str] = []
        insertions: list[tuple[int, str]] = []
        i = 0
        n = len(text)
        while i < n:
            c = text[i]
            if state == NORMAL:
                if c == "'" and text.startswith("'''", i):
                    state = S_TRI
                    i += 3
                    continue
                if c == '"' and text.startswith('"""', i):
                    state = D_TRI
                    i += 3
                    continue
                if c == "'":
                    state = S_STR
                elif c == '"':
                    state = D_STR
                elif c == "#":
                    state = LCOMMENT
                elif c in opens:
                    stack.append(c)
                elif c in closes and stack and stack[-1] == closes[c]:
                    stack.pop()
                i += 1
            elif state == LCOMMENT:
                if c == "\n":
                    state = NORMAL
                i += 1
            elif state in (S_STR, D_STR):
                if c == "\\" and i + 1 < n:
                    i += 2
                    continue
                quote = "'" if state == S_STR else '"'
                if c == "\n":
                    insertions.append((i, quote))
                    state = NORMAL
                elif c == quote:
                    state = NORMAL
                i += 1
            elif state == S_TRI:
                if text.startswith("'''", i):
                    state = NORMAL
                    i += 3
                    continue
                i += 1
            elif state == D_TRI:
                if text.startswith('"""', i):
                    state = NORMAL
                    i += 3
                    continue
                i += 1

        # Close unfinished triple quote first — bracket completion belongs
        # outside the (now-closed) string, not inside it.
        suffix_parts: list[str] = []
        if state == S_TRI:
            suffix_parts.append("'''")
        elif state == D_TRI:
            suffix_parts.append('"""')
        suffix_parts.extend(opens[c] for c in reversed(stack))
        suffix = "".join(suffix_parts)

        if not insertions:
            return text + suffix

        parts: list[str] = []
        last = 0
        for pos, ins in insertions:
            parts.append(text[last:pos])
            parts.append(ins)
            last = pos
        parts.append(text[last:])
        parts.append(suffix)
        return "".join(parts)

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

        bracket_depth = 0  # Combined nesting depth across (), [], {} for rainbow brackets
        n_bracket_colors = len(self._BRACKET_DEPTH_KEYS)

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
                            if j2 < n and tokens[j2].type == _tokenize.OP and tokens[j2].string == "(" and tstr[:1].isupper():
                                add_token(tok, "classname")

                        # Bare function calls 'name(' also get method color
                        if self.ENABLE_METHOD_TAIL and not in_import_stmt:
                            j3 = self._next_meaningful(tokens, i + 1)
                            is_call = j3 < n and tokens[j3].type == _tokenize.OP and tokens[j3].string == "("
                            prev_is_dot = i > 0 and tokens[i - 1].type == _tokenize.OP and tokens[i - 1].string == "."
                            # Let capital 'Name(' be handled by class color if enabled
                            if is_call and not prev_is_dot and not (self.ENABLE_CAPITAL_CALL and tstr[:1].isupper()):
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

                # Brackets get depth-cycled color, punctuation stays uncolored, rest get operator color
                if exact in (_token.LPAR, _token.LSQB, _token.LBRACE):
                    add_token(tok, f"br_d{bracket_depth % n_bracket_colors}")
                    bracket_depth += 1
                elif exact in (_token.RPAR, _token.RSQB, _token.RBRACE):
                    if bracket_depth > 0:
                        bracket_depth -= 1
                    add_token(tok, f"br_d{bracket_depth % n_bracket_colors}")
                elif tstr in (":", ",", ".", ";"):
                    pass
                else:
                    add_token(tok, "op")

            i += 1

        for row in spans:
            spans[row].sort(key=lambda x: x[0])
        return dict(spans)

    # -------------------- Span cache management --------------------

    def _rebuild_now(self):
        """Synchronously rebuild the span cache from the current document text."""
        doc = self.document()
        if doc is None:
            return
        self._spans = self._build_spans(doc.toPlainText())
        self._rev = doc.revision()
        self._last_block_count = doc.blockCount()

    def _on_rebuild_timer(self):
        """Timer callback: rebuild spans, then re-apply formats via rehighlight()."""
        doc = self.document()
        if doc is None:
            return
        if self._rev == doc.revision():
            # A synchronous rebuild (e.g. triggered by block count change) already
            # caught up with the current revision — nothing to do.
            return
        self._rebuild_now()
        # rehighlight() re-invokes highlightBlock for every block; each call now
        # hits the fresh cache and only does the cheap setFormat work.
        self.rehighlight()

    # -------------------- QSyntaxHighlighter hooks --------------------

    def highlightBlock(self, text: str):
        doc = self.document()
        rev = doc.revision()
        block_count = doc.blockCount()

        was_empty = not self._spans

        if not self._spans:
            # First call: must rebuild synchronously so the initial paint is correct.
            self._rebuild_now()
        elif block_count != self._last_block_count:
            # Line count shifted: block-indexed spans would misalign against the new
            # layout, so rebuild synchronously to avoid a visible mis-coloring frame.
            # (Tried debouncing this — the new line painted briefly uncolored until
            # the next keystroke, which is more jarring than the rebuild itself.)
            self._rebuild_now()
        elif rev != self._rev and not self._rebuild_timer.isActive():
            # Character-only edit: keep using stale spans for now and coalesce
            # further keystrokes into a single rebuild after the debounce window.
            self._rebuild_timer.start(self._REBUILD_DELAY_MS)

        # Recovery path: if a prior tokenize failure had emptied _spans and the
        # rebuild above produced real spans, Qt only re-invokes highlightBlock
        # for the block the user just edited — every other line would stay
        # uncoloured. Schedule one full rehighlight so they repaint.
        if was_empty and self._spans:
            QTimer.singleShot(0, self.rehighlight)

        row = self.currentBlock().blockNumber()
        n = len(text)
        for c1, c2, kind in self._spans.get(row, ()):
            fmt = self._fmt.get(kind)
            if fmt is None or c1 < 0 or c1 >= n:
                continue
            # Clip stale spans to the current line length: when the user
            # backspaces inside a comment, the cached span still ends past the
            # now-shorter line and used to be dropped entirely, flashing the
            # line uncolored until the debounce-driven rebuild caught up.
            end = c2 if c2 <= n else n
            if end > c1:
                self.setFormat(c1, end - c1, fmt)
