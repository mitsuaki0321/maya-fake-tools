# Maya Fake Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

English | [日本語](README_JP.md)

A collection of production-ready tools for Autodesk Maya, featuring rigging, modeling, and animation utilities with a plugin-based architecture.

## Features

**Rigging Tools**
- Skin weights management (copy, paste, relax, mirror)
- Component selection and membership tools
- Transform creation and manipulation
- Remote sliders and driven keys

**Modeling Tools**
- Bounding box creator
- Mesh and transform retargeting

**Common Tools**
- Node stocker for quick access
- Attribute management

## Installation

1. Download the latest release from [Releases](https://github.com/mitsuaki0321/maya-fake-tools/releases)
2. Extract `maya-fake-tools_vX.X.X.zip` to a directory (e.g., `C:/maya_tools/`)
3. Add the extracted directory to Maya's `MAYA_MODULE_PATH` environment variable:
   - **Windows**: `set MAYA_MODULE_PATH=C:/maya_tools;%MAYA_MODULE_PATH%`
   - **Linux/Mac**: `export MAYA_MODULE_PATH=/path/to/maya_tools:$MAYA_MODULE_PATH`
4. Restart Maya
5. Open Maya's Script Editor and run:
   ```python
   import faketools.menu
   faketools.menu.add_menu()
   ```
6. The "FakeTools" menu will appear in Maya's main menu bar

## Documentation

Open `docs/index.html` in your web browser for comprehensive documentation with screenshots and usage examples.

Available in:
- 🇯🇵 Japanese
- 🇬🇧 English

## Requirements

- Autodesk Maya 2022 or later
- Python 3.11+ (included in Maya)
- numpy (included in Maya 2022+)
- scipy (included in Maya 2022+)

**Note**: numpy and scipy are included by default in Maya 2022 and later versions.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
