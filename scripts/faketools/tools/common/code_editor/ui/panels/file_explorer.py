"""
File explorer widget for Code Editor.

UI layer: tree view + context menu + drag/drop. All filesystem mutations are
delegated to ``command.file_ops`` so the widget only translates user intent
into ops and renders the resulting error messages.
"""

import contextlib
from logging import getLogger
import os

from ......lib_ui.qt_compat import (
    QAction,
    QApplication,
    QBrush,
    QColor,
    QEvent,
    QFileInfo,
    QFileSystemModel,
    QIcon,
    QItemSelectionModel,
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
from ...languages import ALL_PROFILES, DEFAULT_PROFILE, KNOWN_EXTENSIONS, LanguageProfile
from ...themes import AppTheme
from ..dialogs import CodeEditorMessageBox

logger = getLogger(__name__)


def _path_has_known_extension(path: str) -> bool:
    """Return True when ``path``'s extension matches any registered :class:`LanguageProfile`.

    Used as a single source of truth for "is this a file the editor knows
    how to open?" — drives preview/run/double-click affordances.
    """
    return os.path.splitext(path)[1].lower() in KNOWN_EXTENSIONS


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

    def lessThan(self, left, right):
        """Folders before files, then case-insensitive name within each group.

        Directories always lead regardless of ``sortOrder`` — when the user
        flips to descending we invert the directory branch so Qt's
        post-flip rendering still places folders on top, matching the
        VSCode / Explorer convention.
        """
        source_model = self.sourceModel()
        if source_model is None:
            return super().lessThan(left, right)

        left_info = source_model.fileInfo(left)
        right_info = source_model.fileInfo(right)
        left_is_dir = left_info.isDir()
        right_is_dir = right_info.isDir()

        if left_is_dir != right_is_dir:
            return left_is_dir if self.sortOrder() == Qt.AscendingOrder else not left_is_dir

        return left_info.fileName().lower() < right_info.fileName().lower()

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

        # Only show button for hovered source files in any registered language.
        # Compare against the persistent index by lifting the incoming
        # volatile QModelIndex.
        if self.hovered_index is not None and self.hovered_index.isValid() and QPersistentModelIndex(index) == self.hovered_index:
            # Get file info
            source_index = self.file_explorer.proxy_model.mapToSource(index)
            file_path = self.file_explorer.file_model.filePath(source_index)
            file_info = QFileInfo(file_path)

            if file_info.isFile() and _path_has_known_extension(file_path):
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
        """Create custom editor for inline editing.

        Inline-create flow starts the editor blank so the user types the
        filename from scratch — the on-disk placeholder name is internal
        scratch state. F2 rename of existing files keeps the original
        pre-filled-with-basename-selected behaviour.
        """
        editor = QLineEdit(parent)

        # Inline-create: leave the editor empty; ``setEditorData`` below
        # also skips the default re-population for this case.
        if getattr(self.file_explorer, "_fresh_path", None):
            return editor

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

    def setEditorData(self, editor, index):
        """Skip Qt's default EditRole pre-population when inline-creating.

        Without this override, the default ``QStyledItemDelegate.setEditorData``
        would re-populate the editor with the model's EditRole (the
        placeholder filename), defeating ``createEditor``'s blank start.
        """
        if getattr(self.file_explorer, "_fresh_path", None):
            editor.setText("")
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Commit hook for inline-create edits.

        Three cases, all gated on the explorer having a live
        ``_fresh_path`` (F2 rename of existing files falls straight
        through to the default ``QStyledItemDelegate.setModelData``):

        - **Empty submission** → treat as cancel: clear the tracker
          synchronously so ``_on_inline_rename_closed`` skips the
          open-tab step, then schedule the placeholder deletion for
          after the editor finishes tearing down.
        - **Bare basename** (no dot in the entered name) → append the
          language's default extension so ``foo`` becomes ``foo.py``.
        - **Anything else** → pass through unchanged; an explicit dot
          anywhere in the basename (e.g. ``foo.txt``) signals user intent
          and is respected even if it differs from the language's default.
        """
        fresh_ext = getattr(self.file_explorer, "_fresh_extension", None)
        fresh_path = getattr(self.file_explorer, "_fresh_path", None)
        if fresh_path:
            text = editor.text().strip()
            if not text:
                # Clear trackers synchronously so the closeEditor
                # handler doesn't open or repurpose the placeholder.
                self.file_explorer._fresh_path = None
                self.file_explorer._fresh_extension = None
                QTimer.singleShot(0, lambda p=fresh_path: self.file_explorer._delete_fresh_placeholder(p))
                return
            if fresh_ext:
                basename = os.path.basename(text)
                _name_part, ext_part = os.path.splitext(basename)
                if not ext_part:
                    editor.setText(text + fresh_ext)
        super().setModelData(editor, model, index)


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

        # Path of a just-created file/folder waiting for the user to commit
        # or cancel its inline rename. ``None`` when no fresh entry exists.
        # See :meth:`create_new_file` / :meth:`_on_inline_rename_closed`
        # for the lifecycle.
        self._fresh_path = None
        # Language default extension for the in-flight file create, used
        # by :class:`FileExplorerDelegate.setModelData` to auto-append
        # the extension when the user submits a bare basename. ``None``
        # for folder creates and idle state.
        self._fresh_extension = None

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
        # Watch for editor close so a freshly-created file/folder whose
        # inline rename the user Esc-cancels gets deleted from disk.
        self.delegate.closeEditor.connect(self._on_inline_rename_closed)

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

        if file_info.isFile() and _path_has_known_extension(file_path):
            # Emit preview signal for any source file the editor recognises.
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

        if file_info.isFile() and _path_has_known_extension(file_path):
            # Emit signal for permanent-tab open of any registered source file.
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
        elif event.key() == Qt.Key_Delete:
            # Delete - Delete selected items (no-op when nothing selected so
            # the keypress doesn't trigger an empty confirmation dialog).
            if self.get_selected_paths():
                self.delete_selected_items()
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

        # Open action for files in any registered language
        if has_selection and file_info.isFile() and _path_has_known_extension(file_path):
            open_action = QAction("Open", self)
            open_action.triggered.connect(lambda: self.file_selected.emit(file_path))
            menu.addAction(open_action)
            menu.addSeparator()

        # New file actions — one per registered language profile.
        # Iterate ALL_PROFILES so adding a new language auto-extends the menu.
        if has_selection:
            target_path = file_path
            target_is_dir = file_info.isDir()
        else:
            target_path = self.root_path
            target_is_dir = True
        for profile in ALL_PROFILES:
            new_file_action = QAction(f"New {profile.display_name} File", self)
            new_file_action.triggered.connect(
                lambda checked=False, p=profile, path=target_path, isdir=target_is_dir: self.create_new_file(path, isdir, language=p)
            )
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

        # Delete action (for files and folders). Pass the menu's global
        # position so the confirmation dialog opens near where the user
        # clicked instead of the screen's right-half center.
        delete_action = QAction("Delete\tDel", self)
        menu_global = self.tree_view.mapToGlobal(position)
        delete_action.triggered.connect(lambda checked=False, pos=menu_global: self.delete_selected_items(anchor_global_pos=pos))
        delete_action.setEnabled(has_selection)
        menu.addAction(delete_action)

        menu.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        menu.addAction(refresh_action)

        # Show menu
        menu.exec_(self.tree_view.mapToGlobal(position))

    def begin_inline_create_file(self, language: LanguageProfile = DEFAULT_PROFILE):
        """Selection-aware entry point used by the toolbar / ``Ctrl+N``.

        Mirrors the context-menu rule so all three entry points behave
        the same way — selected folder anchors the create, a selected
        file places the new entry next to it, and no selection falls
        back to the workspace root.
        """
        base_path, is_dir = self._resolve_creation_target()
        if base_path:
            self.create_new_file(base_path, is_dir, language=language)

    def begin_inline_create_folder(self):
        """Selection-aware entry point for inline folder creation."""
        base_path, is_dir = self._resolve_creation_target()
        if base_path:
            self.create_new_folder(base_path, is_dir)

    def _resolve_creation_target(self) -> tuple[str, bool]:
        """Return ``(base_path, is_dir)`` for selection-driven creation."""
        for path in self.get_selected_paths():
            if os.path.exists(path):
                return path, os.path.isdir(path)
        if self.root_path:
            return self.root_path, True
        return "", False

    def create_new_file(self, base_path: str, is_dir: bool, language: LanguageProfile = DEFAULT_PROFILE):
        """Create a source file under ``base_path`` and start inline rename on its row.

        Uses the "pre-create + rename" pattern: the file is written to disk
        with a unique default name, the model is refreshed, and Qt's
        standard rename machinery (``tree_view.edit``) is invoked on the
        new row so the user can type the real name directly in the tree.

        - **Enter / focus-loss** → ``QFileSystemModel.setData`` renames the
          file on disk; ``on_file_renamed`` keeps ``_fresh_path`` in sync
          and ``_on_inline_rename_closed`` opens the file as a tab.
        - **Esc** → ``_on_inline_rename_closed`` deletes the freshly-created
          file so the disk doesn't accumulate ``new_script.py`` placeholders.

        Args:
            base_path (str): Path that anchors the creation directory; if it's
                a file, the new file is created next to it.
            is_dir (bool): Whether ``base_path`` itself is a directory.
            language (LanguageProfile): Profile driving the default extension.
        """
        parent_dir = base_path if is_dir else os.path.dirname(base_path)
        # ``file_ops.create_source_file`` overwrites if the path exists, so
        # pick a unique default name up-front to avoid clobbering anything.
        default_path = os.path.join(parent_dir, f"new_script{language.default_extension}")
        unique_name = os.path.basename(file_ops.get_unique_name(default_path))

        result = file_ops.create_source_file(parent_dir, unique_name, language=language)
        if not result.success:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to create file: {result.error}")
            return

        self._fresh_path = result.destination
        self._fresh_extension = language.default_extension
        # Force a model rebuild — QFileSystemWatcher misses creations on
        # SMB shares — and arrange for the new row to be reachable.
        self._refresh_preserving_state(ensure_visible_path=result.destination)
        self._schedule_inline_rename()

    def create_new_folder(self, base_path: str, is_dir: bool):
        """Create a folder under ``base_path`` and start inline rename on its row.

        Same lifecycle as :meth:`create_new_file` — folder is created with
        a unique default name, then Qt's rename machinery takes over.
        """
        parent_dir = base_path if is_dir else os.path.dirname(base_path)
        default_path = os.path.join(parent_dir, "new_folder")
        unique_name = os.path.basename(file_ops.get_unique_name(default_path))

        result = file_ops.create_folder(parent_dir, unique_name)
        if not result.success:
            CodeEditorMessageBox.warning(self, "Error", f"Failed to create folder: {result.error}")
            return

        self._fresh_path = result.destination
        self._refresh_preserving_state(ensure_visible_path=result.destination)
        self._schedule_inline_rename()

    def _schedule_inline_rename(self, attempts_left: int = 10):
        """Locate the freshly-created row and start ``tree_view.edit`` on it.

        ``QFileSystemModel`` populates directories asynchronously, so the
        freshly-written path may not have an index in the model the
        instant we ask. Retry up to ``attempts_left`` times at 100 ms
        intervals — enough latitude for slow SMB shares without making
        cancel feel sluggish.
        """
        if not self._fresh_path:
            return
        src_index = self.file_model.index(self._fresh_path)
        if src_index.isValid():
            proxy_index = self.proxy_model.mapFromSource(src_index)
            if proxy_index.isValid():
                self.tree_view.setCurrentIndex(proxy_index)
                self.tree_view.scrollTo(proxy_index)
                self.tree_view.edit(proxy_index)
                return
        if attempts_left > 0:
            QTimer.singleShot(100, lambda: self._schedule_inline_rename(attempts_left - 1))
        else:
            logger.warning(f"Inline rename: model never exposed the fresh path {self._fresh_path}")

    def _delete_fresh_placeholder(self, path: str):
        """Disk-side cleanup for an empty-named inline-create commit.

        Invoked one event-loop tick after the editor's ``setModelData``
        cleared the trackers — the editor is fully torn down by then so
        the refresh isn't racing with an in-flight rename.
        """
        result = file_ops.delete_item(path)
        if not result.success:
            logger.warning(f"Failed to delete empty-named new entry: {result.error}")
        self._refresh_preserving_state()

    def _on_inline_rename_closed(self, editor, hint):
        """Editor-close handler — decides whether the fresh entry survives.

        Fires for *every* editor close (F2 rename of existing files too),
        but only acts when ``_fresh_path`` is set, which marks a pending
        inline-create. On Esc (``RevertModelCache``) the disk file is
        deleted; on any other hint we treat the close as a commit, leave
        the file in place (it may already be at its final name thanks to
        ``QFileSystemModel.setData``), and open it as a tab.
        """
        if not self._fresh_path:
            return
        fresh = self._fresh_path
        self._fresh_path = None
        self._fresh_extension = None

        if hint == QStyledItemDelegate.RevertModelCache:
            result = file_ops.delete_item(fresh)
            if not result.success:
                logger.warning(f"Failed to clean up canceled new file: {result.error}")
            self._refresh_preserving_state()
            return
        # Commit (Enter, Tab, focus-out, etc.). The path may have been
        # updated mid-flight by ``on_file_renamed`` when the user actually
        # changed the name.
        if os.path.isfile(fresh):
            self.file_selected.emit(fresh)

    def refresh(self):
        """Refresh the file tree, preserving expansion / selection / scroll."""
        self._refresh_preserving_state()

    def _refresh_preserving_state(self, ensure_visible_path: str = "") -> None:
        """Recreate the file system model so caches are dropped, preserving UI state.

        ``QFileSystemModel`` keeps an internal per-directory listing cache
        (populated even for sub-folders that were only listed to determine
        ``hasChildren``) and invalidates it through ``QFileSystemWatcher``.
        The watcher does not fire on SMB/CIFS shares, so once a directory
        has been listed — including a freshly created empty folder whose
        listing got cached during the parent's enumeration — subsequent
        changes are invisible even after ``setRootPath`` is toggled. To
        guarantee an up-to-date view after explicit local mutations or a
        manual Refresh we therefore drop the model entirely and rebuild
        it, replaying expansion / selection / scroll from snapshots.

        Args:
            ensure_visible_path (str): Optional path that should be reachable
                after the refresh — its ancestor folders are added to the
                expansion set so a newly created or moved entry is visible
                even when its parent wasn't previously expanded.
        """
        if not self.root_path:
            return

        target_expansion = self._snapshot_expanded_paths()
        target_selection = {os.path.normpath(p) for p in self.get_selected_paths()}
        target_scroll = self.tree_view.verticalScrollBar().value()
        norm_root = os.path.normpath(self.root_path)

        if ensure_visible_path:
            ancestor = os.path.dirname(ensure_visible_path)
            while ancestor:
                norm_anc = os.path.normpath(ancestor)
                try:
                    common = os.path.commonpath([norm_anc, norm_root])
                except ValueError:
                    # Different drives — nothing more to add upwards.
                    break
                if common != norm_root:
                    break
                target_expansion.add(norm_anc)
                if norm_anc == norm_root:
                    break
                parent = os.path.dirname(ancestor)
                if parent == ancestor:
                    break
                ancestor = parent

        # Detach signals tied to the outgoing model so they don't fire mid-swap.
        old_model = self.file_model
        with contextlib.suppress(RuntimeError, TypeError):
            old_model.fileRenamed.disconnect(self.on_file_renamed)
        previous_restorer = getattr(self, "_directory_loaded_restorer", None)
        if previous_restorer is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                old_model.directoryLoaded.disconnect(previous_restorer)
        self._directory_loaded_restorer = None

        new_model = QFileSystemModel()
        new_model.setReadOnly(False)
        new_model.fileRenamed.connect(self.on_file_renamed)

        state = {"expand_remaining": set(target_expansion), "root_loaded": False}

        def on_directory_loaded(loaded_path: str) -> None:
            # ``directoryLoaded`` is queued from QFileSystemModel's worker
            # thread; by the time it fires the tree_view / proxy_model C++
            # objects may already be gone (dock workspaceControl tore down
            # while a refresh was in flight). Wrap the whole body so a stale
            # callback aborts cleanly instead of throwing into Qt's event loop.
            try:
                # Resolve the proxy index for the directory that just finished
                # loading; fall back to the view's rootIndex for the workspace
                # root because mapFromSource returns an invalid index there.
                norm_loaded = os.path.normpath(loaded_path)
                if norm_loaded == norm_root:
                    parent_proxy = self.tree_view.rootIndex()
                else:
                    parent_src = new_model.index(loaded_path)
                    parent_proxy = self.proxy_model.mapFromSource(parent_src)
                    if not parent_proxy.isValid():
                        return

                row_count = self.proxy_model.rowCount(parent_proxy)
                for row in range(row_count):
                    child_proxy = self.proxy_model.index(row, 0, parent_proxy)
                    child_src = self.proxy_model.mapToSource(child_proxy)
                    child_path = os.path.normpath(new_model.filePath(child_src))

                    if child_path in state["expand_remaining"]:
                        # Expanding triggers a fetchMore on the child which in
                        # turn re-emits directoryLoaded — that's how the restore
                        # cascades through nested folders.
                        self.tree_view.expand(child_proxy)
                        state["expand_remaining"].discard(child_path)

                    if child_path in target_selection:
                        selection_model = self.tree_view.selectionModel()
                        selection_model.select(
                            child_proxy,
                            QItemSelectionModel.Select | QItemSelectionModel.Rows,
                        )

                if norm_loaded == norm_root:
                    state["root_loaded"] = True
                    self.tree_view.verticalScrollBar().setValue(target_scroll)

                if state["root_loaded"] and not state["expand_remaining"]:
                    with contextlib.suppress(RuntimeError, TypeError):
                        new_model.directoryLoaded.disconnect(on_directory_loaded)
            except RuntimeError:
                # Underlying C++ widget/model was destroyed while we were queued —
                # nothing left to restore. Stop listening so further loads don't
                # repeat the failure.
                with contextlib.suppress(RuntimeError, TypeError):
                    new_model.directoryLoaded.disconnect(on_directory_loaded)

        self._directory_loaded_restorer = on_directory_loaded
        new_model.directoryLoaded.connect(on_directory_loaded)

        # Swap models. ``setSourceModel`` resets the proxy and clears the
        # view's selection/root, so the explicit ``setRootIndex`` below has
        # to come after ``setRootPath`` triggers initial loading.
        self.file_model = new_model
        self.proxy_model.setSourceModel(new_model)

        root_index = new_model.setRootPath(self.root_path)
        proxy_root_index = self.proxy_model.mapFromSource(root_index)
        self.tree_view.setRootIndex(proxy_root_index)

        # Defer destruction of the old model so any in-flight gatherer-thread
        # signals can drain on the (now disconnected) instance safely.
        old_model.deleteLater()

    def _snapshot_expanded_paths(self) -> set:
        """Walk the proxy tree and return normalized paths of expanded folders."""
        paths: set = set()

        def walk(parent_proxy_index):
            for row in range(self.proxy_model.rowCount(parent_proxy_index)):
                child_proxy = self.proxy_model.index(row, 0, parent_proxy_index)
                if self.tree_view.isExpanded(child_proxy):
                    child_src = self.proxy_model.mapToSource(child_proxy)
                    paths.add(os.path.normpath(self.file_model.filePath(child_src)))
                    walk(child_proxy)

        walk(self.tree_view.rootIndex())
        return paths

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

        # When the rename targets a freshly-created entry that's still mid
        # inline-create, keep the tracked path in sync so the closeEditor
        # handler can find the right file (or skip the disk-cleanup).
        if self._fresh_path and os.path.normpath(self._fresh_path) == os.path.normpath(old_full_path):
            self._fresh_path = new_full_path

        # Check if it's a file or folder and emit appropriate signal
        if os.path.isfile(new_full_path):
            self.file_renamed.emit(old_full_path, new_full_path)
            logger.info(f"File renamed: {old_name} -> {new_name}")
        elif os.path.isdir(new_full_path):
            self.folder_renamed.emit(old_full_path, new_full_path)
            logger.info(f"Folder renamed: {old_name} -> {new_name}")

    def delete_selected_items(self, anchor_global_pos=None):
        """Confirm, then delete every selected file/folder via ``file_ops``.

        Args:
            anchor_global_pos: Optional screen-space anchor for the confirmation
                dialog. Context-menu callers pass the click position; key /
                toolbar callers leave it unset and the anchor is derived from
                the first selected row so the dialog opens near the selection.
        """
        selected_paths = self.get_selected_paths()
        if not selected_paths:
            return

        if anchor_global_pos is None:
            anchor_global_pos = self._compute_selection_anchor()

        if not self._confirm_delete(selected_paths, anchor_global_pos=anchor_global_pos):
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

    def _confirm_delete(self, selected_paths: list, anchor_global_pos=None) -> bool:
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
            anchor_global_pos=anchor_global_pos,
        )
        return reply == CodeEditorMessageBox.Yes

    def _compute_selection_anchor(self):
        """Return a screen-space anchor near the first selected row, or ``None``.

        Used by the Delete shortcut and the toolbar entry point so the
        confirmation dialog still opens close to what's being deleted even
        though there's no click position to inherit.
        """
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return None
        rect = self.tree_view.visualRect(indexes[0])
        if rect.isNull():
            return None
        return self.tree_view.viewport().mapToGlobal(rect.topRight())

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

        # Refresh view, anchoring on the paste destination so it stays visible.
        self._refresh_preserving_state(ensure_visible_path=destination_path)

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

    def duplicate_item(self, source_path, destination_dir):
        """Duplicate through ``file_ops`` (Ctrl+drag) with `` copy`` naming."""
        result = file_ops.duplicate_item(source_path, destination_dir)
        if not result.success:
            name = os.path.basename(source_path)
            CodeEditorMessageBox.warning(self, "Copy Error", f"Failed to copy {name}: {result.error}")
        return result.success

    def start_drag(self, supportedActions):
        """Start drag operation with custom mime data.

        Restricted to left-button presses. ``QAbstractItemView`` will invoke
        this hook whenever its drag-distance threshold is crossed, and
        without this guard middle-click panning / right-click context-menu
        gestures could accidentally drag the selection into a sibling
        folder.
        """
        from ......lib_ui.qt_compat import QtCore, QtGui

        if not (QApplication.mouseButtons() & Qt.LeftButton):
            return

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
                    # Accept any file whose extension matches a registered language
                    if _path_has_known_extension(local_path):
                        dragged_paths.append(local_path)
            is_external_drag = True

        if not dragged_paths:
            if is_external_drag and event.mimeData().hasUrls():
                accepted = ", ".join(sorted(KNOWN_EXTENSIONS))
                logger.warning(f"Only registered source files ({accepted}) can be dropped into the explorer")
            event.ignore()
            return

        # Ctrl-held internal drag becomes a duplicate (with `` copy`` suffix)
        # instead of a move. External drags stay on the original copy path
        # so dropping foreign files keeps their original name. Any other
        # modifier (Shift, Alt, ...) is treated as a plain move — the
        # previous code path silently auto-renamed collisions to ``(1)``
        # which surprised users dropping on empty area.
        is_internal_duplicate = not is_external_drag and bool(event.keyboardModifiers() & Qt.ControlModifier)

        # Normalize for cross-separator / case-insensitive equality.
        # ``self.root_path`` is stored in OS-native form (often backslash on
        # Windows) while paths read out of ``QFileSystemModel`` use forward
        # slashes; without normalization the same-dir guard misfires when
        # the user drops on the workspace's empty area.
        norm_target = os.path.normcase(os.path.normpath(target_dir))

        # Perform the operation (move / duplicate / copy depending on the gesture)
        success_count = 0
        error_count = 0
        if is_external_drag:
            operation_name = "Copied"
        elif is_internal_duplicate:
            operation_name = "Duplicated"
        else:
            operation_name = "Moved"

        for source_path in dragged_paths:
            norm_source = os.path.normcase(os.path.normpath(source_path))
            norm_source_parent = os.path.normcase(os.path.normpath(os.path.dirname(source_path)))

            # Plain move into the same folder is a no-op; Ctrl-duplicate into
            # the same folder is the *primary* use case so we don't skip it.
            if not is_external_drag and not is_internal_duplicate and norm_source_parent == norm_target:
                continue

            # Never let a folder be copied/moved into itself or its own subtree.
            if not is_external_drag and (norm_target == norm_source or norm_target.startswith(norm_source + os.sep)):
                continue

            # For plain move (no Ctrl), refuse collisions instead of
            # auto-appending ``(N)``. Renames are explicit (F2) and copies
            # are explicit (Ctrl+drag); a drag-move that silently renames
            # the file is the exact behaviour we're trying to retire.
            if not is_external_drag and not is_internal_duplicate:
                collision_path = os.path.join(target_dir, os.path.basename(source_path))
                if os.path.exists(collision_path):
                    error_count += 1
                    logger.warning(f"Move skipped: '{os.path.basename(source_path)}' already exists in {target_dir}")
                    continue

            try:
                if is_external_drag:
                    # Copy external files
                    success = self.copy_item(source_path, target_dir)
                elif is_internal_duplicate:
                    # Ctrl+drag: duplicate with `` copy`` naming
                    success = self.duplicate_item(source_path, target_dir)
                else:
                    # Move internal files
                    success = self.move_item(source_path, target_dir)

                if success:
                    success_count += 1

                    # Emit signals for file tracking (only for internal moves)
                    if not is_external_drag and not is_internal_duplicate:
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
                if is_external_drag or is_internal_duplicate:
                    operation = "copying"
                else:
                    operation = "moving"
                logger.error(f"Error {operation} {source_path}: {e!s}")

        # Refresh the view, anchoring on the drop target so it stays visible.
        self._refresh_preserving_state(ensure_visible_path=target_dir)

        if success_count > 0:
            event.acceptProposedAction()
            logger.info(f"{operation_name} {success_count} item(s) to workspace")
            if error_count > 0:
                logger.warning(f"Failed to {operation_name.lower()} {error_count} item(s)")
        else:
            event.ignore()
