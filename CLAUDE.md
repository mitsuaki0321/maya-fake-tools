# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maya tools package that extends Autodesk Maya through plugins and scripts. The project uses Maya's module system (`.mod` file) for integration.

## Project Structure

- **faketools.mod**: Maya module descriptor defining package paths
  - Module name: `maya_fake_tools` version 1.0.0
  - Declares paths: `plug-ins: .\plug-ins` and `scripts: .\scripts`
- **plug-ins/**: Maya plugins (Python/C++ API plugins)
- **scripts/**: Maya scripts (Python/MEL)

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

## Workflow

**Always run Ruff at the end of any code changes:**
```bash
uv run ruff format .
uv run ruff check . --fix
```
