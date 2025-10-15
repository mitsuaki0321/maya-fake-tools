---
title: Membership Handler
category: rig
description: Deformer component tag membership management tool
lang: en
lang-ref: membership_handler
---

# Overview

Edits deformer membership. Available only when component tag settings are enabled.

Only WeightGeometryFilter type deformers are supported.

## How to Launch

Launch the tool from the dedicated menu or with the following command.

```python
import faketools.tools.rig.membership_handler_ui
faketools.tools.rig.membership_handler_ui.show_ui()
```

![image001](../../images/rig/membership_handler/image001.png)

### Launch Requirements

This tool is only available when component tags are enabled.

Enable component tags with the following settings:

1. Navigate to `Preferences` > `Settings` > `Animation`.
2. Configure the following three settings in the `Rigging` section:
    - Check `Use component tags for deformation component subsets`.
    - Check `Create component tags on deformer creation`.
    - Uncheck `Add tweak nodes on deformer creation`.

## Usage

1. Select the deformer to edit and press ![image002](../../images/rig/membership_handler/image002.png) button.
![image006](../../images/rig/membership_handler/image006.png)
※ In the image, a cluster deformer handle is selected, but please select the deformer itself when pressing the button.

1. The selected deformer's name is displayed in the middle field.
![image005](../../images/rig/membership_handler/image005.png)

1. Press ![image004](../../images/rig/membership_handler/image004.png) button to select membership registered to that deformer.
![image007](../../images/rig/membership_handler/image007.png)

1. Select components to update and press ![image001](../../images/rig/membership_handler/image003.png) button to update membership.
![image008](../../images/rig/membership_handler/image008.png)
