"""Shared configuration settings dialog.

Provides a GUI for editing FakeTools shared settings
(mirror patterns, hotkeys) stored in shared_config.

To add a new settings section:
    1. Add defaults to ``_DEFAULTS`` in ``shared_config.py``.
    2. Create or reuse a ``BaseConfigSection`` subclass below.
    3. Append an entry to ``_SECTIONS``.
"""

from abc import abstractmethod
from logging import getLogger
import re

import maya.cmds as cmds

from .base_window import get_margins, get_spacing
from .maya_dialog import show_error_dialog
from .maya_qt import get_maya_main_window
from .qt_compat import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from .shared_config import get_defaults, get_shared_config, save_shared_config
from .ui_utils import get_relative_size

logger = getLogger(__name__)

_instance = None

# =============================================================================
# Section definitions (add new sections here)
# =============================================================================

_SECTIONS = [
    {
        "key": "mirror_patterns",
        "type": "regex_patterns",
        "args": {
            "title": "Mirror Patterns",
            "fields": [
                ("left_to_right", "Left to Right:"),
                ("right_to_left", "Right to Left:"),
                ("adjust_center_weight", "Adjust Center:"),
            ],
        },
    },
    {
        "key": "hotkeys",
        "type": "string_fields",
        "args": {
            "title": "Hotkeys",
            "fields": [
                ("single_commands_popup", "Single Commands Popup:"),
            ],
            "note": "Changes take effect after Reload Menu.",
        },
    },
]


# =============================================================================
# Section widgets
# =============================================================================


class BaseConfigSection(QGroupBox):
    """Base class for a settings section widget.

    Subclasses must implement ``populate``, ``collect``, and optionally
    override ``validate``.

    Args:
        title (str): Group box title.
        fields (list[tuple[str, str]]): List of (key, label) pairs.
        parent: Parent widget.
    """

    def __init__(self, title: str, fields: list[tuple[str, str]], parent=None):
        super().__init__(title, parent)
        self._field_defs = fields

    @abstractmethod
    def populate(self, data: dict) -> None:
        """Fill widgets from a data dict."""

    @abstractmethod
    def collect(self) -> dict:
        """Return current widget values as a dict."""

    def validate(self) -> tuple[bool, str]:
        """Validate current values.

        Returns:
            tuple[bool, str]: (is_valid, error_message). Default always valid.
        """
        return True, ""


class RegexPatternsSection(BaseConfigSection):
    """Section for editing regex / replacement pattern pairs."""

    def __init__(self, title: str, fields: list[tuple[str, str]], parent=None):
        super().__init__(title, fields, parent)
        self._inputs: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        spacing = get_spacing(self)
        grid = QGridLayout()
        grid.setSpacing(int(spacing * 0.75))

        # Header row
        header_regex = QLabel("Regex Pattern")
        header_replace = QLabel("Replacement")
        header_regex.setEnabled(False)
        header_replace.setEnabled(False)
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(header_regex, 0, 1)
        grid.addWidget(header_replace, 0, 2)

        for row, (key, label) in enumerate(self._field_defs, start=1):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            regex_edit = QLineEdit()
            replace_edit = QLineEdit()
            regex_edit.setPlaceholderText("e.g. (.*)(L)")
            replace_edit.setPlaceholderText(r"e.g. \g<1>R")

            grid.addWidget(lbl, row, 0)
            grid.addWidget(regex_edit, row, 1)
            grid.addWidget(replace_edit, row, 2)

            self._inputs[key] = (regex_edit, replace_edit)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        self.setLayout(grid)

    def populate(self, data: dict) -> None:
        for key, (regex_edit, replace_edit) in self._inputs.items():
            pattern = data.get(key, ["", ""])
            regex_edit.setText(pattern[0] if len(pattern) > 0 else "")
            replace_edit.setText(pattern[1] if len(pattern) > 1 else "")

    def collect(self) -> dict:
        return {key: [r.text(), p.text()] for key, (r, p) in self._inputs.items()}

    def validate(self) -> tuple[bool, str]:
        for key, (regex_edit, _) in self._inputs.items():
            pattern = regex_edit.text()
            if not pattern:
                continue
            try:
                re.compile(pattern)
            except re.error as e:
                label = next(lbl for k, lbl in self._field_defs if k == key)
                return False, f"{label}\n{e}"
        return True, ""


class StringFieldsSection(BaseConfigSection):
    """Section for editing simple string values."""

    def __init__(self, title: str, fields: list[tuple[str, str]], parent=None, note: str = ""):
        super().__init__(title, fields, parent)
        self._note = note
        self._inputs: dict[str, QLineEdit] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        spacing = get_spacing(self)
        grid = QGridLayout()
        grid.setSpacing(int(spacing * 0.75))

        for row, (key, label) in enumerate(self._field_defs):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            edit = QLineEdit()

            grid.addWidget(lbl, row, 0)
            grid.addWidget(edit, row, 1)

            self._inputs[key] = edit

        if self._note:
            note_label = QLabel(self._note)
            note_label.setEnabled(False)
            grid.addWidget(note_label, len(self._field_defs), 0, 1, 2)

        grid.setColumnStretch(1, 1)
        self.setLayout(grid)

    def populate(self, data: dict) -> None:
        for key, edit in self._inputs.items():
            edit.setText(data.get(key, ""))

    def collect(self) -> dict:
        return {key: edit.text() for key, edit in self._inputs.items()}


# Type string -> widget class mapping (registered after class definitions)
_SECTION_TYPES: dict[str, type[BaseConfigSection]] = {
    "regex_patterns": RegexPatternsSection,
    "string_fields": StringFieldsSection,
}


# =============================================================================
# Dialog
# =============================================================================


class SharedConfigDialog(QDialog):
    """Dialog for editing FakeTools shared configuration."""

    def __init__(self, parent=None):
        """Initialize the shared config dialog.

        Args:
            parent: Parent widget (typically Maya main window).
        """
        super().__init__(parent)

        self.setWindowTitle("FakeTools Settings")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._section_widgets: dict[str, BaseConfigSection] = {}

        self._setup_ui()
        self._populate_all(get_shared_config())

        width, height = get_relative_size(self, width_ratio=1.8, height_ratio=0.7)
        self.resize(width, height)

        logger.debug("SharedConfigDialog initialized")

    def _setup_ui(self) -> None:
        """Build the dialog UI from section definitions."""
        spacing = get_spacing(self)
        left, top, right, bottom = get_margins(self)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(spacing)
        main_layout.setContentsMargins(left, top, right, bottom)

        # Build sections from definitions
        for section_def in _SECTIONS:
            widget_class = _SECTION_TYPES[section_def["type"]]
            section = widget_class(**section_def["args"])
            self._section_widgets[section_def["key"]] = section
            main_layout.addWidget(section)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(spacing)

        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._on_reset_clicked)
        button_layout.addWidget(reset_button)

        button_layout.addStretch()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save_clicked)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        button_layout.addWidget(cancel_button)

        main_layout.addLayout(button_layout)

    def _populate_all(self, config: dict) -> None:
        """Populate all sections from a config dict.

        Args:
            config (dict): Full shared configuration.
        """
        for key, section in self._section_widgets.items():
            section.populate(config.get(key, {}))

    def _on_save_clicked(self) -> None:
        """Validate and save the current settings."""
        for section in self._section_widgets.values():
            is_valid, error_msg = section.validate()
            if not is_valid:
                show_error_dialog("Invalid Setting", error_msg)
                return

        data = {key: section.collect() for key, section in self._section_widgets.items()}
        saved_path = save_shared_config(data)
        logger.info(f"Shared config saved: {saved_path}")
        cmds.inViewMessage(amg="Settings saved", pos="topCenter", fade=True, fst=1000, ft=0.5)
        self.close()

    def _on_reset_clicked(self) -> None:
        """Reset all fields to default values without saving."""
        self._populate_all(get_defaults())


def show_shared_config_dialog():
    """Show the shared config settings dialog (singleton)."""
    global _instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass
    _instance = SharedConfigDialog(get_maya_main_window())
    _instance.show()
    return _instance
