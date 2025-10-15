---
title: Skin Weights Copy/Paste
category: rig
description: Skin weight copy & paste tool
lang: en
lang-ref: skinweights_copy_paste
---

## How to Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.rig.skinWeights_copy_paste_ui
faketools.tools.rig.skinWeights_copy_paste_ui.show_ui()
```

![image001](../../images/rig/skinWeights_copy_paste/image001.png)

## Usage

To copy and paste weights, follow these steps:

**When copying from single component to multiple components**

![image002](../../images/rig/skinWeights_copy_paste/image002.png)

1. Set first button to `1:N`.
2. Select source component and select second button. When selected, source component is remembered. Multiple are remembered but first selected one is used as source.
3. Select destination components and select third button. When selected, destination components are remembered.
4. Adjust weights from source to destination using spinbox or slider for blending. Also, the rightmost button pastes source weights to destination as is.

**When copying between selected components one-to-one**

![image003](../../images/rig/skinWeights_copy_paste/image003.png)

1. Set first button to `1:1`.
2. Select source component and select second button. When selected, source component is remembered.
3. Select same number of components as source and select third button. When selected, destination components are remembered.
4. Adjust weights from source to destination using spinbox or slider for blending. Also, the rightmost button pastes source weights to destination as is.

※ Selecting too many components may cause heavy processing.

## Optional Features

### Input with Spinbox

You can change values in the spinbox by clicking the up or down arrows while holding the Ctrl key for increments of 0.01.\
Holding the Shift key while clicking changes the value in increments of 0.5.

### Lock Feature

![image005](../../images/rig/skinWeights_copy_paste/image005.png) Turning on the icon allows weight transfer only between unlocked influences.\
If all influences linked to the target component are locked, an error will occur, so please be careful.

**Locked State**

![image004](../../images/rig/skinWeights_copy_paste/image004.png)

**Unlocked State**

![image001](../../images/rig/skinWeights_copy_paste/image001.png)
