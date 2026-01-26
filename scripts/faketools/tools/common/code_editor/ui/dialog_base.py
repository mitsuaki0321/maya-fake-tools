"""
Base dialog classes for Maya Code Editor.
Provides centralized dialog positioning and styling for consistent UX.
"""

from .....lib_ui.qt_compat import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox


class DialogPositioner:
    """Utility class for positioning dialogs relative to the code editor."""

    @staticmethod
    def get_code_editor_parent():
        """Get the main code editor window for dialog positioning."""
        # Try to find the main Maya Code Editor window
        app = QApplication.instance()
        if not app:
            return None

        for widget in app.allWidgets():
            if hasattr(widget, "__class__") and "MayaCodeEditor" in widget.__class__.__name__:
                return widget
        return None

    @staticmethod
    def position_dialog(dialog, parent_widget=None):
        """Position dialog at the center of the right half of the screen."""
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


class CodeEditorMessageBox(QMessageBox):
    """QMessageBox that automatically positions itself relative to the code editor."""

    def __init__(self, parent=None):
        # Always use code editor as parent for consistent positioning
        code_editor_parent = DialogPositioner.get_code_editor_parent()
        super().__init__(code_editor_parent or parent)

    def showEvent(self, event):
        """Position dialog when shown."""
        super().showEvent(event)
        DialogPositioner.position_dialog(self)

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
    def question(parent, title, text, buttons=None, defaultButton=QMessageBox.NoButton):
        """Show question dialog positioned relative to code editor."""
        if buttons is None:
            buttons = QMessageBox.StandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg = CodeEditorMessageBox(parent)
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
