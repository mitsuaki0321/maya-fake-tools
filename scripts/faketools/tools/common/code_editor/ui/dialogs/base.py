"""
Base dialog classes for Code Editor.
Provides centralized dialog positioning and styling for consistent UX.
"""

from ......lib_ui.qt_compat import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox


class DialogPositioner:
    """Utility class for positioning dialogs relative to the code editor."""

    @staticmethod
    def get_code_editor_parent():
        """Get the main code editor window for dialog positioning."""
        # Try to find the main Code Editor window
        app = QApplication.instance()
        if not app:
            return None

        for widget in app.allWidgets():
            if hasattr(widget, "__class__") and "MayaCodeEditor" in widget.__class__.__name__:
                return widget
        return None

    # Visual offset from an anchor point so the dialog opens just below-right of
    # the trigger (a context-menu pick or a row's edge) rather than under the
    # cursor, which would obscure the item the user is acting on.
    _ANCHOR_OFFSET_X = 12
    _ANCHOR_OFFSET_Y = 12

    @staticmethod
    def position_dialog(dialog, parent_widget=None, anchor_global_pos=None):
        """Place dialog near ``anchor_global_pos`` if given, else center-right.

        When an anchor is supplied (typically the screen-space position of a
        context-menu click or the right edge of a selected row), the dialog is
        offset below-and-right of it and clamped to the anchor's screen so it
        appears close to where the user just acted instead of jumping to the
        right half of the primary display.
        """
        if anchor_global_pos is not None:
            DialogPositioner._position_near(dialog, anchor_global_pos)
            return

        # Get screen geometry
        screen = QApplication.primaryScreen().geometry()

        # Calculate right half center position
        right_half_width = screen.width() // 2
        right_half_center_x = screen.width() // 2 + right_half_width // 2
        screen_center_y = screen.height() // 2

        # Get dialog size
        dialog_size = dialog.size()

        # Calculate dialog position (center of right half)
        dialog_x = right_half_center_x - dialog_size.width() // 2
        dialog_y = screen_center_y - dialog_size.height() // 2

        # Ensure dialog stays within screen bounds
        dialog_x = max(screen.width() // 2, min(dialog_x, screen.width() - dialog_size.width()))
        dialog_y = max(0, min(dialog_y, screen.height() - dialog_size.height()))

        dialog.move(dialog_x, dialog_y)

    @staticmethod
    def _position_near(dialog, anchor_global_pos):
        """Place ``dialog`` with a small offset from ``anchor_global_pos``, clamped to its screen."""
        screen = QApplication.screenAt(anchor_global_pos) if hasattr(QApplication, "screenAt") else None
        if screen is None:
            screen = QApplication.primaryScreen()
        sg = screen.availableGeometry()
        size = dialog.size()

        x = anchor_global_pos.x() + DialogPositioner._ANCHOR_OFFSET_X
        y = anchor_global_pos.y() + DialogPositioner._ANCHOR_OFFSET_Y
        x = max(sg.left(), min(x, sg.right() - size.width()))
        y = max(sg.top(), min(y, sg.bottom() - size.height()))
        dialog.move(x, y)


class CodeEditorMessageBox(QMessageBox):
    """QMessageBox that automatically positions itself relative to the code editor."""

    def __init__(self, parent=None, anchor_global_pos=None):
        # Always use code editor as parent for consistent positioning
        code_editor_parent = DialogPositioner.get_code_editor_parent()
        super().__init__(code_editor_parent or parent)
        self._anchor_global_pos = anchor_global_pos

    def showEvent(self, event):
        """Position dialog when shown."""
        super().showEvent(event)
        DialogPositioner.position_dialog(self, anchor_global_pos=self._anchor_global_pos)

    @staticmethod
    def information(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
        """Show information dialog positioned relative to code editor."""
        msg = CodeEditorMessageBox(parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(defaultButton)
        return msg.exec()

    @staticmethod
    def warning(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
        """Show warning dialog positioned relative to code editor."""
        msg = CodeEditorMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(defaultButton)
        return msg.exec()

    @staticmethod
    def critical(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
        """Show critical dialog positioned relative to code editor."""
        msg = CodeEditorMessageBox(parent)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(defaultButton)
        return msg.exec()

    @staticmethod
    def question(parent, title, text, buttons=None, defaultButton=QMessageBox.NoButton, anchor_global_pos=None):
        """Show question dialog positioned relative to code editor.

        Args:
            anchor_global_pos: Optional screen-space point; when provided the
                dialog opens just below-right of it instead of the default
                center-right of the screen. Used so context-menu / row-anchored
                confirmations appear near where the user just clicked.
        """
        if buttons is None:
            buttons = QMessageBox.StandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg = CodeEditorMessageBox(parent, anchor_global_pos=anchor_global_pos)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(defaultButton)
        return msg.exec()


class CodeEditorInputDialog(QInputDialog):
    """QInputDialog that automatically positions itself relative to the code editor."""

    def __init__(self, parent=None):
        # Always use code editor as parent for consistent positioning
        code_editor_parent = DialogPositioner.get_code_editor_parent()
        super().__init__(code_editor_parent or parent)

    def showEvent(self, event):
        """Position dialog when shown."""
        super().showEvent(event)
        DialogPositioner.position_dialog(self)

    @staticmethod
    def getText(parent, title, label, echo=None, text=""):
        """Show text input dialog positioned relative to code editor."""
        dialog = CodeEditorInputDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)

        if echo is not None:
            dialog.setTextEchoMode(echo)

        if dialog.exec() == QInputDialog.Accepted:
            return dialog.textValue(), True
        return "", False


class CodeEditorFileDialog(QFileDialog):
    """QFileDialog that automatically positions itself relative to the code editor."""

    def __init__(self, parent=None, caption="", directory="", filter=""):
        # Always use code editor as parent for consistent positioning
        code_editor_parent = DialogPositioner.get_code_editor_parent()
        super().__init__(code_editor_parent or parent, caption, directory, filter)

    def showEvent(self, event):
        """Position dialog when shown."""
        super().showEvent(event)
        DialogPositioner.position_dialog(self)

    @staticmethod
    def getSaveFileName(parent=None, caption="", dir="", filter="", selectedFilter="", options=None):
        """Show save file dialog positioned relative to code editor."""
        if options is None:
            options = QFileDialog.Options()
        dialog = CodeEditorFileDialog(parent, caption, dir, filter)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setOptions(options)

        if dialog.exec() == QDialog.Accepted:
            files = dialog.selectedFiles()
            if files:
                return files[0], dialog.selectedNameFilter()
        return "", ""

    @staticmethod
    def getOpenFileName(parent=None, caption="", dir="", filter="", selectedFilter="", options=None):
        """Show open file dialog positioned relative to code editor."""
        if options is None:
            options = QFileDialog.Options()
        dialog = CodeEditorFileDialog(parent, caption, dir, filter)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setOptions(options)

        if dialog.exec() == QDialog.Accepted:
            files = dialog.selectedFiles()
            if files:
                return files[0], dialog.selectedNameFilter()
        return "", ""


class CodeEditorDialog(QDialog):
    """Base QDialog class that automatically positions itself relative to the code editor."""

    def __init__(self, parent=None):
        # Always use code editor as parent for consistent positioning
        code_editor_parent = DialogPositioner.get_code_editor_parent()
        super().__init__(code_editor_parent or parent)

    def showEvent(self, event):
        """Position dialog when shown."""
        super().showEvent(event)
        DialogPositioner.position_dialog(self)
