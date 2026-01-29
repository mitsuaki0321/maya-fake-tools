---
title: glTF Importer
category: common
description: Import glTF/GLB files into Maya via Blender conversion
lang: en
lang-ref: gltf_importer
order: 40
---

## Overview

A tool that converts glTF/GLB files to FBX using Blender and imports them into Maya.

Maya does not natively support the glTF format, but this tool enables seamless import of glTF/GLB files by leveraging Blender as a conversion backend.

## Requirements

- **Blender** must be installed

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
import faketools.tools.common.gltf_importer.ui
faketools.tools.common.gltf_importer.ui.show_ui()
```

## Interface

### Input File

Specify the glTF/GLB file to import. Click the `...` button to select from the file browser.

### Output Directory

Specify the output directory for FBX files and textures. If left empty, outputs to the same directory as the input file.

### Shader Type

Select the shader type to use during import.

| Option | Description |
|--------|-------------|
| Auto Detect | Use materials as included in the FBX |
| Arnold | Convert to Arnold shaders |
| Stingray PBS | Convert to Stingray PBS shaders |
| Standard | Convert to Standard shaders |

### Import Button

Execute the import based on the current settings.

## Processing Flow

1. **GLB to FBX Conversion**: Convert glTF/GLB file to FBX using Blender's headless mode
2. **FBX Import**: Import the converted FBX file into Maya
3. **Texture Processing**: Extract embedded textures and update paths
4. **Material Conversion**: Convert materials based on selected shader type (except Auto Detect)

## Command Line Usage

You can also import directly from scripts without using the UI.

```python
from faketools.tools.common.gltf_importer import command

# Basic usage
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    shader_type="auto"
)

# With output directory
imported_nodes = command.import_gltf_file(
    file_path="path/to/model.glb",
    output_dir="path/to/output",
    shader_type="arnold"
)
```

## Notes

- Blender runs in the background during conversion
- Large files may take longer to convert (timeout: 5 minutes)
- Textures are extracted to a `{filename}.fbm` directory
