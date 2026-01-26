"""
VSCode Dark Modern style toolbar widget for Maya Code Editor.
Provides quick access to common actions with proper icon states and styling.
"""

import os

from .....lib_ui.qt_compat import QFrame, QHBoxLayout, QIcon, QPushButton, Qt, QWidget, Signal


class VSCodeButton(QPushButton):
    """VSCode-style button with dynamic icon states."""

    def __init__(self, icon_name, tooltip, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_base_path = self._get_icon_path()

        # Set up button properties
        self.setFixedSize(26, 20)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)

        # Load icons
        self._load_icons()

        # Set initial state
        self._set_normal_state()

    def _get_icon_path(self):
        """Get the base path for icons."""
        # Get the directory containing this file (ui directory)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Icons are now in the ui/icons directory
        return os.path.join(current_dir, "icons")

    def _load_icons(self):
        """Load all icon states."""
        self.icons = {}
        for state in ["normal", "hover", "pressed"]:
            icon_path = os.path.join(self.icon_base_path, f"{self.icon_name}_{state}.png")
            if os.path.exists(icon_path):
                self.icons[state] = QIcon(icon_path)
            else:
                # Fallback to normal if specific state doesn't exist
                normal_path = os.path.join(self.icon_base_path, f"{self.icon_name}_normal.png")
                if os.path.exists(normal_path):
                    self.icons[state] = QIcon(normal_path)

    def _set_normal_state(self):
        """Set button to normal state."""
        if "normal" in self.icons:
            self.setIcon(self.icons["normal"])
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)

    def enterEvent(self, event):
        """Handle mouse enter - switch to hover icon."""
        if "hover" in self.icons:
            self.setIcon(self.icons["hover"])
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave - switch to normal icon."""
        if "normal" in self.icons:
            self.setIcon(self.icons["normal"])
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press - switch to pressed icon."""
        if "pressed" in self.icons:
            self.setIcon(self.icons["pressed"])
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release - switch to hover icon."""
        if "hover" in self.icons:
            self.setIcon(self.icons["hover"])
        super().mouseReleaseEvent(event)


class RunButton(VSCodeButton):
    """Special run button with green theme."""

    def _set_normal_state(self):
        """Set button to normal state with green theme."""
        if "normal" in self.icons:
            self.setIcon(self.icons["normal"])
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)


class ToolBarSeparator(QFrame):
    """VSCode-style vertical separator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Plain)
        self.setFixedWidth(1)
        self.setStyleSheet("""
            QFrame {
                color: #3c3c3c;
                background-color: #3c3c3c;
                margin-top: 3px;
                margin-bottom: 3px;
            }
        """)


class ToolBar(QWidget):
    """VSCode Dark Modern style toolbar with icon-based buttons."""

    # Signals
    toggle_explorer_clicked = Signal()  # Signal for toggling file explorer visibility
    run_clicked = Signal()
    save_clicked = Signal()
    save_all_clicked = Signal()
    new_clicked = Signal()
    clear_clicked = Signal()
    workspace_clicked = Signal()
    swap_layout_clicked = Signal()  # Signal for swapping editor/terminal layout

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """Initialize the user interface."""
        # Main layout with VSCode spacing
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(2)

        # Apply VSCode Dark Modern toolbar styling
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d30;
                border-bottom: 1px solid #3c3c3c;
            }
        """)

        # Toggle explorer button (leftmost)
        self.toggle_explorer_button = QPushButton("≡")
        self.toggle_explorer_button.setFixedSize(26, 20)
        self.toggle_explorer_button.setToolTip("Toggle File Explorer")
        self.toggle_explorer_button.setCursor(Qt.PointingHandCursor)
        self.toggle_explorer_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 2px;
                color: #CCCCCC;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)

        # First separator (after toggle explorer)
        sep0 = ToolBarSeparator()

        # Create buttons with proper icons and tooltips
        self.new_button = VSCodeButton("new", "New File (Ctrl+N)")

        # First separator
        sep1 = ToolBarSeparator()

        self.run_button = RunButton("run", "Run Code (Numpad Enter / Ctrl+Enter)")

        # Second separator
        sep2 = ToolBarSeparator()

        self.save_button = VSCodeButton("save", "Save Current File (Ctrl+S)")
        self.save_all_button = VSCodeButton("saveall", "Save All Files (Ctrl+Shift+S)")

        # Third separator
        sep3 = ToolBarSeparator()

        self.clear_button = VSCodeButton("clear", "Clear Terminal")

        # Fourth separator
        sep4 = ToolBarSeparator()

        self.workspace_button = VSCodeButton("folder", "Open Root Directory")

        # Fifth separator
        sep5 = ToolBarSeparator()

        # Swap layout button
        self.swap_layout_button = QPushButton("⇅")
        self.swap_layout_button.setFixedSize(26, 20)
        self.swap_layout_button.setToolTip("Swap Editor/Terminal Position")
        self.swap_layout_button.setCursor(Qt.PointingHandCursor)
        self.swap_layout_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 2px;
                color: #CCCCCC;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)

        # Add widgets to layout following the specified order
        layout.addWidget(self.toggle_explorer_button)
        layout.addWidget(sep0)
        layout.addWidget(self.new_button)
        layout.addWidget(sep1)
        layout.addWidget(self.run_button)
        layout.addWidget(sep2)
        layout.addWidget(self.save_button)
        layout.addWidget(self.save_all_button)
        layout.addWidget(sep3)
        layout.addWidget(self.clear_button)
        layout.addWidget(sep4)
        layout.addWidget(self.workspace_button)
        layout.addWidget(sep5)
        layout.addWidget(self.swap_layout_button)
        layout.addStretch()

        # Calculate dynamic height
        # icon_height(16px) + button_padding(4px) + toolbar_padding(6px) = 26px
        icon_height = 16
        button_padding = 4
        toolbar_padding = 6
        toolbar_height = icon_height + button_padding + toolbar_padding

        self.setFixedHeight(toolbar_height)

    def connect_signals(self):
        """Connect button signals."""
        self.toggle_explorer_button.clicked.connect(self.toggle_explorer_clicked.emit)
        self.run_button.clicked.connect(self.run_clicked.emit)
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.save_all_button.clicked.connect(self.save_all_clicked.emit)
        self.new_button.clicked.connect(self.new_clicked.emit)
        self.clear_button.clicked.connect(self.clear_clicked.emit)
        self.workspace_button.clicked.connect(self.workspace_clicked.emit)
        self.swap_layout_button.clicked.connect(self.swap_layout_clicked.emit)

    def set_run_enabled(self, enabled: bool):
        """Enable or disable the run button."""
        self.run_button.setEnabled(enabled)

    def set_save_enabled(self, enabled: bool):
        """Enable or disable the save button."""
        self.save_button.setEnabled(enabled)
