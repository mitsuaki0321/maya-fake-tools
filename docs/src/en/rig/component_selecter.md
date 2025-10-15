---
title: Component Selecter
category: rig
description: Component selection and filtering tool for mesh/curve/surface
lang: en
lang-ref: component_selecter
---

## Overview

A tool to assist in selecting Vertex, NurbsCurveCV, NurbsSurfaceCV, and LatticePoint.
Mainly provides the following features:

- Reselect components in SoftSelection, SymmetrySelection state
- Invert selection
- Select components at same position as mesh
- Area selection of components
- Area selection of CVs

Each component can be selected across multiple geometries.

## How to Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.rig.component_selecter_ui
faketools.tools.rig.component_selecter_ui.show_ui()
```

![image001](../../images/rig/component_selecter/image001.png)

## Unique Selection

Reselects components in various ways.

![image002](../../images/rig/component_selecter/image002.png)

### Unique

Reselects selected components from SoftSelection, SymmetrySelection state.

To select, follow these steps:

1. Select components in SoftSelection, SymmetrySelection mode.
2. Press `Unique` button.

※ You can toggle each mode with `Toggle Soft Selection` and `Toggle Symmetry Selection` in the Edit menu.

![image005](../../images/rig/component_selecter/image005.png)

### Reverse

Inverts selected components.

### Same

Selects components at the same position as the mesh.

To select, follow these steps:

1. Select mesh.
2. Add select components.
3. Press `Same` button.

### Area Selection

![image003](../../images/rig/component_selecter/image003.png)

Performs area selection of components. Can select right, left, and center areas based on the YZ plane.

To select, follow these steps:

1. Select geometryShape derivative nodes or their transform nodes (multiple selection allowed).
2. Press the button for the area you want to select (`Right`, `Center`, `Left`).

### CV Area Selection

![image004](../../images/rig/component_selecter/image004.png)

Performs area selection of CVs.

To select, follow these steps:

1. Select nurbsCurve, nurbsSurface derivative nodes or their transform nodes (multiple selection allowed).
2. For nurbsSurface, select `u` or `v` direction.
3. Specify selection range with **max** and **min** spin boxes.
4. Press `Select` button.

For example, if you select nurbsCurve, enter 2 for **max** and 0 for **min**, and press `Select` button, CVs 0 to 2 will be selected.
