---
title: Dependency Installer
category: common
description: Install optional Python packages required by FakeTools tools
lang: en
lang-ref: dependency_installer
order: 90
---

## Overview

Dependency Installer is a tool for installing optional Python packages required by some FakeTools tools directly from within Maya.\
Instead of running `mayapy -m pip install` on the command line, you can check package status and install packages through a GUI.

Two launch methods are supported:

| Method | Description |
|--------|-------------|
| Maya menu | FakeTools > Common > Dependency Installer |
| Standalone | Double-click `install_dependencies.bat` at the repository root |


## Target Packages

| Package | Used By | Required |
|---------|---------|----------|
| numpy | Bounding Box Creator, Mesh Retargeter | Yes |
| scipy | Bounding Box Creator, Mesh Retargeter | Yes |
| trimesh | Mesh Fitter, BlendShape Transfer | Yes |
| rtree | Mesh Fitter, BlendShape Transfer | Yes |
| fast-simplification | Mesh Fitter, BlendShape Transfer | Yes |
| Pillow | Snapshot Capture | Yes |
| aggdraw | Snapshot Capture | No |
| mss | Snapshot Capture | No |


## How to Launch

### From Maya

Launch the tool from the dedicated menu or using the following command:

```python
import faketools.tools.common.dependency_installer.ui
faketools.tools.common.dependency_installer.ui.show_ui()
```

![image](../../images/common/dependency_installer/image001.png)

### Standalone

Double-click `install_dependencies.bat` at the repository root.\
It automatically detects installed Maya versions (2023-2026) and launches the UI using the latest available mayapy.


## Usage

### Basic Procedure

1. Select the target Maya version from the **Maya Version** dropdown. When launched from Maya, the current version is selected by default.

2. Choose the **Install Location** (Standard or Custom path).

3. Review the package status in the package table.

4. Check the packages you want to install, or click `Select All Missing` to select all missing packages at once.

5. Click `Install Selected` to run the installation.

6. After completion, the table is automatically refreshed.


## Maya Version Section

Select the target Maya version. Versions are detected by scanning `C:\Program Files\Autodesk\Maya*`.

- **When launched from Maya**: The currently running Maya version is selected by default. Package status is checked within the current Maya process, so paths added by `userSetup.py` are reflected.
- **When a different version is selected / Standalone**: Package status is checked by running the target version's mayapy via subprocess.


## Install Location Section

- **Standard (Maya site-packages)**: Installs to Maya's default site-packages. May require administrator privileges.
- **Custom path**: Installs to a custom directory. The actual install path is `<specified_path>/<maya_version>/site-packages/`.

When using a custom path, you need to configure a `.env` file so that FakeTools automatically loads packages from that path on startup (see below).


## Proxy Settings Section

Use this section when installing behind a proxy. Enable the checkbox and enter HTTP_PROXY / HTTPS_PROXY values.

- Example: `http://user:pass@proxy:3128`
- Proxy settings are **session-only** and are not saved.


## Package Table

Package status is displayed in 4 columns:

| Column | Description |
|--------|-------------|
| Package | Package name. A checkbox is shown for uninstalled packages |
| Status | Installed (green) / Missing (required: red, optional: orange) |
| Version | Version number if installed |
| Required By | Tools that depend on this package |


## Buttons

| Button | Description |
|--------|-------------|
| Select All Missing | Select all uninstalled packages at once |
| Install Selected | Install the checked packages |
| Refresh | Re-check package status |


## Custom Path Auto-Loading

To load packages installed to a custom path when Maya starts, add the install path to Python's search path using one of the following methods.

### Method 1: .env File (Recommended)

Create a `.env` file at the repository root. Copy `.env.example` to `.env` and set the path:

```
FAKETOOLS_SITE_PACKAGES=D:/my_packages
```

When FakeTools initializes, `<FAKETOOLS_SITE_PACKAGES>/<maya_version>/site-packages/` is automatically added to `sys.path`.

> **Note**: The `.env` file is included in `.gitignore` and will not be committed to the repository.

### Method 2: Manual Addition via userSetup.py

You can also add the install path directly to `sys.path` in Maya's `userSetup.py`.

```python
import sys
sys.path.insert(0, "D:/my_packages/2025/site-packages")
```

> **Note**: `userSetup.py` is only executed when Maya starts, so paths added this way are not reflected in standalone mode's status display.


## Notes

- Standard installation may require administrator privileges. Run Maya as administrator if needed.
- If pip is not available, run `mayapy -m ensurepip` first.
- When launched standalone, paths added by `userSetup.py` are not detected. Paths specified via `FAKETOOLS_SITE_PACKAGES` in `.env` are detected.
- If installation fails, pip error messages are displayed in the status label and logged.
