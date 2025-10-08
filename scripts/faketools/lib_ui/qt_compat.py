"""
Qt compatibility layer for PySide2/PySide6.

This module provides a unified import interface for Qt modules,
automatically handling the differences between PySide2 and PySide6.

Usage:
    from faketools.lib_ui.qt_compat import (
        QtCore, QtGui, QtWidgets,
        Qt, Signal, Slot
    )
"""

# Try to import PySide2 first (Maya 2022 and earlier)
try:
    from PySide2 import QtCore, QtGui, QtNetwork, QtOpenGL, QtSvg, QtWidgets
    from PySide2.QtCore import QAbstractItemModel, QEvent, QObject, QPoint, QRectF, QSize, Qt, QThread, QTimer, Signal, Slot
    from PySide2.QtGui import (
        QBrush,
        QColor,
        QCursor,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QImage,
        QIntValidator,
        QKeySequence,
        QPainter,
        QPalette,
        QPen,
        QPixmap,
        QPolygon,
        QPolygonF,
        QRegExpValidator,
        QStandardItem,
        QStandardItemModel,
        QTransform,
        QValidator,
    )
    from PySide2.QtWidgets import (
        QAbstractItemView,
        QAction,
        QActionGroup,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QCompleter,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFontDialog,
        QFormLayout,
        QFrame,
        QGraphicsItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QGraphicsWidget,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QInputDialog,
        QItemDelegate,
        QLabel,
        QLineEdit,
        QListView,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMenuBar,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QRubberBand,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QSpacerItem,
        QSpinBox,
        QSplitter,
        QStackedLayout,
        QStackedWidget,
        QStatusBar,
        QStyle,
        QStyledItemDelegate,
        QStyleOption,
        QStyleOptionButton,
        QStyleOptionComboBox,
        QSystemTrayIcon,
        QTableView,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QToolButton,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    # Version flag
    QT_VERSION = "PySide2"
    QT_VERSION_MAJOR = 5

    # Additional compatibility helpers
    def get_open_file_name(parent=None, caption: str = "", directory: str = "", filter: str = "", selectedFilter: str = "") -> tuple[str, str]:
        """Wrapper for QFileDialog.getOpenFileName with consistent signature."""
        return QFileDialog.getOpenFileName(parent, caption, directory, filter, selectedFilter)

    def get_save_file_name(parent=None, caption: str = "", directory: str = "", filter: str = "", selectedFilter: str = "") -> tuple[str, str]:
        """Wrapper for QFileDialog.getSaveFileName with consistent signature."""
        return QFileDialog.getSaveFileName(parent, caption, directory, filter, selectedFilter)

    import shiboken2 as shiboken

except ImportError:
    # Fall back to PySide6 (Maya 2023 and later)
    from PySide6 import QtCore, QtGui, QtNetwork, QtOpenGL, QtSvg, QtWidgets
    from PySide6.QtCore import QAbstractItemModel, QEvent, QObject, QPoint, QRectF, QSize, Qt, QThread, QTimer, Signal, Slot
    from PySide6.QtGui import (
        QAction,
        QActionGroup,
        QBrush,
        QColor,
        QCursor,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QImage,
        QIntValidator,
        QKeySequence,
        QPainter,
        QPalette,
        QPen,
        QPixmap,
        QPolygon,
        QPolygonF,
        QRegularExpressionValidator as QRegExpValidator,
        QStandardItem,
        QStandardItemModel,
        QTransform,
        QValidator,
    )
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QCompleter,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFontDialog,
        QFormLayout,
        QFrame,
        QGraphicsItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QGraphicsWidget,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QInputDialog,
        QItemDelegate,
        QLabel,
        QLineEdit,
        QListView,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMenuBar,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QRubberBand,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QSpacerItem,
        QSpinBox,
        QSplitter,
        QStackedLayout,
        QStackedWidget,
        QStatusBar,
        QStyle,
        QStyledItemDelegate,
        QStyleOption,
        QStyleOptionButton,
        QStyleOptionComboBox,
        QSystemTrayIcon,
        QTableView,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QToolButton,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    # Version flag
    QT_VERSION = "PySide6"
    QT_VERSION_MAJOR = 6

    # Additional compatibility helpers
    def get_open_file_name(parent=None, caption: str = "", directory: str = "", filter: str = "", selectedFilter: str = "") -> tuple[str, str]:
        """Wrapper for QFileDialog.getOpenFileName with consistent signature."""
        result = QFileDialog.getOpenFileName(parent, caption, directory, filter, selectedFilter)
        return result[0], result[1]

    def get_save_file_name(parent=None, caption: str = "", directory: str = "", filter: str = "", selectedFilter: str = "") -> tuple[str, str]:
        """Wrapper for QFileDialog.getSaveFileName with consistent signature."""
        result = QFileDialog.getSaveFileName(parent, caption, directory, filter, selectedFilter)
        return result[0], result[1]

    import shiboken6 as shiboken


# Common aliases for convenience
QT_BINDING = QT_VERSION


def is_pyside2() -> bool:
    """Check if using PySide2."""
    return QT_VERSION == "PySide2"


def is_pyside6() -> bool:
    """Check if using PySide6."""
    return QT_VERSION == "PySide6"


# Export all for easy star import if needed
__all__ = [
    # Core modules
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtOpenGL",
    "QtSvg",
    "QtNetwork",
    # Common classes
    "Qt",
    "Signal",
    "Slot",
    "QObject",
    "QEvent",
    "QTimer",
    "QThread",
    "QSize",
    "QPoint",
    "QRectF",
    # GUI classes
    "QFont",
    "QFontMetrics",
    "QIcon",
    "QPalette",
    "QPixmap",
    "QImage",
    "QColor",
    "QCursor",
    "QKeySequence",
    "QValidator",
    "QIntValidator",
    "QDoubleValidator",
    "QRegExpValidator",
    "QPainter",
    "QPen",
    "QBrush",
    "QPolygon",
    "QPolygonF",
    "QTransform",
    # Widget classes
    "QApplication",
    "QMainWindow",
    "QDialog",
    "QWidget",
    "QHBoxLayout",
    "QVBoxLayout",
    "QGridLayout",
    "QFormLayout",
    "QStackedLayout",
    "QLabel",
    "QPushButton",
    "QLineEdit",
    "QTextEdit",
    "QPlainTextEdit",
    "QCheckBox",
    "QRadioButton",
    "QComboBox",
    "QSpinBox",
    "QDoubleSpinBox",
    "QSlider",
    "QProgressBar",
    "QGroupBox",
    "QTabWidget",
    "QStackedWidget",
    "QListWidget",
    "QListWidgetItem",
    "QTreeWidget",
    "QTreeWidgetItem",
    "QTableWidget",
    "QTableWidgetItem",
    "QListView",
    "QTreeView",
    "QTableView",
    "QSplitter",
    "QScrollArea",
    "QToolBar",
    "QStatusBar",
    "QMenuBar",
    "QMenu",
    "QAction",
    "QActionGroup",
    "QToolButton",
    "QButtonGroup",
    "QAbstractItemView",
    "QAbstractItemModel",
    "QStandardItemModel",
    "QStandardItem",
    "QItemDelegate",
    "QStyledItemDelegate",
    "QFileDialog",
    "QColorDialog",
    "QFontDialog",
    "QMessageBox",
    "QInputDialog",
    "QGraphicsScene",
    "QGraphicsView",
    "QGraphicsItem",
    "QGraphicsRectItem",
    "QGraphicsTextItem",
    "QGraphicsWidget",
    "QRubberBand",
    "QSizePolicy",
    "QSpacerItem",
    "QCompleter",
    "QSystemTrayIcon",
    "QStyle",
    "QStyleOption",
    "QStyleOptionButton",
    "QStyleOptionComboBox",
    "QFrame",
    # Version info
    "QT_VERSION",
    "QT_VERSION_MAJOR",
    "QT_BINDING",
    # Helper functions
    "is_pyside2",
    "is_pyside6",
    "get_open_file_name",
    "get_save_file_name",
    # "shiboken"
    "shiboken",
]
