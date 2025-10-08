"""
Example Tool UI.

Demonstrates proper UI structure with decorators and Qt compatibility.
"""

from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_ui import error_handler, get_maya_window, undo_chunk
from ....lib_ui.qt_compat import QLabel, QPushButton
from . import command

# Global instance for singleton pattern
_instance = None


class MainWindow(BaseMainWindow):
    """Main window for Example Tool."""

    def __init__(self, parent=None):
        """
        Initialize the main window.

        Args:
            parent: Parent widget (typically Maya main window)

        Returns:
            MainWindow: The initialized MainWindow instance
        """
        super().__init__(
            parent=parent,
            object_name="ExampleToolMainWindow",
            window_title="Example Tool",
            central_layout="vertical",
        )
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        # Add a label
        label = QLabel("This is an example tool template.")
        self.central_layout.addWidget(label)

        # Add a button
        btn_execute = QPushButton("Execute")
        btn_execute.clicked.connect(self.on_execute_clicked)
        self.central_layout.addWidget(btn_execute)

    @error_handler
    @undo_chunk("Example Tool Execute")
    def on_execute_clicked(self):
        """
        Handle execute button click.

        Note: Decorators are applied in UI layer, not in command layer.
        """
        result = command.execute_example()
        print(f"Example tool executed: {result}")


def show_ui():
    """
    Show the tool UI.

    Uses singleton pattern to ensure only one instance exists.

    Returns:
        MainWindow: The tool window instance
    """
    global _instance

    # Close existing instance if it exists
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    # Create new instance
    parent = get_maya_window()
    _instance = MainWindow(parent)
    _instance.show()

    return _instance


__all__ = ["MainWindow", "show_ui"]
