"""
Syntax highlighting configuration loader.
Loads color schemes and token rules from JSON configuration files.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..ui.qt_compat import QColor, QFont, QTextCharFormat
from ..utils.logger_config import get_logger

# Set up module logger
logger = get_logger(__name__)


class SyntaxConfigLoader:
    """Loads and manages syntax highlighting configuration."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default path relative to this file
            current_dir = os.path.dirname(__file__)
            config_path = os.path.join(current_dir, "..", "themes", "syntax_colors.json")

        self.config_path = config_path
        self.config = None
        self.formats = {}
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                self.config = json.load(f)

            # Create QTextCharFormat objects from color configuration
            self._create_formats()

        except Exception as e:
            logger.warning(f"Could not load syntax config from {self.config_path}: {e}")
            # Fallback to hardcoded values
            self._create_fallback_config()

    def _create_formats(self):
        """Create QTextCharFormat objects from loaded config."""
        colors = self.config.get("colors", {})

        for token_type, color_hex in colors.items():
            format_obj = QTextCharFormat()
            format_obj.setForeground(QColor(color_hex))

            # Apply bold formatting to specific types
            if token_type in ["control_keyword", "def_class_keyword", "boolean", "class", "decorator"]:
                format_obj.setFontWeight(QFont.Bold)

            self.formats[token_type] = format_obj

    def _create_fallback_config(self):
        """Create fallback configuration if file loading fails."""
        fallback_colors = {
            "control_keyword": "#c586c0",
            "def_class_keyword": "#569cd6",
            "boolean": "#559ad3",
            "string": "#ce9178",
            "comment": "#6a9955",
            "number": "#b5cea8",
            "function": "#dcdcaa",
            "class": "#4ec9b0",
            "variable": "#9cdcfe",
            "operator": "#d4d4d4",
            "bracket": "#ffd700",
            "punctuation": "#d4d4d4",
            "decorator": "#c586c0",
            "type_annotation": "#4ec9b0",
            "escape_sequence": "#d7ba7d",
            "method": "#dcdcaa",
        }

        fallback_rules = {
            "control_keywords": [
                "if",
                "elif",
                "else",
                "for",
                "while",
                "break",
                "continue",
                "return",
                "yield",
                "import",
                "from",
                "as",
                "try",
                "except",
                "finally",
                "raise",
                "with",
                "pass",
                "del",
                "global",
                "nonlocal",
                "and",
                "or",
                "not",
                "in",
                "is",
                "lambda",
                "assert",
            ],
            "def_class_keywords": ["def", "class"],
            "boolean_values": ["True", "False", "None"],
            "high_priority_keywords": ["for", "in"],
        }

        self.config = {"colors": fallback_colors, "token_rules": fallback_rules}
        self._create_formats()

    def get_format(self, token_type: str) -> QTextCharFormat:  # type: ignore
        """Get QTextCharFormat for a specific token type."""
        return self.formats.get(token_type, QTextCharFormat())

    def get_keywords(self, keyword_group: str) -> list[str]:
        """Get list of keywords for a specific group."""
        return self.config.get("token_rules", {}).get(keyword_group, [])

    def get_color(self, token_type: str) -> str:
        """Get hex color string for a token type."""
        return self.config.get("colors", {}).get(token_type, "#ffffff")

    def reload_config(self):
        """Reload configuration from file."""
        self.load_config()

    def get_all_formats(self) -> dict[str, QTextCharFormat]:  # type: ignore
        """Get all available formats."""
        return self.formats.copy()

    def save_config(self, new_config: dict[str, Any]):
        """Save new configuration to file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)

            self.config = new_config
            self._create_formats()

        except Exception as e:
            logger.error(f"Could not save syntax config to {self.config_path}: {e}")
