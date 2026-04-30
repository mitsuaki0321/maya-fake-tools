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
    from PySide2.QtCore import (
        QAbstractItemModel,
        QByteArray,  # noqa: F401
        QDateTime,
        QDir,
        QEvent,
        QFileInfo,
        QFileSystemWatcher,
        QItemSelectionModel,
        QMimeData,  # noqa: F401
        QModelIndex,
        QObject,
        QPersistentModelIndex,
        QPoint,
        QPointF,
        QRect,
        QRectF,
        QRunnable,
        QSize,
        QSortFilterProxyModel,
        QStringListModel,
        Qt,
        QThread,
        QThreadPool,
        QTimer,
        QUrl,
        Signal,
        Slot,
    )
    from PySide2.QtGui import (
        QBrush,
        QColor,
        QCursor,
        QDesktopServices,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QImage,
        QIntValidator,
        QKeyEvent,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPalette,
        QPen,
        QPixmap,
        QPolygon,
        QPolygonF,
        QRegExpValidator,
        QRegion,
        QResizeEvent,
        QStandardItem,
        QStandardItemModel,
        QSyntaxHighlighter,
        QTextBlockFormat,
        QTextCharFormat,
        QTextCursor,
        QTextDocument,
        QTransform,
        QValidator,
    )
    from PySide2.QtMultimedia import QMediaContent, QMediaPlayer
    from PySide2.QtMultimediaWidgets import QGraphicsVideoItem, QVideoWidget
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
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFileSystemModel,
        QFontDialog,
        QFormLayout,
        QFrame,
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsLineItem,
        QGraphicsOpacityEffect,
        QGraphicsPathItem,
        QGraphicsPolygonItem,
        QGraphicsProxyWidget,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QGraphicsWidget,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
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
        QShortcut,
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
        QStyleOptionTab,
        QStyleOptionViewItem,
        QStylePainter,
        QSystemTrayIcon,
        QTabBar,
        QTableView,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QToolButton,
        QToolTip,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
        QWidgetAction,
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
    from PySide6.QtCore import (
        QAbstractItemModel,
        QByteArray,  # noqa: F401
        QDateTime,
        QDir,
        QEvent,
        QFileInfo,
        QFileSystemWatcher,
        QItemSelectionModel,
        QMimeData,  # noqa: F401
        QModelIndex,
        QObject,
        QPersistentModelIndex,
        QPoint,
        QPointF,
        QRect,
        QRectF,
        QRunnable,
        QSize,
        QSortFilterProxyModel,
        QStringListModel,
        Qt,
        QThread,
        QThreadPool,
        QTimer,
        QUrl,
        Signal,
        Slot,
    )
    from PySide6.QtGui import (
        QAction,
        QActionGroup,
        QBrush,
        QColor,
        QCursor,
        QDesktopServices,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QImage,
        QIntValidator,
        QKeyEvent,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPalette,
        QPen,
        QPixmap,
        QPolygon,
        QPolygonF,
        QRegion,
        QRegularExpressionValidator as QRegExpValidator,
        QResizeEvent,
        QShortcut,
        QStandardItem,
        QStandardItemModel,
        QSyntaxHighlighter,
        QTextBlockFormat,
        QTextCharFormat,
        QTextCursor,
        QTextDocument,
        QTransform,
        QValidator,
    )
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem, QVideoWidget
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QCompleter,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFileSystemModel,
        QFontDialog,
        QFormLayout,
        QFrame,
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsLineItem,
        QGraphicsOpacityEffect,
        QGraphicsPathItem,
        QGraphicsPolygonItem,
        QGraphicsProxyWidget,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QGraphicsWidget,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
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
        QStyleOptionTab,
        QStyleOptionViewItem,
        QStylePainter,
        QSystemTrayIcon,
        QTabBar,
        QTableView,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QToolButton,
        QToolTip,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
        QWidgetAction,
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


# ---------------------------------------------------------------------------
# QtMultimedia compatibility helpers
# ---------------------------------------------------------------------------


def create_media_player(parent: QObject) -> tuple:
    """Create a QMediaPlayer with audio support.

    Returns:
        tuple: (player, audio_output) where audio_output is None for PySide2
            and QAudioOutput for PySide6.
    """
    if is_pyside2():
        player = QMediaPlayer(parent)
        return player, None
    else:
        audio_output = QAudioOutput(parent)
        player = QMediaPlayer(parent)
        player.setAudioOutput(audio_output)
        return player, audio_output


def set_media_source(player: QMediaPlayer, path: str) -> None:
    """Load a media file into the player.

    Args:
        player: QMediaPlayer instance.
        path: Absolute file path to the media file.
    """
    url = QUrl.fromLocalFile(path)
    if is_pyside2():
        player.setMedia(QMediaContent(url))
    else:
        player.setSource(url)


def set_player_volume(target, volume: int) -> None:
    """Set playback volume.

    Args:
        target: QMediaPlayer (PySide2) or QAudioOutput (PySide6).
        volume: Volume level 0-100.
    """
    if is_pyside2():
        target.setVolume(int(volume))
    else:
        target.setVolume(max(0.0, min(1.0, volume / 100.0)))


def get_player_volume(target) -> int:
    """Get playback volume as 0-100.

    Args:
        target: QMediaPlayer (PySide2) or QAudioOutput (PySide6).

    Returns:
        int: Volume level 0-100.
    """
    if is_pyside2():
        return int(target.volume())
    else:
        return int(round(target.volume() * 100))


def get_playback_state(player: QMediaPlayer) -> str:
    """Get the current playback state as a string.

    Returns:
        str: One of "playing", "paused", or "stopped".
    """
    if is_pyside2():
        state = player.state()
        if state == QMediaPlayer.PlayingState:
            return "playing"
        elif state == QMediaPlayer.PausedState:
            return "paused"
        return "stopped"
    else:
        state = player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            return "playing"
        elif state == QMediaPlayer.PlaybackState.PausedState:
            return "paused"
        return "stopped"


def connect_state_changed(player: QMediaPlayer, callback) -> None:
    """Connect the playback state changed signal.

    Args:
        player: QMediaPlayer instance.
        callback: Callable that receives a single argument (the player).
    """
    if is_pyside2():
        player.stateChanged.connect(lambda _state: callback(player))
    else:
        player.playbackStateChanged.connect(lambda _state: callback(player))


def connect_frame_signal(player: "QMediaPlayer", video_output, callback) -> "QObject | None":
    """Connect a callback to the video frame output signal.

    Args:
        player: QMediaPlayer instance.
        video_output: QVideoWidget or QGraphicsVideoItem receiving frames.
        callback: Callable that receives a QVideoFrame.

    Returns:
        The signal source object (must be kept alive for PySide2 QVideoProbe),
        or None if the connection failed.
    """
    if is_pyside2():
        from PySide2.QtMultimedia import QVideoProbe

        probe = QVideoProbe()
        if not probe.setSource(player):
            return None
        probe.videoFrameProbed.connect(callback)
        return probe
    else:
        sink = video_output.videoSink()
        if sink is None:
            return None
        sink.videoFrameChanged.connect(callback)
        return sink


def disconnect_frame_signal(source: "QObject", callback) -> None:
    """Disconnect a callback from the video frame signal.

    Args:
        source: Object returned by :func:`connect_frame_signal`.
        callback: The same callable passed to :func:`connect_frame_signal`.
    """
    try:
        if is_pyside2():
            source.videoFrameProbed.disconnect(callback)
        else:
            source.videoFrameChanged.disconnect(callback)
    except RuntimeError:
        pass  # Already disconnected


def get_video_fps(player: "QMediaPlayer") -> "float | None":
    """Get the video's native frame rate from media metadata.

    Args:
        player: QMediaPlayer instance with loaded media.

    Returns:
        float | None: Video FPS if available, None otherwise.
    """
    try:
        if is_pyside2():
            value = player.metaData("VideoFrameRate")
        else:
            from PySide6.QtMultimedia import QMediaMetaData

            value = player.metaData().value(QMediaMetaData.VideoFrameRate)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    except Exception:
        pass
    return None


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
    "QThreadPool",
    "QRunnable",
    "QSize",
    "QPoint",
    "QPointF",
    "QRect",
    "QRectF",
    "QDir",
    "QFileInfo",
    "QDateTime",
    "QModelIndex",
    "QPersistentModelIndex",
    "QFileSystemWatcher",
    "QUrl",
    # GUI classes
    "QDesktopServices",
    "QFont",
    "QFontMetrics",
    "QIcon",
    "QPalette",
    "QPixmap",
    "QImage",
    "QColor",
    "QCursor",
    "QKeySequence",
    "QKeyEvent",
    "QResizeEvent",
    "QValidator",
    "QIntValidator",
    "QDoubleValidator",
    "QRegExpValidator",
    "QPainter",
    "QPainterPath",
    "QPen",
    "QBrush",
    "QPolygon",
    "QPolygonF",
    "QRegion",
    "QTransform",
    "QSyntaxHighlighter",
    "QTextBlockFormat",
    "QTextCharFormat",
    "QTextCursor",
    "QTextDocument",
    "QShortcut",
    # Widget classes
    "QApplication",
    "QMainWindow",
    "QDialog",
    "QDialogButtonBox",
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
    "QTabBar",
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
    "QHeaderView",
    "QSplitter",
    "QScrollArea",
    "QToolBar",
    "QStatusBar",
    "QMenuBar",
    "QMenu",
    "QAction",
    "QActionGroup",
    "QToolButton",
    "QToolTip",
    "QButtonGroup",
    "QAbstractItemView",
    "QAbstractItemModel",
    "QStandardItemModel",
    "QStandardItem",
    "QStringListModel",
    "QSortFilterProxyModel",
    "QItemSelectionModel",
    "QItemDelegate",
    "QStyledItemDelegate",
    "QStyleOptionViewItem",
    "QFileSystemModel",
    "QFileDialog",
    "QColorDialog",
    "QFontDialog",
    "QMessageBox",
    "QInputDialog",
    "QGraphicsScene",
    "QGraphicsView",
    "QGraphicsItem",
    "QGraphicsEllipseItem",
    "QGraphicsLineItem",
    "QGraphicsOpacityEffect",
    "QGraphicsPathItem",
    "QGraphicsPolygonItem",
    "QGraphicsProxyWidget",
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
    "QStyleOptionTab",
    "QStylePainter",
    "QFrame",
    "QWidgetAction",
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
    # QtMultimedia
    "QMediaPlayer",
    "QGraphicsVideoItem",
    "QVideoWidget",
    "create_media_player",
    "set_media_source",
    "set_player_volume",
    "get_player_volume",
    "get_playback_state",
    "connect_state_changed",
]
