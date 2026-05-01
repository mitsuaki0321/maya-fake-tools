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

    def _refresh_active_bridge(self, language_override: Optional[LanguageProfile] = None):
        """Point :attr:`native_bridge` at the bridge for the relevant language.

        Uses ``language_override`` when supplied — file-explorer Run on a
        ``foo.mel`` while a Python tab is focused needs the MEL bridge, not
        the active tab's. Otherwise falls back to the active editor's
        language.

        Bridges are created lazily and cached in :attr:`_bridges`. Languages
        whose profile has no ``source_type`` (i.e. don't support execution at
        all) leave :attr:`native_bridge` at ``None`` and consumers fall back to
        the plain ``exec`` path or skip execution entirely.
        """
        if not MAYA_AVAILABLE:
            self.native_bridge = None
            return
        language = language_override or self._active_editor_language()
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
            self.execute_with_echo(code)
        else:
            # Execute full code
            code = self.main_window.code_editor.get_current_code()
            if not code.strip():
                self.output_terminal.append_warning("No code to execute")
                return

            self.is_selection_execution = False
            self.is_full_execution = True
            self.execute_with_echo(code)

    def execute_code(self, code: str, language: Optional[LanguageProfile] = None):
        """Execute code without showing it in terminal (for variable replacement).

        ``language`` overrides the active-tab dispatch when caller has a
        better source of truth — e.g. the file-explorer Run button passes
        the file's own language so a ``foo.mel`` runs through the MEL
        executer regardless of which tab is focused.
        """
        # This is called when executing with variables
        # The replaced code has already been shown in terminal
        self.is_selection_execution = False
        self.is_full_execution = True
        self._execute_code_internal(code, show_code=False, language_override=language)

    def execute_with_echo(self, code: str):
        """Execute the active tab's code, echoing it into the output terminal.

        Despite its historical name (``execute_python_code``), the dispatch
        is language-agnostic: the active tab's :class:`LanguageProfile`
        decides which bridge runs the snippet, so a MEL tab's Run button
        routes through the MEL executer.
        """
        self._execute_code_internal(code, show_code=True)

    def _execute_code_internal(self, code: str, show_code: bool = True, language_override: Optional[LanguageProfile] = None):
        """Internal method to execute code through the appropriate bridge."""
        self._refresh_active_bridge(language_override)

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
