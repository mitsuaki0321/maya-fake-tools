"""
Base window class for FakeTools.

Provides standard window classes with resolution-independent UI setup.
"""

from .icons import get_path
from .maya_qt import get_maya_main_window
from .qt_compat import QApplication, QHBoxLayout, QIcon, QLabel, QMainWindow, QPushButton, Qt, QVBoxLayout, QWidget, is_pyside2


def _get_target_screen_geometry(target="maya"):
    """
    Get the geometry of the target screen.

    Args:
        target (str): "maya" - Screen containing Maya main window
                      "primary" - Primary screen

    Returns:
        QRect: The screen geometry
    """
    if target == "maya":
        maya_window = get_maya_main_window()
        if maya_window is not None:
            # Get the center point of Maya window
            maya_center = maya_window.frameGeometry().center()

            if is_pyside2():
                # PySide2: Use QDesktopWidget
                desktop = QApplication.desktop()
                screen_num = desktop.screenNumber(maya_center)
                return desktop.screenGeometry(screen_num)
            else:
                # PySide6: Use QScreen
                screen = QApplication.screenAt(maya_center)
                if screen is not None:
                    return screen.geometry()

    # Fallback to primary screen
    if is_pyside2():
        desktop = QApplication.desktop()
        return desktop.screenGeometry(desktop.primaryScreen())
    else:
        primary_screen = QApplication.primaryScreen()
        if primary_screen is not None:
            return primary_screen.geometry()

    # Ultimate fallback
    return QApplication.desktop().screenGeometry() if is_pyside2() else QApplication.primaryScreen().geometry()


def center_on_screen(widget, target="maya"):
    """
    Center a widget on the target screen.

    Args:
        widget (QWidget): The widget to center
        target (str): "maya" - Screen containing Maya main window (default)
                      "primary" - Primary screen
    """
    screen_geometry = _get_target_screen_geometry(target)
    frame_geometry = widget.frameGeometry()
    center_point = screen_geometry.center()
    frame_geometry.moveCenter(center_point)
    widget.move(frame_geometry.topLeft())


class BaseMainWindow(QMainWindow):
    """
    Base class for tool main windows.

    Provides standard setup for tool windows including:
    - Automatic central widget/layout configuration
    - Resolution-independent spacing
    - Proper cleanup on close (WA_DeleteOnClose)
    - Menu bar, status bar, toolbar support from QMainWindow
    - Automatic centering on first show (can be disabled)

    Attributes:
        central_widget (QWidget): The central widget of the main window
        central_layout (Union[QVBoxLayout, QHBoxLayout]): The main layout (vertical or horizontal)
    """

    def __init__(self, parent=None, object_name="MainWindow", window_title="Main Window", central_layout="vertical", center_on_show=True):
        """
        Initialize the base main window.

        Args:
            parent: Parent widget (typically Maya main window)
            object_name (str): Object name for the window (used for identification)
            window_title (str): Title displayed in window title bar
            central_layout (str): Layout orientation - "vertical" or "horizontal"
            center_on_show (bool): If True, center window on Maya's screen on first show
        """
        super().__init__(parent=parent)

        self.setObjectName(object_name)
        self.setWindowTitle(window_title)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Centering flags
        self._center_on_show = center_on_show
        self._first_show = True

        # Setup central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        if central_layout == "vertical":
            self.central_layout = QVBoxLayout()
        else:
            self.central_layout = QHBoxLayout()

        self.central_widget.setLayout(self.central_layout)

        # Apply resolution-independent spacing
        default_spacing = get_spacing(self.central_widget)
        self.central_layout.setSpacing(int(default_spacing * 0.75))

    def showEvent(self, event):
        """Handle show event to center window on first display."""
        super().showEvent(event)
        if self._first_show and self._center_on_show:
            self._first_show = False
            center_on_screen(self, target="maya")


def get_spacing(widget, direction="vertical"):
    """
    Get default spacing for a widget based on its style.

    This function retrieves the spacing value from the widget's style,
    ensuring resolution-independent UI that respects user preferences.

    Args:
        widget (QWidget): The widget to get spacing for
        direction (str): "vertical" or "horizontal"

    Returns:
        int: The spacing value in pixels (DPI-aware)

    Example:
        >>> spacing = get_spacing(my_widget, "vertical")
        >>> layout.setSpacing(spacing)
    """
    orientation = Qt.Vertical if direction == "vertical" else Qt.Horizontal
    return QApplication.style().layoutSpacing(
        widget.sizePolicy().controlType(),
        widget.sizePolicy().controlType(),
        orientation,
    )


def get_margins(widget):
    """
    Get default margins for a widget based on its style.

    Retrieves style-based margins that are resolution-independent and
    consistent with the application theme.

    Args:
        widget (QWidget): The widget to get margins for

    Returns:
        tuple[int, int, int, int]: (left, top, right, bottom) margins in pixels (DPI-aware)

    Example:
        >>> left, top, right, bottom = get_margins(my_widget)
        >>> layout.setContentsMargins(left, top, right, bottom)
    """
    style = QApplication.style()

    # Get margin pixel metrics from style
    # Handle both PySide2 and PySide6 attribute access patterns
    left_margin_style = getattr(style, "PM_LayoutLeftMargin", None) or style.PixelMetric.PM_LayoutLeftMargin
    top_margin_style = getattr(style, "PM_LayoutTopMargin", None) or style.PixelMetric.PM_LayoutTopMargin
    right_margin_style = getattr(style, "PM_LayoutRightMargin", None) or style.PixelMetric.PM_LayoutRightMargin
    bottom_margin_style = getattr(style, "PM_LayoutBottomMargin", None) or style.PixelMetric.PM_LayoutBottomMargin

    left = style.pixelMetric(left_margin_style, None, widget)
    top = style.pixelMetric(top_margin_style, None, widget)
    right = style.pixelMetric(right_margin_style, None, widget)
    bottom = style.pixelMetric(bottom_margin_style, None, widget)

    return (left, top, right, bottom)


class BaseFramelessWindow(QWidget):
    """
    Base class for frameless tool windows.

    Provides a compact frameless window with custom title bar:
    - No system title bar (very compact)
    - Custom title bar with drag support
    - Close button with hover effect
    - Escape key to close
    - Resolution-independent spacing
    - Proper cleanup on close (WA_DeleteOnClose)
    - Normal window behavior (can go behind other apps)
    - Automatic centering on first show (can be disabled)

    Attributes:
        central_layout (Union[QVBoxLayout, QHBoxLayout]): The main layout (vertical or horizontal)
        title_bar (QWidget): The custom title bar widget
        title_label (QLabel): The title label in the title bar
    """

    def __init__(self, parent=None, object_name="FramelessWindow", window_title="Window", central_layout="vertical", center_on_show=True):
        """
        Initialize the frameless window.

        Args:
            parent: Parent widget (typically Maya main window)
            object_name (str): Object name for the window (used for identification)
            window_title (str): Title displayed in custom title bar
            central_layout (str): Layout orientation - "vertical" or "horizontal"
            center_on_show (bool): If True, center window on Maya's screen on first show
        """
        super().__init__(parent=parent)

        self.setObjectName(object_name)

        # Centering flags
        self._center_on_show = center_on_show
        self._first_show = True

        # Set attribute for proper cleanup (compatible with PySide2/6)
        delete_on_close = getattr(Qt, "WA_DeleteOnClose", None) or Qt.WidgetAttribute.WA_DeleteOnClose
        self.setAttribute(delete_on_close)

        # Set window flags (Qt.Window is required for QWidget to be a top-level window)
        window_flag = getattr(Qt, "Window", None) or Qt.WindowType.Window
        frameless_flag = getattr(Qt, "FramelessWindowHint", None) or Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(window_flag | frameless_flag)

        # Main vertical layout (title bar + content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create custom title bar
        self.title_bar = self._create_title_bar(window_title)
        main_layout.addWidget(self.title_bar)

        # Create central widget and layout
        central_widget = QWidget()
        if central_layout == "vertical":
            self.central_layout = QVBoxLayout()
        else:
            self.central_layout = QHBoxLayout()

        central_widget.setLayout(self.central_layout)
        main_layout.addWidget(central_widget)

        # Apply resolution-independent spacing and margins
        default_spacing = get_spacing(central_widget)
        self.central_layout.setSpacing(int(default_spacing * 0.5))

        margins = get_margins(central_widget)
        self.central_layout.setContentsMargins(int(margins[0] * 0.5), int(margins[1] * 0.5), int(margins[2] * 0.5), int(margins[3] * 0.5))

        # Store drag position for window movement
        self._drag_position = None

    def _create_title_bar(self, title):
        """
        Create the custom title bar.

        Args:
            title (str): Title text to display

        Returns:
            QWidget: The title bar widget
        """
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)

        # Compact margins and spacing (2/3 height of standard)
        margins = get_margins(self)
        # Use same margin value for top, right, and bottom to align button properly
        compact_margin = int(margins[1] * 0.15)
        title_layout.setContentsMargins(int(margins[0] * 0.5), compact_margin, compact_margin, compact_margin)
        title_layout.setSpacing(int(get_spacing(self) * 0.5))

        # Title label
        self.title_label = QLabel(title)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        title_layout.addWidget(self.title_label, stretch=1)

        # Close button (square with icon)
        close_button = QPushButton()
        close_icon_path = get_path("close")
        close_button.setIcon(QIcon(close_icon_path))
        button_size = int(close_button.fontMetrics().height() * 1.2)
        close_button.setFixedSize(button_size, button_size)
        close_button.setIconSize(close_button.size())
        # Style: transparent background, red on hover
        close_button.setStyleSheet(
            """
            QPushButton {
                border: none;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #c42b1c;
            }
            """
        )
        close_button.clicked.connect(self.close)
        title_layout.addWidget(close_button)

        return title_bar

    def showEvent(self, event):
        """Handle show event to center window on first display."""
        super().showEvent(event)
        if self._first_show and self._center_on_show:
            self._first_show = False
            center_on_screen(self, target="maya")

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        # Get global position (compatible with PySide2/6)
        try:
            # PySide6
            global_pos = event.globalPosition().toPoint()
        except AttributeError:
            # PySide2
            global_pos = event.globalPos()

        # Get left button constant (compatible with PySide2/6)
        left_button = getattr(Qt, "LeftButton", None) or Qt.MouseButton.LeftButton

        # Check if click is in title bar
        if event.button() == left_button and self.title_bar.geometry().contains(event.pos()):
            self._drag_position = global_pos - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        # Get global position (compatible with PySide2/6)
        try:
            # PySide6
            global_pos = event.globalPosition().toPoint()
        except AttributeError:
            # PySide2
            global_pos = event.globalPos()

        # Get left button constant (compatible with PySide2/6)
        left_button = getattr(Qt, "LeftButton", None) or Qt.MouseButton.LeftButton

        if event.buttons() == left_button and self._drag_position is not None:
            self.move(global_pos - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging."""
        self._drag_position = None

    def keyPressEvent(self, event):
        """Handle key press events (Escape to close)."""
        # Handle both PySide2 and PySide6 key constants
        escape_key = getattr(Qt.Key, "Key_Escape", None) or Qt.Key_Escape
        if event.key() == escape_key:
            self.close()
        else:
            super().keyPressEvent(event)


__all__ = ["BaseMainWindow", "BaseFramelessWindow", "get_spacing", "get_margins", "center_on_screen"]
