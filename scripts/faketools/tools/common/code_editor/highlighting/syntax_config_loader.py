"""
Syntax highlighting configuration loader.

Reads the bundled ``themes/syntax_colors.json`` and exposes per-token
:class:`QTextCharFormat` objects (foreground colour only). Style attributes
like bold belong to the consumer — see :class:`PythonHighlighter` — so this
module stays a pure colour-table loader.
"""

from __future__ import annotations

import json
from logging import getLogger
import os

from .....lib_ui.qt_compat import QColor, QTextCharFormat

logger = getLogger(__name__)


class SyntaxConfigLoader:
    """Loads and caches per-token QTextCharFormat objects from JSON."""

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            current_dir = os.path.dirname(__file__)
            config_path = os.path.join(current_dir, "..", "themes", "syntax_colors.json")

        self.config_path = config_path
        self.formats: dict[str, QTextCharFormat] = {}
        self._load()

    def _load(self):
        """Populate :attr:`formats` from the JSON config.

        Failures log a warning and leave ``formats`` empty — the editor stays
        usable without colour rather than silently masking corruption with a
        hardcoded duplicate of the JSON.
        """
        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as exc:
            logger.warning(f"syntax config load failed at {self.config_path}: {exc}")
            return

        for token_type, color_hex in (config.get("colors") or {}).items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color_hex))
            self.formats[token_type] = fmt

    def get_format(self, token_type: str) -> QTextCharFormat:  # type: ignore
        """Return the format for ``token_type``; empty default on miss."""
        return self.formats.get(token_type, QTextCharFormat())
