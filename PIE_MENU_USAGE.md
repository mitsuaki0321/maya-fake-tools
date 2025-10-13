# PieMenu Widget - Usage Guide

A directional pie menu widget for Maya tools with support for 2, 4, or 8 segments.

## Features

- **Multiple segment counts**: 2, 4, or 8 directional segments
- **Fixed directions**: Cardinal (Up, Down, Left, Right) and diagonal (UpRight, UpLeft, DownRight, DownLeft)
- **Empty segments**: Use `None` for segments without actions (no text displayed)
- **Customizable trigger**: Left-click, middle-click, or right-click
- **Muscle memory friendly**: Consistent directional layout for fast operation
- **Clean design**: Professional look with anti-aliased graphics

## Quick Start

### Basic Usage with PieMenuButton

```python
from faketools.lib_ui import PieMenuButton
from faketools.lib_ui.qt_compat import QPushButton, Qt

class MyButton(PieMenuButton, QPushButton):
    def __init__(self):
        super().__init__("My Button")

        # Setup 4-segment pie menu (Up, Right, Down, Left)
        self.setup_pie_menu(
            items=[
                {"label": "Register", "callback": self.on_register},
                {"label": "Select", "callback": self.on_select},
                {"label": "Clear", "callback": self.on_clear},
                None,  # Empty segment (Left direction)
            ],
            trigger_button=Qt.MouseButton.MiddleButton
        )

    def on_register(self):
        print("Register action")

    def on_select(self):
        print("Select action")

    def on_clear(self):
        print("Clear action")
```

### Direct PieMenu Usage

```python
from faketools.lib_ui import PieMenu

# Create menu items
items = [
    {"label": "Up Action", "callback": lambda: print("Up")},
    {"label": "Down Action", "callback": lambda: print("Down")},
]

# Show pie menu at cursor
menu = PieMenu(items, parent=self)
menu.show_at_cursor()
```

## Segment Counts and Directions

### 2 Segments (Vertical)
```python
items = [
    {"label": "Up Action", "callback": ...},      # Up
    {"label": "Down Action", "callback": ...},    # Down
]
```

**Use case**: Simple binary choices (Register/Clear, On/Off, etc.)

### 4 Segments (Cardinal Directions)
```python
items = [
    {"label": "Up Action", "callback": ...},      # Up
    {"label": "Right Action", "callback": ...},   # Right
    {"label": "Down Action", "callback": ...},    # Down
    {"label": "Left Action", "callback": ...},    # Left
]
```

**Use case**: Basic tool operations with 3-4 main actions

### 8 Segments (Cardinal + Diagonal)
```python
items = [
    {"label": "Up", "callback": ...},             # Up
    {"label": "UpRight", "callback": ...},        # UpRight (45°)
    {"label": "Right", "callback": ...},          # Right (90°)
    {"label": "DownRight", "callback": ...},      # DownRight (135°)
    {"label": "Down", "callback": ...},           # Down (180°)
    {"label": "DownLeft", "callback": ...},       # DownLeft (225°)
    {"label": "Left", "callback": ...},           # Left (270°)
    {"label": "UpLeft", "callback": ...},         # UpLeft (315°)
]
```

**Use case**: Power users with many operations

## Empty Segments

Use `None` to create segments without text or actions. Useful when you don't need all directions:

```python
items = [
    {"label": "Register", "callback": ...},  # Up
    {"label": "Select", "callback": ...},    # Right
    {"label": "Clear", "callback": ...},     # Down
    None,                                    # Left (empty, no action)
]
```

## Mouse Button Configuration

```python
# Middle-click trigger (default)
self.setup_pie_menu(
    items=[...],
    trigger_button=Qt.MouseButton.MiddleButton
)

# Left-click trigger
self.setup_pie_menu(
    items=[...],
    trigger_button=Qt.MouseButton.LeftButton
)

# Right-click trigger
self.setup_pie_menu(
    items=[...],
    trigger_button=Qt.MouseButton.RightButton
)
```

### Multiple Mouse Buttons

You can set up different pie menus for different mouse buttons by calling `setup_pie_menu` multiple times:

```python
class MyButton(PieMenuButton, QPushButton):
    def __init__(self):
        super().__init__("My Button")

        # Middle-click: 2-way menu
        self.setup_pie_menu(
            items=[
                {"label": "Register", "callback": self.on_register},
                {"label": "Clear", "callback": self.on_clear},
            ],
            trigger_button=Qt.MouseButton.MiddleButton
        )

        # Right-click: 4-way menu
        self.setup_pie_menu(
            items=[
                {"label": "Action 1", "callback": self.on_action1},
                {"label": "Action 2", "callback": self.on_action2},
                None,  # Empty
                None,  # Empty
            ],
            trigger_button=Qt.MouseButton.RightButton
        )
```

## Customization

### Menu Size

```python
self.setup_pie_menu(
    items=[...],
    outer_radius=150,  # Default: 130
    inner_radius=40    # Default: 35
)
```

### Item Format

Items can be strings or dictionaries:

```python
# String format (display only, no callback)
items = ["Action 1", "Action 2"]

# Dictionary format (full control)
items = [
    {
        "label": "Action 1",      # Text to display
        "callback": self.action1  # Function to call
    },
    {
        "label": "Action 2",
        "callback": lambda: print("Action 2")
    }
]

# Mixed format
items = [
    "Display Only",                              # No action
    {"label": "Action", "callback": self.act},  # With action
    None                                         # Empty segment
]
```

## Complete Example

```python
from faketools.lib_ui import PieMenuButton
from faketools.lib_ui.qt_compat import QPushButton, Qt
import maya.cmds as cmds

class NodeStockerButton(PieMenuButton, QPushButton):
    """Button with pie menu for node operations."""

    def __init__(self, node_data=None, parent=None):
        super().__init__("Node Slot", parent)
        self.node_data = node_data

        # Setup 4-segment pie menu
        self.setup_pie_menu(
            items=[
                {"label": "Register", "callback": self.register_nodes},
                {"label": "Select", "callback": self.select_nodes},
                {"label": "Clear", "callback": self.clear_nodes},
                None,  # Empty segment (Left)
            ],
            trigger_button=Qt.MouseButton.MiddleButton,
            outer_radius=130,
            inner_radius=35
        )

    def register_nodes(self):
        """Register selected nodes to this button."""
        selection = cmds.ls(selection=True)
        if selection:
            self.node_data = selection
            self.setText(f"{len(selection)} nodes")
            cmds.inViewMessage(
                amg=f"Registered <hl>{len(selection)}</hl> nodes",
                pos="topCenter",
                fade=True
            )

    def select_nodes(self):
        """Select nodes stored in this button."""
        if self.node_data:
            cmds.select(self.node_data)
            cmds.inViewMessage(
                amg=f"Selected <hl>{len(self.node_data)}</hl> nodes",
                pos="topCenter",
                fade=True
            )

    def clear_nodes(self):
        """Clear stored nodes."""
        self.node_data = None
        self.setText("Node Slot")
        cmds.inViewMessage(
            amg="<hl>Cleared</hl> registration",
            pos="topCenter",
            fade=True
        )
```

## Testing

Run the test window to try different segment counts and mouse buttons:

```python
import sys
sys.path.insert(0, r"D:\claude\maya-fake-tools\scripts")
import test_marking_menu_pie_8way
test_marking_menu_pie_8way.show_test_window()
```

The test window demonstrates:
- **2 segments** with middle-click
- **4 segments** with right-click (including empty segment)
- **8 segments** with left-click (including empty segment)

## Design Guidelines

### Recommended Layouts

**2 Segments:**
- Up: Primary action (Register, On, Create)
- Down: Opposite action (Clear, Off, Delete)

**4 Segments:**
- Up: Primary action (Register, most frequent)
- Right: Secondary action (Select, next frequent)
- Down: Destructive action (Clear, Delete)
- Left: Info or utility (Info, Settings, or empty)

**8 Segments:**
- Cardinal directions (Up, Right, Down, Left): Main actions
- Diagonal directions (UpRight, DownRight, DownLeft, UpLeft): Secondary actions
- Keep related actions near each other (e.g., Copy at UpRight, Paste at DownRight)

### Muscle Memory Tips

1. **Consistent placement**: Always put the same action in the same direction across your tools
2. **Frequency-based**: Most frequent actions in cardinal directions (easier to reach)
3. **Symmetry**: Use opposite directions for opposite actions (Register↑ / Clear↓)
4. **Related pairs**: Group related actions (Copy/Paste on the right side)

## API Reference

### PieMenu Class

```python
PieMenu(items, parent=None, outer_radius=130, inner_radius=35)
```

**Parameters:**
- `items` (list): Menu items (str, dict, or None)
- `parent` (QWidget): Parent widget
- `outer_radius` (int): Outer radius in pixels
- `inner_radius` (int): Inner circle radius in pixels

**Methods:**
- `show_at_cursor()`: Show menu at current cursor position

**Signals:**
- `item_selected(str)`: Emitted when item is selected (label as argument)

### PieMenuButton Mixin

```python
setup_pie_menu(items, trigger_button=Qt.MouseButton.MiddleButton,
               outer_radius=130, inner_radius=35)
```

**Parameters:**
- `items` (list): Menu items
- `trigger_button` (Qt.MouseButton): Mouse button to trigger menu
- `outer_radius` (int): Outer radius in pixels
- `inner_radius` (int): Inner circle radius in pixels

**Important:**
- `PieMenuButton` is a true mixin class (does not inherit from any base class)
- Always use as the first base class in multiple inheritance: `class MyButton(PieMenuButton, QPushButton)`

## Integration with FakeTools

PieMenu is part of the FakeTools lib_ui package:

```python
# Import from lib_ui
from faketools.lib_ui import PieMenu, PieMenuButton

# Available alongside other UI utilities
from faketools.lib_ui import (
    BaseMainWindow,
    PieMenu,
    PieMenuButton,
    error_handler,
    undo_chunk,
)
```

Use in your tool's UI layer (`ui.py`) to add quick-access menus to buttons and widgets.
