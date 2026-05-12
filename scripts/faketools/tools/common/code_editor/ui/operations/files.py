"""File-operation coordinator for the Code Editor main window.

Owns the multi-step recipes triggered by toolbar buttons, file-explorer
signals, and shortcut keys: open / save / save-all / new / rename /
delete / execute-without-opening. Each recipe wires up the same
side-effects (tab updates, recent-files list, terminal status messages)
that used to be duplicated across ``MayaCodeEditor``.

The controller holds a back-reference to the main window so it can
reach ``code_editor`` (tab widget), ``output_terminal``,
``settings_manager``, ``file_explorer``, and ``execution_manager``.
Filesystem reads/writes go through :mod:`...command.file_io` rather
than raw ``open()``.
"""

from __future__ import annotations

from logging import getLogger
import os

from ...command import file_io
from ...languages import DEFAULT_PROFILE, LanguageProfile, get_profile_for_path
from ..dialogs import CodeEditorInputDialog, CodeEditorMessageBox

logger = getLogger(__name__)


class FileOperationsController:
    """Coordinates file-related actions across editor / explorer / settings."""

    def __init__(self, main_window):
        self.main_window = main_window

    # -------------------- Open --------------------

    def open_file_permanent(self, file_path: str) -> None:
        """Open ``file_path`` in a permanent (non-preview) tab."""
        mw = self.main_window
        if not mw.code_editor:
            return

        # Promote a matching preview tab in-place if there is one.
        mw.code_editor.make_preview_permanent(file_path)

        if not mw.code_editor.open_file_permanent(file_path):
            return

        mw.settings_manager.add_recent_file(file_path)
        mw.settings_manager.save_settings()

    def open_file_preview(self, file_path: str) -> None:
        """Open ``file_path`` in a preview tab."""
        mw = self.main_window
        if not mw.code_editor:
            return

        if not mw.code_editor.open_file_preview(file_path):
            return

        mw.settings_manager.add_recent_file(file_path)
        mw.settings_manager.save_settings()

    # -------------------- Save --------------------

    def save_current_file(self) -> None:
        """Save the active tab and surface the result in the terminal."""
        mw = self.main_window
        if not mw.code_editor:
            return

        if mw.code_editor.save_current_file():
            mw.output_terminal.append_output("File saved successfully.")
            current_editor = mw.get_current_editor()
            if current_editor is not None and current_editor.file_path:
                mw.settings_manager.add_recent_file(current_editor.file_path)
        else:
            mw.output_terminal.append_output("Failed to save file.")

    def save_all_files(self) -> None:
        """Save every open tab that has a real ``file_path``."""
        mw = self.main_window
        if not mw.code_editor:
            return

        saved_count = 0
        failed_count = 0

        for i in range(mw.code_editor.count()):
            editor = mw.code_editor.widget(i)
            if getattr(editor, "is_draft", False):
                continue
            file_path = getattr(editor, "file_path", None)
            if not file_path:
                mw.output_terminal.append_output(f"Skipped untitled file in tab {i + 1}")
                continue

            content = editor.toPlainText()
            error = file_io.write_text(file_path, content)
            if error:
                failed_count += 1
                mw.output_terminal.append_output(f"Failed to save tab {i + 1}: {error}")
                continue

            saved_count += 1
            editor.is_modified = False
            editor.document().setModified(False)
            mw.code_editor.update_tab_title(editor)

        if saved_count > 0:
            mw.output_terminal.append_output(f"Saved {saved_count} file(s)")
        if failed_count > 0:
            mw.output_terminal.append_output(f"Failed to save {failed_count} file(s)")
        if saved_count == 0 and failed_count == 0:
            mw.output_terminal.append_output("No files to save")

    # -------------------- New --------------------

    def new_file(self, language: LanguageProfile = DEFAULT_PROFILE) -> None:
        """Prompt for a filename, create it in the workspace, and open it.

        Args:
            language (LanguageProfile): Profile that drives the default extension
                and dialog wording. Defaults to :data:`DEFAULT_PROFILE`, which
                is what the ``Ctrl+N`` shortcut path uses; per-language toolbar
                buttons and file-explorer menu items pass their own profile.
        """
        mw = self.main_window
        workspace_dir = mw.settings_manager.get_workspace_directory()
        if not workspace_dir or not os.path.exists(workspace_dir):
            CodeEditorMessageBox.warning(mw, "Error", "Workspace directory not found.")
            return

        ext = language.default_extension
        filename, ok = CodeEditorInputDialog.getText(
            mw,
            f"New {language.display_name} File",
            f"Enter filename (with {ext} extension):",
            text=f"new_script{ext}",
        )
        if not ok or not filename.strip():
            return

        filename = filename.strip()
        if not filename.endswith(ext):
            filename += ext

        file_path = os.path.join(workspace_dir, filename)
        if os.path.exists(file_path):
            reply = CodeEditorMessageBox.question(
                mw,
                "File Exists",
                f"File '{filename}' already exists. Do you want to overwrite it?",
                CodeEditorMessageBox.Yes | CodeEditorMessageBox.No,
                CodeEditorMessageBox.No,
            )
            if reply != CodeEditorMessageBox.Yes:
                return

        error = file_io.write_text(file_path, "")
        if error:
            CodeEditorMessageBox.critical(mw, "Error", f"Failed to create file: {error}")
            return

        if mw.file_explorer:
            mw.file_explorer.refresh()
        self.open_file_permanent(file_path)
        mw.output_terminal.append_output(f"Created new file: {filename}")

    def new_folder(self) -> None:
        """Prompt for a folder name and create it at the workspace root.

        Delegates to :meth:`FileExplorer.create_new_folder` so the dialog,
        creation, and state-preserving refresh follow the same path as the
        explorer's own context menu.
        """
        mw = self.main_window
        workspace_dir = mw.settings_manager.get_workspace_directory()
        if not workspace_dir or not os.path.exists(workspace_dir):
            CodeEditorMessageBox.warning(mw, "Error", "Workspace directory not found.")
            return
        if not mw.file_explorer:
            return
        mw.file_explorer.create_new_folder(workspace_dir, True)

    # -------------------- Rename / Delete (file_explorer signals) --------------------

    def handle_file_renamed(self, old_path: str, new_path: str) -> None:
        """Update tabs / recent-files for a renamed file."""
        mw = self.main_window
        if not mw.code_editor:
            return

        old_norm = old_path.replace("\\", "/")
        new_norm = new_path.replace("\\", "/")
        new_filename = os.path.basename(new_path)
        old_filename = os.path.basename(old_path)
        tabs_updated = 0

        for i in range(mw.code_editor.count()):
            editor = mw.code_editor.widget(i)
            editor_path = getattr(editor, "file_path", None)
            if not editor_path or editor_path.replace("\\", "/") != old_norm:
                continue

            editor.file_path = new_norm
            current_tab_text = mw.code_editor.tabText(i)
            if " (Preview)" in current_tab_text:
                mw.code_editor.setTabText(i, new_filename + " (Preview)")
            else:
                mw.code_editor.setTabText(i, new_filename)

            tabs_updated += 1

        if tabs_updated > 0:
            mw.settings_manager.update_recent_file_path(old_path, new_path)
            mw.output_terminal.append_output(f"File renamed: {old_filename} → {new_filename}")
            # Tab paths and titles changed without a focus event — persist now.
            mw.session_manager.save_session_state()

    def handle_folder_renamed(self, old_folder_path: str, new_folder_path: str) -> None:
        """Update tabs / recent-files for files inside a renamed folder."""
        mw = self.main_window
        if not mw.code_editor:
            return

        updated_count = 0
        prefix = old_folder_path + os.sep

        for i in range(mw.code_editor.count()):
            editor = mw.code_editor.widget(i)
            old_file_path = getattr(editor, "file_path", None)
            if not old_file_path or not old_file_path.startswith(prefix):
                continue

            relative_path = old_file_path[len(prefix) :]
            new_file_path = os.path.join(new_folder_path, relative_path)

            editor.file_path = new_file_path
            mw.code_editor.setTabText(i, os.path.basename(new_file_path))

            mw.settings_manager.update_recent_file_path(old_file_path, new_file_path)
            updated_count += 1

        if updated_count > 0:
            folder_name = os.path.basename(new_folder_path)
            mw.output_terminal.append_output(f"Updated {updated_count} file(s) in renamed folder: {folder_name}")
            # Tab paths changed without a focus event — persist now.
            mw.session_manager.save_session_state()

    def handle_file_deleted(self, deleted_file_path: str) -> None:
        """Close the tab matching ``deleted_file_path`` and clean up state."""
        mw = self.main_window
        if not mw.code_editor:
            return

        for i in range(mw.code_editor.count()):
            editor = mw.code_editor.widget(i)
            if getattr(editor, "file_path", None) != deleted_file_path:
                continue

            mw.code_editor.removeTab(i)

            recent_files = mw.settings_manager.get("recent_files", [])
            if deleted_file_path in recent_files:
                recent_files.remove(deleted_file_path)
                mw.settings_manager.set("recent_files", recent_files)
                mw.settings_manager.save_settings()

            filename = os.path.basename(deleted_file_path)
            mw.output_terminal.append_output(f"Closed tab for deleted file: {filename}")
            # Direct removeTab() bypasses close_tab's session save hook.
            mw.session_manager.save_session_state()
            return

    def handle_folder_deleted(self, deleted_folder_path: str) -> None:
        """Close all tabs matching files inside ``deleted_folder_path``."""
        mw = self.main_window
        if not mw.code_editor:
            return

        prefix = deleted_folder_path + os.sep
        tabs_to_remove: list[tuple[int, str]] = []
        for i in range(mw.code_editor.count()):
            editor = mw.code_editor.widget(i)
            file_path = getattr(editor, "file_path", None)
            if file_path and file_path.startswith(prefix):
                tabs_to_remove.append((i, file_path))

        if not tabs_to_remove:
            return

        # Reverse order to keep earlier indices stable while removing.
        for i, file_path in reversed(tabs_to_remove):
            mw.code_editor.removeTab(i)
            recent_files = mw.settings_manager.get("recent_files", [])
            if file_path in recent_files:
                recent_files.remove(file_path)
                mw.settings_manager.set("recent_files", recent_files)

        mw.settings_manager.save_settings()
        folder_name = os.path.basename(deleted_folder_path)
        mw.output_terminal.append_output(f"Closed {len(tabs_to_remove)} tab(s) from deleted folder: {folder_name}")
        # Direct removeTab() bypasses close_tab's session save hook.
        mw.session_manager.save_session_state()

    # -------------------- Execute without opening --------------------

    def execute_file_directly(self, file_path: str) -> None:
        """Run ``file_path`` through the execution manager without opening a tab.

        The file's own language profile (resolved from its extension) drives
        execution, so a ``foo.mel`` clicked while a Python tab is focused still
        runs through the MEL executer rather than the active tab's bridge.
        """
        mw = self.main_window
        if not os.path.exists(file_path):
            CodeEditorMessageBox.warning(mw, "File Not Found", f"File does not exist: {file_path}")
            return

        content, error = file_io.read_text(file_path)
        if content is None:
            mw.output_terminal.append_output(f"Error executing file: {error}")
            return

        file_name = os.path.basename(file_path)
        mw.output_terminal.append_output(f"\n# Executing: {file_name}")
        mw.output_terminal.append_output("-" * 40)

        if mw.execution_manager:
            mw.execution_manager.execute_code(content, language=get_profile_for_path(file_path))
