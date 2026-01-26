# CODE_EDITOR_CLAUDE.md

This document provides comprehensive documentation for the Code Editor module in FakeTools. Use this to understand the codebase without re-reading all files.

## Overview

Maya Code Editor is a full-featured Python code editor with native Maya integration. It provides:
- Python syntax highlighting (tokenize-based)
- Multi-cursor editing (VSCode-style)
- Tab-based file management with preview mode
- File explorer with drag-and-drop
- Session/settings persistence
- Autosave functionality
- Maya docking (WorkspaceControl)
- Native Maya execution via cmdScrollFieldExecuter
- Find/replace with regex support
- VSCode Dark Modern theme

## Conversion Status

| Component | Status | Notes |
|-----------|--------|-------|
| `__init__.py` | ✅ Done | TOOL_CONFIG + show_ui() configured |
| Logger usage | ✅ Done | Uses `from logging import getLogger` |
| Entry point | ✅ Done | maya_integration.py → main.py, show_ui() in ui/__init__.py |
| Maya menu | ✅ Done | Removed standalone menu, uses FakeTools menu |
| docs module | ✅ Done | Removed (user guide button removed from toolbar) |
| Import paths | ❌ Pending | Still references `maya_code_editor` in some places |
| Config paths | ✅ Done | Uses ToolDataManager: `{data_root}/common/code_editor/config/` |
| Workspace paths | ✅ Done | Uses ToolDataManager: `{data_root}/common/code_editor/workspace/` |
| Qt imports | ✅ Done | Uses FakeTools `lib_ui/qt_compat.py` |

## Directory Structure

```
code_editor/
├── __init__.py              # TOOL_CONFIG + show_ui() (FakeTools entry point)
├── main.py                  # Main entry: show_editor(), hide_editor(), close_editor()
├── module_cleaner.py        # Module reload utility
├── CODE_EDITOR_CLAUDE.md    # This documentation
│
├── highlighting/            # Syntax highlighting
│   ├── __init__.py
│   ├── python_highlighter.py    # PythonHighlighter class
│   └── syntax_config_loader.py  # JSON-based color config
│
├── integration/             # Maya integration
│   ├── __init__.py
│   └── maya_dock.py         # MayaDock (WorkspaceControl)
│
├── settings/                # Settings management
│   ├── __init__.py
│   ├── settings_manager.py  # Main coordinator
│   ├── session_manager.py   # Window state, tabs, recent files
│   ├── user_settings.py     # Editor preferences
│   ├── workspace_manager.py # Workspace directory management
│   └── startup/
│       └── welcome.py       # Welcome tab content
│
├── themes/                  # Visual themes
│   ├── __init__.py
│   └── app_theme.py         # AppTheme (VSCode Dark Modern)
│
├── ui/                      # User interface
│   ├── __init__.py
│   ├── main_window.py       # MayaCodeEditor main widget
│   ├── code_editor.py       # PythonEditor, CodeEditorWidget
│   ├── line_number_area.py  # Line numbers widget
│   ├── output_terminal.py   # OutputTerminal
│   ├── tab_bar.py           # CodeEditorTabBar
│   ├── file_explorer.py     # FileExplorer with tree view
│   ├── toolbar.py           # Toolbar
│   ├── find_replace_dialog.py   # Find/replace UI
│   ├── execution_manager.py     # Code execution
│   ├── ui_layout_manager.py     # Layout management
│   ├── ui_session_manager.py    # UI session state
│   ├── shortcut_handler.py      # Global shortcuts
│   ├── editor_shortcuts.py      # Editor key handling
│   ├── editor_text_operations.py # Text operation mixin
│   ├── multi_cursor_handler.py  # Multi-cursor mixin
│   └── dialog_base.py           # Base dialog classes
│
└── utils/                   # Utilities
    ├── __init__.py
    ├── autosave_manager.py  # Autosave/backup
    └── maya_help_detector.py # Maya help context menu
```

## Architecture

### Entry Points

1. **FakeTools Menu**: Via `TOOL_CONFIG` in `__init__.py`, calls `ui.show_ui()`
2. **Direct Call**: `from faketools.tools.common.code_editor import show_ui; show_ui()`
3. **Low-level**: `from faketools.tools.common.code_editor.main import show_editor; show_editor(floating=False)`

### Core Classes

#### Main Window (`ui/main_window.py`)

```
MayaCodeEditor(QWidget)
├── Managers
│   ├── SettingsManager      # All settings coordination
│   ├── ExecutionManager     # Code execution
│   ├── ShortcutHandler      # Global shortcuts
│   ├── UILayoutManager      # Splitter layouts
│   └── UISessionManager     # Session state
│
├── UI Components
│   ├── Toolbar              # Top toolbar
│   ├── FileExplorer         # Left panel
│   ├── CodeEditorWidget     # Center (tabs)
│   └── OutputTerminal       # Bottom panel
│
└── Layout
    ├── main_splitter        # Horizontal (explorer | content)
    └── content_splitter     # Vertical (editor | terminal)
```

#### Code Editor (`ui/code_editor.py`)

```
PythonEditor(EditorTextOperationsMixin, MultiCursorMixin, QPlainTextEdit)
├── PythonHighlighter        # Syntax highlighting
├── LineNumberArea           # Line numbers
├── AutoSaveManager          # Autosave
└── Features
    ├── Tab handling
    ├── Bracket matching
    ├── Auto-indent
    ├── Multi-cursor editing
    └── Text operations (duplicate, move, delete lines)

CodeEditorWidget(QTabWidget)
├── Manages multiple PythonEditor tabs
├── Preview mode (italic tab, replaced on open)
├── File tracking (modified, path)
└── Welcome tab on empty
```

#### File Explorer (`ui/file_explorer.py`)

```
FileExplorer(QWidget)
├── QFileSystemModel
├── HiddenFileFilterModel    # .pyc, __pycache__ filter
├── QTreeView
├── Run button overlay
└── Features
    ├── Drag-and-drop
    ├── Copy/Cut/Paste
    ├── New file/folder
    ├── Rename (F2)
    ├── Delete
    └── Open in system explorer
```

#### Settings System (`settings/`)

```
SettingsManager
├── UserSettings             # Editor/terminal preferences
├── SessionManager           # Window state, tabs, recent files
└── WorkspaceManager         # Workspace directories

Storage Locations (FakeTools convention):
├── {MAYA_APP_DIR}/faketools_workspace/common/code_editor/config/  # Settings JSON
└── {MAYA_APP_DIR}/faketools_workspace/common/code_editor/workspace/  # Default workspace
```

### Key Patterns

#### Mixin Pattern (Editor Features)

```python
# PythonEditor uses multiple mixins
class PythonEditor(EditorTextOperationsMixin, MultiCursorMixin, QPlainTextEdit):
    pass

# EditorTextOperationsMixin provides:
# - duplicate_line(), delete_line(), move_line_up/down()
# - toggle_comment(), indent/unindent

# MultiCursorMixin provides:
# - Ctrl+Click: add cursor
# - Ctrl+D: select next occurrence
# - Alt+Shift+Drag: rectangle selection
```

#### Signal-Slot Communication

```python
# File explorer → Main window
file_explorer.file_selected.connect(main_window.open_file)
file_explorer.file_run_requested.connect(main_window.run_file)

# Code editor → Execution
code_editor.execution_requested.connect(execution_manager.execute_code)

# Tab changes
code_editor_widget.currentChanged.connect(update_title)
```

#### Manager Pattern

All major functionality is encapsulated in Manager classes:
- `SettingsManager` - Coordinates all settings
- `ExecutionManager` - Handles code execution
- `ShortcutHandler` - Global keyboard shortcuts
- `UILayoutManager` - Splitter state
- `UISessionManager` - Tab/window session

## File-by-File Reference

### Root Level

#### `__init__.py` ✅
- TOOL_CONFIG for FakeTools integration
- Exports: `TOOL_CONFIG`, `show_ui()`

#### `main.py` ✅
- **Functions**: `show_editor(floating)`, `hide_editor()`, `close_editor()`, `get_editor()`, `reload_editor_dev()`
- **Callbacks**: `_setup_maya_callbacks()` - Save session on Maya exit
- **Globals**: `_editor_instance`, `_dock_instance`

#### `ui/__init__.py` ✅
- **Function**: `show_ui()` - FakeTools registry entry point
- Lazy imports `show_editor` from `main.py`

### highlighting/

#### `python_highlighter.py`
- **Class**: `PythonHighlighter(QSyntaxHighlighter)`
- Uses Python's `tokenize` module for accurate highlighting
- Token types: keyword, string, comment, number, decorator, type annotation, method call, builtin
- Special handling for multiline strings (state-based)
- Uses `SyntaxConfigLoader` for colors

#### `syntax_config_loader.py`
- **Class**: `SyntaxConfigLoader`
- Loads syntax colors from JSON config
- Methods: `load_config()`, `get_format(token_type)`, `apply_format()`
- Fallback colors if no config file

### integration/

#### `maya_dock.py`
- **Class**: `MayaDock`
- **Constants**: `CONTROL_NAME = "MayaCodeEditorWorkspaceControl"`
- **Methods**:
  - `create_docked_widget()` - Create WorkspaceControl
  - `show()` - Show/restore dock
  - `hide()` - Hide dock
  - `close()` - Cleanup
- Handles floating vs docked state transitions
- Uses `shiboken` for Qt pointer wrapping

### settings/

#### `settings_manager.py`
- **Class**: `SettingsManager`
- Coordinates: `UserSettings`, `SessionManager`, `WorkspaceManager`
- **Config Path**: `{maya_prefs}/maya_code_editor_config/`
- **TODO**: Update path to FakeTools convention

#### `session_manager.py`
- **Class**: `SessionManager`
- Manages: window geometry, splitter sizes, open tabs, recent files, drafts
- **File**: `session.json`
- Draft content saved for unsaved files

#### `user_settings.py`
- **Class**: `UserSettings`
- Editor settings: font family/size, tab width, show line numbers
- Terminal settings: font size, height
- Autosave settings: enabled, interval, max versions

#### `workspace_manager.py`
- **Class**: `WorkspaceManager`
- Default workspace: `{maya_prefs}/maya_code_editor_workspace/`
- Methods: `get_workspace_dir()`, `set_workspace_dir()`, `get_default_pythonpath()`
- **TODO**: Update path to FakeTools convention

### themes/

#### `app_theme.py`
- **Class**: `AppTheme`
- VSCode Dark Modern color scheme
- Color constants for: background, text, selection, buttons, borders
- Methods: `get_main_stylesheet()`, `get_editor_stylesheet()`, etc.
- Editor colors: line highlight, bracket match, error, etc.

### ui/

#### `main_window.py`
- **Class**: `MayaCodeEditor(QWidget)`
- Central coordinator for all components
- Creates: Toolbar, FileExplorer, CodeEditorWidget, OutputTerminal
- Manages: SettingsManager, ExecutionManager, ShortcutHandler, etc.
- Key methods: `open_file()`, `save_file()`, `run_file()`, `run_selected()`

#### `code_editor.py`
- **Class**: `PythonEditor(EditorTextOperationsMixin, MultiCursorMixin, QPlainTextEdit)`
  - Syntax highlighting, line numbers, autosave
  - Tab handling (insert spaces)
  - Bracket matching, auto-indent
  - Context menu with copy/paste/undo/redo

- **Class**: `CodeEditorWidget(QTabWidget)`
  - Tab management with close buttons
  - Preview mode (single-click = preview, double-click = open)
  - File tracking: path, modified state
  - Welcome tab when empty

#### `line_number_area.py`
- **Class**: `LineNumberArea(QWidget)`
- Displays line numbers with proper sizing
- Matches editor font and scroll position

#### `output_terminal.py`
- **Class**: `OutputTerminal(QWidget)`
- Two modes:
  1. Native Maya: Uses `cmdScrollFieldExecuter`
  2. Fallback: Custom `QTextEdit`
- Clear button, proper styling

#### `tab_bar.py`
- **Class**: `CodeEditorTabBar(QTabBar)`
- Close button on tabs
- Middle-click to close
- Tab context menu

#### `file_explorer.py`
- **Class**: `FileExplorer(QWidget)`
- **Class**: `HiddenFileFilterModel(QSortFilterProxyModel)`
- Tree view with file system model
- Run button overlay (play icon)
- Drag-and-drop file moving
- Clipboard operations (copy/cut/paste)
- Keyboard shortcuts: F2 rename, Delete

#### `toolbar.py`
- **Class**: `Toolbar(QWidget)`
- Buttons: New, Open, Save, Run, Settings

#### `find_replace_dialog.py`
- **Class**: `FindReplaceWidget(QWidget)`
- Find/Replace functionality
- Options: case sensitive, whole word, regex
- Find all, replace all

#### `execution_manager.py`
- **Class**: `ExecutionManager`
- **Class**: `NativeExecutionBridge`
- Executes Python code in Maya
- Native execution via `cmdScrollFieldExecuter` (preserves Maya behavior)
- Fallback execution via `exec()`

#### `ui_layout_manager.py`
- **Class**: `UILayoutManager`
- Manages splitter sizes
- Save/restore layout state

#### `ui_session_manager.py`
- **Class**: `UISessionManager`
- Manages session state for UI
- Open tabs, active tab, etc.

#### `shortcut_handler.py`
- **Class**: `ShortcutHandler`
- Global keyboard shortcuts
- Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Shift+S, F5, Ctrl+Enter

#### `editor_shortcuts.py`
- **Class**: `EditorShortcuts`
- Editor-specific key handling
- Ctrl+D, Ctrl+/, Ctrl+Shift+K, Alt+Up/Down

#### `editor_text_operations.py`
- **Class**: `EditorTextOperationsMixin`
- Line operations: duplicate, delete, move up/down
- Comment toggle
- Indent/unindent

#### `multi_cursor_handler.py`
- **Class**: `MultiCursorMixin`
- Multi-cursor editing
- Ctrl+Click: add cursor
- Ctrl+D: select next occurrence
- Alt+Shift+Drag: rectangle selection

#### `dialog_base.py`
- **Class**: `DialogBase(QDialog)`
- **Class**: `FramelessDialogBase(QDialog)`
- Centralized positioning relative to parent

### utils/

#### `autosave_manager.py`
- **Class**: `AutoSaveManager`
- Manages autosave/backup files
- Configurable interval and max versions
- Network HDD performance considerations

#### `maya_help_detector.py`
- **Class**: `MayaHelpDetector`
- Detects Maya commands for context menu help

## Keyboard Shortcuts

### Global (ShortcutHandler)

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save file |
| Ctrl+Shift+S | Save as |
| F5 | Run file |
| Ctrl+Enter | Run selected |

### Editor (EditorShortcuts / Mixins)

| Shortcut | Action |
|----------|--------|
| Ctrl+D | Select next occurrence / Duplicate line |
| Ctrl+/ | Toggle comment |
| Ctrl+Shift+K | Delete line |
| Alt+Up | Move line up |
| Alt+Down | Move line down |
| Ctrl+Click | Add cursor |
| Alt+Shift+Drag | Rectangle selection |
| Ctrl+Shift+D | Duplicate line |
| Tab | Indent |
| Shift+Tab | Unindent |

## Signals Reference

### FileExplorer
- `file_selected(str)` - File path selected
- `file_run_requested(str)` - Run button clicked
- `directory_changed(str)` - Directory changed

### CodeEditorWidget
- `current_file_changed(str)` - Active tab changed
- `file_modified(str, bool)` - File modification state
- `execution_requested(str, str)` - Code to execute

### PythonEditor
- `modificationChanged(bool)` - Text modified

## Areas Needing FakeTools Adjustment

### ~~1. Import Path Updates~~ ✅ DONE (Phase 1)
- ~~`maya_integration.py` renamed to `main.py`~~
- ~~`reload_editor_dev()` fixed to call `show_editor()` directly~~

### ~~2. Config Directory Path~~ ✅ DONE (Phase 2)
- ~~`settings/settings_manager.py` now uses `ToolDataManager`~~
- ~~Path: `{data_root}/common/code_editor/config/`~~
- ~~Auto-migration from legacy location~~

### ~~3. Workspace Directory Path~~ ✅ DONE (Phase 2)
- ~~`settings/workspace_manager.py` now uses `ToolDataManager`~~
- ~~Path: `{data_root}/common/code_editor/workspace/`~~

### ~~4. Qt Compatibility Layer~~ ✅ DONE (Phase 3)
- ~~Current: `ui/qt_compat.py` (own implementation)~~
- ~~Consider: Using FakeTools' `lib_ui/qt_compat.py`~~

### 5. Window Base Class
Current: Custom `MayaCodeEditor(QWidget)`
Consider: Using FakeTools' `BaseMainWindow`

### 6. Settings Storage
Current: Custom `SettingsManager` with JSON
Consider: Using FakeTools' `ToolSettingsManager`

### 7. Maya Dialog Integration
Current: Custom dialogs
Consider: Using FakeTools' `lib_ui/maya_dialog.py`

## Testing

### Quick Test in Maya
```python
from faketools.tools.common.code_editor import show_ui
show_ui()
```

### Reload During Development
```python
from faketools.tools.common.code_editor import module_cleaner
module_cleaner.cleanup()

from faketools.tools.common.code_editor import show_ui
show_ui()
```

## Version History

- **1.0.0**: Initial integration into FakeTools
  - Converted TOOL_CONFIG
  - Converted logging to standard Python logging

---

## Phase 1: FakeTools Entry Point Adaptation ✅ COMPLETE

**Status**: 完了 (Commit: fdceaf9)

### 実施内容
- `maya_integration.py` → `main.py` にリネーム
- `ui/__init__.py` に `show_ui()` 追加（FakeTools registry 用）
- `__init__.py` に `show_ui()` 追加（便利インポート用）
- Maya 独自メニュー削除（FakeTools メニューを使用）
- docs モジュール・ヘルプボタン削除

### 動作確認
- FakeTools メニュー → Common → Code Editor から起動可能

---

## Phase 2: Config/Workspace Path ✅ COMPLETE

**Status**: 完了

### Goal
Config/Workspace パス の FakeTools 規約への統一

### 実施内容

#### Path Changes
| Type | Old | New |
|------|-----|-----|
| Config | `{maya_app_dir}/scripts/maya_code_editor_config/` | `{data_root}/common/code_editor/config/` |
| Workspace | `{maya_app_dir}/scripts/maya_code_editor_workspace/` | `{data_root}/common/code_editor/workspace/` |

`{data_root}` = `{MAYA_APP_DIR}/faketools_workspace/` (GlobalConfig から取得)

#### Files Modified
- `settings/settings_manager.py`
  - `_get_settings_directory()`: Uses `ToolDataManager` for path resolution

- `settings/workspace_manager.py`
  - `_create_default_workspace()`: Uses `ToolDataManager` for path resolution

#### New Directory Structure
```
{MAYA_APP_DIR}/faketools_workspace/common/code_editor/
├── config/
│   ├── user_settings.json
│   ├── session.json
│   ├── workspace.json
│   └── backups/
└── workspace/
    └── welcome.py
```

#### Note
- レガシーからの自動マイグレーションは行わない
- 旧バージョンのユーザーは必要に応じて手動で設定を移行

---

## Phase 3: Qt Compatibility Layer Migration ✅ COMPLETE

**Status**: 完了

### Goal
Code Editor の独自 `ui/qt_compat.py` を FakeTools の `lib_ui/qt_compat.py` に統一

### 実施内容

#### Import Path Changes
| Location | Old | New |
|----------|-----|-----|
| `ui/*.py` | `from .qt_compat` | `from .....lib_ui.qt_compat` |
| `utils/*.py` | `from ..ui.qt_compat` | `from .....lib_ui.qt_compat` |
| `highlighting/*.py` | `from ..ui.qt_compat` | `from .....lib_ui.qt_compat` |
| `integration/*.py` | `from ..ui.qt_compat` | `from .....lib_ui.qt_compat` |
| `settings/*.py` | `from ..ui.qt_compat` | `from .....lib_ui.qt_compat` |

#### Files Modified (18 files)
- `ui/main_window.py`
- `ui/code_editor.py`
- `ui/file_explorer.py`
- `ui/output_terminal.py`
- `ui/tab_bar.py`
- `ui/toolbar.py`
- `ui/find_replace_dialog.py`
- `ui/dialog_base.py`
- `ui/shortcut_handler.py`
- `ui/editor_shortcuts.py`
- `ui/editor_text_operations.py`
- `ui/multi_cursor_handler.py`
- `ui/ui_layout_manager.py`
- `ui/line_number_area.py`
- `ui/ui_session_manager.py`
- `ui/maya_terminal_widget.py`
- `utils/autosave_manager.py`
- `highlighting/python_highlighter.py`
- `highlighting/syntax_config_loader.py`
- `integration/maya_dock.py`
- `settings/settings_manager.py`

#### Files Deleted
- `ui/qt_compat.py` - No longer needed, using shared `lib_ui/qt_compat.py`

#### Compatibility Notes
- Code Editor used PySide6-first import order; lib_ui uses PySide2-first
- `QT_VERSION` integer (2/6) replaced by `is_pyside6()` helper function
- All 49 Qt items used by Code Editor are available in lib_ui/qt_compat.py

---

## Future Phases (優先度低)

### Phase 4: Window Base Class
- `MayaCodeEditor(QWidget)` → `BaseMainWindow` への移行
- 大規模リファクタリングが必要

### Phase 5: Settings Integration
- Custom `SettingsManager` → FakeTools `ToolSettingsManager`
- セッション管理など独自機能が多いため検討が必要
