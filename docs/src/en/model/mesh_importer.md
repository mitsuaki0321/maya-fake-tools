---
title: Mesh Importer
category: model
description: Import glTF/GLB and PLY files into Maya
lang: en
lang-ref: mesh_importer
order: 40
---

## Overview

A tool that imports 3D mesh files into Maya. Supports the following formats:

- **glTF/GLB**: Converted to FBX using Blender and imported with materials and textures
- **PLY**: Imported directly with vertex color support (requires trimesh)

## Requirements

### glTF/GLB Import

- **Blender** must be installed

### PLY Import

- **trimesh** must be installed (install via FakeTools > Dependency Installer)

### Blender Path Detection Order

Blender is automatically detected in the following order:

1. **Environment variable `BLENDER_PATH`** (highest priority)
   - Uses the path explicitly set by the user

2. **Standard installation directories**
   - **Windows**: `C:/Program Files/Blender Foundation/Blender X.X/blender.exe`
     - If multiple versions exist, the latest version is preferred
   - **macOS**: `/Applications/Blender.app/Contents/MacOS/Blender`
   - **Linux**: `/usr/bin/blender` or `/usr/local/bin/blender`

3. **System PATH** (lowest priority)
   - Searches using `where blender` (Windows) or `which blender` (macOS/Linux)

Steam versions or portable versions of Blender may not be automatically detected. In such cases, please set the `BLENDER_PATH` environment variable.

## How to Launch

Launch from the dedicated menu or with the following command.

```python
import faketools.tools.model.mesh_importer.ui
faketools.tools.model.mesh_importer.ui.show_ui()
```

## Interface

### Input File

Specify the file to import. Supports glTF (.gltf), GLB (.glb), and PLY (.ply) formats. Click the `...` button to select from the file browser.

### Output Directory

Specify the output directory for FBX files and textures (glTF/GLB only). If left empty, outputs to the same directory as the input file. This option is disabled for PLY files.

### Shader Type

Select the shader type to use during import (glTF/GLB only). This option is disabled for PLY files.

| Option | Description |
|--------|-------------|
| Auto Detect | Use materials as included in the FBX |
| Arnold | Convert to Arnold shaders |
| Stingray PBS | Convert to Stingray PBS shaders |
| Standard | Convert to Standard shaders |

### Import Button

Execute the import based on the current settings.

## Processing Flow

### glTF/GLB

1. **GLB to FBX Conversion**: Convert glTF/GLB file to FBX using Blender's headless mode
2. **FBX Import**: Import the converted FBX file into Maya
3. **Texture Processing**: Extract embedded textures and update paths
4. **Material Conversion**: Convert materials based on selected shader type (except Auto Detect)

### PLY

1. **File Parsing**: Read PLY file using trimesh
2. **Mesh Creation**: Create Maya polygon mesh via API
3. **Vertex Colors**: Apply vertex colors if present in the PLY file
4. **Material Assignment**: Assign default material (initialShadingGroup)

## Command Line Usage

You can also import directly from scripts without using the UI.

```python
from faketools.tools.model.mesh_importer import command

# Unified import (auto-detects format by extension)
imported_nodes = command.import_file(
    file_path="path/to/model.glb",
    shader_type="auto"
)

# glTF/GLB with output directory
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    output_dir="path/to/output",
    shader_type="arnold"
)

# PLY import
imported_nodes = command.import_ply_file(
    file_path="path/to/scan.ply"
)
```

## Notes

- Blender runs in the background during glTF/GLB conversion
- Large glTF/GLB files may take longer to convert (timeout: 5 minutes)
- Textures are extracted to a `{filename}.fbm` directory
- PLY vertex colors are applied as a Maya `colorSet` and displayed in the viewport
