"""
Execution Manager for Code Editor.

UI-layer coordinator: reads the active editor's selection/content, formats
inspection snippets, and routes execution through the command-layer
``NativeExecutionBridge``. All Maya API calls live in ``command.execution``.

Bridges are cached per language id so a tab switch between languages reuses
the previously created hidden executer instead of tearing it down.
"""

import contextlib
from logging import getLogger
from typing import Optional

from ..command.execution import MAYA_AVAILABLE, NativeExecutionBridge
from ..languages import PYTHON, LanguageProfile

logger = getLogger(__name__)


class ExecutionManager:
    """Manages code execution and object inspection for the Code Editor."""

    def __init__(self, main_window):
        """Initialize the ExecutionManager with reference to main window.

        Args:
            main_window: The main MayaCodeEditor window instance
        """
        self.main_window = main_window
        self.native_bridge: Optional[NativeExecutionBridge] = None
        # One bridge per language id, kept around so switching tabs between
        # Python and other languages doesn't recreate the hidden executer.
        self._bridges: dict[str, NativeExecutionBridge] = {}
        self.is_selection_execution = False
        self.is_full_execution = False

    @property
    def output_terminal(self):
        """Get output terminal from main window."""
        return self.main_window.output_terminal

    @property
    def exec_globals(self):
        """Get execution globals from main window."""
        return self.main_window.exec_globals

    @property
    def code_editor(self):
        """Get code editor from main window."""
        return self.main_window.code_editor

    def _active_editor_language(self) -> LanguageProfile:
        """Resolve the language profile of the currently focused tab.

        Falls back to :data:`PYTHON` when the tab widget or active editor isn't
        ready yet (e.g. during early window construction).
        """
        editor_widget = getattr(self.main_window, "code_editor", None)
        if editor_widget is None:
            return PYTHON
        current = editor_widget.currentWidget()
        if current is None:
            return PYTHON
        return getattr(current, "language", PYTHON)

    def cleanup_bridges(self):
        """Tear down every cached :class:`NativeExecutionBridge`.

        Called on window close so each language's hidden Maya window is
        deleted. Safe to call when no bridges exist.
        """
        for bridge in self._bridges.values():
            with contextlib.suppress(Exception):
                bridge.cleanup()
        self._bridges.clear()
        self.native_bridge = None

    def _refresh_active_bridge(self):
        """Point :attr:`native_bridge` at the bridge for the active editor's language.

        Bridges are created lazily and cached in :attr:`_bridges`. Languages
        whose profile has no ``source_type`` (i.e. don't support execution at
        all) leave :attr:`native_bridge` at ``None`` and consumers fall back to
        the plain ``exec`` path or skip execution entirely.
        """
        if not MAYA_AVAILABLE:
            self.native_bridge = None
            return
        language = self._active_editor_language()
        if language.source_type is None:
            self.native_bridge = None
            return
        bridge = self._bridges.get(language.id)
        if bridge is None:
            try:
                bridge = NativeExecutionBridge(language=language)
            except Exception as e:
                logger.warning(f"Failed to create NativeExecutionBridge for {language.id}: {e}")
                self.native_bridge = None
                return
            self._bridges[language.id] = bridge
        self.native_bridge = bridge

    def run_current_script(self):
        """Execute the current script or selected text in Maya."""
        if not self.main_window.code_editor:
            return

        # Get selected text or current tab code
        current_editor = self.main_window.code_editor.currentWidget()
        if not current_editor:
            return

        # Check if there's selected text
        selected_text = current_editor.textCursor().selectedText()
        if selected_text.strip():
            code = selected_text
            # For selected text, set execution mode
            self.is_selection_execution = True
            self.is_full_execution = False
            self.execute_python_code(code)
        else:
            # Execute full code
            code = self.main_window.code_editor.get_current_code()
            if not code.strip():
                self.output_terminal.append_warning("No code to execute")
                return

            self.is_selection_execution = False
            self.is_full_execution = True
            self.execute_python_code(code)

    def execute_code(self, code: str):
        """Execute code without showing it in terminal (for variable replacement)."""
        # This is called when executing with variables
        # The replaced code has already been shown in terminal
        self.is_selection_execution = False
        self.is_full_execution = True
        self._execute_code_internal(code, show_code=False)

    def execute_python_code(self, code: str):
        """Execute Python code and display results with undoChunk for single undo."""
        self._execute_code_internal(code, show_code=True)

    def _execute_code_internal(self, code: str, show_code: bool = True):
        """Internal method to execute Python code."""
        self._refresh_active_bridge()

        # Check if Maya cmds is available for undoChunk
        maya_available = "cmds" in self.exec_globals

        try:
            # Open undo chunk if Maya is available
            if maya_available:
                try:
                    self.exec_globals["cmds"].undoInfo(openChunk=True)
                except Exception as e:
                    logger.debug(f"Maya undo not available: {e}")
                    maya_available = False  # Maya cmds not working

            # Use native execution if available
            if self.native_bridge:
                # Determine execution mode
                if self.is_full_execution:
                    mode = "all"
                else:
                    mode = "selected"  # Default for line-by-line or selection

                # Execute using native bridge with exec_globals
                success = self.native_bridge.execute_code(code, mode=mode, exec_globals=self.exec_globals)

                if not success:
                    # Fallback to exec if native execution fails
                    exec(code, self.exec_globals)
            else:
                # Fallback to original exec-based execution
                exec(code, self.exec_globals)

        except Exception:
            # Errors will be shown in Maya's native terminal
            import traceback

            traceback.print_exc()

        finally:
            # Always close undo chunk if it was opened
            if maya_available:
                with contextlib.suppress(Exception):
                    self.exec_globals["cmds"].undoInfo(closeChunk=True)

            # Reset execution flags
            self.is_selection_execution = False
            self.is_full_execution = False

    def handle_object_inspection(self, object_name: str, inspection_type: str):
        """Handle object inspection requests through the active language profile.

        The actual snippet (``dir(X)`` for Python, ``whatIs $X`` for MEL, ...)
        is generated by ``language.inspection_snippets``; this method is
        responsible only for printing the section header and dispatching the
        snippet through :meth:`execute_inspection_code`. Languages whose
        profile lacks ``inspection_snippets`` (or doesn't recognise the
        requested type) become a graceful no-op.
        """
        if not self.output_terminal:
            return

        try:
            # Header — printed before the early-exit checks so the
            # "Syntax Errors" overload still surfaces in the terminal.
            if inspection_type == "dir":
                self.output_terminal.append_output("\n=== " + object_name + " ===")
                # The ``inspect_object`` signal is reused to display syntax errors;
                # short-circuit before generating any inspection code.
                if object_name.startswith("Syntax Errors:"):
                    self.output_terminal.append_error(object_name.replace("Syntax Errors:\n", ""))
                    return
            elif inspection_type == "help":
                self.output_terminal.append_output("\n=== Help: " + object_name + " ===")

            language = self._active_editor_language()
            if language.inspection_snippets is None:
                return  # Language doesn't support inspection.

            inspection_code = language.inspection_snippets(inspection_type, object_name)
            if inspection_code is None:
                return  # Language doesn't recognise this inspection type.

            self.execute_inspection_code(inspection_code)

        except Exception as inspection_error:
            logger.error(f"Error during inspection: {inspection_error}")
            self.output_terminal.append_error("Error during inspection: " + str(inspection_error))

    def execute_inspection_code(self, code: str):
        """Execute inspection code silently (code text itself is not echoed)."""
        self._refresh_active_bridge()

        if self.native_bridge:
            self.native_bridge.execute_silent(code, exec_globals=self.exec_globals)
            return

        # Non-Maya fallback
        try:
            exec(code, self.exec_globals)
        except Exception:
            import traceback

            traceback.print_exc()
