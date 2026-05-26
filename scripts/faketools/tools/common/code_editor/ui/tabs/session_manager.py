"""
Session management for Code Editor UI.
Handles saving and restoring session state including open tabs and their content.
"""

from logging import getLogger
import os

from ...languages import DEFAULT_PROFILE, get_profile_for_path

logger = getLogger(__name__)


class UISessionManager:
    """Saves and restores tab state (open tabs and their content) via session.json."""

    def __init__(self, main_window):
        """Initialize session manager with reference to main window.

        Args:
            main_window: The main MayaCodeEditor window instance
        """
        self.main_window = main_window
        # Re-entrancy guard: ``restore_session_state`` calls ``new_file`` /
        # ``open_file_preview``, which themselves trigger ``save_session_state``
        # via the tab-state hooks. Saving mid-restore would freeze a partially
        # populated tab into session.json. The flag suppresses those nested
        # saves; restore explicitly fires one save at the end.
        self._restoring = False

    @property
    def code_editor(self):
        """Get code editor from main window."""
        return self.main_window.code_editor

    @property
    def settings_manager(self):
        """Get settings manager from main window."""
        return self.main_window.settings_manager

    def save_session_state(self):
        """Save current session state (open tabs).

        Tolerant of the window being partially torn down: Qt can fire this
        save after the underlying C++ widget has already been deleted (Maya
        workspace close, tool reload). Swallow the resulting ``RuntimeError``
        rather than spam the Script Editor — there's nothing left to persist
        at that point anyway.
        """
        if self._restoring:
            return
        if not self.code_editor:
            return

        try:
            open_tabs = []
            draft_content = ""  # Save Draft tab content separately

            for i in range(self.code_editor.count()):
                editor = self.code_editor.widget(i)
                if editor:
                    tab_name = self.code_editor.tabText(i)
                    file_path = getattr(editor, "file_path", None)

                    # Save Draft tab content separately
                    if hasattr(editor, "is_draft") and editor.is_draft:
                        draft_content = editor.toPlainText()
                        continue

                    # Skip snippet preview tabs (but keep file preview tabs)
                    # Check if it's a snippet preview (no file_path) or file preview (has file_path)
                    if hasattr(editor, "is_preview") and editor.is_preview and not file_path:
                        # This is a snippet preview tab, skip it
                        continue
                    # If it has a file_path, it's a file preview tab, continue to save it

                    tab_info = self.settings_manager.create_tab_info(
                        file_path=file_path,
                        content=editor.toPlainText(),
                        cursor_position=editor.textCursor().position(),
                        is_modified=getattr(editor, "is_modified", False),
                        tab_name=tab_name,
                    )
                    open_tabs.append(tab_info)
        except RuntimeError:
            # Underlying QWidget was deleted mid-save; drop this save quietly.
            return

        # Save session and draft content
        self.settings_manager.save_session_state(open_tabs)
        self.settings_manager.set("draft_content", draft_content)
        self.settings_manager.save_settings()
        logger.debug("session saved: %d tab(s), draft=%d chars", len(open_tabs), len(draft_content))

    def restore_session_state(self):
        """Restore session state (open tabs)."""
        if not self.code_editor:
            return

        self._restoring = True
        try:
            # Always restore Draft tab content regardless of session settings
            self._restore_draft_content()

            if not self.settings_manager.should_restore_session():
                return

            saved_tabs = self.settings_manager.get_session_state()
            if not saved_tabs:
                return

            # Clear default empty tab if it exists (but keep Draft tab)
            if self.code_editor.count() == 1:
                editor = self.code_editor.widget(0)
                if (
                    editor
                    and not getattr(editor, "file_path", None)
                    and not editor.toPlainText().strip()
                    and not (hasattr(editor, "is_draft") and editor.is_draft)
                ):
                    self.code_editor.removeTab(0)
                    # removeTab doesn't delete the page widget; free it so the
                    # discarded empty tab doesn't leak for the session.
                    if hasattr(editor, "shutdown"):
                        editor.shutdown()
                    editor.deleteLater()

            # Check for preview tabs and ensure only one is restored
            preview_tabs = [tab for tab in saved_tabs if tab.get("tab_name", "").startswith("[Preview]") or " (Preview)" in tab.get("tab_name", "")]
            non_preview_tabs = [tab for tab in saved_tabs if tab not in preview_tabs]

            # Restore non-preview tabs first
            for tab_info in non_preview_tabs:
                self.restore_tab(tab_info)

            # Restore only the last preview tab (if any)
            if preview_tabs:
                self.restore_tab(preview_tabs[-1])

            # Ensure we have at least a Draft tab
            if self.code_editor.count() == 0:
                self.code_editor.new_file(is_draft=True)
        finally:
            self._restoring = False

        # One explicit save so session.json reflects the final restored state.
        self.save_session_state()

    def _restore_draft_content(self):
        """Restore Draft tab content."""
        draft_content = self.settings_manager.get("draft_content", "")
        if not draft_content:
            return

        # Check if code_editor is available
        if not self.code_editor:
            return

        # Find the Draft tab and restore its content
        for i in range(self.code_editor.count()):
            editor = self.code_editor.widget(i)
            if hasattr(editor, "is_draft") and editor.is_draft:
                editor.setPlainText(draft_content)
                break

    def restore_tab(self, tab_info: dict):
        """Restore a single tab from saved information."""
        file_path = tab_info.get("file_path")
        saved_content = tab_info.get("content", "")
        cursor_position = tab_info.get("cursor_position", 0)
        tab_name = tab_info.get("tab_name", f"Untitled{DEFAULT_PROFILE.default_extension}")

        # Check if this is a file preview tab (from explorer)
        is_file_preview = tab_name.startswith("[Preview]") and file_path

        if is_file_preview:
            # Restore as file preview tab
            if file_path and os.path.exists(file_path):
                self.code_editor.open_file_preview(file_path)
                # The preview tab is already created and content loaded
                # Just restore cursor position
                editor = self.code_editor.widget(self.code_editor.currentIndex())
                if editor:
                    try:
                        cursor = editor.textCursor()
                        cursor.setPosition(min(cursor_position, len(saved_content)))
                        editor.setTextCursor(cursor)
                    except Exception:
                        pass
            return

        # Determine if tab should be marked as modified
        is_modified = self.determine_tab_modified_state(file_path, saved_content)

        # Create new editor bound to the file's language. ``new_file`` creates
        # the editor with the default profile; restored ``.mel`` tabs would
        # otherwise dispatch Run / placeholder / highlighter to Python.
        language = get_profile_for_path(file_path) if file_path else DEFAULT_PROFILE
        editor = self.code_editor.new_file(language=language)

        # Set content
        editor.setPlainText(saved_content)

        # Set file path if it exists
        if file_path and os.path.exists(file_path):
            editor.file_path = file_path
        elif file_path:
            # File doesn't exist - mark as modified
            editor.file_path = file_path
            is_modified = True

        # Set modified state
        editor.is_modified = is_modified

        # Set tab name
        tab_index = self.code_editor.indexOf(editor)
        self.code_editor.setTabText(tab_index, tab_name)

        # Restore cursor position
        try:
            cursor = editor.textCursor()
            cursor.setPosition(min(cursor_position, len(saved_content)))
            editor.setTextCursor(cursor)
        except Exception:
            pass  # Ignore cursor position errors

    def determine_tab_modified_state(self, file_path: str, saved_content: str) -> bool:
        """Determine if tab should be marked as modified based on file content comparison."""
        if not file_path or not os.path.exists(file_path):
            # File doesn't exist - mark as modified (unsaved)
            return True

        try:
            with open(file_path, encoding="utf-8") as f:
                disk_content = f.read()

            # Compare content
            return disk_content != saved_content
        except Exception:
            # Error reading file - mark as modified
            return True
