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

### Editor Settings (editor)
Settings for code editor display and behavior.

| Setting | Default | Description |
|---------|---------|-------------|
| `font_size` | 10 | Editor font size |

Note: Font family is fixed to "Consolas" (fallback: "Courier New"). Tab size is 4 spaces. Word wrap and line numbers are always enabled.

### Terminal Settings (terminal)
Settings for the terminal that displays execution results.

| Setting | Default | Description |
|---------|---------|-------------|
| `font_size` | 9 | Terminal font size |

Note: Font family is fixed to "Consolas" (fallback: "Courier New"). Maximum lines is 1000.

### Search Settings (search)
Initial settings for find/replace functionality.

| Setting | Default | Description |
|---------|---------|-------------|
| `match_case` | false | Whether to match case when searching |
| `whole_words` | false | Whether to search for whole words only |
| `use_regex` | false | Whether to use regular expressions |
| `search_direction` | "down" | Search direction (down / up) |

### Maya Integration Settings (maya)
Settings for Maya-specific features.

#### Help Settings (maya.help)
Settings for Maya command help display available from the code editor context menu.

| Setting | Default | Description |
|---------|---------|-------------|
| `language` | "JPN" | Maya help language (JPN: Japanese / ENU: English) |

### Command Port Settings (command_port)
Settings for integration with external tools.\
Used when integrating with tools like MCP Server.

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | false | Whether to enable command port |
| `port` | 7001 | Port number to use |

### Autosave Settings (autosave)
Settings for automatic saving of work.

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | true | Whether to enable autosave |
| `interval_seconds` | 60 | Autosave interval in seconds |
| `backup_on_change` | true | Whether to create backup on file change |

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
    "font_size": 12
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
  "maya": {
    "help": {
      "language": "ENU"
    }
  },
  "command_port": {
    "enabled": false,
    "port": 7001
  },
  "autosave": {
    "enabled": true,
    "interval_seconds": 60,
    "backup_on_change": true
  },
  "layout": {
    "terminal_at_bottom": true
  }
}
```

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
