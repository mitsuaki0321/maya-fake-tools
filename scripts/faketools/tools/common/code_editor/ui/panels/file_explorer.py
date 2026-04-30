"""
File explorer widget for Code Editor.

UI layer: tree view + context menu + drag/drop. All filesystem mutations are
delegated to ``command.file_ops`` so the widget only translates user intent
into ops and renders the resulting error messages.
"""

from logging import getLogger
import os

from ......lib_ui.qt_compat import (
    QAction,
    QBrush,
    QColor,
    QEvent,
    QFileInfo,
    QFileSystemModel,
    QIcon,
    QLineEdit,
    QMenu,
    QModelIndex,
    QPainter,
    QPen,
    QPersistentModelIndex,
    QPointF,
    QPolygonF,
    QRect,
    QSize,
    QSortFilterProxyModel,
    QStyledItemDelegate,
    Qt,
    QTimer,
    QTreeView,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ...command import file_ops
from ...themes import AppTheme
from ..dialog_base import CodeEditorInputDialog, CodeEditorMessageBox

logger = getLogger(__name__)


class HiddenFileFilterModel(QSortFilterProxyModel):
    """Proxy model that filters hidden entries and pipes folder chevrons through DecorationRole.

    Showing the chevron via the model's ``DecorationRole`` (instead of Qt's
    default branch indicator) puts it in the same x slot as a file's
    type icon — matching VSCode's explorer where the chevron *is* the
    folder's leading glyph rather than sitting in a separate column.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Wired up via :meth:`setup_chevrons` once the view exists.
        self._tree_view = None
        self._chevron_right = None
        self._chevron_down = None
        # Material-Icon-Theme glyphs for known file extensions / names.
        # Populated by :meth:`setup_chevrons` when a ``files_icon_dir`` is
        # supplied — kept on the proxy so ``data(DecorationRole)`` can hand
        # them back without rebuilding ``QIcon``s on every paint.
        self._file_icons = {}

    def setup_chevrons(self, tree_view, chevron_right_path, chevron_down_path, files_icon_dir=None):
        """Bind the proxy to the view so folder rows can render their own chevron.

        ``data(DecorationRole)`` looks up ``isExpanded`` on the view, so we
        also need to hear about expand/collapse to re-emit ``dataChanged``
        and force the row to repaint with the flipped chevron. When
        ``files_icon_dir`` is provided, the per-extension Material Icon
        Theme SVGs in that folder are loaded into a small cache for the
        file rows.
        """
        self._tree_view = tree_view
        self._chevron_right = QIcon(chevron_right_path)
        self._chevron_down = QIcon(chevron_down_path)
        if files_icon_dir is not None:
            unique_glyphs = set(_FILE_EXTENSION_ICONS.values()) | set(_FILE_NAME_ICONS.values())
            for glyph in unique_glyphs:
                path = os.path.join(files_icon_dir, f"{glyph}.svg")
                if os.path.exists(path):
                    self._file_icons[glyph] = QIcon(path)
        tree_view.expanded.connect(self._on_expansion_changed)
        tree_view.collapsed.connect(self._on_expansion_changed)

    def _on_expansion_changed(self, index):
        """Re-emit DecorationRole change so the icon flips on expand/collapse."""
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def filterAcceptsRow(self, source_row, source_parent):
        """Drop dot-prefixed entries plus a small list of platform/system noise."""
        source_model = self.sourceModel()
        if not source_model:
            return True

        index = source_model.index(source_row, 0, source_parent)
        file_name = source_model.fileInfo(index).fileName()

        if file_name.startswith("."):
            return False
        # Substring match (not just suffix) so Python build artefacts like
        # ``foo.pyc`` or stray ``.DS_Store`` files are hidden too.
        return all(pattern not in file_name for pattern in _HIDDEN_PATTERNS)

    def data(self, index, role=Qt.DisplayRole):
        """Custom decorations: chevron for folders, Material glyph for known files."""
        if role == Qt.DecorationRole and self._tree_view is not None and self._chevron_right is not None:
            source_index = self.mapToSource(index)
            if source_index.isValid():
                source_model = self.sourceModel()
                if source_model is not None:
                    file_info = source_model.fileInfo(source_index)
                    if file_info.isDir():
                        return self._chevron_down if self._tree_view.isExpanded(index) else self._chevron_right
                    file_icon = self._lookup_file_icon(file_info)
                    if file_icon is not None:
                        return file_icon
        return super().data(index, role)

    def _lookup_file_icon(self, file_info):
        """Return a bundled file-type ``QIcon`` for ``file_info`` or None.

        Whole-name matches (``LICENSE``, ``CMakeLists.txt``, ``.gitignore``)
        win over extension matches so files that double as configuration
        get the more specific glyph. Anything not in either map falls
        through to the source model's default decoration.
        """
        if not self._file_icons:
            return None
        name_key = file_info.fileName().lower()
        glyph = _FILE_NAME_ICONS.get(name_key)
        if glyph is None:
            ext = file_info.suffix().lower()
            glyph = _FILE_EXTENSION_ICONS.get(ext)
        if glyph is None:
            return None
        return self._file_icons.get(glyph)


def _icons_dir() -> str:
    """Absolute path to the explorer / toolbar shared SVG directory."""
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "icons"))


# Map a lower-cased file extension (without dot) to one of the bundled
# Material Icon Theme SVGs in ``ui/icons/files/``. Anything missing here
# falls through to ``QFileSystemModel``'s default decoration provider so
# the OS-registered icon still shows.
_FILE_EXTENSION_ICONS = {
    "py": "python",
    "md": "markdown",
    "json": "json",
    "yml": "yaml",
    "yaml": "yaml",
    "toml": "toml",
    "txt": "document",
    "ini": "settings",
    "cfg": "settings",
    "conf": "settings",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "h": "h",
    "hpp": "h",
    "hh": "h",
    "cmake": "cmake",
    "bat": "console",
    "sh": "console",
    "cmd": "console",
    "ps1": "console",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "gif": "image",
    "svg": "image",
    "bmp": "image",
    "ico": "image",
    "webp": "image",
    "tiff": "image",
    "log": "log",
}

# Whole-filename matches (case-insensitive). Wins over the extension map
# so e.g. ``CMakeLists.txt`` is the cmake glyph rather than ``document``.
_FILE_NAME_ICONS = {
    "license": "certificate",
    "cmakelists.txt": "cmake",
    ".env": "tune",
    ".gitignore": "git",
    ".gitattributes": "git",
}

# Patterns matched against the *full* filename (substring) by
# ``HiddenFileFilterModel.filterAcceptsRow``. Dot-prefixed entries like
# ``.gitignore`` are already dropped by the leading-dot rule, so this list
# only carries the ones that wouldn't be caught by that — Python build
# artefacts and platform noise.
_HIDDEN_PATTERNS = ("__pycache__", ".pyc", ".pyo", ".DS_Store", "Thumbs.db")


class _ExplorerTreeView(QTreeView):
    """``QTreeView`` subclass for the file explorer.

    Owns the paint customisations that QSS alone can't express — currently
    the VSCode-style vertical indent guides drawn over the branch column.
    """

    def drawBranches(self, painter, rect, index):
        """Indent guides only — no default chevron.

        ``HiddenFileFilterModel`` returns the expand chevron through
        ``DecorationRole`` so it lands in the same x column as a file's
        type icon. Calling ``super().drawBranches`` would also paint Qt's
        own chevron in the branch column, leaving us with two duplicates
        at different x positions; we deliberately skip the base call and
        stamp only the vertical guide lines for ancestor levels.

        Each line sits at the centre of the column where an ancestor's
        chevron (or file icon) is rendered — VSCode's "the guide threads
        through the parent's expander" placement. When
        ``rootIsDecorated`` is on, depth 0 has an empty branch slot at
        ``x = 0..indent`` so the first chevron lives at ``x = indent``;
        without it, depth 0 chevrons sit flush at ``x = 0``. We bake that
        offset into ``base_indent`` so the formula stays a single line.
        """
        depth = 0
        parent = index.parent()
        root = self.rootIndex()
        while parent.isValid() and parent != root:
            depth += 1
            parent = parent.parent()
        if depth == 0:
            return

        indent = self.indentation()
        if indent <= 0:
            return

        # The chevron / file icon is rendered at the left of the icon
        # column with a 16 px pixmap, so half-icon = 8 px centres us.
        icon_half = 8
        base_indent = indent if self.rootIsDecorated() else 0
        painter.save()
        painter.setPen(QPen(QColor(AppTheme.INDENT_GUIDE_COLOR), 1))
        for level in range(depth):
            x = rect.left() + base_indent + level * indent + icon_half
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()


class FileExplorerDelegate(QStyledItemDelegate):
    """Custom delegate to show run button on hover for Python files."""

    # Constants for run button appearance
    BUTTON_SIZE = 16
    BUTTON_MARGIN = 4
    CLICK_AREA_MULTIPLIER = 1.5

    # Extra horizontal space inserted between the file/folder icon and the
    # name. Qt's default delegate packs them tighter than VSCode reads.
    ICON_TEXT_GAP = 4

    def __init__(self, file_explorer, parent=None):
        super().__init__(parent)
        self.file_explorer = file_explorer
        # ``QPersistentModelIndex`` survives layoutChanged / row insertions
        # under the proxy + QFileSystemModel — a plain ``QModelIndex`` goes
        # silently invalid after a folder expansion and dereferencing it
        # later (e.g. ``visualRect``) crashes Maya.
        self.hovered_index = None  # QPersistentModelIndex when set
        self.run_button_rect = None

    def initStyleOption(self, option, index):
        """Widen the icon's reserved rect so the name renders with breathing room.

        Inflating ``decorationSize`` keeps the icon centred at its natural
        pixel size while pushing the text start position by the extra width.
        """
        super().initStyleOption(option, index)
        size = option.decorationSize
        option.decorationSize = QSize(size.width() + self.ICON_TEXT_GAP, size.height())

    def paint(self, painter, option, index):
        """Paint the item with optional run button."""
        # Call parent paint first
        super().paint(painter, option, index)

        # Only show button for hovered Python files. Compare against the
        # persistent index by lifting the incoming volatile QModelIndex.
        if self.hovered_index is not None and self.hovered_index.isValid() and QPersistentModelIndex(index) == self.hovered_index:
            # Get file info
            source_index = self.file_explorer.proxy_model.mapToSource(index)
            file_path = self.file_explorer.file_model.filePath(source_index)
            file_info = QFileInfo(file_path)

            if file_info.isFile() and file_info.suffix().lower() == "py":
                # Calculate button position
                button_x = option.rect.right() - self.BUTTON_SIZE - self.BUTTON_MARGIN
                button_y = option.rect.center().y() - self.BUTTON_SIZE // 2

                # Create a larger clickable area for better UX
                click_area_size = int(self.BUTTON_SIZE * self.CLICK_AREA_MULTIPLIER)
                click_area_offset = (click_area_size - self.BUTTON_SIZE) // 2
                self.run_button_rect = QRect(button_x - click_area_offset, button_y - click_area_offset, click_area_size, click_area_size)

                # Draw run button
                self._draw_run_button(painter, button_x, button_y)

    def _draw_run_button(self, painter, x, y):
        """Draw the run button (play icon) at the specified position."""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Background circle (slightly darker for better visibility)
        painter.setPen(QPen(QColor(*AppTheme.EXPLORER_RUN_BUTTON_BORDER), 1))
        painter.setBrush(QBrush(QColor(*AppTheme.EXPLORER_RUN_BUTTON_BACKGROUND)))
        painter.drawEllipse(x, y, self.BUTTON_SIZE, self.BUTTON_SIZE)

        # Play triangle (centered in the button, matching toolbar icon color)
        triangle_points = [
            QPointF(x + self.BUTTON_SIZE * 0.375, y + self.BUTTON_SIZE * 0.25),  # Top left
            QPointF(x + self.BUTTON_SIZE * 0.375, y + self.BUTTON_SIZE * 0.75),  # Bottom left
            QPointF(x + self.BUTTON_SIZE * 0.75, y + self.BUTTON_SIZE * 0.5),  # Right center
        ]
        triangle = QPolygonF(triangle_points)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(*AppTheme.EXPLORER_RUN_BUTTON_PLAY)))
        painter.drawPolygon(triangle)

        painter.restore()

    def set_hovered_index(self, index):
        """Update the hovered index.

        ``index`` is the volatile ``QModelIndex`` from ``indexAt`` (or
        ``None``); we keep a ``QPersistentModelIndex`` so a later folder
        expand / sort doesn't leave us pointing at freed memory.
        """
        old_index = self.hovered_index
        self.hovered_index = QPersistentModelIndex(index) if index is not None and index.isValid() else None
        self.run_button_rect = None

        # Request repaint for both old and new indices. ``visualRect`` accepts
        # ``QPersistentModelIndex`` directly in PySide; convert to a
        # ``QModelIndex`` to be explicit about which API contract we expect.
        view = self.parent()
        if old_index is not None and old_index.isValid():
            view.viewport().update(view.visualRect(QModelIndex(old_index)))
        if self.hovered_index is not None and self.hovered_index.isValid():
            view.viewport().update(view.visualRect(QModelIndex(self.hovered_index)))

    def get_run_button_rect(self):
        """Get the current run button rect."""
        return self.run_button_rect

    def createEditor(self, parent, option, index):
        """Create custom editor for inline editing with pre-selected filename."""
        editor = QLineEdit(parent)

        # Get the current filename
        filename = index.data(Qt.DisplayRole)
        if filename:
            editor.setText(filename)

            # Select only the filename part without extension
            if "." in filename and not filename.startswith("."):
                # Find the last dot to handle files like 'file.tar.gz'
                last_dot_index = filename.rfind(".")
                if last_dot_index > 0:
                    # Select from start to the last dot (excluding the dot and extension)
                    QTimer.singleShot(0, lambda: editor.setSelection(0, last_dot_index))

        return editor


class FileExplorer(QWidget):
    """File tree explorer widget."""

    file_selected = Signal(str)  # Emitted when a file is double-clicked (permanent tab)
    file_preview = Signal(str)  # Emitted when a file is single-clicked (preview mode)
    file_executed = Signal(str)  # Emitted when a file is executed via run button
    file_renamed = Signal(str, str)  # Emitted when a file is renamed (old_path, new_path)
    folder_renamed = Signal(str, str)  # Emitted when a folder is renamed (old_path, new_path)
    file_deleted = Signal(str)  # Emitted when a file is deleted
    folder_deleted = Signal(str)  # Emitted when a folder is deleted

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_model = None
        self.proxy_model = None
        self.tree_view = None
        self.root_path = None
        self.delegate = None

        # Clipboard for file operations
        self.clipboard_paths = []
        self.clipboard_operation = None  # 'copy' or 'cut'
        self.startup_complete = False  # Prevent auto-preview during startup

        self.init_ui()
        self.setup_file_model()

        # Enable preview after startup
        QTimer.singleShot(1000, self._enable_preview)

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tree view
        self.tree_view = _ExplorerTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAlternatingRowColors(False)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)  # Enable multi-selection
        self.tree_view.setMouseTracking(True)  # Enable mouse tracking for hover
        # Drop the empty branch column at depth 0 — our chevrons are rendered
        # via the model's DecorationRole in the icon column, so the default
        # branch slot is just wasted left padding (~one indentation unit).
        self.tree_view.setRootIsDecorated(False)
        # NOTE: ``setSortingEnabled(True)`` is intentionally deferred to
        # ``setup_file_model``. With QFileSystemModel + QSortFilterProxyModel,
        # enabling sort *before* the model is attached and then expanding a
        # folder triggers a row-insert / sort / repaint race that has
        # historically crashed Maya. Order is: setModel -> sortByColumn ->
        # setSortingEnabled.

        # Enable editing only through F2 or context menu
        self.tree_view.setEditTriggers(QTreeView.EditKeyPressed)

        # Set custom delegate for run button
        self.delegate = FileExplorerDelegate(self, self.tree_view)
        self.tree_view.setItemDelegate(self.delegate)

        # Connect signals
        self.tree_view.clicked.connect(self.on_single_click)
        self.tree_view.doubleClicked.connect(self.on_double_click)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

        # Install event filter for hover and mouse events
        self.tree_view.viewport().installEventFilter(self)

        # Override drag and drop events
        self.tree_view.startDrag = self.start_drag
        self.tree_view.dragEnterEvent = self.drag_enter_event
        self.tree_view.dragMoveEvent = self.drag_move_event
        self.tree_view.dropEvent = self.drop_event

        layout.addWidget(self.tree_view)

        # Enable keyboard shortcuts
        self.tree_view.setFocusPolicy(Qt.StrongFocus)

        # Enable drag and drop
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setDragDropMode(QTreeView.DragDrop)

    def setup_file_model(self):
        """Setup the file system model with hidden file filtering."""
        self.file_model = QFileSystemModel()
        self.file_model.setReadOnly(False)  # Enable rename functionality

        # Connect rename signal
        self.file_model.fileRenamed.connect(self.on_file_renamed)

        # Create proxy model for filtering hidden files
        self.proxy_model = HiddenFileFilterModel()
        self.proxy_model.setSourceModel(self.file_model)

        # Set the proxy model to tree view
        self.tree_view.setModel(self.proxy_model)

        # Wire folder chevrons through DecorationRole now that the view and
        # model are attached. Has to come after ``setModel`` so the model
        # can observe ``expanded`` / ``collapsed`` from the live view.
        icon_dir = _icons_dir()
        self.proxy_model.setup_chevrons(
            self.tree_view,
            os.path.join(icon_dir, "chevron_right.svg"),
            os.path.join(icon_dir, "chevron_down.svg"),
            files_icon_dir=os.path.join(icon_dir, "files"),
        )

        # Establish a stable initial sort order *before* enabling interactive
        # sort. Doing this against an attached model keeps row insertion (which
        # QFileSystemModel does asynchronously while users expand folders) from
        # racing with the sort/repaint pipeline.
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)
        self.tree_view.setSortingEnabled(True)

        # Hide size, type, and date columns - only show name
        header = self.tree_view.header()
        header.hideSection(1)  # Size
        header.hideSection(2)  # Type
        header.hideSection(3)  # Date Modified

        # Don't initialize root path here - let setup_workspace() set it
        # This avoids unnecessary setRootPath() calls and os.listdir() operations
        # The actual root path will be set by main_window.setup_workspace()

    def set_root_path(self, path: str):
        """Set the root path for the file explorer."""

        if os.path.exists(path):
            self.root_path = path
            root_index = self.file_model.setRootPath(path)

            # Map from source model to proxy model
            proxy_root_index = self.proxy_model.mapFromSource(root_index)
            self.tree_view.setRootIndex(proxy_root_index)

            # Use a timer to check row count after model has loaded
            def check_model_loaded():
                try:
                    # Check if tree_view still exists
                    if not hasattr(self, "tree_view") or self.tree_view is None:
                        return

                    row_count = self.file_model.rowCount(root_index)
                    if row_count > 0:
                        self.tree_view.expand(root_index)
                except RuntimeError:
                    # Handle case where C++ object has been deleted
                    return
                except Exception as e:
                    logger.error(f"FileExplorer model check error - {e}")
                    return
                else:
                    # Try to list directory contents manually
                    try:
                        os.listdir(path)
                    except Exception as e:
                        logger.error(f"FileExplorer directory listing error - {e}")

            # Check after a short delay for lazy loading
            QTimer.singleShot(100, check_model_loaded)

        else:
            logger.warning(f"FileExplorer path does not exist - {path}")

    def get_selected_path(self) -> str:
        """Get the currently selected file/folder path."""
        indexes = self.tree_view.selectedIndexes()
        if indexes:
            # Map proxy index to source index
            source_index = self.proxy_model.mapToSource(indexes[0])
            return self.file_model.filePath(source_index)
        return ""

    def _enable_preview(self):
        """Enable preview mode after startup."""
        self.startup_complete = True

    def on_single_click(self, index: QModelIndex):  # type: ignore
        """Handle single-click on file/folder."""
        # Skip preview during startup
        if not self.startup_complete:
            return

        # Check if this click was on the run button - if so, skip preview
        if hasattr(self, "_run_button_clicked") and self._run_button_clicked:
            self._run_button_clicked = False
            return

        # Map proxy index to source index
        source_index = self.proxy_model.mapToSource(index)
        file_path = self.file_model.filePath(source_index)
        file_info = QFileInfo(file_path)

        if file_info.isFile() and file_info.suffix().lower() == "py":
            # Emit signal for Python file preview mode
            self.file_preview.emit(file_path)
        elif file_info.isDir():
            # Toggle folder expansion/collapse on single-click
            if self.tree_view.isExpanded(index):
                self.tree_view.collapse(index)
            else:
                self.tree_view.expand(index)

    def on_double_click(self, index: QModelIndex):  # type: ignore
        """Handle double-click on file/folder."""
        # Map proxy index to source index
        source_index = self.proxy_model.mapToSource(index)
        file_path = self.file_model.filePath(source_index)
        file_info = QFileInfo(file_path)

        if file_info.isFile() and file_info.suffix().lower() == "py":
            # Emit signal for Python file permanent tab
            self.file_selected.emit(file_path)
        # Folders: expansion/collapse handled by single-click

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for file operations."""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                # Ctrl+C - Copy
                self.copy_selected()
            elif event.key() == Qt.Key_X:
                # Ctrl+X - Cut
                self.cut_selected()
            elif event.key() == Qt.Key_V:
                # Ctrl+V - Paste
                self.paste_items()
            else:
                super().keyPressEvent(event)
        elif event.key() == Qt.Key_F2:
            # F2 - Rename
            self.start_rename()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, position):
        """Show context menu for file operations."""
        index = self.tree_view.indexAt(position)

        # Get file info if clicking on a valid item
        file_path = None
        file_info = None
        has_selection = False

        if index.isValid():
            # Map proxy index to source index
            source_index = self.proxy_model.mapToSource(index)
            file_path = self.file_model.filePath(source_index)
            file_info = QFileInfo(file_path)
            has_selection = True

        # Always show menu, but enable/disable items based on selection

        menu = QMenu(self)

        # Apply styling matching code editor context menu
        menu.setStyleSheet(AppTheme.get_menu_stylesheet())

        # Open action for Python files
        if has_selection and file_info.isFile() and file_info.suffix().lower() == "py":
            open_action = QAction("Open", self)
            open_action.triggered.connect(lambda: self.file_selected.emit(file_path))
            menu.addAction(open_action)
            menu.addSeparator()

        # New file action
        new_file_action = QAction("New Python File", self)
        if has_selection:
            new_file_action.triggered.connect(lambda: self.create_new_file(file_path, file_info.isDir()))
        else:
            new_file_action.triggered.connect(lambda: self.create_new_file(self.root_path, True))
        menu.addAction(new_file_action)

        # New folder action
        new_folder_action = QAction("New Folder", self)
        if has_selection:
            new_folder_action.triggered.connect(lambda: self.create_new_folder(file_path, file_info.isDir()))
        else:
            new_folder_action.triggered.connect(lambda: self.create_new_folder(self.root_path, True))
        menu.addAction(new_folder_action)

        menu.addSeparator()

        # Copy action
        copy_action = QAction("Copy\tCtrl+C", self)
        copy_action.triggered.connect(self.copy_selected)
        copy_action.setEnabled(has_selection)
        menu.addAction(copy_action)

        # Cut action
        cut_action = QAction("Cut\tCtrl+X", self)
        cut_action.triggered.connect(self.cut_selected)
        cut_action.setEnabled(has_selection)
        menu.addAction(cut_action)

        # Paste action
        paste_action = QAction("Paste\tCtrl+V", self)
        paste_action.triggered.connect(self.paste_items)
        paste_action.setEnabled(len(self.clipboard_paths) > 0)
        menu.addAction(paste_action)

        menu.addSeparator()

        # Rename action (for files and folders)
        rename_action = QAction("Rename\tF2", self)
        if has_selection:
            rename_action.triggered.connect(self.start_rename)
        rename_action.setEnabled(has_selection)
        menu.addAction(rename_action)

        # Delete action (for files and folders)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_selected_items)
        delete_action.setEnabled(has_selection)
        menu.addAction(delete_action)

        menu.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        menu.addAction(refresh_action)

        # Show menu
        menu.exec_(self.tree_view.mapToGlobal(position))

    def create_new_file(self, base_path: str, is_dir: bool):
        """Prompt for a filename and create a new Python file next to it."""
        parent_dir = base_path if is_dir else os.path.dirname(base_path)
        name, ok = CodeEditorInputDialog.getText(self, "New Python File", "Enter file name:", text="new_script.py")
        if not (ok and name):
            return

        result = file_ops.create_python_file(parent_dir, name)
        if result.success:
            self.file_selected.emit(result.destination)
        else:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to create file: {result.error}")

    def create_new_folder(self, base_path: str, is_dir: bool):
        """Prompt for a folder name and create a new folder."""
        parent_dir = base_path if is_dir else os.path.dirname(base_path)
        name, ok = CodeEditorInputDialog.getText(self, "New Folder", "Enter folder name:")
        if not (ok and name):
            return

        result = file_ops.create_folder(parent_dir, name)
        if not result.success:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to create folder: {result.error}")

    def refresh(self):
        """Refresh the file tree."""
        if self.root_path:
            current_index = self.tree_view.currentIndex()
            self.file_model.setRootPath("")  # Reset
            root_index = self.file_model.setRootPath(self.root_path)

            # Map from source model to proxy model
            proxy_root_index = self.proxy_model.mapFromSource(root_index)
            self.tree_view.setRootIndex(proxy_root_index)

            # Try to restore selection
            if current_index.isValid():
                self.tree_view.setCurrentIndex(current_index)

    def start_rename(self):
        """Start inline rename for the selected item."""
        indexes = self.tree_view.selectedIndexes()
        if indexes:
            # Start editing on the first selected item
            self.tree_view.edit(indexes[0])

    def on_file_renamed(self, old_path: str, old_name: str, new_name: str):
        """Handle file renamed signal from the file system model."""
        # Construct full paths
        parent_dir = old_path
        old_full_path = os.path.join(parent_dir, old_name)
        new_full_path = os.path.join(parent_dir, new_name)

        # Check if it's a file or folder and emit appropriate signal
        if os.path.isfile(new_full_path):
            self.file_renamed.emit(old_full_path, new_full_path)
            logger.info(f"File renamed: {old_name} -> {new_name}")
        elif os.path.isdir(new_full_path):
            self.folder_renamed.emit(old_full_path, new_full_path)
            logger.info(f"Folder renamed: {old_name} -> {new_name}")

    def delete_selected_items(self):
        """Confirm, then delete every selected file/folder via ``file_ops``."""
        selected_paths = self.get_selected_paths()
        if not selected_paths:
            return

        if not self._confirm_delete(selected_paths):
            return

        success_count = 0
        errors = []
        for path in selected_paths:
            was_file = os.path.isfile(path)
            was_dir = os.path.isdir(path)
            result = file_ops.delete_item(path)
            if result.success:
                success_count += 1
                if was_file:
                    self.file_deleted.emit(path)
                elif was_dir:
                    self.folder_deleted.emit(path)
            else:
                errors.append(f"{os.path.basename(path)}: {result.error}")

        self.refresh()

        if errors:
            error_msg = f"Successfully deleted {success_count} item(s), but failed to delete {len(errors)} item(s)."
            error_msg += "\n\nErrors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            CodeEditorMessageBox.warning(self, "Delete Operation", error_msg)
        elif success_count > 0:
            logger.info(f"Successfully deleted {success_count} item(s)")

    def _confirm_delete(self, selected_paths: list) -> bool:
        """Build the confirmation prompt for a delete and return True on Yes."""
        num_items = len(selected_paths)
        if num_items == 1:
            item_name = os.path.basename(selected_paths[0])
            confirmation_msg = f"Are you sure you want to delete this item?\n\n{item_name}"
        else:
            items_to_show = min(5, num_items)
            item_names = [os.path.basename(path) for path in selected_paths[:items_to_show]]
            items_list = "\n".join(f"  • {name}" for name in item_names)
            if num_items > items_to_show:
                items_list += f"\n  ... and {num_items - items_to_show} more"
            confirmation_msg = f"Are you sure you want to delete {num_items} items?\n\n{items_list}"

        reply = CodeEditorMessageBox.question(
            self,
            "Confirm Delete",
            confirmation_msg,
            CodeEditorMessageBox.Yes | CodeEditorMessageBox.No,
            CodeEditorMessageBox.No,
        )
        return reply == CodeEditorMessageBox.Yes

    def copy_selected(self):
        """Copy selected items to clipboard."""
        selected_paths = self.get_selected_paths()
        if selected_paths:
            self.clipboard_paths = selected_paths
            self.clipboard_operation = "copy"
            logger.info(f"Copied {len(selected_paths)} item(s) to clipboard")

    def cut_selected(self):
        """Cut selected items to clipboard."""
        selected_paths = self.get_selected_paths()
        if selected_paths:
            self.clipboard_paths = selected_paths
            self.clipboard_operation = "cut"
            logger.info(f"Cut {len(selected_paths)} item(s) to clipboard")

    def paste_items(self):
        """Paste items from clipboard to current location."""
        if not self.clipboard_paths or not self.clipboard_operation:
            return

        # Get current selection or root path as destination
        destination_path = self.get_paste_destination()
        if not destination_path:
            return

        success_count = 0
        error_count = 0

        for source_path in self.clipboard_paths:
            try:
                if self.clipboard_operation == "copy":
                    success = self.copy_item(source_path, destination_path)
                else:  # cut
                    success = self.move_item(source_path, destination_path)

                if success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing {source_path}: {e!s}")

        # Clear clipboard after cut operation
        if self.clipboard_operation == "cut" and success_count > 0:
            self.clipboard_paths = []
            self.clipboard_operation = None

        # Refresh view
        self.refresh()

        logger.info(f"Completed: {success_count} successful, {error_count} errors")

    def get_selected_paths(self):
        """Get paths of all selected items."""
        selected_paths = []
        indexes = self.tree_view.selectedIndexes()

        for index in indexes:
            source_index = self.proxy_model.mapToSource(index)
            file_path = self.file_model.filePath(source_index)
            if file_path and file_path not in selected_paths:
                selected_paths.append(file_path)

        return selected_paths

    def get_paste_destination(self):
        """Get destination path for paste operation."""
        indexes = self.tree_view.selectedIndexes()

        if indexes:
            # Use first selected item's parent directory
            source_index = self.proxy_model.mapToSource(indexes[0])
            file_path = self.file_model.filePath(source_index)
            file_info = QFileInfo(file_path)

            if file_info.isDir():
                return file_path
            return file_info.dir().absolutePath()
        # Use root path
        return self.root_path

    def copy_item(self, source_path, destination_dir):
        """Copy through ``file_ops`` and surface errors via the UI."""
        result = file_ops.copy_item(source_path, destination_dir)
        if not result.success:
            name = os.path.basename(source_path)
            CodeEditorMessageBox.warning(self, "Copy Error", f"Failed to copy {name}: {result.error}")
        return result.success

    def move_item(self, source_path, destination_dir):
        """Move through ``file_ops`` and surface errors via the UI."""
        result = file_ops.move_item(source_path, destination_dir)
        if not result.success:
            name = os.path.basename(source_path)
            CodeEditorMessageBox.warning(self, "Move Error", f"Failed to move {name}: {result.error}")
        return result.success

    def start_drag(self, supportedActions):
        """Start drag operation with custom mime data."""
        from ......lib_ui.qt_compat import QtCore, QtGui

        # Get selected items
        selected_paths = self.get_selected_paths()
        if not selected_paths:
            return

        # Create mime data
        mime_data = QtCore.QMimeData()

        # Set text data for internal drag detection
        mime_data.setText("internal_drag")

        # Set URLs for external compatibility
        urls = []
        for path in selected_paths:
            url = QtCore.QUrl.fromLocalFile(path)
            urls.append(url)
        mime_data.setUrls(urls)

        # Create drag object
        drag = QtGui.QDrag(self.tree_view)
        drag.setMimeData(mime_data)

        # Execute drag
        drag.exec_(supportedActions)

    def drag_enter_event(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def drag_move_event(self, event):
        """Handle drag move event."""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            # Get the index under mouse cursor
            index = self.tree_view.indexAt(event.pos())
            if index.isValid():
                # Map to source model
                source_index = self.proxy_model.mapToSource(index)
                file_path = self.file_model.filePath(source_index)
                file_info = QFileInfo(file_path)

                # Only accept drops on directories
                if file_info.isDir():
                    event.acceptProposedAction()
                else:
                    event.ignore()
            else:
                # Drop on empty area - accept for root directory
                event.acceptProposedAction()
        else:
            event.ignore()

    def eventFilter(self, obj, event):
        """Handle mouse events for hover and click detection."""
        if obj == self.tree_view.viewport():
            if event.type() == QEvent.MouseMove:
                # Update hover state
                index = self.tree_view.indexAt(event.pos())
                self.delegate.set_hovered_index(index if index.isValid() else None)
                return False

            if event.type() == QEvent.Leave:
                # Clear hover state when mouse leaves
                self.delegate.set_hovered_index(None)
                return False

            # Check if click is on run button
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                index = self.tree_view.indexAt(event.pos())
                hovered = self.delegate.hovered_index
                if index.isValid() and hovered is not None and hovered.isValid() and QPersistentModelIndex(index) == hovered:
                    button_rect = self.delegate.get_run_button_rect()
                    if button_rect and button_rect.contains(event.pos()):
                        # Execute the file
                        source_index = self.proxy_model.mapToSource(index)
                        file_path = self.file_model.filePath(source_index)

                        # Set flag to prevent preview tab from opening
                        self._run_button_clicked = True

                        self.file_executed.emit(file_path)
                        return True  # Consume the event

        return super().eventFilter(obj, event)

    def drop_event(self, event):
        """Handle drop event."""
        if not (event.mimeData().hasUrls() or event.mimeData().hasText()):
            event.ignore()
            return

        # Get drop target
        index = self.tree_view.indexAt(event.pos())
        target_dir = None

        if index.isValid():
            # Dropped on an item
            source_index = self.proxy_model.mapToSource(index)
            file_path = self.file_model.filePath(source_index)
            file_info = QFileInfo(file_path)

            if file_info.isDir():
                target_dir = file_path
            else:
                # Dropped on a file - use its parent directory
                target_dir = file_info.dir().absolutePath()
        else:
            # Dropped on empty area - use root path
            target_dir = self.root_path

        if not target_dir:
            event.ignore()
            return

        # Get dragged items and determine operation type
        dragged_paths = []
        is_external_drag = False

        # Check if this is an internal drag (from our tree view)
        if event.mimeData().hasText() and event.mimeData().text() == "internal_drag":
            # Internal drag - get selected items for move operation
            dragged_paths = self.get_selected_paths()
            is_external_drag = False
        elif event.mimeData().hasUrls():
            # External drag - get URLs for copy operation
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    # Filter for Python files (.py) when dragging from external source
                    if local_path.lower().endswith(".py"):
                        dragged_paths.append(local_path)
            is_external_drag = True

        if not dragged_paths:
            if is_external_drag and event.mimeData().hasUrls():
                # Inform user that only Python files are accepted
                logger.warning("Only Python (.py) files can be dropped into the explorer")
            event.ignore()
            return

        # Perform the operation (move for internal, copy for external)
        success_count = 0
        error_count = 0
        operation_name = "Copied" if is_external_drag else "Moved"

        for source_path in dragged_paths:
            # Skip if source and target are the same (only for internal move)
            if not is_external_drag and os.path.dirname(source_path) == target_dir:
                continue

            # Skip if trying to move a parent into its child (only for internal move)
            if not is_external_drag and target_dir.startswith(source_path + os.sep):
                continue

            try:
                if is_external_drag:
                    # Copy external files
                    success = self.copy_item(source_path, target_dir)
                else:
                    # Move internal files
                    success = self.move_item(source_path, target_dir)

                if success:
                    success_count += 1

                    # Emit signals for file tracking (only for internal moves)
                    if not is_external_drag:
                        if os.path.isfile(os.path.join(target_dir, os.path.basename(source_path))):
                            # File moved
                            new_path = os.path.join(target_dir, os.path.basename(source_path))
                            self.file_renamed.emit(source_path, new_path)
                        else:
                            # Folder moved
                            new_path = os.path.join(target_dir, os.path.basename(source_path))
                            self.folder_renamed.emit(source_path, new_path)
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                operation = "copying" if is_external_drag else "moving"
                logger.error(f"Error {operation} {source_path}: {e!s}")

        # Refresh the view
        self.refresh()

        if success_count > 0:
            event.acceptProposedAction()
            logger.info(f"{operation_name} {success_count} item(s) to workspace")
            if error_count > 0:
                logger.warning(f"Failed to {operation_name.lower()} {error_count} item(s)")
        else:
            event.ignore()
