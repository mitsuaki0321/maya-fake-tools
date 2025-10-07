# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maya tools package that extends Autodesk Maya through plugins and scripts using a plugin-based architecture with automatic tool discovery and registration. The project uses Maya's module system (`.mod` file) for integration.

## Core Architecture

### FakeTools Framework Components

1. **Tool Registry System** ([scripts/faketools/core/registry.py](scripts/faketools/core/registry.py))
   - `ToolRegistry`: Automatically discovers and registers tools from `tools/` directory
   - `get_registry()`: Access global singleton registry instance
   - Discovers tools by scanning for `TOOL_CONFIG` dictionaries in tool `__init__.py` files
   - Alternative: Auto-detects `BaseTool` subclasses if no config found

2. **Menu System** ([scripts/faketools/menu.py](scripts/faketools/menu.py))
   - Creates dynamic "FakeTools" menu in Maya's main menu bar
   - Automatically organizes tools by category (rig/model/anim/common)
   - Functions: `add_menu()`, `remove_menu()`, `reload_menu()`

3. **Qt Compatibility Layer** ([scripts/faketools/lib_ui/qt_compat.py](scripts/faketools/lib_ui/qt_compat.py))
   - Provides unified imports for PySide2 (Maya 2022-) and PySide6 (Maya 2023+)
   - All Qt imports must use this module, never import PySide2/6 directly
   - Provides helper functions: `get_open_file_name()`, `get_save_file_name()`

4. **Maya UI Decorators** ([scripts/faketools/lib_ui/maya_ui.py](scripts/faketools/lib_ui/maya_ui.py))
   - `@error_handler`: Catches errors and displays in Maya dialog (UI layer only)
   - `@undo_chunk(name)`: Groups operations into single undo operation (UI layer only)
   - `@disable_undo`: Disables undo for query operations (UI layer only)
   - `get_maya_window()`: Returns Maya main window as Qt parent widget

5. **BaseTool** ([scripts/faketools/core/base/tool.py](scripts/faketools/core/base/tool.py))
   - Optional base class for tools (inheritance not required)
   - Provides standard metadata structure
   - TOOL_CONFIG approach is preferred over BaseTool inheritance

6. **Logging System** ([scripts/faketools/logging_config.py](scripts/faketools/logging_config.py))
   - Centralized logging for entire package under `faketools` logger
   - Auto-initialized on package import via `__init__.py`
   - Functions: `setup_logging(level, detailed)`, `set_log_level(level)`, `get_log_level()`
   - All modules use `logging.getLogger(__name__)` for automatic hierarchy
   - See [LOGGING_USAGE.md](LOGGING_USAGE.md) for detailed guide

7. **Settings System** (3 independent systems for different purposes)
   - **Global Config** ([scripts/faketools/config.py](scripts/faketools/config.py)): FakeTools-wide settings stored in JSON at `~/Documents/maya/faketools/config.json`
     - **Requires `MAYA_APP_DIR` environment variable** - throws `RuntimeError` if not set
     - Data directory: `$MAYA_APP_DIR/faketools_workspace`
   - **ToolOptionSettings** ([scripts/faketools/lib_ui/optionvar.py](scripts/faketools/lib_ui/optionvar.py)): Per-tool settings in Maya optionVar with JSON serialization
     - Includes convenience methods: `get_window_geometry()`, `set_window_geometry()`
     - Use this for all tool UI preferences (window size, checkbox states, etc.)
   - **Tool Data Manager** ([scripts/faketools/lib_ui/tool_data.py](scripts/faketools/lib_ui/tool_data.py)): Per-tool data directory management for files
   - See [SETTINGS_USAGE.md](SETTINGS_USAGE.md) for detailed guide

## Tool Structure

Tools are organized under [scripts/faketools/tools/](scripts/faketools/tools/) by category:
- `rig/`: Rigging tools
- `model/`: Modeling tools
- `anim/`: Animation tools
- `common/`: Common/utility tools

Each tool follows this structure:
```
tools/{category}/{tool_name}/
├── __init__.py      # TOOL_CONFIG dict + exports
├── ui.py           # UI layer with show_ui() function
└── command.py      # Business logic (Maya operations)
```

### Layer Separation Pattern

**IMPORTANT**: Tools must separate UI and business logic:

- **UI Layer** (`ui.py`): User interaction, decorators, Qt widgets
  - Must define `show_ui()` function (called by menu system)
  - Use decorators: `@error_handler`, `@undo_chunk`, `@disable_undo`
  - Calls functions in command layer

- **Command Layer** (`command.py`): Pure Maya operations
  - NO decorators allowed (pure functions)
  - Returns results to UI layer
  - No error dialogs, only return values/raise exceptions

### Tool Registration

Tools must define `TOOL_CONFIG` in `__init__.py`:
```python
TOOL_CONFIG = {
    "name": "Tool Display Name",
    "version": "1.0.0",
    "description": "Tool description",
    "menu_label": "Menu Item Label",
    "requires_selection": False,
    "author": "Author Name",
    "category": "rig",  # rig/model/anim/common
}
```

## Project Structure

- **faketools.mod**: Maya module descriptor defining package paths
  - Module name: `maya_fake_tools` version 1.0.0
  - Declares paths: `plug-ins: .\plug-ins` and `scripts: .\scripts`
- **plug-ins/**: Maya plugins (currently empty, planned for future)
- **scripts/faketools/**: Main package
  - `core/`: Framework core (registry, base classes)
  - `lib/`: Shared utilities (planned for future)
  - `lib_ui/`: UI utilities (Qt compat, Maya decorators, widgets)
  - `tools/`: Category-organized tools
  - `menu.py`: Menu system

## Development Commands

### Linting and Formatting
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix
```

## Code Standards

- Python 3.11.4 (specified in `.python-version`)
- Line length: 150 characters
- Ruff linting: E, F, UP, B, SIM, I rules enabled (ignoring E203, E501, E701, SIM108)
- Double quotes, space indentation
- Import sorting with combined imports
- **Docstrings: Google style** - All docstrings must follow Google style format

## Docstring Format (Google Style)

All docstrings in this project must follow Google style:

```python
def function_name(arg1: str, arg2: int) -> bool:
    """
    Brief description of the function.

    Longer description if needed. Can span multiple lines.

    Args:
        arg1 (str): Description of arg1
        arg2 (int): Description of arg2

    Returns:
        bool: Description of return value

    Raises:
        ValueError: Description of when this is raised

    Example:
        >>> function_name("test", 5)
        True
    """
    pass
```

For classes:
```python
class ClassName:
    """
    Brief description of the class.

    Longer description if needed.

    Attributes:
        attr1: Description of attr1
        attr2: Description of attr2
    """
    pass
```

## Import Patterns

### Relative Imports (within tools)
```python
from . import command              # Same tool's command.py
from .ui import MainWindow         # Same tool's ui.py
```

### Global Library Imports (from tool files)
```python
# From tools/{category}/{tool_name}/ui.py to lib_ui (4 levels up):
from ....lib_ui.qt_compat import QWidget, QPushButton
from ....lib_ui.maya_ui import error_handler, get_maya_window, undo_chunk
```

### CRITICAL: Never Import PySide Directly
```python
# WRONG - Do not do this:
from PySide2.QtWidgets import QWidget

# CORRECT - Always use qt_compat:
from ....lib_ui.qt_compat import QWidget
```

## Creating New Tools

When creating a new tool:

1. Create directory: `tools/{category}/{tool_name}/`
2. Create `__init__.py` with `TOOL_CONFIG` and exports
3. Create `ui.py` with `MainWindow` class and `show_ui()` function
4. Create `command.py` with pure Maya operations (no decorators)
5. Test in Maya with: `import faketools.menu; faketools.menu.reload_menu()`

Refer to [scripts/faketools/tools/common/example_tool/](scripts/faketools/tools/common/example_tool/) as a template.

## Workflow

**Always run Ruff at the end of any code changes:**
```bash
uv run ruff format .
uv run ruff check . --fix
```

## Logging Management

### Change Log Level at Runtime
```python
import faketools
import logging

# Set to DEBUG for verbose output during development
faketools.set_log_level(logging.DEBUG)

# Set to INFO for normal operation (default)
faketools.set_log_level(logging.INFO)
```

### Use Logger in Modules
```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
```

## Settings Management

### Global Settings (JSON file)
```python
from faketools.config import get_global_config

config = get_global_config()
config.set_data_root_dir("D:/MyProject/maya_data")
config.set_log_level("DEBUG")
config.save()  # Must call save() to persist changes
```

### Tool Settings (Maya optionVar) - Use ToolOptionSettings
```python
from faketools.lib_ui.optionvar import ToolOptionSettings

settings = ToolOptionSettings(__name__)
settings.write("window_size", [800, 600])
size = settings.read("window_size", [400, 300])

# Window geometry helpers
settings.set_window_geometry([800, 600], [100, 100])
geometry = settings.get_window_geometry()
```

### Tool Data Files (filesystem)
```python
from faketools.lib_ui.tool_data import ToolDataManager

data_manager = ToolDataManager("skin_weights", "rig")
data_manager.ensure_data_dir()
file_path = data_manager.get_data_path("character_a.json")
```

## Future Work

- **Plugins directory**: Currently empty, planned for future C++ plugins

## Additional Documentation

- **[DEVELOP.md](DEVELOP.md)**: Detailed Japanese documentation covering internal architecture, best practices, and troubleshooting
- **[SETTINGS_USAGE.md](SETTINGS_USAGE.md)**: Settings system usage guide (Japanese)
- **[LOGGING_USAGE.md](LOGGING_USAGE.md)**: Logging system usage guide (Japanese)
- **Example Tool**: [scripts/faketools/tools/common/example_tool/](scripts/faketools/tools/common/example_tool/) demonstrates complete tool structure
