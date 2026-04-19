"""
Tabbed container that hosts one ``PythonEditor`` per open file.

Split from ``code_editor.py`` so the editor widget and the tab widget can be
read independently. The tab widget owns preview-tab lifecycle, session
persistence hooks, and the cross-tab actions (save, close, word-wrap toggle).
"""

from __future__ import annotations

import contextlib
from logging import getLogger
import os

from .....lib_ui.qt_compat import (
    QColor,
    QFileDialog,
    Qt,
    QTabWidget,
    QTextCharFormat,
    QTextCursor,  # noqa: F401 — re-exported historically; kept for downstream compat
    QTextEdit,
    QTimer,
    Signal,
)
from ..themes import AppTheme
from .code_editor import PythonEditor
from .dialog_base import CodeEditorMessageBox
from .tab_bar import EditableTabBar

logger = getLogger(__name__)


class CodeEditorWidget(QTabWidget):
    """Tabbed code editor widget."""

    inspect_object = Signal(str, str)  # (object_name, inspection_type)
    textChanged = Signal()  # Emitted when any tab's text changes

    def __init__(self, parent=None):
        super().__init__(parent)

        self.untitled_counter = 1
        self.preview_tab_index = -1  # Index of current preview tab (-1 if none)
        self.preview_tab_editor = None
        self._word_wrap_enabled = True  # Word wrap ON by default
        self._autocomplete_enabled = True  # Matches settings default; MainWindow overrides at startup

        self.custom_tab_bar = EditableTabBar()
        self.setTabBar(self.custom_tab_bar)

        self.init_ui()
        self.connect_signals()
        self.apply_close_button_styles()

        self.currentChanged.connect(self.update_active_tab_styling)

        self.setup_middle_click_close()

        # Create initial Draft tab so the editor is never empty.
        self.new_file(is_draft=True)

    def wheelEvent(self, event):
        """Forward wheel events to current editor (font-size zoom with Ctrl)."""
        current_editor = self.currentWidget()
        if current_editor and hasattr(current_editor, "wheelEvent"):
            current_editor.wheelEvent(event)
        else:
            super().wheelEvent(event)

    def init_ui(self):
        self.setTabsClosable(False)  # Disable default close buttons (we draw our own)
        self.setMovable(True)
        self.setDocumentMode(True)

    def connect_signals(self):
        self.tabCloseRequested.connect(self.close_tab)

    def new_file(self, is_draft=False) -> PythonEditor:
        """Create a new file tab (or the Draft tab on first launch)."""
        editor = PythonEditor(self)

        if is_draft:
            tab_name = "Draft"
            editor.is_draft = True
            editor.is_modified = False
        else:
            tab_name = f"Untitled{self.untitled_counter}.py"
            self.untitled_counter += 1
            editor.is_draft = False
            editor.is_modified = True

        editor.is_preview = False

        index = self.addTab(editor, tab_name)
        self.setCurrentIndex(index)

        self.apply_editor_theme(editor)
        editor.set_word_wrap(self._word_wrap_enabled)
        self._apply_autocomplete(editor)

        editor.textChanged.connect(lambda: self.update_tab_title(editor))
        editor.textChanged.connect(self.textChanged.emit)
        editor.inspect_object.connect(self.inspect_object.emit)

        QTimer.singleShot(0, self.update_active_tab_styling)
        QTimer.singleShot(100, self.save_session_if_available)

        return editor

    def open_preview(self, content: str, title: str = "Preview") -> PythonEditor:
        """Open ``content`` in a preview tab, reusing the existing one if present."""
        if self.preview_tab_index >= 0 and self.preview_tab_index < self.count():
            editor = self.widget(self.preview_tab_index)
            if editor and hasattr(editor, "is_preview") and editor.is_preview:
                # Temporarily drop listeners so the setPlainText doesn't flip
                # the modified flag and convert the tab to a regular one.
                with contextlib.suppress(Exception):
                    editor.textChanged.disconnect()

                editor.setPlainText(content)
                editor.is_modified = False
                editor.document().setModified(False)
                editor.preview_title = title
                self.setTabText(self.preview_tab_index, f"[Preview] {title}")
                self.setCurrentIndex(self.preview_tab_index)

                editor.textChanged.connect(lambda: self.on_preview_text_changed(editor))
                editor.textChanged.connect(self.textChanged.emit)

                return editor

        editor = PythonEditor(self)
        editor.is_preview = True
        editor.is_modified = False
        editor.preview_title = title

        tab_title = f"[Preview] {title}"
        index = self.addTab(editor, tab_title)

        editor.setPlainText(content)
        editor.is_modified = False
        editor.document().setModified(False)

        self.preview_tab_index = index
        self.preview_tab_editor = editor
        self.setCurrentIndex(index)

        self.apply_editor_theme(editor)
        editor.set_word_wrap(self._word_wrap_enabled)
        self._apply_autocomplete(editor)

        editor.textChanged.connect(lambda: self.on_preview_text_changed(editor))
        editor.textChanged.connect(self.textChanged.emit)
        editor.inspect_object.connect(self.inspect_object.emit)

        self.style_preview_tab(index)

        # Preview tabs are intentionally excluded from session persistence.
        return editor

    def style_preview_tab(self, index):
        """Apply italic styling to preview tab (no-op: caused Maya crashes)."""

    def on_preview_text_changed(self, editor):
        """If the user edits a preview tab, promote it to a regular tab."""
        if hasattr(editor, "is_preview") and editor.is_preview and editor.is_modified:
            self.convert_preview_to_regular(editor)

    def convert_preview_to_regular(self, editor):
        """Strip the preview marker and start saving this tab in the session."""
        if not hasattr(editor, "is_preview") or not editor.is_preview:
            return

        editor.is_preview = False
        index = self.indexOf(editor)
        if index < 0:
            return

        title = editor.preview_title if hasattr(editor, "preview_title") else "Untitled"
        if not title.endswith(".py"):
            title = f"{title}.py"
        if index == self.currentIndex():
            self.setTabText(index, f"● {title}")
        else:
            self.setTabText(index, title)

        if index == self.preview_tab_index:
            self.preview_tab_index = -1
            self.preview_tab_editor = None

        if hasattr(self.custom_tab_bar, "set_preview_tab"):
            self.custom_tab_bar.set_preview_tab(index, False)

        QTimer.singleShot(100, self.save_session_if_available)

    def set_word_wrap_all(self, enabled):
        """Push ``enabled`` to every open editor tab."""
        self._word_wrap_enabled = enabled
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor):
                editor.set_word_wrap(enabled)

    def set_autocomplete_enabled(self, enabled: bool):
        """Broadcast the autocomplete toggle to every open editor tab.

        Stored on the widget so tabs created later (preview / permanent / new)
        inherit the current choice without the caller having to re-apply.
        """
        self._autocomplete_enabled = enabled
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor) and getattr(editor, "autocomplete", None) is not None:
                editor.autocomplete.set_enabled(enabled)

    def _apply_autocomplete(self, editor):
        """Apply the current autocomplete flag to a freshly-created tab."""
        if getattr(editor, "autocomplete", None) is not None:
            editor.autocomplete.set_enabled(self._autocomplete_enabled)

    def apply_editor_theme(self, editor):
        """Apply theme styling + current-line highlight to ``editor``."""
        editor.setStyleSheet(AppTheme.get_editor_stylesheet())

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(AppTheme.CURRENT_LINE))
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        selection.cursor = editor.textCursor()
        selection.cursor.clearSelection()
        editor.setExtraSelections([selection])

    def open_file_permanent(self, file_path: str):
        """Open ``file_path`` in a permanent tab, or refocus an existing one."""
        file_path = os.path.normpath(os.path.abspath(file_path)).replace("\\", "/")

        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor) and editor.file_path:
                existing_path = os.path.normpath(os.path.abspath(editor.file_path)).replace("\\", "/")
                if existing_path == file_path:
                    # Promote preview tab to permanent if this file was previewed.
                    if i == self.preview_tab_index:
                        tab_text = self.tabText(i)
                        if tab_text.endswith(" (Preview)"):
                            self.setTabText(i, tab_text.replace(" (Preview)", ""))
                            self.preview_tab_index = -1
                    self.setCurrentIndex(i)
                    return True

        editor = PythonEditor(self)
        if not editor.load_file(file_path):
            return False

        file_name = os.path.basename(file_path)
        index = self.addTab(editor, file_name)
        self.setCurrentIndex(index)

        self.apply_editor_theme(editor)
        editor.set_word_wrap(self._word_wrap_enabled)
        self._apply_autocomplete(editor)

        editor.textChanged.connect(lambda: self.update_tab_title(editor))
        editor.textChanged.connect(self.textChanged.emit)
        editor.inspect_object.connect(self.inspect_object.emit)

        QTimer.singleShot(0, self.update_active_tab_styling)
        QTimer.singleShot(100, self.save_session_if_available)
        return True

    def open_file_preview(self, file_path: str):
        """Open ``file_path`` in a preview tab, replacing any existing preview."""
        file_path = os.path.normpath(os.path.abspath(file_path)).replace("\\", "/")

        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, PythonEditor) and editor.file_path:
                existing_path = os.path.normpath(os.path.abspath(editor.file_path)).replace("\\", "/")
                if existing_path == file_path:
                    # Already open — just focus it (no duplicate preview).
                    self.setCurrentIndex(i)
                    return True

        # Find an existing preview tab by title; the stored index might be stale
        # after tab moves, so we scan tab texts.
        existing_preview_index = -1
        for i in range(self.count()):
            tab_text = self.tabText(i)
            if " (Preview)" in tab_text or tab_text.startswith("[Preview]"):
                existing_preview_index = i
                break

        if existing_preview_index >= 0:
            preview_editor = self.widget(existing_preview_index)
            if preview_editor and preview_editor.load_file(file_path):
                file_name = os.path.basename(file_path)
                self.setTabText(existing_preview_index, file_name + " (Preview)")
                self.setCurrentIndex(existing_preview_index)
                self.preview_tab_index = existing_preview_index
                QTimer.singleShot(100, self.save_session_if_available)
                return True

        editor = PythonEditor(self)
        if not editor.load_file(file_path):
            return False

        file_name = os.path.basename(file_path)
        index = self.addTab(editor, file_name + " (Preview)")
        self.preview_tab_index = index
        self.setCurrentIndex(index)

        self.apply_editor_theme(editor)
        editor.set_word_wrap(self._word_wrap_enabled)
        self._apply_autocomplete(editor)

        editor.textChanged.connect(lambda: self.update_tab_title(editor))
        editor.textChanged.connect(self.textChanged.emit)
        editor.inspect_object.connect(self.inspect_object.emit)

        QTimer.singleShot(0, self.update_active_tab_styling)
        QTimer.singleShot(100, self.save_session_if_available)
        return True

    def make_preview_permanent(self, file_path: str = None):
        """Strip ``(Preview)`` from the current preview tab's title."""
        if self.preview_tab_index < 0 or self.preview_tab_index >= self.count():
            return False

        editor = self.widget(self.preview_tab_index)
        if not (editor and isinstance(editor, PythonEditor)):
            return False

        current_text = self.tabText(self.preview_tab_index)
        if current_text.endswith(" (Preview)"):
            self.setTabText(self.preview_tab_index, current_text.replace(" (Preview)", ""))

        self.preview_tab_index = -1
        QTimer.singleShot(100, self.save_session_if_available)
        return True

    def apply_close_button_styles(self):
        """Apply basic tab styling (kept Maya-safe: no custom paintEvent)."""
        try:
            tab_style = """
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #242424;
                }

                QTabBar {
                    background-color: #242424;
                    padding-top: 4px;
                    border-bottom: 1px solid #0a0a0a;
                }

                QTabWidget::tab-bar {
                    background-color: #242424;
                }

                QTabBar::tab {
                    background-color: #242424;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                    padding: 8px 16px 8px 16px;
                    margin-right: 2px;
                    margin-top: 0px;
                }

                QTabBar::tab:selected {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border-top: 2px solid #0078d4;
                }

                QTabBar::tab:hover:!selected {
                    background-color: #2a2a2a;
                }

            """
            self.setStyleSheet(tab_style)
        except Exception as e:
            logger.error(f"Error applying tab styles - {e}")

    def update_active_tab_styling(self):
        """Prefix the active tab title with ● (skip preview tabs, which self-style)."""
        try:
            if self.count() == 0:
                return

            current_index = self.currentIndex()
            for i in range(self.count()):
                text = self.tabText(i)
                editor = self.widget(i)
                is_preview = hasattr(editor, "is_preview") and editor.is_preview
                if is_preview:
                    continue

                if i == current_index:
                    if not text.startswith("● "):
                        text = f"● {text}"
                else:
                    text = text.removeprefix("● ")
                self.setTabText(i, text)

        except Exception as e:
            logger.error(f"Error updating active tab styling - {e}")

    def setup_middle_click_close(self):
        """Install an event filter so middle-click on a tab closes it."""
        try:
            self.tabBar().installEventFilter(self)
        except Exception as e:
            logger.error(f"Failed to setup middle-click close - {e}")

    def eventFilter(self, obj, event):
        """Middle-click on the tab bar → close the hovered tab."""
        try:
            if obj == self.tabBar() and hasattr(event, "type"):
                from .....lib_ui.qt_compat import QtCore

                if event.type() == QtCore.QEvent.MouseButtonPress and hasattr(event, "button") and event.button() == Qt.MiddleButton:
                    tab_index = self.tabBar().tabAt(event.pos())
                    if tab_index >= 0:
                        self.close_tab(tab_index)
                        return True
            return super().eventFilter(obj, event)
        except Exception as e:
            logger.error(f"Event filter error - {e}")
            return super().eventFilter(obj, event)

    def close_current_tab(self):
        current_index = self.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def save_current_file(self) -> bool:
        """Save the active editor, prompting for a destination if untitled."""
        editor = self.currentWidget()
        if not isinstance(editor, PythonEditor):
            return False

        if hasattr(editor, "is_draft") and editor.is_draft:
            CodeEditorMessageBox.information(self, "Cannot Save Draft", "The Draft tab cannot be saved to file.")
            return False

        if editor.file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py)")
            if not file_path:
                return False
        elif not os.path.exists(editor.file_path):
            # File path remembered but the file itself was removed — recreate, or
            # fall back to Save As if the parent dir is also gone.
            file_path = editor.file_path
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except OSError:
                    file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", editor.file_path, "Python Files (*.py)")
                    if not file_path:
                        return False
        else:
            file_path = editor.file_path

        success = editor.save_file(file_path)
        if success:
            self.update_tab_title(editor)
            QTimer.singleShot(100, self.save_session_if_available)
        return success

    def get_current_code(self) -> str:
        editor = self.currentWidget()
        if isinstance(editor, PythonEditor):
            return editor.toPlainText()
        return ""

    def close_tab(self, index: int):
        """Close ``index`` after prompting if there are unsaved changes."""
        editor = self.widget(index)
        if not isinstance(editor, PythonEditor):
            return

        if hasattr(editor, "is_draft") and editor.is_draft:
            CodeEditorMessageBox.warning(
                self,
                "Draft Tab",
                "The Draft tab cannot be closed.\n\nThis is a permanent workspace for temporary code.",
            )
            return

        if editor.is_modified:
            file_name = editor.get_display_name().rstrip("*")
            reply = CodeEditorMessageBox.question(
                self,
                "Unsaved Changes",
                f"'{file_name}' has unsaved changes. Save before closing?",
                CodeEditorMessageBox.Yes | CodeEditorMessageBox.No | CodeEditorMessageBox.Cancel,
            )

            if reply == CodeEditorMessageBox.Yes:
                if not self.save_file_at_index(index):
                    return
            elif reply == CodeEditorMessageBox.Cancel:
                return

        self.removeTab(index)

        QTimer.singleShot(0, self.update_active_tab_styling)
        QTimer.singleShot(100, self.save_session_if_available)

        # Never leave the editor empty — spawn a Draft tab if everything is gone.
        if self.count() == 0:
            self.new_file(is_draft=True)

    def save_file_at_index(self, index: int) -> bool:
        """Save the tab at ``index`` while preserving the user's active tab."""
        current_index = self.currentIndex()
        self.setCurrentIndex(index)
        success = self.save_current_file()
        self.setCurrentIndex(current_index)
        return success

    def update_tab_title(self, editor: PythonEditor):
        """Refresh the tab text for ``editor`` (skip preview tabs)."""
        if hasattr(editor, "is_preview") and editor.is_preview:
            return

        for i in range(self.count()):
            if self.widget(i) == editor:
                self.setTabText(i, editor.get_display_name())
                break

    def save_session_if_available(self):
        """Walk up the parent chain and trigger the main window's session save."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "save_session_state"):
                parent.save_session_state()
                break
            parent = parent.parent()

    def get_current_editor(self):
        return self.currentWidget()

    def get_current_file_path(self):
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, "file_path"):
            return current_editor.file_path
        return None
