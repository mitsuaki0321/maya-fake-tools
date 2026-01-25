"""
Welcome to Maya Code Editor Workspace!

This is your personal Maya scripting workspace.
All files here are automatically added to Python path.

You can organize your scripts into subdirectories:
- utils/     - Utility functions
- tools/     - Maya tools and scripts
- plugins/   - Custom Maya plugins
- tests/     - Unit tests

=== KEYBOARD SHORTCUTS ===

File Operations:
  Ctrl+N             - Create new file
  Ctrl+S             - Save current file
  Ctrl+Shift+S       - Save all open files

Code Editing:
  Ctrl+D             - Select next occurrence (multi-selection)
  Ctrl+Shift+D       - Duplicate current line
  Ctrl+Shift+K       - Delete current line
  Ctrl+L             - Select current line (extend on repeat)
  Ctrl+Shift+Up/Down - Move line up/down
  F2                 - Rename all occurrences in multi-selection
  Ctrl+/             - Toggle line comments
  Tab / Shift+Tab    - Indent/unindent selection
  Enter              - Smart line break with auto-indentation

Multi-Cursor Editing:
  Ctrl+Click         - Add cursor at click position
  Ctrl+Drag          - Add selection range (drag to select different code)
  Middle-Click+Drag  - Rectangle/column selection
  Ctrl+D             - Select word and add next occurrence
  Ctrl+Shift+L       - Select all occurrences of current word
  Alt+Shift+I        - Add cursors to line ends in selection
  Escape             - Clear all multi-cursors

Search & Navigation:
  Ctrl+F             - Find dialog
  Ctrl+H             - Replace dialog
  F3 / Shift+F3      - Find next/previous

Code Execution:
  Ctrl+Enter         - Execute current line or selection
  Numpad Enter       - Execute current script (same as Run button)
  Ctrl+Shift+Enter   - Execute entire file
  Ctrl+K             - Clear terminal output

Interface:
  Ctrl+MouseWheel    - Adjust font size
"""

import maya.cmds as cmds


def hello_maya():
    """Simple test function."""
    cmds.confirmDialog(title="Maya Code Editor", message="Welcome to your workspace!", button="OK")


if __name__ == "__main__":
    hello_maya()
