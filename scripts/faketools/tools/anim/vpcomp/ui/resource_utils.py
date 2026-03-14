"""UI asset loading utilities (SVG icons, QSS) for vpcomp."""

from __future__ import annotations

import os

from .....lib_ui.qt_compat import QByteArray, QFrame, QIcon, QPainter, QPixmap, Qt, QtSvg

_UI_DIR = os.path.dirname(__file__)
_ICONS_DIR = os.path.join(_UI_DIR, "icons")
_QSS_PATH = os.path.join(_UI_DIR, "style.qss")


def load_qss() -> str:
    """Load the shared dark-theme QSS and return as a string."""
    with open(_QSS_PATH, encoding="utf-8") as f:
        return f.read()


def make_separator() -> QFrame:
    """Create a thin horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    return line


def load_svg_icon(name: str, color: str | None = None, size: int = 16) -> QIcon:
    """Load icons/<name>.svg, replace currentColor with *color*, and return a QIcon.

    For delegate paint() which requires QPixmap instead of QIcon,
    use load_svg_pixmap().
    """
    svg_data = _read_svg(name, color)
    return _svg_to_icon(svg_data, size)


def load_svg_pixmap(name: str, color: str | None = None, size: int = 16) -> QPixmap:
    """Return a QPixmap for direct drawing inside paint()."""
    svg_data = _read_svg(name, color)
    return _svg_to_pixmap(svg_data, size)


def _read_svg(name: str, color: str | None) -> str:
    path = os.path.join(_ICONS_DIR, f"{name}.svg")
    with open(path, encoding="utf-8") as f:
        data = f.read()
    if color:
        data = data.replace("currentColor", color)
    return data


def _svg_to_pixmap(svg_data: str, size: int) -> QPixmap:
    renderer = QtSvg.QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _svg_to_icon(svg_data: str, size: int) -> QIcon:
    return QIcon(_svg_to_pixmap(svg_data, size))
