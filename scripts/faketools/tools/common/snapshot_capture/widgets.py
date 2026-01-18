"""Custom widgets for Snapshot Capture tool."""

from ....lib_ui.qt_compat import QPushButton, QToolButton


class IconButton(QPushButton):
    """Transparent icon button with hover/pressed styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)


class IconToolButton(QToolButton):
    """Transparent icon tool button with hover/pressed styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
