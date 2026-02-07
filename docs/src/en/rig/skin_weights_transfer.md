---
title: Skin Weights Transfer
category: rig
description: Transfer skin weights between influences
lang: en
lang-ref: skin_weights_transfer
order: 125
---

## Overview

Skin Weights Transfer is a tool for moving skin weights from multiple source influences to a single target influence on selected components.

Weights are proportionally removed from source influences and added to the target influence. The transfer amount is adjustable from 0 to 100% using a slider.

## Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.rig.skin_weights_transfer.ui
faketools.tools.rig.skin_weights_transfer.ui.show_ui()
```

## Usage

To transfer weights, follow these steps:

1. Select a mesh or components with a skinCluster and click the `SET` button to set the skinCluster.
2. In the left **Source (from)** list, select the influences to take weights from (multi-select: Ctrl+click / Shift+click).
3. In the right **Target (to)** list, select a single influence to receive the weights.
4. Select the target vertices, CVs, or lattice points.
5. Set the transfer amount (0-100%) using the **Amount** slider.
6. Click the execute button to transfer the weights.

## Options

### SkinCluster

Sets the skinCluster to operate on.

- Select a mesh or components and click the `SET` button to automatically detect the skinCluster assigned to the selected object.
- The detected skinCluster name is displayed in the field.

### Influence Filter

Filters the influence list display.

- **Text Filter**: Enter space-separated keywords to show only influences containing any of the keywords (OR search).
- **Affected Only button**: When enabled, only influences with non-zero weights on the currently selected components are shown. Items are sorted by total weight in descending order. The list updates in real-time as the Maya selection changes.

### Source (from) List

Select the influences to take weights from.

- Multiple influences can be selected (Ctrl+click / Shift+click).
- The number of selected influences is shown in the label as `[N]`.
- Selected influences are highlighted in the Maya viewport.

### Target (to) List

Select the influence to receive weights.

- Only one influence can be selected.
- The same influence cannot be set as both source and target (when source is a single influence).

### Amount

Specifies the percentage of source weights to transfer (0-100%).

- **100%**: Transfers all weights from source influences to the target.
- **50%**: Transfers half of the source influence weights to the target.
- **0%**: No weights are transferred.

When multiple source influences are selected, each source's weight is proportionally reduced based on its share of the total.

## How Weight Transfer Works

The following calculation is performed for each component:

1. Calculate the total weight of all source influences.
2. Multiply the total by the Amount percentage to determine the transfer amount.
3. Proportionally reduce each source influence based on its share of the total.
4. Add the total reduced amount to the target influence.

**Example:**
- Source A weight: 0.6, Source B weight: 0.3, Amount: 50%
- Transfer amount: (0.6 + 0.3) x 0.5 = 0.45
- Reduction from Source A: 0.45 x (0.6 / 0.9) = 0.30 → remaining 0.30
- Reduction from Source B: 0.45 x (0.3 / 0.9) = 0.15 → remaining 0.15
- Added to Target: +0.45

## Supported Components

The following component types are supported:

- Vertices
- CVs (Control Vertices)
- Lattice Points

An error occurs if the selected components do not belong to the skinCluster's geometry.
