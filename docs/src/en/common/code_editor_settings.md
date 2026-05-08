---
title: User Settings
hidden: true
parent: code_editor
parent_title: Code Editor
lang: en
lang-ref: code_editor_settings
---

## Overview

This document describes the Code Editor user settings.

## Settings File Location

Settings files are automatically saved in the following locations:

- Windows: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/config/user_settings.json`
- Mac: `~/Library/Preferences/Autodesk/maya/faketools_workspace/common/code_editor/config/user_settings.json`
- Linux: `~/maya/faketools_workspace/common/code_editor/config/user_settings.json`

Note: Settings can be changed from the editor settings screen. You can also edit the JSON file directly.

## Settings Options

### General Settings (general)

| Setting | Default | Description |
|---------|---------|-------------|
| `language` | "JPN" | UI language (JPN: Japanese / ENU: English / ...) |

### Editor Settings (editor)
Settings for code editor display and behavior.

| Setting | Default | Description |
|---------|---------|-------------|
| `font_size` | 10 | Editor font size |
| `word_wrap` | true | Enable word wrap at editor width |

Note: Font family is fixed to "Cascadia Code" (fallback: "Consolas" → "Courier New"). Line height is roughly 1.6× the font's natural metrics. Tab size is 4 spaces. Line numbers are always enabled.

### Terminal Settings (terminal)
Settings for the terminal that displays execution results.

| Setting | Default | Description |
|---------|---------|-------------|
| `font_size` | 9 | Terminal font size |

Note: Font family is fixed to "Cascadia Code" (fallback: "Consolas" → "Courier New"). Maximum lines is 1000.

### Search Settings (search)
Initial settings for find/replace functionality.

| Setting | Default | Description |
|---------|---------|-------------|
| `match_case` | false | Whether to match case when searching |
| `whole_words` | false | Whether to search for whole words only |
| `use_regex` | false | Whether to use regular expressions |
| `search_direction` | "down" | Search direction (down / up) |

### Autocomplete Settings (autocomplete)
Settings for the code editor's autocomplete feature.

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | true | Whether to enable autocomplete |
| `debounce_ms` | 100 | Debounce window (ms) for identifier-triggered completion. Dot-triggered completion (`foo.`) bypasses the debounce. |

Note: Also toggleable via the Toggle Autocomplete toolbar button or `Ctrl+Space`. Auto-disabled when jedi is not installed. MEL tabs ignore this setting (Python-only feature).

### Layout Settings (layout)
Settings for window layout.

| Setting | Default | Description |
|---------|---------|-------------|
| `terminal_at_bottom` | true | Terminal position (true: bottom / false: top) |

## Settings File Example

```json
{
  "general": {
    "language": "JPN"
  },
  "editor": {
    "font_size": 12,
    "word_wrap": true
  },
  "terminal": {
    "font_size": 10
  },
  "search": {
    "match_case": false,
    "whole_words": false,
    "use_regex": false,
    "search_direction": "down"
  },
  "autocomplete": {
    "enabled": true,
    "debounce_ms": 100
  },
  "layout": {
    "terminal_at_bottom": true
  }
}
```

## Sessions and Workspace State

`user_settings.json` only stores UI-display preferences. Working state lives in companion files:

| File | Purpose |
|------|------|
| `session.json` | Open tabs, caret positions, the Draft buffer's text, the autocomplete MRU, etc. |
| `workspace.json` | Workspace root, file-explorer expansion state, and other project-leaning data. |

These are read and written automatically on Code Editor startup / shutdown and are independent of the user settings file.\
The standalone autosave (`autosave`), Maya help language, and command port (`command_port`) options that earlier versions exposed in user settings have been removed — unsaved content is now covered by the Draft mechanism inside `session.json`.

## How to Change Settings

### Method 1: From the Editor Settings Screen
1. Open Code Editor
2. Select "Settings" from the menu
3. Change each item and click "Save"

### Method 2: Edit JSON File Directly
1. Open the JSON file at the settings file location with a text editor
2. Change values and save
3. Restart Code Editor

## Resetting Settings

To restore all settings to default:
1. Close Code Editor
2. Delete the `user_settings.json` file
3. Restart Code Editor (default settings will be created automatically)

## Backup and Restore Settings

### Backup
To save your current settings elsewhere, copy the `user_settings.json` file.

### Restore
1. Close Code Editor
2. Overwrite the original location with your backup JSON file
3. Restart Code Editor

## Troubleshooting

### Settings Not Being Applied
- Close and restart Code Editor completely
- Check for JSON syntax errors (comma placement, bracket matching, etc.)

### Settings File Not Found
- The file is created automatically when Code Editor is launched
- To create manually, copy the "Settings File Example" above
