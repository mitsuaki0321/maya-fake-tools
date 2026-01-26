---
title: Code Editor
category: common
description: Custom Python code editor for Maya
lang: en
lang-ref: code_editor
order: 10
---


## Overview

A custom Python code editor for Maya.\
It features syntax highlighting, file explorer, terminal, and more.


## How to Launch

Launch the tool from the dedicated menu or with the following commands.

```python
import faketools.tools.common.code_editor.ui
faketools.tools.common.code_editor.ui.show_ui()
```

```python
import faketools.tools.common.code_editor.ui
faketools.tools.common.code_editor.ui.show_ui(floating=True)
```

Use `floating=True` to launch as a floating window.\
Use `floating=False` (default) to dock it to Maya's main window.


## Interface

The tool interface consists of the following main components.

![image](../../images/common/code_editor/window.png)

### Toolbar

The toolbar provides quick access to main actions like creating files, saving, and running code.\
See [Toolbar Documentation](code_editor_toolbar.html) for details.

![image](../../images/common/code_editor/toolbar.png)

### File Explorer

The file explorer displays the project directory structure and makes file management easy.\
See [File Explorer Documentation](code_editor_file_explorer.html) for details.

![image](../../images/common/code_editor/file-explorer.png)

### Code Editor

The code editor provides advanced code editing features like syntax highlighting and error checking.\
See [Code Editor Documentation](code_editor_editor.html) for details.

![image](../../images/common/code_editor/code-editor.png)

### Terminal

The terminal displays code execution results and error messages.\
See [Terminal Documentation](code_editor_terminal.html) for details.

![image](../../images/common/code_editor/terminal.png)

## Running Code

1. Click the + icon in the toolbar to create a new file.
2. Enter Python code in the code editor.
3. Click the Play icon in the toolbar to run the code.
4. The execution results will be displayed in the output console.

## Configuration Files

The tool saves configuration files in the following locations.

* User settings: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/config/user_settings.json`
* Session: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/config/session.json`
* Workspace settings: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/config/workspace.json`
* Workspace files: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/workspace/`
* Autosave: `%MAYA_APP_DIR%/faketools_workspace/common/code_editor/workspace/.maya_code_editor_backups/`

See [User Settings](code_editor_settings.html) for detailed configuration options.
