"""File item widget for the skin weights import/export tool."""

import os
from pathlib import Path

from ....lib_ui import icons
from ....lib_ui.base_window import get_margins, get_spacing
from ....lib_ui.qt_compat import QHBoxLayout, QIcon, QLabel, QPixmap, QPushButton, QSize, QSizePolicy, Qt, QWidget
from ....lib_ui.ui_utils import scale_by_dpi

_IMAGES_DIR = Path(__file__).parent / "images"


class FileItemWidget(QWidget):
    """Custom widget for file list items."""

    def __init__(self, file_path, on_select_influences=None, on_select_geometry=None, parent=None):
        """Initialize the file item widget.

        Args:
            file_path (str): The file or directory path
            on_select_influences (callable, optional): Callback for Select Influences button
            on_select_geometry (callable, optional): Callback for Select Geometry button
            parent (QWidget, optional): The parent widget
        """
        super().__init__(parent)
        self.file_path = file_path
        self.on_select_influences = on_select_influences
        self.on_select_geometry = on_select_geometry

        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        spacing = get_spacing(self, direction="horizontal")
        left, top, right, bottom = get_margins(self)
        layout.setContentsMargins(left, int(top * 0.5), right, int(bottom * 0.5))
        layout.setSpacing(int(spacing * 0.5))

        # Icon
        icon_label = QLabel()
        icon_size = scale_by_dpi(16, self)

        icon_name = "folder" if os.path.isdir(self.file_path) else "file"
        icon_path = icons.get_path(icon_name, base_dir=_IMAGES_DIR)
        pixmap = QPixmap(icon_path).scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)

        icon_label.setFixedSize(icon_size, icon_size)
        layout.addWidget(icon_label)

        # File name (without extension)
        name_label = QLabel()
        if os.path.isfile(self.file_path):
            name = os.path.splitext(os.path.basename(self.file_path))[0]
        else:
            name = os.path.basename(self.file_path)
        name_label.setText(name)
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(name_label)

        # Select Influences button (icon only)
        influences_button = QPushButton()
        influences_button.setToolTip("Select Influences")
        influences_icon_path = icons.get_path("select_influences", base_dir=_IMAGES_DIR)
        influences_button.setIcon(QIcon(influences_icon_path))
        button_icon_size = int(icon_size * 1.2)
        influences_button.setIconSize(QSize(button_icon_size, button_icon_size))
        influences_button.setFixedSize(int(icon_size * 1.5), int(icon_size * 1.5))
        influences_button.clicked.connect(self._on_influences_clicked)
        # Apply transparent background style
        influences_button.setStyleSheet(
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
        layout.addWidget(influences_button)

        # Select Geometry button (icon only)
        geometry_button = QPushButton()
        geometry_button.setToolTip("Select Geometry")
        geometry_icon_path = icons.get_path("select_geometry", base_dir=_IMAGES_DIR)
        geometry_button.setIcon(QIcon(geometry_icon_path))
        button_icon_size = int(icon_size * 1.2)
        geometry_button.setIconSize(QSize(button_icon_size, button_icon_size))
        geometry_button.setFixedSize(int(icon_size * 1.5), int(icon_size * 1.5))
        geometry_button.clicked.connect(self._on_geometry_clicked)
        # Apply transparent background style
        geometry_button.setStyleSheet(
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
        layout.addWidget(geometry_button)

        # Apply stylesheet
        self.setStyleSheet(
            """
            FileItemWidget {
                background-color: palette(base);
                border-bottom: 1px solid palette(mid);
            }
            """
        )

    def _on_influences_clicked(self):
        """Handle Select Influences button click."""
        if self.on_select_influences:
            self.on_select_influences(self.file_path)

    def _on_geometry_clicked(self):
        """Handle Select Geometry button click."""
        if self.on_select_geometry:
            self.on_select_geometry(self.file_path)


__all__ = ["FileItemWidget"]
