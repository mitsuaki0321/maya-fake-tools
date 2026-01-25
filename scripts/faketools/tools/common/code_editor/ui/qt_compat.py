"""
Qt compatibility layer for Maya integration.
Handles differences between PySide6 and PySide2 in Maya.
"""

# Try to determine which Qt version Maya is using
QT_VERSION = None
QtWidgets = None
QtCore = None
QtGui = None

try:
    # Try PySide6 first (Maya 2025)
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

    QT_VERSION = 6
except ImportError:
    try:
        # Fallback to PySide2 (Maya 2024 and earlier)
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore

        QT_VERSION = 2
    except ImportError as e:
        raise ImportError("Neither PySide6 nor PySide2 found") from e

# QFileSystemModel location varies between versions
# In both PySide2 and PySide6, it's typically in QtWidgets
if hasattr(QtWidgets, "QFileSystemModel"):
    QFileSystemModel = QtWidgets.QFileSystemModel
elif hasattr(QtGui, "QFileSystemModel"):
    QFileSystemModel = QtGui.QFileSystemModel
elif hasattr(QtCore, "QFileSystemModel"):
    QFileSystemModel = QtCore.QFileSystemModel
else:
    raise ImportError("QFileSystemModel not found in any Qt module")

# Common Qt classes
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget
QMainWindow = QtWidgets.QMainWindow
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QSplitter = QtWidgets.QSplitter
QTreeView = QtWidgets.QTreeView
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QHeaderView = QtWidgets.QHeaderView
QAbstractItemView = QtWidgets.QAbstractItemView
QTabWidget = QtWidgets.QTabWidget
QTabBar = QtWidgets.QTabBar
QPlainTextEdit = QtWidgets.QPlainTextEdit
QTextEdit = QtWidgets.QTextEdit
QPushButton = QtWidgets.QPushButton
QToolBar = QtWidgets.QToolBar
QMenu = QtWidgets.QMenu
# QAction moved from QtGui to QtWidgets in PySide6
if QT_VERSION == 6:
    QAction = QtGui.QAction
else:
    QAction = QtWidgets.QAction
QMessageBox = QtWidgets.QMessageBox
QInputDialog = QtWidgets.QInputDialog
QFileDialog = QtWidgets.QFileDialog
QFrame = QtWidgets.QFrame
QCompleter = QtWidgets.QCompleter
QDialog = QtWidgets.QDialog
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QCheckBox = QtWidgets.QCheckBox
QRadioButton = QtWidgets.QRadioButton
QButtonGroup = QtWidgets.QButtonGroup
QGridLayout = QtWidgets.QGridLayout
QToolTip = QtWidgets.QToolTip
QComboBox = QtWidgets.QComboBox
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QScrollArea = QtWidgets.QScrollArea
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QTextEdit = QtWidgets.QTextEdit
QListView = QtWidgets.QListView
QStyledItemDelegate = QtWidgets.QStyledItemDelegate
QStyleOptionViewItem = QtWidgets.QStyleOptionViewItem
# QStylePainter location differs between versions
if hasattr(QtGui, "QStylePainter"):
    QStylePainter = QtGui.QStylePainter
else:
    QStylePainter = QtWidgets.QStylePainter

# QStyleOptionTab location differs between versions
if hasattr(QtWidgets, "QStyleOptionTab"):
    QStyleOptionTab = QtWidgets.QStyleOptionTab
else:
    QStyleOptionTab = QtWidgets.QStyleOption
QStyle = QtWidgets.QStyle
QSizePolicy = QtWidgets.QSizePolicy

# Qt Core classes
Qt = QtCore.Qt
QDir = QtCore.QDir
QModelIndex = QtCore.QModelIndex
QFileInfo = QtCore.QFileInfo
Signal = QtCore.Signal
QDateTime = QtCore.QDateTime
QTimer = QtCore.QTimer
QStringListModel = QtCore.QStringListModel
QObject = QtCore.QObject
QSortFilterProxyModel = QtCore.QSortFilterProxyModel
QEvent = QtCore.QEvent
QSize = QtCore.QSize
QRect = QtCore.QRect
QResizeEvent = QtGui.QResizeEvent

# Qt GUI classes
QFont = QtGui.QFont
QFontMetrics = QtGui.QFontMetrics
QColor = QtGui.QColor
QIcon = QtGui.QIcon
QKeySequence = QtGui.QKeySequence
QKeyEvent = QtGui.QKeyEvent
QTextCharFormat = QtGui.QTextCharFormat
QTextCursor = QtGui.QTextCursor
QSyntaxHighlighter = QtGui.QSyntaxHighlighter
QPainter = QtGui.QPainter
QPalette = QtGui.QPalette
# QShortcut moved from QtGui to QtWidgets in PySide6
if QT_VERSION == 6:
    QShortcut = QtGui.QShortcut
else:
    QShortcut = QtWidgets.QShortcut
QTextDocument = QtGui.QTextDocument
QBrush = QtGui.QBrush
QPen = QtGui.QPen
QPolygonF = QtGui.QPolygonF
QPointF = QtCore.QPointF

# Handle shiboken differences
if QT_VERSION == 6:
    try:
        import shiboken6  # type: ignore

        shiboken = shiboken6
    except ImportError:
        shiboken = None
else:
    try:
        import shiboken2  # type: ignore

        shiboken = shiboken2
    except ImportError:
        shiboken = None

__all__ = [
    "QT_VERSION",
    "QtWidgets",
    "QtCore",
    "QtGui",
    "shiboken",
    "QFileSystemModel",
    "QApplication",
    "QWidget",
    "QMainWindow",
    "QVBoxLayout",
    "QHBoxLayout",
    "QSplitter",
    "QTreeView",
    "QTreeWidget",
    "QTreeWidgetItem",
    "QHeaderView",
    "QAbstractItemView",
    "QListView",
    "QStyledItemDelegate",
    "QStyleOptionViewItem",
    "QTabWidget",
    "QTabBar",
    "QPlainTextEdit",
    "QTextEdit",
    "QPushButton",
    "QToolBar",
    "QMenu",
    "QAction",
    "QMessageBox",
    "QInputDialog",
    "QFileDialog",
    "QFrame",
    "QCompleter",
    "QDialog",
    "QLabel",
    "QLineEdit",
    "QCheckBox",
    "QRadioButton",
    "QButtonGroup",
    "QGridLayout",
    "QToolTip",
    "QComboBox",
    "QSpinBox",
    "QDoubleSpinBox",
    "QScrollArea",
    "QDialogButtonBox",
    "Qt",
    "QDir",
    "QModelIndex",
    "QRect",
    "QFileInfo",
    "Signal",
    "QDateTime",
    "QTimer",
    "QStringListModel",
    "QObject",
    "QSortFilterProxyModel",
    "QFont",
    "QFontMetrics",
    "QColor",
    "QIcon",
    "QKeySequence",
    "QKeyEvent",
    "QTextCharFormat",
    "QTextCursor",
    "QSyntaxHighlighter",
    "QPainter",
    "QPalette",
    "QShortcut",
    "QTextDocument",
    "QBrush",
    "QPen",
    "QPolygonF",
    "QPointF",
    "QSize",
    "QEvent",
    "QResizeEvent",
    "QStylePainter",
    "QStyleOptionTab",
    "QStyle",
    "QSizePolicy",
]
