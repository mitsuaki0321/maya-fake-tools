"""
Auto-save manager for Code Editor.
Provides automatic backup and recovery functionality to prevent data loss.
"""

import json
import os
import time
from typing import Optional

from .....lib_ui.qt_compat import QObject, QTimer, Signal


class AutoSaveManager(QObject):
    """Manages automatic saving and backup recovery for unsaved files."""

    # Signals
    backup_created = Signal(str)  # Emitted when a backup is created
    backup_restored = Signal(str, str)  # Emitted when a backup is restored

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.backup_dir = self._get_backup_directory()
        self.active_files = {}  # file_path: editor_content mapping
        self.unsaved_files = {}  # temp_id: editor_content for unsaved files
        self.next_temp_id = 1

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_all)

        # Backup debounce timer (5 second fallback for network HDD performance)
        self._backup_timer = QTimer()
        self._backup_timer.setSingleShot(True)
        self._backup_timer.timeout.connect(self._flush_pending_backups)
        self._pending_backups = {}  # {file_path_or_id: (content, is_unsaved)}

        # Start auto-save if enabled
        if self.settings_manager.get("autosave.enabled", True):
            self.start_auto_save()

    def _get_backup_directory(self) -> str:
        """Get the backup directory path."""
        workspace_dir = self.settings_manager.get_workspace_directory()
        backup_dir = os.path.join(workspace_dir, ".maya_code_editor_backups")
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    def start_auto_save(self):
        """Start the auto-save timer."""
        interval = self.settings_manager.get("autosave.interval_seconds", 60) * 1000
        self.auto_save_timer.start(interval)
        print("Auto-save started with " + str(interval // 1000) + "s interval")

    def stop_auto_save(self):
        """Stop the auto-save timer."""
        self.auto_save_timer.stop()
        # print("Auto-save stopped")

    def register_file(self, file_path: str, content: str):
        """Register a file for auto-save monitoring."""
        self.active_files[file_path] = {"content": content, "last_saved": time.time(), "modified": False}

    def register_unsaved_file(self, content: str) -> str:
        """Register an unsaved file and return a temporary ID."""
        temp_id = "unsaved_" + str(self.next_temp_id)
        self.next_temp_id += 1

        self.unsaved_files[temp_id] = {"content": content, "last_saved": time.time(), "modified": False}
        return temp_id

    def update_file_content(self, file_path_or_id: str, content: str):
        """Update the content of a monitored file."""
        if file_path_or_id in self.active_files:
            old_content = self.active_files[file_path_or_id]["content"]
            if old_content != content:
                self.active_files[file_path_or_id]["content"] = content
                self.active_files[file_path_or_id]["modified"] = True

                # Schedule backup on change if enabled (debounced for network HDD performance)
                if self.settings_manager.get("autosave.backup_on_change", True):
                    self._schedule_backup(file_path_or_id, content, is_unsaved=False)

        elif file_path_or_id in self.unsaved_files:
            old_content = self.unsaved_files[file_path_or_id]["content"]
            if old_content != content:
                self.unsaved_files[file_path_or_id]["content"] = content
                self.unsaved_files[file_path_or_id]["modified"] = True

                # Schedule backup for unsaved file (debounced for network HDD performance)
                if self.settings_manager.get("autosave.backup_on_change", True):
                    self._schedule_backup(file_path_or_id, content, is_unsaved=True)

    def unregister_file(self, file_path_or_id: str):
        """Unregister a file from auto-save monitoring."""
        if file_path_or_id in self.active_files:
            del self.active_files[file_path_or_id]
        elif file_path_or_id in self.unsaved_files:
            del self.unsaved_files[file_path_or_id]
        # Also remove from pending backups
        if file_path_or_id in self._pending_backups:
            del self._pending_backups[file_path_or_id]

    def _schedule_backup(self, file_path_or_id: str, content: str, is_unsaved: bool = False):
        """Schedule a backup with 5-second fallback timer.

        This debounces backup writes to improve performance on network HDDs.
        Backups are written when:
        - 5 seconds pass without new changes (fallback timer)
        - Focus leaves the editor (flush_backups called)
        - Editor is closed (flush_backups called)
        """
        self._pending_backups[file_path_or_id] = (content, is_unsaved)
        self._backup_timer.stop()
        self._backup_timer.start(5000)  # 5 second fallback

    def _flush_pending_backups(self):
        """Write all pending backups to disk."""
        for file_path_or_id, (content, is_unsaved) in self._pending_backups.items():
            self._create_backup(file_path_or_id, content, is_unsaved=is_unsaved)
        self._pending_backups.clear()

    def flush_backups(self):
        """Flush pending backups immediately.

        Called on focus out or shutdown to ensure data is saved.
        """
        self._backup_timer.stop()
        self._flush_pending_backups()

    def auto_save_all(self):
        """Auto-save all monitored files."""
        saved_count = 0

        # Save regular files
        for file_path, file_info in self.active_files.items():
            if file_info["modified"] and self._create_backup(file_path, file_info["content"]):
                file_info["modified"] = False
                file_info["last_saved"] = time.time()
                saved_count += 1

        # Save unsaved files
        for temp_id, file_info in self.unsaved_files.items():
            if file_info["modified"] and self._create_backup(temp_id, file_info["content"], is_unsaved=True):
                file_info["modified"] = False
                file_info["last_saved"] = time.time()
                saved_count += 1

        if saved_count > 0:
            print("Auto-saved " + str(saved_count) + " file(s)")

    def _create_backup(self, file_path_or_id: str, content: str, is_unsaved: bool = False) -> bool:
        """Create a backup file."""
        try:
            # Generate backup filename (single file per tab, overwrites previous backup)
            if is_unsaved:
                backup_name = file_path_or_id + ".py.bak"
            else:
                file_name = os.path.basename(file_path_or_id)
                name, ext = os.path.splitext(file_name)
                backup_name = name + ext + ".bak"

            backup_path = os.path.join(self.backup_dir, backup_name)

            # Remove old backup if it exists
            if os.path.exists(backup_path):
                os.remove(backup_path)

            # Save backup file
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Save metadata
            self._save_backup_metadata(backup_name, file_path_or_id, is_unsaved)

            # No cleanup needed since we overwrite the single backup file

            self.backup_created.emit(backup_path)
            return True

        except OSError as e:
            print("Failed to create backup: " + str(e))
            return False

    def _save_backup_metadata(self, backup_name: str, original_path: str, is_unsaved: bool):
        """Save metadata about the backup."""
        metadata_file = os.path.join(self.backup_dir, "backup_metadata.json")

        # Load existing metadata
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        # Add new backup info
        metadata[backup_name] = {
            "original_path": original_path,
            "is_unsaved": is_unsaved,
            "created_time": int(time.time()),
            "readable_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Save updated metadata
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception:
            pass

    def _cleanup_old_backups(self, file_path_or_id: str):
        """Remove old backup files beyond the limit."""
        # No longer needed - we only keep one backup file per tab

    def get_available_backups(self) -> list[dict]:
        """Get list of available backups for recovery."""
        backups = []
        metadata_file = os.path.join(self.backup_dir, "backup_metadata.json")

        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        for filename in os.listdir(self.backup_dir):
            if filename.endswith(".bak"):
                backup_path = os.path.join(self.backup_dir, filename)
                if os.path.exists(backup_path):
                    backup_info = {
                        "filename": filename,
                        "path": backup_path,
                        "size": os.path.getsize(backup_path),
                        "modified_time": os.path.getmtime(backup_path),
                    }

                    # Add metadata if available
                    if filename in metadata:
                        backup_info.update(metadata[filename])

                    backups.append(backup_info)

        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x["modified_time"], reverse=True)
        return backups

    def restore_backup(self, backup_path: str) -> Optional[str]:
        """Restore content from a backup file."""
        try:
            with open(backup_path, encoding="utf-8") as f:
                content = f.read()

            self.backup_restored.emit(backup_path, content)
            return content

        except OSError as e:
            print("Failed to restore backup: " + str(e))
            return None
