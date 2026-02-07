"""Custom widgets for Node Stocker Tool."""

from logging import getLogger
from pathlib import Path

from ....lib import lib_name
from ....lib_ui.qt_compat import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
    Signal,
)
from ....lib_ui.widgets import IconButton, IconButtonStyle, IconToggleButton

_IMAGES_DIR = Path(__file__).parent / "images"

logger = getLogger(__name__)


class ToolBar(QWidget):
    """Tool bar for the node stocker."""

    refresh_button_clicked = Signal()
    clear_button_clicked = Signal()

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent)

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        self.clear_button = IconButton(icon_name="clear", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_IMAGES_DIR)
        self.main_layout.addWidget(self.clear_button)

        self.refresh_button = IconButton(icon_name="refresh", style_mode=IconButtonStyle.TRANSPARENT, icon_dir=_IMAGES_DIR)
        self.main_layout.addWidget(self.refresh_button)

        self.setLayout(self.main_layout)

        # Signals & Slots
        self.clear_button.clicked.connect(self.clear_button_clicked.emit)
        self.refresh_button.clicked.connect(self.refresh_button_clicked.emit)


class StockAreaSwitchButtons(QWidget):
    """Switch buttons for the stock area stack widget."""

    button_selection_changed = Signal(int)

    def __init__(self, num_buttons: int = 10, parent=None):
        """Constructor.

        Args:
            num_buttons (int): The number of buttons.
        """
        super().__init__(parent=parent)

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for i in range(num_buttons):
            radio_button = QRadioButton()
            self.button_group.addButton(radio_button, i)
            self.main_layout.addWidget(radio_button)

        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.main_layout.addItem(spacer)

        self.setLayout(self.main_layout)

        # Signals & Slots
        self.button_group.buttonClicked.connect(self._button_clicked)

    def set_index(self, index: int) -> None:
        """Set the index of the radio button to be selected."""
        self.button_group.button(index).setChecked(True)

    def _button_clicked(self, button: QRadioButton) -> None:
        """Emit the signal when the button is clicked."""
        self.button_selection_changed.emit(self.button_group.id(button))


class NameSpaceBox(QWidget):
    """Name Space Box."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent)

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.check_box = QCheckBox()
        self.main_layout.addWidget(self.check_box)

        self.name_space_box = QComboBox()
        self.main_layout.addWidget(self.name_space_box, stretch=1)

        self.setLayout(self.main_layout)

        self.refresh_name_spaces()

        # Signals & Slots
        self.check_box.stateChanged.connect(self.name_space_box.setEnabled)

    def refresh_name_spaces(self) -> None:
        """Populate the name space box with the name spaces."""
        name_spaces = lib_name.list_all_namespace()
        name_spaces.insert(0, "")
        self.name_space_box.clear()
        self.name_space_box.addItems(name_spaces)

    def get_name_space(self) -> str:
        """Get the name space.

        Returns:
            str: The name space.
        """
        if not self.check_box.isChecked():
            return ""

        return self.name_space_box.currentText()

    def set_enabled(self, enabled: bool) -> None:
        """Set the name space box enabled.

        Args:
            enabled (bool): True if the name space box is enabled.
        """
        self.check_box.setChecked(enabled)
        self.name_space_box.setEnabled(enabled)

    def is_enabled(self) -> bool:
        """Check if the name space box is enabled.

        Returns:
            bool: True if the name space box is enabled.
        """
        return self.check_box.isChecked()


class NameReplaceField(QWidget):
    """Name Replace Field."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent)

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.check_box = QCheckBox()
        self.main_layout.addWidget(self.check_box)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self.search_field = QLineEdit()
        layout.addWidget(self.search_field)

        self.switch_button = IconToggleButton(icon_on="switch-on", icon_off="switch-off", icon_dir=_IMAGES_DIR)
        layout.addWidget(self.switch_button)

        self.replace_field = QLineEdit()
        layout.addWidget(self.replace_field)

        self.re_button = IconToggleButton(icon_on="regex-on", icon_off="regex-off", icon_dir=_IMAGES_DIR)
        layout.addWidget(self.re_button)

        self.main_layout.addLayout(layout)

        self.setLayout(self.main_layout)

        # Signals & Slots
        self.check_box.stateChanged.connect(self.enabled_changed)

    def set_enabled(self, enabled: bool) -> None:
        """Set the name replace field enabled.

        Args:
            enabled (bool): True if the name replace field is enabled.
        """
        self.check_box.setChecked(enabled)
        self.enabled_changed(enabled)

    def is_enabled(self) -> bool:
        """Check if the name replace field is enabled.

        Returns:
            bool: True if the name replace field is enabled.
        """
        return self.check_box.isChecked()

    def enabled_changed(self, enabled: bool) -> None:
        """Set the name replace field enabled.

        Args:
            enabled (bool): True if the name replace field is enabled.
        """
        self.search_field.setEnabled(enabled)
        self.switch_button.setEnabled(enabled)
        self.replace_field.setEnabled(enabled)
        self.re_button.setEnabled(enabled)

    def is_switched(self) -> bool:
        """Check if the switch button is checked.

        Returns:
            bool: True if the switch button is checked.
        """
        return self.switch_button.isChecked()

    def set_switched(self, checked: bool) -> None:
        """Set the switch button checked.

        Args:
            checked (bool): True if the switch button is checked.
        """
        self.switch_button.setChecked(checked)

    def is_re(self) -> bool:
        """Check if the re button is checked.

        Returns:
            bool: True if the re button is checked.
        """
        return self.re_button.isChecked()

    def set_re(self, checked: bool) -> None:
        """Set the re button checked.

        Args:
            checked (bool): True if the re button is checked.
        """
        self.re_button.setChecked(checked)

    def get_search_replace_text(self) -> tuple[str, str]:
        """Get the search and replace text.

        Returns:
            tuple[str, str]: The search and replace text.
        """
        search_text = self.search_field.text()
        replace_text = self.replace_field.text()

        return search_text, replace_text

    def set_search_replace_text(self, search_text: str, replace_text: str) -> None:
        """Set the search and replace text.

        Args:
            search_text (str): The search text.
            replace_text (str): The replace text.
        """
        self.search_field.setText(search_text)
        self.replace_field.setText(replace_text)


__all__ = ["ToolBar", "StockAreaSwitchButtons", "NameSpaceBox", "NameReplaceField"]
