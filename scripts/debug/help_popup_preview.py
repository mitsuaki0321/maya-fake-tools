"""Standalone preview for the Code Editor help popup rendering.

One-shot harness. Iterates on ``help_renderer.render_docstring`` by
showing canned docstring samples side-by-side in plain-text and HTML
form in a PySide6 window. Run with:

    uv run python scripts/debug/help_popup_preview.py

Not part of the shipped code — safe to delete when rendering is
signed off. Requires ``pygments``, ``docstring_parser``, and
``PySide6`` in the .venv; everything installed via
``uv add --group dev ...``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

# Make ``faketools`` importable without installing the package.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from faketools.tools.common.code_editor.ui.help_renderer import render_docstring  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Sample:
    title: str
    text: str


# -----------------------------------------------------------------------------
# Canned docstrings
# -----------------------------------------------------------------------------


def _numpy_abs_doc() -> str:
    # numpy.abs actual docstring, copied from numpy 1.26 for offline use.
    # (importing numpy at preview time would also work but that'd depend on
    # the sample's code path not failing on stub module paths — keep it
    # self-contained.)
    return """abs(x, /, out=None, *, where=True, casting='same_kind', order='K', dtype=None, subok=True[, signature])

Calculate the absolute value element-wise.

``np.abs`` is a shorthand for this function.

Parameters
----------
x : array_like
    Input array.
out : ndarray, None, or tuple of ndarray and None, optional
    A location into which the result is stored. If provided, it must
    have a shape that the inputs broadcast to. If not provided or
    None, a freshly-allocated array is returned.
where : array_like, optional
    This condition is broadcast over the input. At locations where
    the condition is True, the `out` array will be set to the ufunc
    result. Elsewhere, the `out` array will retain its original
    value.

Returns
-------
absolute : ndarray
    An ndarray containing the absolute value of each element in `x`.
    For complex input, ``a + ib``, the absolute value is
    :math:`\\sqrt{ a^2 + b^2 }`.
    This is a scalar if `x` is a scalar.

Examples
--------
>>> x = np.array([-1.2, 1.2])
>>> np.absolute(x)
array([1.2, 1.2])
>>> np.absolute(1.2 + 1j)
1.5620499351813308
"""


def _google_style_doc() -> str:
    return """fetch_user(user_id, *, include_avatar=False, timeout=30.0)

Fetch a user record from the backend.

Hits the public ``/users/<id>`` endpoint. Cached for 60 seconds via the
session-level LRU.

Args:
    user_id (int): Primary key of the user record. Must be positive.
    include_avatar (bool): Whether to also fetch the avatar blob.
        Defaults to False because the blob is ~200 KB per user.
    timeout (float): Per-request timeout in seconds.

Returns:
    User: The hydrated user record, with ``avatar`` populated iff
    ``include_avatar`` was True.

Raises:
    UserNotFound: The id resolved to no row.
    TransportError: Wrapped network / HTTP failures.

Examples:
    >>> u = fetch_user(42)
    >>> u.name
    'Alice'
"""


def _maya_cmds_help_doc() -> str:
    # Sample of what ``cmds.help("polyCube")`` prints inside Maya — format
    # matches what we saw when testing the existing context-menu help path.
    return """Synopsis: polyCube [flags] [String]

Flags:
  -ax -axis             Float Float Float
  -ch -constructionHistory on|off
  -cuv -createUVs        Int32
  -d  -depth            Float
  -h  -height           Float
   -n  -name             String
   -o  -object           on|off
   -sd -subdivisionsDepth Int32
  -sh -subdivisionsHeight Int32
   -sw -subdivisionsWidth Int32
  -tx -texture           Int32
  -w  -width             Float

Return value:
    String[]    Object name and node name

Modes:
    Create mode (default)
    Edit mode (-e)
    Query mode (-q)

Examples:
    cmds.polyCube(w=2, h=1, d=1, sx=10, sy=5, sz=5)
"""


def _unstructured_doc() -> str:
    return """do_thing(x)

Just does the thing. No params section, no returns section — just
prose so we verify the plain / low-structure path still looks decent.

It wraps, paragraphs split on blank lines, and that's about it.
"""


def _empty_doc() -> str:
    return ""


SAMPLES: list[Sample] = [
    Sample("numpy.abs (numpydoc)", _numpy_abs_doc()),
    Sample("Google-style", _google_style_doc()),
    Sample("Maya cmds.help (polyCube)", _maya_cmds_help_doc()),
    Sample("Unstructured prose", _unstructured_doc()),
    Sample("Empty", _empty_doc()),
]


# -----------------------------------------------------------------------------
# Preview window
# -----------------------------------------------------------------------------


class PreviewWindow(QMainWindow):
    """Main harness window. Left pane = sample list, right = split preview."""

    def __init__(self, samples: list[Sample]):
        super().__init__()
        self.setWindowTitle("Help popup rendering preview")
        self.resize(1400, 820)

        self._samples = samples

        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Sample list
        self._list = QListWidget()
        for s in samples:
            QListWidgetItem(s.title, self._list)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setFixedWidth(220)

        # Plain vs Rich split
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_pane("Plain text (current)", self._make_plain_view()))
        splitter.addWidget(self._build_pane("Rendered (prototype)", self._make_rich_view()))
        splitter.setSizes([560, 820])

        root.addWidget(self._list)
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

        # Dark-ish background to approximate the editor's look.
        self.setStyleSheet("QMainWindow { background-color: #1e1e1e; } QLabel { color: #d4d4d4; }")

        if samples:
            self._list.setCurrentRow(0)

    # ---------------- UI construction ----------------

    def _make_plain_view(self) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.WidgetWidth)
        self._apply_mono_font(view)
        # Explicit widget-level background so the rich view's HTML — which
        # deliberately doesn't paint its own bg — sits on a uniform surface.
        # Surface is LIGHTER than the code blocks inside the HTML so
        # signatures / examples read as "inset" panels, not raised cards.
        view.setStyleSheet("QTextEdit { background-color: #262626; color: #d4d4d4; border: 1px solid #3e3e42; padding: 8px; }")
        self._plain = view
        return view

    def _make_rich_view(self) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.WidgetWidth)
        self._apply_mono_font(view)
        # Surface is LIGHTER than the code blocks inside the HTML so
        # signatures / examples read as "inset" panels, not raised cards.
        view.setStyleSheet("QTextEdit { background-color: #262626; color: #d4d4d4; border: 1px solid #3e3e42; padding: 8px; }")
        self._rich = view
        return view

    def _build_pane(self, label_text: str, content: QTextEdit) -> QWidget:
        holder = QWidget()
        vbox = QVBoxLayout(holder)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("QLabel { color: #858585; padding: 2px 4px; font-weight: bold; }")
        vbox.addWidget(lbl)
        vbox.addWidget(content, 1)
        return holder

    def _apply_mono_font(self, view: QTextEdit) -> None:
        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setPointSize(10)
        view.setFont(font)

    # ---------------- behaviour ----------------

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._samples):
            s = self._samples[row]
            self._plain.setPlainText(s.text or "(empty)")
            self._rich.setHtml(render_docstring(s.text))


def main() -> int:
    app = QApplication(sys.argv)
    win = PreviewWindow(SAMPLES)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
