"""Shared configuration settings dialog.

Provides a GUI for editing FakeTools shared settings
(mirror patterns, hotkeys) stored in shared_config.
"""

from logging import getLogger
import re
from typing import Optional

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

# Mirror pattern field definitions: (key, label)
_MIRROR_FIELDS = [
    ("left_to_right", "Left to Right:"),
    ("right_to_left", "Right to Left:"),
    ("adjust_center_weight", "Adjust Center:"),
]


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

        self._mirror_fields: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        self._hotkey_field: Optional[QLineEdit] = None

        self._setup_ui()
        self._populate_fields(get_shared_config())

        width, height = get_relative_size(self, width_ratio=1.8, height_ratio=0.7)
        self.resize(width, height)

        logger.debug("SharedConfigDialog initialized")

    def _setup_ui(self):
        """Build the dialog UI."""
        spacing = get_spacing(self)
        left, top, right, bottom = get_margins(self)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(spacing)
        main_layout.setContentsMargins(left, top, right, bottom)

        # --- Mirror Patterns ---
        mirror_group = QGroupBox("Mirror Patterns")
        mirror_grid = QGridLayout()
        mirror_grid.setSpacing(int(spacing * 0.75))

        # Header row
        header_regex = QLabel("Regex Pattern")
        header_replace = QLabel("Replacement")
        header_regex.setEnabled(False)
        header_replace.setEnabled(False)
        mirror_grid.addWidget(QLabel(""), 0, 0)
        mirror_grid.addWidget(header_regex, 0, 1)
        mirror_grid.addWidget(header_replace, 0, 2)

        for row, (key, label) in enumerate(_MIRROR_FIELDS, start=1):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            regex_edit = QLineEdit()
            replace_edit = QLineEdit()
            regex_edit.setPlaceholderText("e.g. (.*)(L)")
            replace_edit.setPlaceholderText(r"e.g. \g<1>R")

            mirror_grid.addWidget(lbl, row, 0)
            mirror_grid.addWidget(regex_edit, row, 1)
            mirror_grid.addWidget(replace_edit, row, 2)

            self._mirror_fields[key] = (regex_edit, replace_edit)

        mirror_grid.setColumnStretch(1, 1)
        mirror_grid.setColumnStretch(2, 1)
        mirror_group.setLayout(mirror_grid)
        main_layout.addWidget(mirror_group)

        # --- Hotkeys ---
        hotkey_group = QGroupBox("Hotkeys")
        hotkey_grid = QGridLayout()
        hotkey_grid.setSpacing(int(spacing * 0.75))

        hotkey_label = QLabel("Single Commands Popup:")
        hotkey_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._hotkey_field = QLineEdit()
        self._hotkey_field.setPlaceholderText("e.g. Ctrl+Shift+Z")

        hotkey_grid.addWidget(hotkey_label, 0, 0)
        hotkey_grid.addWidget(self._hotkey_field, 0, 1)

        info_label = QLabel("Changes take effect after Reload Menu.")
        info_label.setEnabled(False)
        hotkey_grid.addWidget(info_label, 1, 0, 1, 2)

        hotkey_grid.setColumnStretch(1, 1)
        hotkey_group.setLayout(hotkey_grid)
        main_layout.addWidget(hotkey_group)

        # --- Buttons ---
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

    def _populate_fields(self, config: dict) -> None:
        """Set field values from a config dict.

        Args:
            config (dict): Configuration dict with mirror_patterns and hotkeys.
        """
        mirror = config.get("mirror_patterns", {})
        for key, (regex_edit, replace_edit) in self._mirror_fields.items():
            pattern = mirror.get(key, ["", ""])
            regex_edit.setText(pattern[0] if len(pattern) > 0 else "")
            replace_edit.setText(pattern[1] if len(pattern) > 1 else "")

        hotkeys = config.get("hotkeys", {})
        self._hotkey_field.setText(hotkeys.get("single_commands_popup", ""))

    def _collect_from_fields(self) -> dict:
        """Collect current field values into a config dict.

        Returns:
            dict: Configuration dict matching the shared_config structure.
        """
        mirror_patterns = {}
        for key, (regex_edit, replace_edit) in self._mirror_fields.items():
            mirror_patterns[key] = [regex_edit.text(), replace_edit.text()]

        return {
            "mirror_patterns": mirror_patterns,
            "hotkeys": {
                "single_commands_popup": self._hotkey_field.text(),
            },
        }

    def _validate_patterns(self) -> tuple[bool, str]:
        """Validate regex patterns by attempting to compile them.

        Returns:
            tuple[bool, str]: (is_valid, error_message).
        """
        for key, (regex_edit, _) in self._mirror_fields.items():
            pattern = regex_edit.text()
            if not pattern:
                continue
            try:
                re.compile(pattern)
            except re.error as e:
                label = next(lbl for k, lbl in _MIRROR_FIELDS if k == key)
                return False, f"{label}\n{e}"
        return True, ""

    def _on_save_clicked(self) -> None:
        """Validate and save the current settings."""
        is_valid, error_msg = self._validate_patterns()
        if not is_valid:
            show_error_dialog("Invalid Regex Pattern", error_msg)
            return

        data = self._collect_from_fields()
        saved_path = save_shared_config(data)
        logger.info(f"Shared config saved: {saved_path}")
        cmds.inViewMessage(amg="Settings saved", pos="topCenter", fade=True, fst=1000, ft=0.5)
        self.close()

    def _on_reset_clicked(self) -> None:
        """Reset fields to default values without saving."""
        self._populate_fields(get_defaults())


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
