"""File item widget for the animation IO tool."""

import os
from pathlib import Path

from ....lib_ui import icons
from ....lib_ui.base_window import get_margins, get_spacing
from ....lib_ui.qt_compat import QHBoxLayout, QIcon, QLabel, QPixmap, QPushButton, QSize, QSizePolicy, Qt, QWidget
from ....lib_ui.ui_utils import scale_by_dpi

_IMAGES_DIR = Path(__file__).parent / "images"


class FileItemWidget(QWidget):
    """Custom widget for animation file list items."""

    def __init__(self, file_path, on_select_nodes=None, parent=None):
        """Initialize the file item widget.

        Args:
            file_path (str): The file path.
            on_select_nodes (callable | None): Callback for Select Nodes button. Receives file_path.
            parent (QWidget | None): The parent widget.
        """
        super().__init__(parent)
        self.file_path = file_path
        self.on_select_nodes = on_select_nodes

        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        spacing = get_spacing(self, direction="horizontal")
        left, top, right, bottom = get_margins(self)
        layout.setContentsMargins(left, int(top * 0.5), right, int(bottom * 0.5))
        layout.setSpacing(int(spacing * 0.5))

        # File icon
        icon_label = QLabel()
        icon_size = scale_by_dpi(16, self)
        icon_path = icons.get_path("file", base_dir=_IMAGES_DIR)
        pixmap = QPixmap(icon_path).scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(icon_size, icon_size)
        layout.addWidget(icon_label)

        # File name (without extension)
        name = os.path.splitext(os.path.basename(self.file_path))[0]
        name_label = QLabel(name)
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(name_label)

        # Select Nodes button
        select_button = QPushButton()
        select_button.setToolTip("Select Nodes")
        select_icon_path = icons.get_path("select_nodes", base_dir=_IMAGES_DIR)
        select_button.setIcon(QIcon(select_icon_path))
        button_icon_size = int(icon_size * 1.2)
        select_button.setIconSize(QSize(button_icon_size, button_icon_size))
        select_button.setFixedSize(int(icon_size * 1.5), int(icon_size * 1.5))
        select_button.clicked.connect(self._on_select_nodes)
        select_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                border: 1px solid #ffffff;
                background-color: rgba(255, 255, 255, 10);
            }
            QPushButton:pressed {
                border: 2px solid #ffffff;
                background-color: rgba(255, 255, 255, 20);
            }
            """
        )
        layout.addWidget(select_button)

        self.setStyleSheet(
            """
            FileItemWidget {
                background-color: palette(base);
                border-bottom: 1px solid palette(mid);
            }
            """
        )

    def _on_select_nodes(self):
        """Handle Select Nodes button click."""
        if self.on_select_nodes:
            self.on_select_nodes(self.file_path)
