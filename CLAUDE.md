# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maya tools package that extends Autodesk Maya through plugins and scripts using a plugin-based architecture with automatic tool discovery and registration. The project uses Maya's module system (`.mod` file) for integration.

## External Dependencies

### Allowed Libraries (Runtime)

**Python Standard Library:**
- All built-in modules are allowed (e.g., `os`, `sys`, `json`, `math`, `re`, `logging`, etc.)

**Maya-Provided Libraries:**
- **Maya Python API** (`maya.cmds`, `maya.api.OpenMaya`) - Required, provided by Maya
- **PySide2** (Maya 2022 and earlier) - Qt bindings for UI
- **PySide6** (Maya 2023+) - Qt bindings for UI
- **numpy** - Numerical operations (included in Maya 2022+)
- **scipy** - Scientific computing (included in Maya 2022+)

**CRITICAL RULES:**
- ✅ **ONLY use libraries listed above**
- ❌ **DO NOT add external dependencies** (e.g., scikit-learn, pandas, requests, etc.)
- ❌ **DO NOT use `pip install` or similar** for runtime dependencies
- 💡 **Implement algorithms manually** using numpy/scipy if needed (see `lib_cluster.py` for K-means/DBSCAN examples)

### Development Dependencies

**Development-Only Libraries (not used in runtime code):**
- **ruff** - Code formatting and linting
- **mypy** - Import validation (type checking disabled)
- **numpy, scipy** - Used only for testing/benchmarking

**Important Notes:**
- **NO scikit-learn dependency**: All clustering algorithms (`lib_cluster.py`) are implemented using numpy only
- **Maya 2022+** includes numpy and scipy by default
- External Python packages cannot be easily added to Maya's Python environment
- When implementing new features, check if required algorithms can be implemented with allowed libraries first

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
   - Tools within each category are sorted by `menu_order` (ascending), then alphabetically
   - Functions: `add_menu()`, `remove_menu()`, `reload_menu()`

3. **Qt Compatibility Layer** ([scripts/faketools/lib_ui/qt_compat.py](scripts/faketools/lib_ui/qt_compat.py))
   - Provides unified imports for PySide2 (Maya 2022-) and PySide6 (Maya 2023+)
   - All Qt imports must use this module, never import PySide2/6 directly
   - Provides helper functions: `get_open_file_name()`, `get_save_file_name()`

4. **Maya UI Libraries** ([scripts/faketools/lib_ui/](scripts/faketools/lib_ui/))
   - **base_window.py**: Base window classes
     - `BaseMainWindow`: Standard QMainWindow base class with resolution-independent spacing
     - `BaseFramelessWindow`: Frameless window with custom title bar for compact tools
     - `get_spacing(widget, direction)`: Get style-based spacing (resolution-independent)
     - `get_margins(widget)`: Get style-based margins (resolution-independent)
   - **pie_menu.py**: Directional pie menu widget
     - `PieMenu`: Popup pie menu with 2, 4, or 8 directional segments
     - `PieMenuButton`: True mixin class (no base class) to add pie menu to any widget
       - **IMPORTANT**: Always use as first base class in multiple inheritance
       - Example: `class MyButton(PieMenuButton, QPushButton)`
     - Supports customizable mouse button triggers (left, middle, right)
     - See [PIE_MENU_USAGE.md](PIE_MENU_USAGE.md) for detailed guide
   - **maya_decorator.py**: UI decorators
     - `@error_handler`: Catches errors and displays in Maya dialog (UI layer only)
     - `@undo_chunk(name)`: Groups operations into single undo operation (UI layer only)
     - `@disable_undo`: Disables undo for query operations (UI layer only)
     - `@repeatable(label)`: Makes UI methods repeatable with Maya's repeat last command (G key)
   - **maya_dialog.py**: Dialog helpers
     - `show_error_dialog()`, `show_warning_dialog()`, `show_info_dialog()`, `confirm_dialog()`
   - **maya_ui.py**: Maya UI functions
     - `get_channels()`: Get attributes from channel box
     - `get_modifiers()`: Get current modifier keys (Shift, Ctrl, Alt)
     - `ProgressBar`: Context manager for Maya's main progress bar with cancellation support
   - **maya_qt.py**: Qt-Maya conversion utilities
     - `qt_widget_from_maya_control()`: Convert Maya control to Qt widget
     - `maya_name_from_qt_widget()`: Get Maya name from Qt widget
     - `qt_widget_from_maya_window()`: Convert Maya window to Qt widget
     - `get_maya_main_window()`: Get Maya main window as Qt parent
   - **icons.py**: Icon resource utilities
     - `get_path(picture_name)`: Get absolute path to icon PNG files from lib_ui/images/
   - **widgets/**: Additional UI widgets
     - `extra_widgets.py`: Extended UI widgets (various specialized widgets)
     - `nodeAttr_widgets.py`: Node attribute widgets for Maya node manipulation

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
   - **ToolSettingsManager** ([scripts/faketools/lib_ui/tool_settings.py](scripts/faketools/lib_ui/tool_settings.py)): **RECOMMENDED** - JSON-based per-tool settings with preset support
     - Save/load/delete/rename presets
     - Export/import presets to external files
     - Settings stored in: `{data_root}/{category}/{tool_name}/settings/{preset_name}.json`
     - Best for tools that need preset functionality or shareable configurations
   - **ToolOptionSettings** ([scripts/faketools/lib_ui/optionvar.py](scripts/faketools/lib_ui/optionvar.py)): Per-tool settings in Maya optionVar with JSON serialization
     - Includes convenience methods: `get_window_geometry()`, `set_window_geometry()`
     - Best for simple tool UI preferences (window size, checkbox states, etc.)
     - Stored in Maya's native optionVar system (not portable)
   - **ToolDataManager** ([scripts/faketools/lib_ui/tool_data.py](scripts/faketools/lib_ui/tool_data.py)): Per-tool data directory management for files
     - Use for managing tool-specific data files (not settings)
   - See [SETTINGS_USAGE.md](SETTINGS_USAGE.md) for detailed guide

8. **Shared Utilities** ([scripts/faketools/lib/](scripts/faketools/lib/))
   - **lib_attribute.py**: Maya attribute utilities
     - `is_modifiable(node, attribute)`: Check if attribute can be modified (not locked/connected)
     - `get_channelBox_attr(node)`: Get channel box visible attributes
     - `AttributeLockHandler`: Context manager for temporarily unlocking attributes
   - **lib_name.py**: String and naming utilities
     - `num_to_alpha(num)`, `alpha_to_num(alpha)`: Convert between numbers and letters
     - `solve_names(names, regex_name)`: Generate names with @/#/~ placeholders
     - `get_namespace(name)`, `get_without_namespace(name)`: Namespace handling
     - `replace_namespaces(names, namespace)`: Replace namespaces in names
   - **lib_selection.py**: Node selection and filtering utilities
     - `NodeFilter`: Filter nodes by type or regex pattern
     - `DagHierarchy`: Navigate DAG hierarchy (parent, children, siblings, shapes)
     - `SelectionMode`: Manage Maya's object/component selection modes
     - `HiliteSelection`: Manage hilite selection state
     - `restore_selection()`: Context manager to restore selection
   - **lib_memberShip.py**: Component membership and deformer utilities
     - `ComponentTags`: Manage Maya component tags (create, query, add, remove)
     - `DeformerMembership`: Manage deformer membership with component tags
     - `is_use_component_tag()`: Check if component tags are enabled in preferences
     - `remove_deformer_blank_indices(deformer)`: Clean up deformer indices
   - **lib_cluster.py**: Clustering algorithms (K-means, DBSCAN) implemented with numpy only
   - **lib_mesh*.py**: Mesh utilities (face, edge, point, vertex, conversion)
   - **lib_nurbsCurve*.py**: NURBS curve utilities (positions, conversion)
   - **lib_skinCluster.py**: Skin cluster utilities
   - **lib_keyframe.py**: Animation keyframe utilities
   - And more... (see [scripts/faketools/lib/](scripts/faketools/lib/) for complete list)

9. **Single Commands** ([scripts/faketools/single_commands/](scripts/faketools/single_commands/))
   - Standalone command classes that can be executed directly without UI
   - Automatically registered in "Single Commands" submenu under FakeTools menu
   - **Base Classes** ([single_commands/base_commands.py](scripts/faketools/single_commands/base_commands.py)):
     - `SceneCommand`: Base class for scene-wide operations (auto-executes on init)
     - `AllCommand`: Base class for operations on all selected nodes
     - `PairCommand`: Base class for operations between source and target node pairs

10. **Operations** ([scripts/faketools/operations/](scripts/faketools/operations/))
   - High-level operations that combine multiple `lib` utilities
   - **IMPORTANT RULES**:
     - Operations **CAN** depend on `lib` modules
     - Operations **CANNOT** depend on each other
     - Each operation module should have a **single, focused responsibility**
     - Operations are **lib modules that depend on other lib modules**
   - **Architecture Hierarchy**:
     - `lib/` → Basic utilities (no dependencies within lib)
     - `operations/` → High-level operations (can use lib)
     - `single_commands/` → Standalone commands (can use lib and operations)
     - `tools/*/command.py` → Tool-specific commands (can use lib, operations, and single_commands)
   - **Current Operations**:
     - **mirror.py**: Transform mirroring operations
       - `mirror_transforms(node, axis, mirror_position, mirror_rotation, space)`: Mirror node transform across axis
         - `space="world"`: Mirror in world space
         - `space="local"`: Mirror in local space (relative to parent)
     - **component_selection.py**: Component selection utilities
     - **convert_weight.py**: Weight conversion utilities
     - **create_transforms/**: Transform creation operations with multiple position strategies

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

### Recommended UI Pattern

**UI Layer Structure** (see [transform_connector/ui.py](scripts/faketools/tools/rig/transform_connector/ui.py) as reference):

```python
"""Tool UI layer."""

import logging

from ....lib_ui import (
    BaseMainWindow,
    ToolOptionSettings,
    error_handler,
    get_maya_main_window,
    undo_chunk,
)
from ....lib_ui.qt_compat import QPushButton, QVBoxLayout
from . import command

logger = logging.getLogger(__name__)
_instance = None  # Global instance for singleton pattern


class MainWindow(BaseMainWindow):
    """Main window for the tool."""

    def __init__(self, parent=None):
        """Initialize the window."""
        super().__init__(
            parent=parent,
            object_name="MyToolMainWindow",  # Unique name
            window_title="My Tool",
            central_layout="vertical",  # or "horizontal"
        )
        self.settings = ToolOptionSettings(__name__)
        self.setup_ui()
        self._restore_settings()

    def setup_ui(self):
        """Setup the user interface."""
        # Create widgets
        button = QPushButton("Execute")
        button.clicked.connect(self._on_execute)
        self.central_layout.addWidget(button)

    @error_handler
    @undo_chunk("My Tool: Execute")
    def _on_execute(self):
        """Handle button click."""
        # Call command layer
        result = command.execute_operation()
        logger.info(f"Operation completed: {result}")

    def _restore_settings(self):
        """Restore UI settings from saved preferences."""
        geometry = self.settings.get_window_geometry()
        if geometry:
            self.resize(*geometry["size"])
            if "position" in geometry:
                self.move(*geometry["position"])

    def _save_settings(self):
        """Save UI settings to preferences."""
        self.settings.set_window_geometry(
            size=[self.width(), self.height()],
            position=[self.x(), self.y()]
        )

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)


def show_ui():
    """Show the tool UI (entry point)."""
    global _instance

    # Close existing instance
    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    # Create new instance
    parent = get_maya_main_window()
    _instance = MainWindow(parent)
    _instance.show()
    return _instance


__all__ = ["MainWindow", "show_ui"]
```

**Key Points:**
- Inherit from `BaseMainWindow` (for standard windows) or `BaseFramelessWindow` (for compact, frameless windows)
- Use singleton pattern with global `_instance`
- Implement `_restore_settings()` and `_save_settings()` for persistence
- Use `@error_handler` and `@undo_chunk` decorators on UI callbacks
- Call command layer functions, never implement logic in UI layer
- Use `closeEvent()` to save settings before closing

**BaseFramelessWindow Alternative:**
For compact tools, use `BaseFramelessWindow` instead of `BaseMainWindow`:
```python
from ....lib_ui import BaseFramelessWindow

class MainWindow(BaseFramelessWindow):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="MyCompactToolWindow",
            window_title="Compact Tool",
            central_layout="vertical"
        )
        self.setup_ui()
```

Benefits of BaseFramelessWindow:
- No system title bar (very compact)
- Custom title bar with drag support
- Close button with hover effect
- Escape key to close
- Resolution-independent spacing

### Tool Registration

Tools must define `TOOL_CONFIG` in `__init__.py`:
```python
"""Tool description."""

TOOL_CONFIG = {
    "name": "Tool Display Name",
    "version": "1.0.0",
    "description": "Tool description",
    "menu_label": "Menu Item Label",
    "menu_order": 10,  # Optional: Controls display order in menu (default: 100)
    "requires_selection": False,
    "author": "Author Name",
    "category": "rig",  # rig/model/anim/common
}

__all__ = ["TOOL_CONFIG"]
```

**TOOL_CONFIG Parameters:**
- `name` (str): Tool display name
- `version` (str): Tool version (semantic versioning)
- `description` (str): Brief description of tool functionality
- `menu_label` (str): Label displayed in Maya menu
- `menu_order` (int, optional): Controls display order within category menu
  - Lower numbers appear first (e.g., 10 appears before 20)
  - Default value: 100 (if not specified)
  - Tools with same order are sorted alphabetically by label
  - Use increments of 10 (10, 20, 30...) to allow easy insertion of new tools
- `requires_selection` (bool): Whether tool requires Maya selection to execute
- `author` (str): Tool author name
- `category` (str): Tool category - must be one of: `rig`, `model`, `anim`, `common`

**IMPORTANT**: Do NOT import ui or command modules in `__init__.py`. Only define `TOOL_CONFIG` and `__all__`. The registry system will dynamically import ui modules when needed. This prevents import errors during tool discovery.

### Resolution-Independent UI Design

**CRITICAL RULE**: Direct pixel/size values are **PROHIBITED** except in special cases.

**Why**: UIs must work across different screen resolutions and DPI settings without modification.

#### Window Class Pattern

Always use `BaseMainWindow` or `BaseFramelessWindow` for tool windows:

**Standard window with title bar (BaseMainWindow):**
```python
from ....lib_ui import BaseMainWindow

class MainWindow(BaseMainWindow):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="MyToolMainWindow",
            window_title="My Tool",
            central_layout="vertical"  # or "horizontal"
        )
        self.setup_ui()

    def setup_ui(self):
        # Use self.central_layout (provided by BaseMainWindow)
        self.central_layout.addWidget(my_widget)
```

**Compact frameless window (BaseFramelessWindow):**
```python
from ....lib_ui import BaseFramelessWindow

class MainWindow(BaseFramelessWindow):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            object_name="MyCompactToolWindow",
            window_title="Compact Tool",  # Shown in custom title bar
            central_layout="vertical"  # or "horizontal"
        )
        self.setup_ui()

    def setup_ui(self):
        # Use self.central_layout (provided by BaseFramelessWindow)
        self.central_layout.addWidget(my_widget)
```

**Benefits of BaseMainWindow:**
- Inherits from `QMainWindow` (supports menu bar, status bar, toolbars)
- Auto-configures central widget and layout
- Sets `Qt.WA_DeleteOnClose` for proper cleanup
- Applies resolution-independent spacing automatically

**Benefits of BaseFramelessWindow:**
- Inherits from `QWidget` (lightweight, compact)
- Custom title bar with close button
- Draggable by title bar
- Escape key closes window
- Very compact design for tool palettes

#### ❌ Prohibited Patterns

```python
# WRONG - Hardcoded pixel values
self.resize(300, 100)
button.setFixedWidth(120)
layout.setSpacing(10)
layout.setContentsMargins(5, 5, 5, 5)
```

#### ✅ Correct Patterns

```python
from ....lib_ui.ui_utils import get_relative_size, get_spacing
from ....lib_ui.base_window import get_margins

# Dynamic sizing based on font metrics
width, height = get_relative_size(self, width_ratio=1.5, height_ratio=1.0)
self.resize(width, height)

# Style-based spacing
spacing = get_spacing(self, direction="vertical")
layout.setSpacing(int(spacing * 0.5))  # Half of default spacing

# Style-based margins
left, top, right, bottom = get_margins(self)
layout.setContentsMargins(left, top, right, bottom)
```

#### Available UI Utilities

**From `lib_ui.base_window`:**
- `get_spacing(widget, direction="vertical")`: Get style-based spacing
- `get_margins(widget)`: Get style-based margins (left, top, right, bottom)

**From `lib_ui.ui_utils`:**
- `get_relative_size(widget, width_ratio, height_ratio)`: Calculate size based on font metrics
- `get_default_button_size(widget)`: Get appropriate button size
- `get_text_width(text, widget)`: Calculate text width in widget's font
- `get_line_height(widget)`: Get line height for widget's font
- `scale_by_dpi(value, widget)`: Scale value for DPI (use for icon sizes)

#### Acceptable Exceptions

These cases are acceptable:
- **Multipliers on style-based values**: `spacing * 0.75`, `margin * 1.5`
- **Icon sizes with DPI scaling**: `scale_by_dpi(16)` for 16px icons
- **Minimum constraints from style values**: `setMinimumWidth(get_text_width("Label", widget))`

## Project Structure

- **faketools.mod**: Maya module descriptor defining package paths
  - Module name: `maya_fake_tools` version 1.0.0
  - Declares paths: `plug-ins: .\plug-ins` and `scripts: .\scripts`
- **plug-ins/**: Maya plugins (currently empty, planned for future)
- **scripts/faketools/**: Main package
  - `core/`: Framework core (registry, base classes)
  - `lib/`: Shared Maya utilities (basic, no inter-dependencies)
  - `operations/`: High-level operations (combines lib utilities)
  - `single_commands/`: Standalone commands (menu-accessible, no UI required)
  - `lib_ui/`: UI-specific utilities
    - `base_window.py`: BaseMainWindow and resolution utilities
    - `maya_decorator.py`: UI decorators (@error_handler, @undo_chunk, @disable_undo)
    - `maya_dialog.py`: Dialog helpers
    - `maya_qt.py`: Qt-Maya conversion utilities
    - `maya_ui.py`: Maya UI functions (get_channels, get_modifiers)
    - `tool_settings.py`: JSON-based tool settings with preset support (recommended)
    - `optionvar.py`: Maya optionVar-based tool settings (simple)
    - `tool_data.py`: Tool data directory management
    - `qt_compat.py`: PySide2/6 compatibility layer
    - `ui_utils.py`: Resolution-independent UI calculations
  - `tools/`: Category-organized tools (rig/model/anim/common)
  - `menu.py`: Menu system
  - `single_commands_menu.py`: Single commands menu system
  - `config.py`: Global configuration
  - `logging_config.py`: Logging system
  - `module_cleaner.py`: Development utility for module reloading

## Development Commands

### Environment Setup

This project uses `uv` as the package manager for development dependencies:

```bash
# Install uv (if not already installed)
pip install uv

# Sync dependencies (creates virtual environment and installs dev dependencies)
uv sync
```

### Module Cleanup (Development)
During development, you may need to reload modules after making changes. Use the module cleaner to remove all faketools modules from memory:

```python
# In Maya Script Editor
import faketools.module_cleaner
faketools.module_cleaner.cleanup()

# Or use the short alias
faketools.module_cleaner.clean()

# Then reload
import faketools
import faketools.menu
faketools.menu.add_menu()
```

This will:
1. Close all open tool windows
2. Remove the FakeTools menu
3. Remove all faketools modules from `sys.modules`
4. Force garbage collection

### Documentation Build

Build HTML documentation from Markdown sources:

```bash
# Build documentation (requires Pandoc)
python docs/build.py

# Output will be in docs/output/
# Open docs/output/index.html in browser to view
```

**Requirements**: [Pandoc](https://pandoc.org/installing.html) must be installed.

See [DOCUMENTATION.md](DOCUMENTATION.md) for detailed documentation system guide.

### Linting and Formatting

**Best Practice: Check only changed files during development**

```bash
# Format specific file or directory
uv run ruff format path/to/file.py
uv run ruff format path/to/directory/

# Lint specific file or directory
uv run ruff check path/to/file.py
uv run ruff check path/to/directory/ --fix

# Format/lint entire project (use before commits)
uv run ruff format .
uv run ruff check . --fix
```

### Import Validation

**Best Practice: Check only changed files during development**

```bash
# Check specific file
uv run mypy scripts/faketools/lib/lib_cluster.py

# Check specific directory
uv run mypy scripts/faketools/tools/rig/skin_tools/

# Check entire project (use before commits)
uv run mypy scripts/faketools

# Check for import errors only (Linux/Mac)
uv run mypy scripts/faketools 2>&1 | grep -E "(import-not-found|import-untyped)"

# Check for import errors only (Windows PowerShell)
uv run mypy scripts/faketools 2>&1 | Select-String -Pattern "import-not-found|import-untyped"
```

**Note**: mypy is configured to only check import existence. Type checking is disabled to avoid errors in legacy code. External dependencies (maya, numpy, scipy, PySide2/6) are ignored in the configuration.

## Code Standards

- Python 3.9.7 (specified in `.python-version`, matches Maya 2023)
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

**Recommended: Use consolidated imports from lib_ui**
```python
# From tools/{category}/{tool_name}/ui.py
from ....lib_ui import (
    BaseMainWindow,          # Standard window base class
    BaseFramelessWindow,     # Frameless window base class (compact)
    PieMenu,                 # Directional pie menu widget
    PieMenuButton,           # True mixin (no base class) - Use as first base class
    ToolSettingsManager,     # For preset support (recommended)
    ToolOptionSettings,      # For simple settings (alternative)
    error_handler,
    get_maya_main_window,
    undo_chunk,
)
from ....lib_ui.qt_compat import QPushButton, QVBoxLayout, QWidget

# Example of PieMenuButton usage
# class MyButton(PieMenuButton, QPushButton):  # PieMenuButton MUST be first
#     def __init__(self):
#         super().__init__("Button Text")
#         self.setup_pie_menu(items=[...], trigger_button=Qt.MouseButton.MiddleButton)
```

**Direct module imports (alternative)**
```python
# From tools/{category}/{tool_name}/ui.py
from ....lib_ui.base_window import BaseMainWindow
from ....lib_ui.maya_decorator import error_handler, undo_chunk
from ....lib_ui.maya_dialog import show_error_dialog, confirm_dialog
from ....lib_ui.maya_qt import get_maya_main_window, qt_widget_from_maya_window
from ....lib_ui.maya_ui import get_channels, get_modifiers
from ....lib_ui.optionvar import ToolOptionSettings
from ....lib_ui.qt_compat import QWidget, QPushButton
```

### Operations and Commands Imports (from tool command.py)
```python
# From tools/{category}/{tool_name}/command.py
from ...operations import mirror_transforms
from ...lib.lib_selection import DagHierarchy
from ...single_commands import SceneCommand, AllCommand, PairCommand

# Use operations for high-level reusable operations
# Use lib for basic utilities
# Use single_commands for reusable command patterns
def execute():
    # Mirror in world space
    mirror_transforms("pCube1", axis="x", space="world")

    # Mirror in local space (relative to parent)
    mirror_transforms("pCube1", axis="x", space="local")
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

## Creating New Single Commands

Create a new command class in `scripts/faketools/single_commands/` inheriting from one of the base classes:
- `SceneCommand`: For scene-wide operations (auto-executes on init)
- `AllCommand`: For operations on all selected nodes
- `PairCommand`: For operations between source and target node pairs

## Workflow

### During Development

**Recommended: Check only changed files for faster feedback**

```bash
# After editing a file
uv run ruff format path/to/changed_file.py
uv run ruff check path/to/changed_file.py --fix
uv run mypy path/to/changed_file.py
```

### Before Committing

**Required: Run checks on entire project**

```bash
# Format and lint entire project
uv run ruff format .
uv run ruff check . --fix

# Validate all imports
uv run mypy scripts/faketools
```

## Release Process

### Creating a Release

**IMPORTANT: Do NOT create release tags during regular commits.**

The project uses GitHub Actions to automatically create releases when a version tag is pushed. Release tags should only be created intentionally when you want to publish a new version.

**Release Workflow:**

1. **Complete and commit all changes** for the release
2. **Push commits to main branch** (without tags)
   ```bash
   git push origin main
   ```
3. **Create and push a release tag** (only when ready to publish)
   ```bash
   # Create a version tag (e.g., v1.0.0)
   git tag v1.0.0 -m "Release version 1.0.0"

   # Push the tag (this triggers the release workflow)
   git push origin v1.0.0
   ```

**What Happens Automatically:**
- GitHub Actions workflow (`.github/workflows/release.yml`) is triggered
- Release package is created with necessary files:
  - `docs/output/` → HTML documentation
  - `plug-ins/` → Maya plugins
  - `scripts/` → Python tools
  - `faketools.mod` → Module descriptor
  - `LICENSE`, `README.md`
- ZIP file `maya-fake-tools_{version}.zip` is created
- GitHub Release is published with auto-generated release notes
- Release asset is uploaded

**Tag Naming Convention:**
- Use semantic versioning: `v{major}.{minor}.{patch}`
- Examples: `v1.0.0`, `v1.2.3`, `v2.0.0-beta`

**NEVER do this:**
```bash
# ❌ WRONG - Do not create tags during regular commits
git add .
git commit -m "feat: Add new feature"
git tag v1.0.0  # This will trigger a release!
git push origin main --tags
```

**Always do this:**
```bash
# ✅ CORRECT - Separate commits from releases
git add .
git commit -m "feat: Add new feature"
git push origin main

# Later, when ready to release:
git tag v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

## Logging Management

See [LOGGING_USAGE.md](LOGGING_USAGE.md) for detailed guide on logging system usage, including:
- How to use loggers in modules
- Changing log levels at runtime
- Best practices for logging
- Troubleshooting logging issues

## Settings Management

See [SETTINGS_USAGE.md](SETTINGS_USAGE.md) for detailed guide on settings management, including:
- **Global Config**: FakeTools-wide settings (JSON file)
- **ToolSettingsManager**: Tool settings with preset support (RECOMMENDED)
- **ToolOptionSettings**: Simple tool settings (Maya optionVar)
- **ToolDataManager**: Tool data file management
- Usage examples and best practices

## Future Work

- **Plugins directory**: Currently empty, planned for future C++ plugins

### Potential Improvements (Not Required)

#### @repeatable Decorator Architecture Improvement

**Current Implementation:**
- `@repeatable` decorator is applied to UI layer methods
- Depends on global `_instance` variable
- Commands require UI to be open

**Proposed Improvement:**
```python
# command.py - Pure command functions with @repeatable
from ...lib_ui import repeatable, undo_chunk

@undo_chunk("Move CVs Position")
@repeatable("Move CVs Position")
def move_cvs_position_command():
    """Move curve CVs to vertex positions."""
    cvs = cmds.filterExpand(sm=28, ex=True)
    if not cvs:
        cmds.error("Select nurbsCurve CVs.")
        return

    for cv in cvs:
        move_cv_positions(cv)

# ui.py - UI calls command functions
from . import command

@error_handler
def move_cvs_position(self):
    """Move curve CVs to vertex positions."""
    command.move_cvs_position_command()
```

**Benefits:**
- ✅ Commands work without UI
- ✅ Can be called from scripts directly
- ✅ Can be registered to shelves/hotkeys
- ✅ Easier to test
- ✅ Better separation of concerns

**Considerations:**
- Requires extending `@repeatable` to support standalone functions (not just class methods)
- More complex initial setup for each tool
- May be too much overhead for tools being migrated from legacy code

**Decision:** Defer until more tools are migrated and patterns are established

## Documentation System

See [DOCUMENTATION.md](DOCUMENTATION.md) for detailed guide on the Pandoc-based multilingual documentation system, including:
- Project structure and build process
- Adding new documentation pages
- Design specifications and technologies used

## Additional Documentation

- **[DEVELOP.md](DEVELOP.md)**: Detailed Japanese documentation covering internal architecture, best practices, and troubleshooting
- **[SETTINGS_USAGE.md](SETTINGS_USAGE.md)**: Settings system usage guide (Japanese)
- **[LOGGING_USAGE.md](LOGGING_USAGE.md)**: Logging system usage guide (Japanese)
- **[DOCUMENTATION.md](DOCUMENTATION.md)**: Documentation system guide
- **[PIE_MENU_USAGE.md](PIE_MENU_USAGE.md)**: PieMenu widget usage guide with examples
