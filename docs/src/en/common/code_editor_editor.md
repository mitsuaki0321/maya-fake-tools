---
title: Code Editor
hidden: true
parent: code_editor
parent_title: Code Editor
lang: en
lang-ref: code_editor_editor
---

## Overview

The code editor is the main interface for writing code.\
It provides advanced code editing features such as syntax highlighting and error checking.

![image](../../images/common/code_editor/code-editor.png)

## Tab Management

### Draft Tab

The Draft tab is a space for saving temporary code notes and snippets.\
This tab is always visible and cannot be closed.

![image](../../images/common/code_editor/draft-tab.png)

### Persistent Tabs and Preview Tabs

In the code editor, you can open files in persistent tabs or preview tabs.
Both types of tabs are used for actual file editing.

Clicking files in the file explorer opens tabs as follows:

- **Persistent Tab**: **Double-clicking** a file opens it as a persistent tab.\
    Persistent tabs allow you to open and edit multiple files simultaneously.\
    Files with unsaved changes display an asterisk (*) on the tab.

  ![image](../../images/common/code_editor/pinned-tab.png)

- **Preview Tab**: **Single-clicking** a file opens it as a preview tab.\
    Preview tabs allow you to preview multiple files sequentially in a single tab.\
    Previewing a new file overwrites the previous preview content.

  ![image](../../images/common/code_editor/preview-tab.png)

You can rearrange tabs by dragging and dropping.\
You can also close tabs by middle-clicking on them.

## Find/Replace

The code editor has built-in find and replace functionality.\
Press Ctrl+F/Ctrl+H to open the find/replace dialog.

![image](../../images/common/code_editor/find-and-replace.png)

**Fields**

- **Find:** Enter the string to search for.
- **Replace:** Enter the replacement string.

**Checkboxes**

- **Match case:** When enabled, searches are case-sensitive.
- **Whole words only:** When enabled, only matches complete words.
- **Use regular expression:** When enabled, uses regex for searching.

**Direction**

- **Up:** Searches upward from the cursor position.
- **Down:** Searches downward from the cursor position.

**Buttons**

- **Next:** Moves to the next match.
- **Prev:** Moves to the previous match.
- **Find All:** Selects all matches and enters multi-cursor mode.
- **Replace:** Replaces the current match.
- **Replace All:** Replaces all matches.


## Multi-Cursor

The code editor supports multi-cursor functionality.\
Hold Ctrl and click to place multiple cursors.

![image](../../images/common/code_editor/mult-cursor.png)

Normal editing operations work in multi-cursor mode.\
For example, you can select, copy, paste, and delete.

Main keyboard shortcuts for multi-cursor mode:

| Shortcut                  | Description                    |
|---------------------------|--------------------------------|
| Ctrl+Click                | Add cursor                     |
| Ctrl+Drag                 | Add selection                  |
| Middle-Click+Drag         | Rectangle/column selection     |
| Ctrl+D                    | Next occurrence                |
| Ctrl+Shift+L              | All occurrences                |
| Alt+Shift+I               | Add cursors at line ends       |
| Escape                    | Clear cursors                  |


## Code Folding

The code editor supports Python indent-based code folding.\
Foldable blocks (such as `def`, `class`, `if`, `for`, `while`, `try`, `with`) display a chevron indicator in the gutter area next to line numbers.

- Chevron indicators appear when hovering over the fold gutter area, and fade out when the mouse leaves.
- Folded blocks always display a right-pointing chevron (›) and a placeholder summary (e.g., `... (5 lines)`).

### Fold/Unfold Operations

| Operation | Method |
|-----------|--------|
| Fold/Unfold a block | Click the chevron (˅/›) in the gutter |
| Recursive fold/unfold | Shift+Click the chevron |
| Fold current block | Ctrl+Shift+[ |
| Unfold current block | Ctrl+Shift+] |
| Fold all | Ctrl+Alt+[ or toolbar button |
| Unfold all | Ctrl+Alt+] or toolbar button |

### Integration with Other Features

- **Find/Replace**: If a search match is inside a folded region, the region is automatically unfolded.
- **Multi-cursor**: If an added cursor lands inside a folded region, the region is automatically unfolded.
- **Line operations**: Moving, duplicating, or deleting a folded header line automatically unfolds it first.

## Autocomplete

The code editor ships with [jedi](https://github.com/davidhalter/jedi)-backed autocomplete, covering the Python standard library, user variables, and Maya's `maya.cmds` / `maya.api.OpenMaya` APIs.

![image](../../images/common/code_editor/autocomplete.png)

### Triggering and Acceptance

| Action | Behavior |
|--------|----------|
| Type `.` | Opens attribute completion (e.g. `sys.` → `argv`, `exit`, `path`, ...) |
| Type an identifier char | Filters the open popup |
| ↑ / ↓ / PageUp / PageDown / Home / End | Navigate the candidate list |
| Enter / Tab | Accept the highlighted item |
| Escape | Close the popup |

Acceptance is Tab / Enter only — typing `.`, `(`, or any other character inserts it verbatim without accepting the highlighted candidate, so intermediate punctuation never triggers an unintended accept. The top row is preselected as soon as the popup opens, so Enter / Tab accept the top match without a prior Down press. The popup uses the editor's current font and size; changes via Ctrl+MouseWheel are reflected automatically.

### Candidate Ranking

Candidates whose name **starts with the typed prefix** are listed first, followed by case-insensitive substring matches elsewhere in the name. For example, typing `get` ranks `getAttr` / `getPoints` (prefix matches) above `widgetGet` (mid-name match). Within the same tier, entries are sorted by MRU and then alphabetically.

### Maya API Support

- **Bundled stubs**: `.pyi` stubs for `maya.cmds` and `maya.api.OpenMaya` are shipped per Maya version. No extra setup required.
- **Imports optional**: Typing `cmds.polyCube` in a scratch buffer works without an explicit import — the editor prepends a virtual import shim behind the scenes.
- **Recognised aliases**: `cmds`, `mc`, `maya`, `OpenMaya`, `om`, `om2`.
- **User variables**: When a user variable holds the return value of a call (e.g. `x = cmds.ls(); x.`), completions for that variable come from live `dir()` introspection.

### Numeric Literals

When `.` is preceded by a digit (`0.`, `1.5`), the editor treats it as a float literal and does not open the popup.

### MRU (Most Recently Used)

Items accepted earlier in the same session float to the top of subsequent popups. The MRU resets when the editor is closed.

### Disabling

The [Toggle Autocomplete](code_editor_toolbar.html) toolbar button or **Ctrl+Space** flips the feature on and off. While off, no jedi request is dispatched, so typing stays responsive on low-end machines. The setting is persisted across sessions. Both the button and the shortcut become no-ops when jedi is not installed.

### Performance Characteristics and Caveats

The following behaviours are intentional design trade-offs. Useful to know when deploying or debugging.

**First-completion latency**

- The **first** `cmds.` / `om.` / `OpenMaya.` completion in a session ingests the entire stub module at once and takes noticeable time: ~1 second on local SSD, ~2–6 seconds when the tool is deployed to a network drive.
- Every subsequent keystroke against the same root is served from the in-memory cache in 1–2 ms.
- `cmds` and `om` have separate caches, so each pays the first-time cost once.

**Network drive deployments**

- When the tool (or just its bundled stubs) lives on a DFS / SMB share, only the **first Maya session** pays the full populate cost.
- jedi persists its parsed stubs under `%LOCALAPPDATA%\jedi\Jedi\`, so **subsequent Maya sessions are roughly 1.5–2× faster** at populate time.
- The disk cache is keyed by the stub's absolute path and mtime — updating the stubs or moving them to a different path triggers one re-parse on the next launch.

**Completion order for dynamic (file-less) modules**

- For dynamically constructed modules that carry no `__file__` / `__path__` (common with in-house pipeline packages), the engine skips the category classification step (`param` / `keyword` / `function` / `class` / ...).
- As a result, completions for such modules fall back to **pure alphabetical order** — the "functions first, then classes, then constants" grouping is lost.
- This is a deliberate trade-off: fetching categories for a dynamic module hosted on a network share measured several seconds *per keystroke*. Every candidate is still returned correctly, only the sort order is affected.

**Plugin-loaded commands**

- Commands registered into `cmds.*` via Maya's `loadPlugin` are not picked up by an already-populated completion cache.
- To surface newly-registered commands in the popup, close and re-open the Code Editor.


## Documentation Popup

**Ctrl+Shift+Space** shows the docstring of the symbol at the caret (or the one highlighted in the completion list) in a floating window. The look is close to VS Code's hover popup — the signature, parameters, return values, raises, and examples are rendered with distinct colours.

![image](../../images/common/code_editor/autocomplete-help.png)

### Trigger and Target

| Completion list state | Target |
|-----------------------|--------|
| Open | Docstring of the **currently highlighted** candidate |
| Closed | Docstring of the identifier under the caret |

While the completion list is open, pressing ↑ / ↓ to change the selection refreshes the popup contents to match (with a small debounce).

### Dismissal

- **Escape**
- **Ctrl+Shift+Space** again (toggle)
- Completion list opens or closes (the context is considered stale, so the popup auto-closes)
- The Code Editor window is minimised or hidden

The popup never takes keyboard focus, so caret edits and completion-list navigation keep working while it's visible.

### Rendering

- **Signature line**: extracted as a leading code block; function names, parameters, and default values are syntax-highlighted.
- **Structured docstrings** (numpydoc / Google / RST): parsed via `docstring_parser`; Parameters / Returns / Raises / Examples are rendered with coloured section headers and labels.
- **Maya commands** (`cmds.polyCube`, …): the popup calls `maya.cmds.help(name)` at runtime and renders the Synopsis / Flags / Return value / Modes / Examples sections with a Maya-specific style, giving more detail than the stubs alone could carry.
- **C-implemented objects** (numpy ufuncs, OpenMaya `MFn*` methods, …): when the stubs carry no docstring, the runtime `__doc__` is used as a fallback.

### Optional Dependencies

Rich rendering uses these optional packages. The popup still works without them, but the output is simpler.

- **Pygments**: syntax highlighting (missing → plain-text code blocks).
- **docstring_parser**: structured section parsing (missing → paragraph-based plain rendering).

Both can be installed from the [Dependency Installer](dependency_installer.html).


## Special Context Menu Features

The context menu (right-click menu) has several code editor-specific features.

![image](../../images/common/code_editor/code-editor-menu.png)

### Command Help Display

You can display Maya **python (cmds)** and **OpenMaya (om)** command help in the browser from the context menu.

To display documentation, select the function name following `cmds` as shown below:

![image](../../images/common/code_editor/cmd-help.png)

After selecting, choose **Maya Help: <function_name>** from the context menu.

Supported commands are as follows.\
Help for function names following the corresponding strings will be displayed.

| Module Name          | Corresponding Strings        |
|---------------------|------------------------------|
| maya.cmds           | cmds, mc                     |
| maya.api.OpenMaya   | om, OpenMaya                 |
| maya.api.OpenMayaUI | omui, OpenMayaUI             |
| maya.api.OpenMayaAnim | oma, OpenMayaAnim          |
| maya.api.OpenMayaRender | omr, OpenMayaRender      |


### Inspect Object (Help)

You can inspect Maya objects from the context menu.

Select an object string and execute **Inspect Object: <object_name>** or **Inspect Object Help: <object_name>**.\
The object information will be displayed in the terminal.

**Inspect Object Example**

![image](../../images/common/code_editor/inspect-object.png)


### Reload

You can reload the selected module from the context menu.

Select a module string and execute **Reload Module: <module_name>**.\
The module will be reloaded.

### Add to Shelf

You can add the selected code to the active Maya shelf from the context menu.

Select the code you want to register, then choose **Add to Shelf** from the context menu.\
A shelf button will be created on the currently active shelf tab.\
This is the same feature as the toolbar's Add to Shelf button.

## Keyboard Shortcuts

Main keyboard shortcuts available in the code editor:

| Shortcut                  | Description                              |
|---------------------------|------------------------------------------|
| Ctrl+N                    | Create new file                          |
| Ctrl+S                    | Save current file                        |
| Ctrl+Shift+S              | Save all open files                      |
| Ctrl+D                    | Select next occurrence (multi-selection) |
| Ctrl+Shift+D              | Duplicate current line                   |
| Ctrl+Shift+K              | Delete current line                      |
| Ctrl+L                    | Select current line (repeat to extend)   |
| Ctrl+Shift+Up/Down        | Move line up/down                        |
| Ctrl+/                    | Toggle line comment                      |
| Tab / Shift+Tab           | Indent/unindent selection                |
| Enter                     | Smart newline with auto-indent           |
| Ctrl+Click                | Add cursor at click position             |
| Ctrl+Drag                 | Add selection (drag to select different code) |
| Middle-Click+Drag         | Rectangle/column selection               |
| Ctrl+D                    | Select word and add next occurrence      |
| Ctrl+Shift+L              | Select all occurrences of current word   |
| Alt+Shift+I               | Add cursors at end of lines in selection |
| Escape                    | Clear all multi-cursors                  |
| Ctrl+F                    | Find dialog                              |
| Ctrl+H                    | Replace dialog                           |
| F3 / Shift+F3             | Find next/previous                       |
| Ctrl+Enter                | Execute current line or selection        |
| Numpad Enter              | Execute current script (same as Run button) |
| Ctrl+Shift+Enter          | Execute entire file                      |
| Ctrl+Shift+[              | Fold current block                       |
| Ctrl+Shift+]              | Unfold current block                     |
| Ctrl+Alt+[                | Fold all                                 |
| Ctrl+Alt+]                | Unfold all                               |
| Ctrl+Space                | Toggle autocomplete on/off               |
| Ctrl+Shift+Space          | Toggle documentation popup               |
| Ctrl+K                    | Clear terminal output                    |
| Ctrl+MouseWheel           | Adjust font size                         |
