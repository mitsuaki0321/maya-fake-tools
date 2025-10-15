---
title: Retarget Mesh
category: model
description: Transfer vertex positions between meshes with identical topology
lang: en
lang-ref: retarget_mesh
---

## How to Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.model.retarget_mesh.ui
faketools.tools.model.retarget_mesh.ui.show_ui()
```

![image001](../../images/model/retarget_mesh/image002.png)


## Usage

To use the tool, follow these steps:

1. Select the source geometry for deformation and press `Set Source Mesh` button.
2. Select the destination geometry for deformation and press `Set Destination Mesh` button (multiple selection allowed).
3. Select the target geometry to deform and press `Set Target Mesh` button.
4. If creating new geometry, check the `Create New Mesh` checkbox.
5. Press `Retarget Mesh` button.

![image001](../../images/model/retarget_mesh/image001.gif)


## Advanced Parameters

You can obtain more accurate transfer results by adjusting advanced setting parameters.

### Radius Multiplier

- **Default Value**: 1.0
- **Range**: 0.5 ~ 10.0
- **Description**: Radius multiplier for searching source mesh vertices.
- **How to use**:
  - When meshes are small or far apart, **increase** the value (e.g., 2.0 ~ 5.0)
  - If deformation isn't working well, adjusting this value may improve results
  - If the value is too large, the influence range may be too wide, causing unintended deformation

### Max Vertices

- **Default Value**: 1000
- **Range**: 100 ~ 10000
- **Description**: Maximum number of vertices per group when processing target mesh.
- **How to use**:
  - When target mesh vertex count exceeds this value, it's automatically divided into multiple groups for processing
  - **Reducing** the value divides large meshes into finer groups (processing becomes slower but accuracy may improve)
  - **Increasing** the value speeds up processing but increases memory usage

### Min Source Vertices

- **Default Value**: 10
- **Range**: 4 ~ 100
- **Description**: Minimum number of source mesh vertices used for deformation calculation.
- **How to use**:
  - **Increasing** the value improves deformation accuracy but increases processing time (e.g., 20 ~ 50)
  - **Reducing** the value speeds up processing but may reduce accuracy
  - At least 4 vertices are required (cannot calculate correctly with fewer than 4 vertices)

### Max Iterations

- **Default Value**: 10
- **Range**: 1 ~ 20
- **Description**: Maximum number of attempts to automatically adjust search radius when insufficient source vertices are found.
- **How to use**:
  - The default value (10) is usually fine
  - **Increasing** the value attempts more tries to find appropriate vertices
  - If errors occur, we recommend adjusting Radius Multiplier rather than increasing this value



## Notes

- Source mesh and destination mesh must have the same topology.
- When `Create New Mesh` is off and there are multiple destination meshes, nothing is created.
- Processing may take time when target mesh has many vertices.
