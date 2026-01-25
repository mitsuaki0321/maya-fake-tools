"""
Application theme for Maya Code Editor.

Provides consistent styling across all UI components.
"""


class AppTheme:
    """Application theme color constants and stylesheet definitions."""

    # Core color palette
    BACKGROUND = "#1e1e1e"
    FOREGROUND = "#d4d4d4"
    CURRENT_LINE = "#2a2d2e"
    SELECTION = "#264f78"
    BORDER = "#3e3e42"
    ACCENT_BLUE = "#007acc"

    # UI component colors
    SIDEBAR_BACKGROUND = "#252526"
    TAB_BACKGROUND = "#2d2d30"
    TAB_BAR_BACKGROUND = "#242424"  # Match inactive tab background
    TAB_INACTIVE_BACKGROUND = "#242424"  # Non-active tabs
    TAB_ACTIVE_BACKGROUND = "#1e1e1e"  # Match code editor background
    TAB_HOVER_BACKGROUND = "#2a2a2a"  # Tab hover state
    TOOLBAR_BACKGROUND = "#2d2d30"
    MENU_BACKGROUND = "#252526"
    HOVER_BACKGROUND = "#094771"
    PRESSED_BACKGROUND = "#094771"

    # Scrollbar colors
    SCROLLBAR_BACKGROUND = "#2b2b2b"
    SCROLLBAR_HANDLE = "#565656"
    SCROLLBAR_HANDLE_HOVER = "#6a6a6a"

    # Line number area colors
    LINE_NUMBER_BACKGROUND = "#1e1e1e"
    LINE_NUMBER_ACTIVE = "#c6c6c6"
    LINE_NUMBER_INACTIVE = "#858585"
    CURRENT_LINE_HIGHLIGHT = "#2a2a2a"

    # Output/Terminal colors
    OUTPUT_ERROR = "#ff6b6b"
    OUTPUT_WARNING = "#ffd93d"
    OUTPUT_SUCCESS = "#6bcf7f"
    OUTPUT_COMMAND = "#4fc3f7"
    OUTPUT_TEXT = "#d4d4d4"

    # Tab colors
    TAB_BORDER = "#3c3c3c"
    TAB_ACTIVE_ACCENT = "#0078d4"
    TAB_HOVER_BACKGROUND = "#37373d"

    # Toolbar specific colors
    TOOLBAR_BUTTON_HOVER = "#3c3c3c"
    TOOLBAR_BUTTON_PRESSED = "#094771"
    TOOLBAR_DISABLED = "#3c3c3c"

    # Editor visual guides
    INDENT_GUIDE_COLOR = "#3e3e42"

    @classmethod
    def get_main_window_stylesheet(cls):
        """Get main window stylesheet."""
        return f"""
        QMainWindow {{
            background-color: {cls.BACKGROUND};
            color: {cls.FOREGROUND};
        }}
        QSplitter::handle {{
            background-color: {cls.BORDER};
        }}
        QSplitter::handle:horizontal {{
            width: 3px;
        }}
        QSplitter::handle:vertical {{
            height: 3px;
        }}
        """

    @classmethod
    def get_editor_stylesheet(cls):
        """Get code editor stylesheet."""
        return f"""
        QPlainTextEdit {{
            background-color: {cls.BACKGROUND};
            color: {cls.FOREGROUND};
            border: 1px solid {cls.BORDER};
            selection-background-color: {cls.SELECTION};
        }}
        QPlainTextEdit:focus {{
            border: 1px solid {cls.ACCENT_BLUE};
        }}
        """

    @classmethod
    def get_tab_widget_stylesheet(cls):
        """Get tab widget stylesheet."""
        return f"""
        QTabWidget::pane {{
            border: 1px solid {cls.BORDER};
            background-color: {cls.TAB_BAR_BACKGROUND};
        }}
        QTabBar {{
            background-color: {cls.TAB_BAR_BACKGROUND};
            padding-top: 4px;
            border-bottom: 1px solid #0a0a0a;
        }}
        QTabWidget::tab-bar {{
            background-color: {cls.TAB_BAR_BACKGROUND};
        }}
        QTabBar::tab {{
            background-color: {cls.TAB_INACTIVE_BACKGROUND};
            color: #cccccc;
            padding: 8px 12px;
            border: 1px solid {cls.BORDER};
            border-bottom: none;
            margin-top: 0px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.TAB_ACTIVE_BACKGROUND};
            border-top: 2px solid {cls.ACCENT_BLUE};
            color: #ffffff;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {cls.TAB_HOVER_BACKGROUND};
        }}
        """

    @classmethod
    def get_terminal_stylesheet(cls):
        """Get terminal stylesheet."""
        return f"""
        QTextEdit {{
            background-color: {cls.BACKGROUND};
            color: {cls.FOREGROUND};
            border: 1px solid #3c3c3c;
            selection-background-color: {cls.SELECTION};
        }}
        """

    @classmethod
    def get_file_explorer_stylesheet(cls):
        """Get file explorer stylesheet."""
        return f"""
        QTreeView {{
            background-color: {cls.SIDEBAR_BACKGROUND};
            color: #cccccc;
            border: 1px solid {cls.BORDER};
            selection-background-color: {cls.HOVER_BACKGROUND};
        }}
        QTreeView::item {{
            padding: 2px;
        }}
        QTreeView::item:hover {{
            background-color: {cls.CURRENT_LINE};
        }}
        QTreeView::item:selected {{
            background-color: {cls.HOVER_BACKGROUND};
        }}
        """

    @classmethod
    def get_toolbar_stylesheet(cls):
        """Get toolbar stylesheet."""
        return f"""
        QToolBar {{
            background-color: {cls.TOOLBAR_BACKGROUND};
            border: 1px solid {cls.BORDER};
            spacing: 2px;
            padding: 2px;
        }}
        QToolButton {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 5px;
            margin: 1px;
        }}
        QToolButton:hover {{
            background-color: #3e3e40;
            border: 1px solid {cls.ACCENT_BLUE};
        }}
        QToolButton:pressed {{
            background-color: {cls.PRESSED_BACKGROUND};
        }}
        """

    @classmethod
    def get_menu_stylesheet(cls):
        """Get context menu stylesheet."""
        return f"""
        QMenu {{
            background-color: {cls.MENU_BACKGROUND};
            color: #cccccc;
            border: 1px solid {cls.BORDER};
        }}
        QMenu::item {{
            padding: 5px 20px;
        }}
        QMenu::item:selected {{
            background-color: {cls.HOVER_BACKGROUND};
        }}
        """

    @classmethod
    def get_scrollbar_stylesheet(cls):
        """Get scrollbar stylesheet."""
        return f"""
        QScrollBar:vertical {{
            background-color: {cls.SCROLLBAR_BACKGROUND};
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: {cls.SCROLLBAR_HANDLE};
            border-radius: 6px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {cls.SCROLLBAR_HANDLE_HOVER};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        """
