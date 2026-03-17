# Maya Fake Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

English | [日本語](README_JP.md)

A collection of production-ready tools for Autodesk Maya, featuring rigging, modeling, and animation utilities.

## Features

**Rigging Tools**
- Skin weights management (copy/paste, transfer between influences, import/export, robust weight transfer)
- Proxy geometry builder for joint-based mesh separation
- Transform connection, creation, and snapping
- Transform creation along curves
- Curve/surface creation (offset curve, loft surface)
- Remote attribute slider and driven key tools
- Connection and attribute listing
- Component Tag membership management

**Modeling Tools**
- Non-rigid ICP mesh fitting with landmark support
- BlendShape transfer between meshes
- Mesh and transform retargeting
- Bounding box creator
- Component selection and filtering
- Texture path relocator
- glTF/GLB mesh importer (via Blender)

**Animation Tools**
- Video player synchronized with Maya timeline
- Photoshop-like layer compositing on Maya viewports

**Common Tools**
- Python code editor with syntax highlighting and Maya integration
- Selecter for selection filtering, hierarchical selection, and batch renaming
- Node stocker for quick access
- Scene optimizer for cleanup operations
- Snapshot capture from viewport
- Dependency installer for optional libraries

**Single Commands** — 22 quick-access commands for common operations (snap, freeze, mirror joints, copy weights, etc.)

## Quick Start

1. Download the latest release from [Releases](https://github.com/mitsuaki0321/maya-fake-tools/releases)
2. Extract `maya-fake-tools_vX.X.X.zip` to a directory (e.g., `C:/maya_tools/`)
3. Add the extracted directory to Maya's `MAYA_MODULE_PATH` environment variable
4. Restart Maya
5. Open Maya's Script Editor and run:
   ```python
   import faketools.menu
   faketools.menu.add_menu()
   ```
6. The "FakeTools" menu will appear in Maya's main menu bar

For detailed setup instructions including environment variable configuration, Python library installation, ffmpeg, and OpenRV setup, see the **[Installation Guide](INSTALL.md)**.

## Documentation

Open `docs/index.html` in your web browser for comprehensive documentation with screenshots and usage examples.

Available in:
- 🇯🇵 Japanese
- 🇬🇧 English

## Requirements

- Autodesk Maya 2023 or later
- Python 3.9+ (included in Maya)

### Third-Party Library Dependencies

Some tools require additional libraries that are not included in Maya by default.
These tools will not launch if the required libraries are not installed.

| Tool | Category | Required Libraries |
|------|----------|-------------------|
| Bounding Box Creator | Model | numpy, scipy |
| Retarget Mesh | Model | numpy, scipy |
| Retarget Transforms | Model | numpy |
| Mesh Fitter | Model | trimesh, rtree, fast-simplification |
| BlendShape Transfer | Model | trimesh, rtree, fast-simplification |
| Snapshot Capture | Common | Pillow |
| VP Compositor | Anim | Pillow |

The following libraries are optional. The tool will work without them using a fallback implementation, but installing them provides better performance.

| Tool | Category | Optional Libraries |
|------|----------|--------------------|
| Snapshot Capture | Common | aggdraw, mss |
| Robust Weight Transfer | Rig | robust-laplacian |

These libraries can be installed using the built-in **Dependency Installer** (FakeTools > Common > Dependency Installer). See the **[Installation Guide](INSTALL.md)** for step-by-step instructions.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
