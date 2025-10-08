"""
Base window class for FakeTools.

Provides a standard QMainWindow subclass with resolution-independent UI setup.
"""

from .qt_compat import QApplication, QHBoxLayout, QMainWindow, Qt, QVBoxLayout, QWidget


class BaseMainWindow(QMainWindow):
    """
    Base class for tool main windows.

    Provides standard setup for tool windows including:
    - Automatic central widget/layout configuration
    - Resolution-independent spacing
    - Proper cleanup on close (WA_DeleteOnClose)
    - Menu bar, status bar, toolbar support from QMainWindow

    Attributes:
        central_widget (QWidget): The central widget of the main window
        central_layout (QVBoxLayout | QHBoxLayout): The main layout (vertical or horizontal)
    """

    def __init__(self, parent=None, object_name="MainWindow", window_title="Main Window", central_layout="vertical"):
        """
        Initialize the base main window.

        Args:
            parent (QWidget | None): Parent widget (typically Maya main window)
            object_name (str): Object name for the window (used for identification)
            window_title (str): Title displayed in window title bar
            central_layout (str): Layout orientation - "vertical" or "horizontal"
        """
        super().__init__(parent=parent)

        self.setObjectName(object_name)
        self.setWindowTitle(window_title)
        self.setAttribute(Qt.WA_DeleteOnClose)

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


__all__ = ["BaseMainWindow", "get_spacing", "get_margins"]
