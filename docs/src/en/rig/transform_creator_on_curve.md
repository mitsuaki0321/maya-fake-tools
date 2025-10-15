---
title: Transform Creator on Curve
category: rig
description: Create transform nodes on curve
lang: en
lang-ref: transform_creator_on_curve
---

## How to Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.rig.transform_creator_on_curve_ui
faketools.tools.rig.transform_creator_on_curve_ui.show_ui()
```

![image001](../../images/rig/transform_creator_on_curve/image001.png)

## Usage

1. Select transform creation method from dropdown menu at top.
2. Select NURBS surfaces and curves in scene. Select the nodes themselves or transform nodes.
3. Set other options. Options that are not grayed out can be set.
4. Press **[ Create ]** button to create transform nodes.

### Options

- **Node Type**
  - Select either locator or transform.
- **Divisions**
  - Only valid when creation method is innerDivide. Sets how many divisions between selected nodes.
- **IncludeRotation**
  - Sets whether to include rotation attribute in created transform nodes.
- **Offset rotation values**
  - Sets values to offset rotation for created transform nodes.
- **AimVector**
  - Sets how to obtain aim vector for created transform nodes.
    - **CurveTangent**
      - Obtains curve tangent vector.
    - **NextPoint**
      - Obtains vector to next order node's position.
    - **PreviousPoint**
      - Obtains vector to previous order node's position.
- **UpVector**
  - Sets how to obtain up vector for created transform nodes.
    - **SceneUp**
      - Obtains scene up vector. [0, 1, 0].
    - **CurveNormal**
      - Obtains curve normal vector.
    - **SurfaceNormal**
      - Obtains normal vector of surface curve belongs to. At this time, curve must be created by duplicateCurve command. Otherwise, CurveNormal is forcibly applied.
- **SurfaceDir**
    - When NURBS surface is selected, sets which direction of surface to use as curve normal vector.
      - **U Direction**
        - Uses U direction of surface.
        - **V Direction**
        - Uses V direction of surface.
- **Reverse**
  - When transform nodes are created by duplication, reverses their order.
- **Chain**
  - When transform nodes are created by duplication, makes them chain-like hierarchy structure.

### Creation Methods

- **CVPositions**
  - Creates transform nodes at CV positions of curve.
- **EPPositions**
  - Creates transform nodes at edit point positions of curve.
- **CVClosestPositions**
  - Creates transform nodes at positions on curve closest to CVs.
- **ParameterPositions**
  - Creates transform nodes at equal intervals from curve parameter values. Number of nodes created is set by Divisions.
- **LengthPositions**
  - Creates transform nodes at equal intervals from curve length. Number of nodes created is set by Divisions.
- **CloudPositions**
  - Creates transform nodes to make curve chord length equal intervals. Number of nodes created is set by Divisions.
  - For closed curves, may fail.
