"""
Application theme for Code Editor.

Two layers:

- :class:`_Palette` — raw colour tokens. The single source of hex values.
  Internal: callers should not reference these directly.
- :class:`AppTheme` — role-based aliases over the palette. This is the
  public API every UI module reads (``AppTheme.BACKGROUND``,
  ``AppTheme.TAB_BORDER``, etc.) and the stylesheet getters.

When you need a new colour:

1. Pick (or add) the closest token in :class:`_Palette`.
2. Add an :class:`AppTheme` alias that names *what it is for*, not what it
   looks like.

Touching a palette token cascades through every role that aliases it; that
is the point of the split.
"""

from .....lib_ui.qt_compat import QFont


class _Palette:
    """Raw colour tokens (dark theme). Names describe the value, not the use."""

    # Surfaces — main backgrounds, ordered roughly by elevation.
    SURFACE_PRIMARY = "#1e1e1e"  # editor / window root
    SURFACE_SECONDARY = "#242424"  # tab bar, inactive tabs
    SURFACE_TERTIARY = "#252526"  # sidebar, menus
    SURFACE_SCROLL = "#2b2b2b"  # scrollbar track
    SURFACE_TOOLBAR = "#2d2d30"  # toolbar
    SURFACE_HIGHLIGHT = "#2a2a2a"  # current-line / row highlight
    SURFACE_LIST_HOVER = "#2a2d2e"  # VSCode list.hoverBackground
    SURFACE_HOVER = "#37373d"  # tab / list hover

    # Borders / separators (dark → bright).
    BORDER_SUBTLE = "#0a0a0a"  # near-black underline
    BORDER_DEFAULT = "#3c3c3c"  # tab + toolbar borders
    BORDER_STRONG = "#3e3e42"  # widget borders, indent guide

    # Interactive backgrounds.
    BUTTON_HOVER = "#484848"  # generic VSCode-style button hover
    BUTTON_RUN_PRESSED = "#5a504a"  # run button pressed (warm tint)

    # Scrollbar handle.
    SCROLLBAR_HANDLE = "#565656"
    SCROLLBAR_HANDLE_HOVER = "#6a6a6a"

    # Text / icons (dim → brightest).
    TEXT_DIMMER = "#6a6a6a"  # fold placeholder
    TEXT_DIM = "#858585"  # inactive line numbers, fold indicators
    TEXT_NORMAL = "#cccccc"  # chrome text + active accents (active line, fold hover)
    TEXT_BRIGHTER = "#d4d4d4"  # editor foreground / output text
    TEXT_BRIGHTEST = "#ffffff"  # selected tab text

    # Icon SVG recolouring.
    ICON_SOURCE = "#808080"  # in-file SVG colour, replaced at runtime
    ICON_NORMAL = "#a0a0a0"
    ICON_HOVER = "#d0d0d0"
    ICON_PRESSED = "#888888"

    # Accent (VSCode blue family).
    ACCENT = "#007acc"  # focus / selected-tab indicator
    ACCENT_BG_SUBTLE = "#264f78"  # text-selection background
    ACCENT_BG_STRONG = "#04395e"  # list / menu hover & pressed background (VSCode list.activeSelectionBackground)

    # Status colours (output terminal).
    STATUS_ERROR = "#ff6b6b"
    STATUS_WARNING = "#ffd93d"
    STATUS_SUCCESS = "#6bcf7f"
    STATUS_COMMAND = "#4fc3f7"


class AppTheme:
    """Application theme — role aliases over :class:`_Palette`."""

    # ===== Core =====
    BACKGROUND = _Palette.SURFACE_PRIMARY
    FOREGROUND = _Palette.TEXT_BRIGHTER
    BORDER = _Palette.BORDER_STRONG
    ACCENT_BLUE = _Palette.ACCENT
    SELECTION = _Palette.ACCENT_BG_SUBTLE

    # ===== Tabs =====
    TAB_BAR_BACKGROUND = _Palette.SURFACE_SECONDARY
    TAB_INACTIVE_BACKGROUND = _Palette.SURFACE_SECONDARY
    TAB_ACTIVE_BACKGROUND = _Palette.SURFACE_PRIMARY
    TAB_HOVER_BACKGROUND = _Palette.SURFACE_HOVER
    TAB_BORDER = _Palette.BORDER_DEFAULT
    TAB_TEXT_COLOR = _Palette.TEXT_NORMAL
    TAB_TEXT_ACTIVE = _Palette.TEXT_BRIGHTEST
    TAB_BAR_SEPARATOR = _Palette.BORDER_SUBTLE  # bottom underline of tab bar

    # ===== Toolbar =====
    TOOLBAR_BACKGROUND = _Palette.SURFACE_TOOLBAR
    VSCODE_BUTTON_HOVER_BACKGROUND = _Palette.BUTTON_HOVER
    RUN_BUTTON_HOVER_BACKGROUND = _Palette.BORDER_DEFAULT
    RUN_BUTTON_PRESSED_BACKGROUND = _Palette.BUTTON_RUN_PRESSED

    ICON_SVG_SOURCE = _Palette.ICON_SOURCE
    ICON_NORMAL = _Palette.ICON_NORMAL
    ICON_HOVER = _Palette.ICON_HOVER
    ICON_PRESSED = _Palette.ICON_PRESSED

    # ===== Sidebar (file explorer) =====
    SIDEBAR_BACKGROUND = _Palette.SURFACE_PRIMARY  # share editor's bg
    SIDEBAR_TEXT_COLOR = _Palette.TEXT_NORMAL
    EXPLORER_ROW_HOVER = _Palette.SURFACE_LIST_HOVER

    # ===== Context menus =====
    MENU_BACKGROUND = _Palette.SURFACE_TERTIARY
    MENU_TEXT_COLOR = _Palette.TEXT_NORMAL
    # Menu hover stays a flat charcoal grey (VSCode Dark Modern's
    # ``menu.selectionBackground`` look), separate from the blue
    # selection used in lists / file explorer.
    MENU_HOVER_BACKGROUND = _Palette.SURFACE_HOVER

    # ===== List / menu hover & selection =====
    HOVER_BACKGROUND = _Palette.ACCENT_BG_STRONG
    # VSCode-style 1 px focus outline on the active list selection
    # (matches ``focusBorder`` in the Dark Modern theme).
    EXPLORER_SELECTION_BORDER = "#0078d4"

    # ===== Editor decorations =====
    CURRENT_LINE_BORDER = "#282828"  # rules above/below caret line
    INDENT_GUIDE_COLOR = _Palette.BORDER_STRONG
    BRACKET_MATCH_BORDER = "#666666"  # 1px rectangle around the matched bracket char

    # ===== Line numbers =====
    LINE_NUMBER_BACKGROUND = _Palette.SURFACE_PRIMARY
    LINE_NUMBER_ACTIVE = _Palette.TEXT_NORMAL
    LINE_NUMBER_INACTIVE = _Palette.TEXT_DIM

    # ===== Code folding =====
    FOLD_INDICATOR_COLOR = _Palette.TEXT_DIM
    FOLD_INDICATOR_HOVER = _Palette.TEXT_NORMAL
    FOLD_PLACEHOLDER_COLOR = _Palette.TEXT_DIMMER

    # ===== Scrollbar =====
    SCROLLBAR_BACKGROUND = _Palette.SURFACE_SCROLL
    SCROLLBAR_HANDLE = _Palette.SCROLLBAR_HANDLE
    SCROLLBAR_HANDLE_HOVER = _Palette.SCROLLBAR_HANDLE_HOVER

    # ===== Output terminal =====
    OUTPUT_TEXT = _Palette.TEXT_BRIGHTER  # alias of FOREGROUND
    OUTPUT_ERROR = _Palette.STATUS_ERROR
    OUTPUT_WARNING = _Palette.STATUS_WARNING
    OUTPUT_SUCCESS = _Palette.STATUS_SUCCESS
    OUTPUT_COMMAND = _Palette.STATUS_COMMAND

    # ===== Multi-cursor overlays (RGBA tuples for QColor) =====
    MULTI_CURSOR_COLOR = (255, 255, 255, 200)
    MULTI_SELECTION_COLOR = (60, 120, 200, 100)
    RECT_SELECTION_COLOR = (100, 150, 255, 80)

    # ===== File-explorer hover-run button (RGB tuples) =====
    EXPLORER_RUN_BUTTON_BACKGROUND = (45, 45, 45)
    EXPLORER_RUN_BUTTON_BORDER = (80, 80, 80)
    EXPLORER_RUN_BUTTON_PLAY = (115, 185, 0)

    # ===== Fonts =====
    MONOSPACE_FONT_FAMILY = "Cascadia Code"
    MONOSPACE_FONT_FALLBACK = "Consolas"
    LINE_HEIGHT_PERCENT = 160  # proportional, matches VSCode's default editor.lineHeight

    @classmethod
    def make_monospace_font(cls, size: int) -> "QFont":
        """Build a ``QFont`` for the editor's monospace family with platform fallback."""
        font = QFont(cls.MONOSPACE_FONT_FAMILY, size)
        if not font.exactMatch():
            font = QFont(cls.MONOSPACE_FONT_FALLBACK, size)
        return font

    # ----- Stylesheet getters --------------------------------------------------

    @classmethod
    def get_main_window_stylesheet(cls):
        """Splitter handle styling for the main window.

        The main widget itself is a ``QWidget`` (not a ``QMainWindow``), so a
        ``QMainWindow {}`` rule wouldn't match. Only the ``QSplitter::handle``
        descendants need styling here.
        """
        return f"""
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
            border-bottom: 1px solid {cls.TAB_BAR_SEPARATOR};
        }}
        QTabWidget::tab-bar {{
            background-color: {cls.TAB_BAR_BACKGROUND};
        }}
        QTabBar::tab {{
            background-color: {cls.TAB_INACTIVE_BACKGROUND};
            color: {cls.TAB_TEXT_COLOR};
            padding: 8px 12px;
            border: 1px solid {cls.BORDER};
            border-bottom: none;
            margin-top: 0px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.TAB_ACTIVE_BACKGROUND};
            border-top: 2px solid {cls.ACCENT_BLUE};
            color: {cls.TAB_TEXT_ACTIVE};
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
            border: 1px solid {cls.TAB_BORDER};
            selection-background-color: {cls.SELECTION};
        }}
        """

    @classmethod
    def get_file_explorer_stylesheet(cls):
        """Get file explorer stylesheet."""
        return f"""
        QTreeView {{
            background-color: {cls.SIDEBAR_BACKGROUND};
            color: {cls.SIDEBAR_TEXT_COLOR};
            border: 1px solid {cls.BORDER};
            selection-background-color: {cls.HOVER_BACKGROUND};
            outline: 0;
            font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            font-size: 13px;
            padding-top: 8px;
        }}
        QTreeView::item {{
            padding: 2px;
        }}
        QTreeView::item:hover {{
            background-color: {cls.EXPLORER_ROW_HOVER};
        }}
        QTreeView::item:selected {{
            background-color: {cls.HOVER_BACKGROUND};
            border: 1px solid {cls.EXPLORER_SELECTION_BORDER};
        }}
        """

    @classmethod
    def get_menu_stylesheet(cls):
        """Get context menu stylesheet."""
        return f"""
        QMenu {{
            background-color: {cls.MENU_BACKGROUND};
            color: {cls.MENU_TEXT_COLOR};
            border: 1px solid {cls.BORDER};
        }}
        QMenu::item {{
            padding: 5px 20px;
        }}
        QMenu::item:selected {{
            background-color: {cls.MENU_HOVER_BACKGROUND};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {cls.BORDER};
            margin: 2px 8px;
        }}
        """

    @classmethod
    def get_emphasized_label_stylesheet(cls):
        """Small bold caption label (used inside dialogs / option groups)."""
        return "font-weight: bold; font-size: 10px;"

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
