"""
Editor shortcuts management for Maya Code Editor.
Provides a clean, extensible way to manage keyboard shortcuts in the code editor.
"""

from .....lib_ui.qt_compat import QKeySequence, Qt


class EditorShortcuts:
    """Manages keyboard shortcuts for the code editor."""

    def __init__(self):
        """Initialize the shortcut mappings."""
        # Define shortcut mappings
        # Format: key -> method_name (str) or None (delegate to parent)
        self.shortcuts = {
            # Basic editing keys
            Qt.Key_Return: "handle_return_key",
            Qt.Key_Enter: "handle_return_key",
            Qt.Key_Tab: "handle_tab_key",
            Qt.Key_Backtab: "handle_backtab_key",
            Qt.Key_Backspace: "handle_backspace_key",
            # Standard shortcuts (delegate to parent)
            QKeySequence.SelectAll: None,  # Ctrl+A
            QKeySequence.Copy: None,  # Ctrl+C
            QKeySequence.Paste: None,  # Ctrl+V
            QKeySequence.Cut: None,  # Ctrl+X
            QKeySequence.Undo: None,  # Ctrl+Z
            QKeySequence.Redo: None,  # Ctrl+Y
        }

        # String-based shortcuts for custom key combinations
        self.string_shortcuts = {
            # Example shortcuts - developers can easily add more here
            "Ctrl+D": "select_next_occurrence",
            "Ctrl+Shift+D": "duplicate_current_line",  # Moved from Ctrl+D
            "Ctrl+Shift+K": "delete_current_line",
            "Ctrl+Shift+Up": "move_line_up",
            "Ctrl+Shift+Down": "move_line_down",
            "Ctrl+L": "select_current_line",
        }

    def handle_key_event(self, event, editor):
        """
        Handle a key event using the shortcut mappings.

        Args:
            event: QKeyEvent
            editor: PythonEditor instance

        Returns:
            bool: True if event was handled, False otherwise
        """
        # First check direct key mappings
        key = event.key()
        if key in self.shortcuts:
            method_name = self.shortcuts[key]
            if method_name is None:
                # Delegate to parent class
                editor.QPlainTextEdit.keyPressEvent(editor, event)
                return True
            else:
                # Call the specified method
                if hasattr(editor, method_name):
                    getattr(editor, method_name)()
                    return True

        # Check standard shortcuts (Ctrl+C, Ctrl+V, etc.)
        for shortcut_key, method_name in self.shortcuts.items():
            if hasattr(shortcut_key, "matches") and event.matches(shortcut_key):
                if method_name is None:
                    # Delegate to parent class
                    editor.QPlainTextEdit.keyPressEvent(editor, event)
                    return True
                else:
                    # Call the specified method
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)()
                        return True

        # Check string-based shortcuts
        key_combo = self._get_key_combination(event)
        if key_combo in self.string_shortcuts:
            method_name = self.string_shortcuts[key_combo]
            if hasattr(editor, method_name):
                getattr(editor, method_name)()
                return True

        # Event not handled
        return False

    def _get_key_combination(self, event):
        """
        Convert QKeyEvent to string representation.

        Args:
            event: QKeyEvent

        Returns:
            str: String representation like 'Ctrl+D', 'Ctrl+Shift+K'
        """
        modifiers = []

        if event.modifiers() & Qt.ControlModifier:
            modifiers.append("Ctrl")
        if event.modifiers() & Qt.ShiftModifier:
            modifiers.append("Shift")
        if event.modifiers() & Qt.AltModifier:
            modifiers.append("Alt")
        if event.modifiers() & Qt.MetaModifier:
            modifiers.append("Meta")

        # Get key name
        key = event.key()
        key_name = None

        # Handle special keys
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            key_name = "Return"
        elif key == Qt.Key_Tab:
            key_name = "Tab"
        elif key == Qt.Key_Backspace:
            key_name = "Backspace"
        elif key == Qt.Key_Delete:
            key_name = "Delete"
        elif key == Qt.Key_Up:
            key_name = "Up"
        elif key == Qt.Key_Down:
            key_name = "Down"
        elif key == Qt.Key_Left:
            key_name = "Left"
        elif key == Qt.Key_Right:
            key_name = "Right"
        elif key >= Qt.Key_A and key <= Qt.Key_Z:
            # Letter keys
            key_name = chr(key)
        elif key >= Qt.Key_0 and key <= Qt.Key_9:
            # Number keys
            key_name = chr(key)
        else:
            # Other keys - convert to string
            key_name = f"Key_{key}"

        if key_name:
            if modifiers:
                return "+".join(modifiers + [key_name])
            else:
                return key_name

        return None

    def add_shortcut(self, key, method_name):
        """
        Add a new shortcut mapping.

        Args:
            key: Qt key constant or string (e.g., 'Ctrl+D')
            method_name: Name of method to call, or None to delegate to parent
        """
        if isinstance(key, str):
            self.string_shortcuts[key] = method_name
        else:
            self.shortcuts[key] = method_name

    def remove_shortcut(self, key):
        """
        Remove a shortcut mapping.

        Args:
            key: Qt key constant or string
        """
        if isinstance(key, str):
            self.string_shortcuts.pop(key, None)
        else:
            self.shortcuts.pop(key, None)

    def get_all_shortcuts(self):
        """
        Get all defined shortcuts.

        Returns:
            dict: All shortcuts with their descriptions
        """
        all_shortcuts = {}

        # Add Qt key shortcuts
        for key, method in self.shortcuts.items():
            if hasattr(key, "toString"):
                key_str = key.toString()
            else:
                key_str = f"Key_{key}"
            all_shortcuts[key_str] = method

        # Add string shortcuts
        all_shortcuts.update(self.string_shortcuts)

        return all_shortcuts
