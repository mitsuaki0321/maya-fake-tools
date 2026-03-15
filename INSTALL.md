# FakeTools Installation Guide

This guide walks you through installing FakeTools, external tools (ffmpeg, OpenRV), and Python libraries step by step.

---

## Table of Contents

1. [Installing FakeTools](#1-installing-faketools)
2. [Installing Python Libraries](#2-installing-python-libraries)
3. [Installing ffmpeg](#3-installing-ffmpeg)
4. [Setting Up OpenRV (Optional)](#4-setting-up-openrv-optional)
5. [Auto-Loading the Menu on Maya Startup](#5-auto-loading-the-menu-on-maya-startup)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Installing FakeTools

### 1-1. Download

Download the latest `maya-fake-tools_vX.X.X.zip` from the [Releases page](https://github.com/mitsuaki0321/maya-fake-tools/releases).

### 1-2. Extract

Extract the zip to a folder of your choice.

```
Example: C:/maya_tools/maya-fake-tools/
```

After extraction, the folder structure should look like this:

```
C:/maya_tools/maya-fake-tools/
├── faketools.mod
├── .env.example
├── docs/           <- Open docs/index.html in a browser to view the documentation
├── plug-ins/
└── scripts/
    └── faketools/
```

### 1-3. Register the Module Path in Maya

Add the extracted folder to the `MAYA_MODULE_PATH` environment variable so that Maya can find FakeTools.

#### Option A: Add to Maya.env (Recommended)

Open your Maya.env file and add the following line:

```
MAYA_MODULE_PATH = C:/maya_tools/maya-fake-tools
```

Maya.env location:

```
C:\Users\<username>\Documents\maya\<version>\Maya.env
```

> **Tip**: If Maya.env does not exist, create it as a new text file.

#### Option B: Set as a Windows System Environment Variable

1. Press the Windows key and type "environment variables", then open "Edit the system environment variables"
2. Click "Environment Variables"
3. Under User variables, click "New"
4. Variable name: `MAYA_MODULE_PATH`, Value: `C:/maya_tools/maya-fake-tools`
5. Click OK to close

> **Note**: If `MAYA_MODULE_PATH` already exists, append `;C:/maya_tools/maya-fake-tools` to the end of the existing value (separated by a semicolon).

### 1-4. Show the Menu

Launch (or restart) Maya and run the following in the Script Editor:

```python
import faketools.menu
faketools.menu.add_menu()
```

If the **FakeTools** menu appears in the menu bar, the installation was successful.

> To load the menu automatically on startup, see "[5. Auto-Loading the Menu on Maya Startup](#5-auto-loading-the-menu-on-maya-startup)".

---

## 2. Installing Python Libraries

Some tools require additional Python libraries. FakeTools includes a built-in **Dependency Installer** that lets you install libraries from within Maya.

### 2-1. Required Packages

| Package | Used by | Required |
|---------|---------|:--------:|
| numpy | Bounding Box Creator, Mesh Retargeter | Yes |
| scipy | Bounding Box Creator, Mesh Retargeter | Yes |
| trimesh | Mesh Fitter, BlendShape Transfer | Yes |
| rtree | Mesh Fitter, BlendShape Transfer | Yes |
| fast-simplification | Mesh Fitter, BlendShape Transfer | Yes |
| Pillow | Snapshot Capture | Yes |
| aggdraw | Snapshot Capture | No |
| mss | Snapshot Capture | No |

> **Note**: Packages marked "Required: No" are optional enhancements. The tools will work without them, but installing them enables additional features (anti-aliased drawing, faster screen capture, etc.).

### 2-2. Using the Dependency Installer

1. Open **FakeTools > Common > Dependency Installer** from the Maya menu

2. Confirm the **Maya Version** (the currently running version is selected by default)

3. Choose an **Install Location**:
   - **Custom path (Recommended)**: Installs to a location of your choice. This keeps Maya's installation folder clean and does not require administrator privileges
   - **Standard (Maya site-packages)**: Installs to Maya's default location. May require administrator privileges

4. Click **Select All Missing** to select all uninstalled packages

5. If you are behind a proxy (e.g., corporate network), enable the **Proxy Settings** checkbox and enter the proxy address (e.g., `http://proxy.example.com:8080`). If you don't need a proxy, leave this as-is

6. Click **Install Selected** to start the installation

7. When installation is complete, the package list will update automatically. If the Status column shows green **Installed**, the installation was successful

### 2-3. Additional Setup for Custom Path

When using a custom path, FakeTools needs to be configured to recognize that path. Use either method below.

#### Option A: Configure via .env File (Recommended)

Copy `.env.example` in the FakeTools folder and rename it to `.env`, then edit the contents to set the path:

```
FAKETOOLS_SITE_PACKAGES=D:/my_packages
```

Remove the `#` at the beginning of the line and change the path to match the location you specified in the Dependency Installer. FakeTools will automatically recognize this path the next time it loads.

#### Option B: Configure via userSetup.py

You can also add the path in `userSetup.py` (introduced in "[5. Auto-Loading the Menu on Maya Startup](#5-auto-loading-the-menu-on-maya-startup)"):

```python
import sys
sys.path.insert(0, "D:/my_packages/2025/site-packages")
```

Replace `2025` with your Maya version. The Dependency Installer creates packages under `<specified path>/<Maya version>/site-packages/`.

---

## 3. Installing ffmpeg

Some tools use ffmpeg for video export and playback. If you don't need these features, you can skip this section.

### 3-1. If ffmpeg Is Already Installed

If ffmpeg is already installed on your PC, there is no need to download it again. Just confirm the path to the folder containing `ffmpeg.exe` and skip ahead to "[3-3. Making ffmpeg Available to Maya](#3-3-making-ffmpeg-available-to-maya)".

You can check whether ffmpeg is installed by running the following in Command Prompt:

```
where ffmpeg
```

If a path is displayed, ffmpeg is already installed.

> **How to open Command Prompt**: Press the `Windows key`, type "cmd", and click "Command Prompt" in the search results.

### 3-2. Downloading ffmpeg

1. Go to [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
2. Download `ffmpeg-release-essentials.zip` from the **release builds** section
3. Extract the zip and move the folder to a convenient location

```
Example: C:/tools/ffmpeg/
```

After extraction:

```
C:/tools/ffmpeg/
├── bin/
│   ├── ffmpeg.exe    <- This is what you need
│   ├── ffplay.exe
│   └── ffprobe.exe
├── doc/
└── ...
```

### 3-3. Making ffmpeg Available to Maya

Add the folder containing `ffmpeg.exe` to the PATH so that Maya can find it.

#### Option A: Add to Maya.env (Recommended)

Add the following line to your Maya.env:

```
PATH = C:/tools/ffmpeg/bin
```

Maya.env location:

```
C:\Users\<username>\Documents\maya\<version>\Maya.env
```

> **Note**: The `PATH` entry in Maya.env is appended to the existing system PATH.

#### Option B: Set as a Windows System Environment Variable

1. Press the Windows key and type "environment variables", then open "Edit the system environment variables"
2. Click "Environment Variables"
3. Select `Path` under **User variables** and click "Edit"
4. Click "New" and add `C:\tools\ffmpeg\bin`
5. Click OK to close

### 3-4. Verification

Restart Maya and run the following in the Script Editor:

```python
import shutil
print(shutil.which("ffmpeg"))
```

If the path to ffmpeg.exe is displayed, the setup is complete. If `None` is displayed, review your PATH configuration.

---

## 4. Setting Up OpenRV (Optional)

OpenRV can be used as an external player for VP Compositor playblast output. Even without OpenRV, you can use FakeTools' built-in Sync Player or the system's default player.

> **Note**: OpenRV is an open-source project that does not provide pre-built installers. You must build it from source. See the [OpenRV GitHub repository](https://github.com/AcademySoftwareFoundation/OpenRV) for build instructions.
>
> The steps below describe how to configure FakeTools **if you already have a pre-built copy of OpenRV**.

### 4-1. Making OpenRV Available to Maya

FakeTools communicates with OpenRV via the `rvpush` command. Add the folder containing `rvpush.exe` to the PATH.

#### Option A: Add to Maya.env (Recommended)

Add the following line to your Maya.env. If you have ffmpeg configured as well, combine both paths on a single line separated by a semicolon (`;`).

OpenRV only:

```
PATH = C:/OpenRV/bin
```

Both ffmpeg and OpenRV:

```
PATH = C:/OpenRV/bin;C:/tools/ffmpeg/bin
```

#### Option B: Set as a Windows System Environment Variable

Follow the same steps as for ffmpeg, adding the folder containing `rvpush.exe` to the `Path` user variable.

### 4-2. Verification

Restart Maya and run the following in the Script Editor:

```python
import shutil
print(shutil.which("rvpush"))
```

If a path is displayed, FakeTools can use OpenRV.

---

## 5. Auto-Loading the Menu on Maya Startup

To avoid running the menu command manually each time, you can use `userSetup.py` to load it automatically.

### 5-1. Create or Edit userSetup.py

Open `userSetup.py` at the following location (create it if it does not exist):

```
C:\Users\<username>\Documents\maya\<version>\scripts\userSetup.py
```

Add the following content:

```python
import maya.cmds as cmds

def _load_faketools():
    import faketools.menu
    faketools.menu.add_menu()

cmds.evalDeferred(_load_faketools)
```

> **Why `evalDeferred`?** This ensures the menu is added only after Maya has finished its startup process. Calling it directly may cause errors.

### 5-2. Restart Maya

After restarting Maya, the FakeTools menu will appear automatically on startup.

---

## 6. Troubleshooting

### FakeTools Menu Does Not Appear

- Verify that `MAYA_MODULE_PATH` is set correctly
- Run the following in the Script Editor to check if the module is recognized:
  ```python
  import maya.cmds as cmds
  print(cmds.moduleInfo(listModules=True))
  ```
  If `maya_fake_tools` appears in the list, the module path is configured correctly

### "Administrator Privileges Required" in Dependency Installer

This can happen when installing to Standard (Maya site-packages). Either run Maya as administrator, or use **Custom path** instead (Custom path does not require administrator privileges).

### ffmpeg / rvpush Not Found

- After setting the PATH in Maya.env or Windows environment variables, **restart Maya**
- You can verify in the Script Editor:
  ```python
  import shutil
  print(shutil.which("ffmpeg"))
  print(shutil.which("rvpush"))
  ```
  If a path is displayed, the tool is recognized. If `None`, review your PATH configuration
- When setting PATH in Maya.env, separate multiple paths with a semicolon (`;`)

### pip Not Available

If the Dependency Installer reports that pip cannot be found, you need to set up pip. Follow these steps:

1. Open Command Prompt (press the `Windows key`, type "cmd", and click "Command Prompt")
2. Copy and paste the following command, replacing the Maya version number with your own:
   ```
   "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" -m ensurepip
   ```
3. If you see a message like "Successfully installed pip-...", the setup is complete
4. Restart Maya and open the Dependency Installer again
