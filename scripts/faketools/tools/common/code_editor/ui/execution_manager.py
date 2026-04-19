"""
Execution Manager for Code Editor.

UI-layer coordinator: reads the active editor's selection/content, formats
inspection snippets, and routes execution through the command-layer
``NativeExecutionBridge``. All Maya API calls live in ``command.execution``.
"""

import ast
import contextlib
from logging import getLogger

from ..command.execution import MAYA_AVAILABLE, NativeExecutionBridge

logger = getLogger(__name__)


class ExecutionManager:
    """Manages code execution and object inspection for the Code Editor."""

    def __init__(self, main_window):
        """Initialize the ExecutionManager with reference to main window.

        Args:
            main_window: The main MayaCodeEditor window instance
        """
        self.main_window = main_window
        self.native_bridge = None
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
        # Initialize native bridge if needed
        if MAYA_AVAILABLE and self.native_bridge is None:
            try:
                self.native_bridge = NativeExecutionBridge()
            except Exception as e:
                # Fallback if bridge creation fails
                logger.warning(f"Failed to create NativeExecutionBridge: {e}")
                self.native_bridge = None

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

    def is_single_expression(self, code: str) -> bool:
        """Check if code is a single expression that should return a result."""
        try:
            # Strip whitespace and check if empty
            code = code.strip()
            if not code:
                return False

            # Parse the code
            parsed = ast.parse(code, mode="eval")
            return True
        except SyntaxError:
            # If it can't be parsed as an expression, it's likely a statement
            try:
                # Check if it's a simple statement like variable assignment
                parsed = ast.parse(code, mode="exec")
                if len(parsed.body) == 1:
                    stmt = parsed.body[0]
                    # Don't treat assignments, imports, function/class definitions as expressions
                    if isinstance(
                        stmt,
                        (
                            ast.Assign,
                            ast.AugAssign,
                            ast.Import,
                            ast.ImportFrom,
                            ast.FunctionDef,
                            ast.ClassDef,
                            ast.For,
                            ast.While,
                            ast.If,
                            ast.With,
                            ast.Try,
                        ),
                    ):
                        return False
                    # Single expression statements (like just "variable_name")
                    if isinstance(stmt, ast.Expr):
                        return True
                return False
            except SyntaxError:
                return False
        except Exception:
            return False

    def handle_object_inspection(self, object_name: str, inspection_type: str):
        """Handle object inspection requests."""
        if not self.output_terminal:
            return

        try:
            if inspection_type == "dir":
                # Execute dir() and display each attribute
                self.output_terminal.append_output("\n=== " + object_name + " ===")

                # Check if this is a syntax error display request
                if object_name.startswith("Syntax Errors:"):
                    self.output_terminal.append_error(object_name.replace("Syntax Errors:\n", ""))
                    return

                # Create code to get dir() results
                inspection_code = """
try:
    _obj = OBJECT_NAME_PLACEHOLDER
    _attrs = dir(_obj)
    print("Object type: " + str(type(_obj)))
    print("Number of attributes: " + str(len(_attrs)))
    print("Attributes:")
    for _attr in _attrs:
        print("  " + _attr)
except NameError:
    print("Code Editor: 'OBJECT_NAME_PLACEHOLDER' is not defined")
except Exception as _inspect_err:
    print("Code Editor: Error inspecting 'OBJECT_NAME_PLACEHOLDER' - " + str(_inspect_err))
""".replace("OBJECT_NAME_PLACEHOLDER", object_name)

                # Execute the inspection code
                self.execute_inspection_code(inspection_code)

            elif inspection_type == "help":
                # Execute help() and display result
                self.output_terminal.append_output("\n=== Help: " + object_name + " ===")

                inspection_code = """
try:
    _obj = OBJECT_NAME_PLACEHOLDER
    # Try to get help for the object itself
    import pydoc
    _help_text = pydoc.getdoc(_obj)
    if _help_text and _help_text != 'no documentation found':
        help(_obj)
    else:
        # If no documentation, show help for the type
        print(f"Variable '{object_name}' is of type: {type(_obj).__name__}")
        print(f"Value: {repr(_obj)}")
        print("-" * 40)
        help(type(_obj))
except NameError:
    print("Code Editor: 'OBJECT_NAME_PLACEHOLDER' is not defined")
except Exception as _help_err:
    print("Code Editor: Error getting help for 'OBJECT_NAME_PLACEHOLDER' - " + str(_help_err))
""".replace("OBJECT_NAME_PLACEHOLDER", object_name).replace("object_name", f"'{object_name}'")

                # Execute the inspection code
                self.execute_inspection_code(inspection_code)

        except Exception as inspection_error:
            logger.error(f"Error during inspection: {inspection_error}")
            self.output_terminal.append_error("Error during inspection: " + str(inspection_error))

    def execute_inspection_code(self, code: str):
        """Execute inspection code silently (code text itself is not echoed)."""
        if MAYA_AVAILABLE and self.native_bridge is None:
            with contextlib.suppress(Exception):
                self.native_bridge = NativeExecutionBridge()

        if self.native_bridge:
            self.native_bridge.execute_silent(code, exec_globals=self.exec_globals)
            return

        # Non-Maya fallback
        try:
            exec(code, self.exec_globals)
        except Exception:
            import traceback

            traceback.print_exc()
