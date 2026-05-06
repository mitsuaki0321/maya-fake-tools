"""
Welcome to Code Editor Workspace!

This is your personal Maya scripting workspace.
Python (.py) and MEL (.mel) files are both supported; the workspace
directory is automatically added to Python's import path so any module
you drop here can be ``import``ed from your scripts and the Run button.

You can organize your scripts into subdirectories:
- utils/     - Utility functions
- tools/     - Maya tools and scripts
- plugins/   - Custom Maya plugins
- tests/     - Unit tests

=== KEYBOARD SHORTCUTS ===

File Operations:
  Ctrl+N             - Create new file (Python)
  Ctrl+S             - Save current file
  Ctrl+Shift+S       - Save all open files
  F2                 - Rename file/folder (in file explorer)

Code Editing:
  Ctrl+D             - Select word / next occurrence (multi-selection)
  Ctrl+Shift+D       - Duplicate current line
  Ctrl+Shift+K       - Delete current line
  Ctrl+L             - Select current line (extend on repeat)
  Ctrl+Shift+Up/Down - Move line up/down
  Ctrl+/             - Toggle line comments (Python: #, MEL: //)
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

Code Folding:
  Ctrl+Shift+[       - Fold the block at the cursor
  Ctrl+Shift+]       - Unfold the block at the cursor
  Ctrl+Alt+[         - Fold all foldable regions
  Ctrl+Alt+]         - Unfold all folded regions

Autocomplete & Help (Python only):
  Ctrl+Space         - Toggle autocomplete on/off (requires jedi)
  Ctrl+Shift+Space   - Toggle docstring help popup at the caret

Interface:
  Ctrl+MouseWheel    - Adjust font size
"""

import maya.cmds as cmds


def hello_maya():
    """Simple test function."""
    cmds.confirmDialog(title="Code Editor", message="Welcome to your workspace!", button="OK")


if __name__ == "__main__":
    hello_maya()
