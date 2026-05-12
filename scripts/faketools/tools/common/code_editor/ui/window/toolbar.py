"""
VSCode Dark Modern style toolbar widget for Code Editor.
Provides quick access to common actions with proper icon states and styling.
"""

import os

from ......lib_ui.qt_compat import QByteArray, QFrame, QHBoxLayout, QIcon, QPainter, QPixmap, QPushButton, QSize, Qt, QtSvg, QWidget, Signal
from ...languages import ALL_PROFILES, DEFAULT_PROFILE
from ...themes import AppTheme

# Icon target colours per button state (applied via dynamic SVG recoloring).
_ICON_STATE_COLORS = {
    "normal": AppTheme.ICON_NORMAL,
    "hover": AppTheme.ICON_HOVER,
    "pressed": AppTheme.ICON_PRESSED,
}

# Pixmap resolution for rasterised SVG icons. Sized so that detailed badge
# glyphs in the 24-unit viewBox render legibly inside the 26 px buttons.
_ICON_RENDER_SIZE = 20


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
    # Match VSCodeButton.setIconSize — rendering at the same resolution as
    # the button request keeps fine SVG detail (badge circles, plus glyphs)
    # legible at the on-screen size.
    pixmap = QPixmap(_ICON_RENDER_SIZE, _ICON_RENDER_SIZE)
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
        self.setFixedSize(26, 26)
        # Render icons at the same resolution they're rasterised to so the
        # 24-viewBox details (badge circle, plus glyph) stay sharp instead
        # of collapsing through Qt's default 16 px iconSize.
        self.setIconSize(QSize(_ICON_RENDER_SIZE, _ICON_RENDER_SIZE))
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)

        # Load icons
        self._load_icons()

        # Set initial state
        self._set_normal_state()

    def _get_icon_path(self):
        """Get the base path for icons.

        SVG assets live under ``ui/icons/``; this file moved into
        ``ui/window/`` during the layout refactor, so we step one level
        up to reach the icons directory.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(current_dir, "..", "icons"))

    def _load_icons(self):
        """Load icon states.

        When ``<icon_name>_hover.svg`` and ``<icon_name>_pressed.svg``
        exist alongside ``_normal.svg``, all three are loaded as-is so an
        icon set can carry per-state colours (used by per-language new
        buttons whose accent colour differs from the standard theme).
        Otherwise the normal SVG is used as a template and recoloured
        per state via the placeholder colour replacement, the original
        VSCode-style behaviour.
        """
        self.icons = {}
        normal_path = os.path.join(self.icon_base_path, f"{self.icon_name}_normal.svg")
        if not os.path.exists(normal_path):
            return

        hover_path = os.path.join(self.icon_base_path, f"{self.icon_name}_hover.svg")
        pressed_path = os.path.join(self.icon_base_path, f"{self.icon_name}_pressed.svg")
        if os.path.exists(hover_path) and os.path.exists(pressed_path):
            self.icons["normal"] = QIcon(normal_path)
            self.icons["hover"] = QIcon(hover_path)
            self.icons["pressed"] = QIcon(pressed_path)
            return

        with open(normal_path, encoding="utf-8") as f:
            svg_template = f.read()
        for state, color in _ICON_STATE_COLORS.items():
            self.icons[state] = _create_icon_from_svg(svg_template, AppTheme.ICON_SVG_SOURCE, color)

    def _set_normal_state(self):
        """Set button to normal state."""
        if "normal" in self.icons:
            self.setIcon(self.icons["normal"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {AppTheme.VSCODE_BUTTON_HOVER_BACKGROUND};
            }}
            QPushButton:pressed {{
                background-color: {AppTheme.VSCODE_BUTTON_HOVER_BACKGROUND};
            }}
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
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {AppTheme.RUN_BUTTON_HOVER_BACKGROUND};
            }}
            QPushButton:pressed {{
                background-color: {AppTheme.RUN_BUTTON_PRESSED_BACKGROUND};
            }}
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
                    self._active_icons[state] = _create_icon_from_svg(svg_template, AppTheme.ICON_SVG_SOURCE, color)

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
        self.setStyleSheet(f"""
            QFrame {{
                color: {AppTheme.TOOLBAR_SEPARATOR};
                background-color: {AppTheme.TOOLBAR_SEPARATOR};
                margin-top: 2px;
                margin-bottom: 2px;
            }}
        """)


class ToolBar(QWidget):
    """VSCode Dark Modern style toolbar with icon-based buttons."""

    # Signals
    toggle_explorer_clicked = Signal()  # Signal for toggling file explorer visibility
    refresh_explorer_clicked = Signal()  # Signal for refreshing file explorer
    run_clicked = Signal()
    save_clicked = Signal()
    save_all_clicked = Signal()
    new_clicked = Signal(object)  # Emits the LanguageProfile of the clicked button.
    new_folder_clicked = Signal()  # Signal for creating a folder at the workspace root
    clear_clicked = Signal()
    workspace_clicked = Signal()
    swap_layout_clicked = Signal()  # Signal for swapping editor/terminal layout
    terminal_toggled = Signal(bool)  # Signal for toggling terminal visibility (True=visible, False=hidden)
    echo_all_toggled = Signal(bool)  # Signal for toggling echoAllCommands (True=on, False=off)
    word_wrap_toggled = Signal(bool)  # Signal for toggling word wrap (True=on, False=off)
    fold_all_clicked = Signal()  # Signal for folding all regions
    unfold_all_clicked = Signal()  # Signal for unfolding all regions
    add_to_shelf_clicked = Signal()  # Signal for adding selected code to Maya shelf
    autocomplete_toggled = Signal(bool)  # Signal for toggling autocomplete (True=on, False=off)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """Initialize the user interface."""
        # Main layout with VSCode spacing
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)

        # Apply VSCode Dark Modern toolbar styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {AppTheme.TOOLBAR_BACKGROUND};
                border-bottom: 1px solid {AppTheme.TAB_BORDER};
            }}
        """)

        # Create all buttons
        self.toggle_explorer_button = VSCodeButton("toggle", "Toggle File Explorer")
        self.refresh_explorer_button = VSCodeButton("refresh", "Refresh File Explorer")
        self.run_button = RunButton("run", "Run Code (Numpad Enter / Ctrl+Enter)")
        # Per-language "new file" buttons. Each profile owns an icon
        # named ``new_<id>_normal.svg`` (so ``new_python_normal.svg`` /
        # ``new_mel_normal.svg``) carrying the language letter and the
        # profile's accent_color. The DEFAULT_PROFILE button advertises
        # Ctrl+N because the shortcut path always creates the default
        # language.
        self.new_buttons: dict[str, VSCodeButton] = {}
        for profile in ALL_PROFILES:
            shortcut_hint = " (Ctrl+N)" if profile is DEFAULT_PROFILE else ""
            self.new_buttons[profile.id] = VSCodeButton(f"new_{profile.id}", f"New {profile.display_name} File{shortcut_hint}")
        self.new_folder_button = VSCodeButton("new_folder", "New Folder")
        self.save_button = VSCodeButton("save", "Save Current File (Ctrl+S)")
        self.save_all_button = VSCodeButton("saveall", "Save All Files (Ctrl+Shift+S)")
        self.workspace_button = VSCodeButton("folder", "Open Root Directory")
        self.clear_button = VSCodeButton("clear", "Clear Terminal")
        self.echo_all_button = ToggleButton("echo", "Toggle Echo All Commands", active_icon_name="echo_active")
        self.add_to_shelf_button = VSCodeButton("shelf", "Add Selected Code to Shelf")
        self.word_wrap_button = ToggleButton("wordwrap", "Toggle Word Wrap", active_icon_name="wordwrap_active")
        self.word_wrap_button.set_active(True)  # Word wrap ON by default
        self.fold_all_button = VSCodeButton("foldall", "Fold All")
        self.unfold_all_button = VSCodeButton("unfoldall", "Unfold All")
        self.autocomplete_button = ToggleButton(
            "autocomplete",
            "Toggle Autocomplete",
            active_icon_name="autocomplete_active",
        )
        self.terminal_toggle_button = ToggleButton("terminal", "Toggle Terminal Visibility")
        self.terminal_toggle_button.set_active(True)  # Terminal visible by default
        self.swap_layout_button = VSCodeButton("swap", "Swap Editor/Terminal Position")

        # Create separators
        sep0 = ToolBarSeparator()
        sep1 = ToolBarSeparator()
        sep2 = ToolBarSeparator()
        sep3 = ToolBarSeparator()
        sep4 = ToolBarSeparator()

        # Add widgets to layout following the specified order
        # [Explorer][Refresh] | [Run] | [New per-language][NewFolder][Save][SaveAll][Folder] | [Echo][Shelf] | [WordWrap][FoldAll][UnfoldAll][Autocomplete] | [Clear][Terminal][Swap] | →stretch
        layout.addWidget(self.toggle_explorer_button)
        layout.addWidget(self.refresh_explorer_button)
        layout.addWidget(sep0)
        layout.addWidget(self.run_button)
        layout.addWidget(sep1)
        for profile in ALL_PROFILES:
            layout.addWidget(self.new_buttons[profile.id])
        layout.addWidget(self.new_folder_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.save_all_button)
        layout.addWidget(self.workspace_button)
        layout.addWidget(sep2)
        layout.addWidget(self.echo_all_button)
        layout.addWidget(self.add_to_shelf_button)
        layout.addWidget(sep3)
        layout.addWidget(self.word_wrap_button)
        layout.addWidget(self.fold_all_button)
        layout.addWidget(self.unfold_all_button)
        layout.addWidget(self.autocomplete_button)
        layout.addWidget(sep4)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.terminal_toggle_button)
        layout.addWidget(self.swap_layout_button)
        layout.addStretch()

        # Calculate dynamic height
        # button_height(26px) + toolbar_padding(2px) = 28px
        button_height = 26
        toolbar_padding = 2
        toolbar_height = button_height + toolbar_padding

        self.setFixedHeight(toolbar_height)

    def connect_signals(self):
        """Connect button signals."""
        self.toggle_explorer_button.clicked.connect(self.toggle_explorer_clicked.emit)
        self.refresh_explorer_button.clicked.connect(self.refresh_explorer_clicked.emit)
        self.run_button.clicked.connect(self.run_clicked.emit)
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.save_all_button.clicked.connect(self.save_all_clicked.emit)
        for profile in ALL_PROFILES:
            self.new_buttons[profile.id].clicked.connect(lambda checked=False, p=profile: self.new_clicked.emit(p))
        self.new_folder_button.clicked.connect(self.new_folder_clicked.emit)
        self.clear_button.clicked.connect(self.clear_clicked.emit)
        self.workspace_button.clicked.connect(self.workspace_clicked.emit)
        self.swap_layout_button.clicked.connect(self.swap_layout_clicked.emit)
        self.terminal_toggle_button.clicked.connect(lambda: self.terminal_toggled.emit(self.terminal_toggle_button.is_active()))
        self.echo_all_button.clicked.connect(lambda: self.echo_all_toggled.emit(self.echo_all_button.is_active()))
        self.word_wrap_button.clicked.connect(lambda: self.word_wrap_toggled.emit(self.word_wrap_button.is_active()))
        self.fold_all_button.clicked.connect(self.fold_all_clicked.emit)
        self.unfold_all_button.clicked.connect(self.unfold_all_clicked.emit)
        self.add_to_shelf_button.clicked.connect(self.add_to_shelf_clicked.emit)
        self.autocomplete_button.clicked.connect(lambda: self.autocomplete_toggled.emit(self.autocomplete_button.is_active()))

    def toggle_autocomplete(self):
        """Flip the autocomplete button state and emit the toggled signal.

        Mirrors what a user click does so shortcut callers don't need to
        know about the button widget. No-op when the button is disabled
        (e.g. jedi missing) so the shortcut stays silent rather than
        toggling a setting nobody can see.
        """
        button = self.autocomplete_button
        if not button.isEnabled():
            return
        button.set_active(not button.is_active())
        self.autocomplete_toggled.emit(button.is_active())
