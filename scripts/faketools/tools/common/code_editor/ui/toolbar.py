"""
VSCode Dark Modern style toolbar widget for Code Editor.
Provides quick access to common actions with proper icon states and styling.
"""

import os

from .....lib_ui.qt_compat import QByteArray, QFrame, QHBoxLayout, QIcon, QPainter, QPixmap, QPushButton, Qt, QtSvg, QWidget, Signal

# Icon color definitions for each button state (applied via dynamic SVG recoloring)
_ICON_SOURCE_COLOR = "#808080"
_ICON_STATE_COLORS = {
    "normal": "#A0A0A0",
    "hover": "#D0D0D0",
    "pressed": "#888888",
}


def _create_icon_from_svg(svg_text, source_color, target_color):
    """Create a QIcon from SVG text with color replacement.

    Args:
        svg_text (str): SVG file content.
        source_color (str): Color hex code to replace (e.g. "#808080").
        target_color (str): Replacement color hex code (e.g. "#A0A0A0").

    Returns:
        QIcon: Icon rendered from the modified SVG.
    """
    modified_svg = svg_text.replace(source_color, target_color)
    svg_bytes = QByteArray(modified_svg.encode("utf-8"))
    renderer = QtSvg.QSvgRenderer(svg_bytes)
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


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
        """Load icon states with dynamic color replacement from the normal SVG template."""
        self.icons = {}
        normal_path = os.path.join(self.icon_base_path, f"{self.icon_name}_normal.svg")
        if not os.path.exists(normal_path):
            return
        with open(normal_path, encoding="utf-8") as f:
            svg_template = f.read()
        for state, color in _ICON_STATE_COLORS.items():
            self.icons[state] = _create_icon_from_svg(svg_template, _ICON_SOURCE_COLOR, color)

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
                background-color: #484848;
            }
            QPushButton:pressed {
                background-color: #484848;
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

    def _load_icons(self):
        """Load all icon states from separate SVG files (no recoloring)."""
        self.icons = {}
        for state in ["normal", "hover", "pressed"]:
            icon_path = os.path.join(self.icon_base_path, f"{self.icon_name}_{state}.svg")
            if os.path.exists(icon_path):
                self.icons[state] = QIcon(icon_path)
            else:
                normal_path = os.path.join(self.icon_base_path, f"{self.icon_name}_normal.svg")
                if os.path.exists(normal_path):
                    self.icons[state] = QIcon(normal_path)

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
                background-color: #5A504A;
            }
        """)


class ToggleButton(VSCodeButton):
    """VSCode-style toggle button that switches icons between active/inactive states."""

    def __init__(self, icon_name, tooltip, active_icon_name=None, parent=None):
        self._active = False
        self._active_icon_name = active_icon_name
        self._active_icons = {}
        super().__init__(icon_name, tooltip, parent)

    def _load_icons(self):
        """Load icon states for both inactive and active modes."""
        super()._load_icons()
        if self._active_icon_name:
            active_path = os.path.join(self.icon_base_path, f"{self._active_icon_name}_normal.svg")
            if os.path.exists(active_path):
                with open(active_path, encoding="utf-8") as f:
                    svg_template = f.read()
                for state, color in _ICON_STATE_COLORS.items():
                    self._active_icons[state] = _create_icon_from_svg(svg_template, _ICON_SOURCE_COLOR, color)

    def is_active(self):
        """Return current toggle state."""
        return self._active

    def set_active(self, active):
        """Set active state and update icon."""
        self._active = active
        self._update_icon("normal")

    def _current_icons(self):
        """Return the icon set for the current state."""
        if self._active and self._active_icons:
            return self._active_icons
        return self.icons

    def _update_icon(self, state):
        """Update icon to the given state using the current icon set."""
        icons = self._current_icons()
        if state in icons:
            self.setIcon(icons[state])

    def enterEvent(self, event):
        """Handle mouse enter - switch to hover icon."""
        self._update_icon("hover")
        QPushButton.enterEvent(self, event)

    def leaveEvent(self, event):
        """Handle mouse leave - switch to normal icon."""
        self._update_icon("normal")
        QPushButton.leaveEvent(self, event)

    def mousePressEvent(self, event):
        """Handle mouse press - switch to pressed icon."""
        self._update_icon("pressed")
        QPushButton.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """Toggle active state on click."""
        if self.rect().contains(event.pos()):
            self._active = not self._active
        self._update_icon("hover")
        QPushButton.mouseReleaseEvent(self, event)


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
    echo_all_toggled = Signal(bool)  # Signal for toggling echoAllCommands (True=on, False=off)
    word_wrap_toggled = Signal(bool)  # Signal for toggling word wrap (True=on, False=off)
    fold_all_clicked = Signal()  # Signal for folding all regions
    unfold_all_clicked = Signal()  # Signal for unfolding all regions

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
        self.toggle_explorer_button = VSCodeButton("toggle", "Toggle File Explorer")

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

        # Echo All toggle button
        self.echo_all_button = ToggleButton("echo", "Toggle Echo All Commands", active_icon_name="echo_active")

        # Fourth separator
        sep4 = ToolBarSeparator()

        self.workspace_button = VSCodeButton("folder", "Open Root Directory")

        # Fifth separator
        sep5 = ToolBarSeparator()

        # Swap layout button
        self.swap_layout_button = VSCodeButton("swap", "Swap Editor/Terminal Position")

        # Sixth separator
        sep6 = ToolBarSeparator()

        # Word wrap toggle button
        self.word_wrap_button = ToggleButton("wordwrap", "Toggle Word Wrap", active_icon_name="wordwrap_active")
        self.word_wrap_button.set_active(True)  # Word wrap ON by default

        # Seventh separator
        sep7 = ToolBarSeparator()

        # Fold all / Unfold all buttons
        self.fold_all_button = VSCodeButton("foldall", "Fold All")
        self.unfold_all_button = VSCodeButton("unfoldall", "Unfold All")

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
        layout.addWidget(self.echo_all_button)
        layout.addWidget(sep4)
        layout.addWidget(self.workspace_button)
        layout.addWidget(sep5)
        layout.addWidget(self.swap_layout_button)
        layout.addWidget(sep6)
        layout.addWidget(self.word_wrap_button)
        layout.addWidget(sep7)
        layout.addWidget(self.fold_all_button)
        layout.addWidget(self.unfold_all_button)
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
        self.echo_all_button.clicked.connect(lambda: self.echo_all_toggled.emit(self.echo_all_button.is_active()))
        self.word_wrap_button.clicked.connect(lambda: self.word_wrap_toggled.emit(self.word_wrap_button.is_active()))
        self.fold_all_button.clicked.connect(self.fold_all_clicked.emit)
        self.unfold_all_button.clicked.connect(self.unfold_all_clicked.emit)

    def set_run_enabled(self, enabled: bool):
        """Enable or disable the run button."""
        self.run_button.setEnabled(enabled)

    def set_save_enabled(self, enabled: bool):
        """Enable or disable the save button."""
        self.save_button.setEnabled(enabled)
