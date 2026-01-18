---
title: Snapshot Capture
category: common
description: Capture PNG snapshots and animated GIFs from viewport
lang: en
lang-ref: snapshot_capture
order: 30
---

## Overview

Snapshot Capture is a tool for capturing images from the Maya viewport. It offers three capture modes:

| Mode | Description |
|------|-------------|
| PNG | Save the current frame as a PNG image or copy to clipboard |
| GIF | Save timeline range as an animated GIF |
| Rec | Record the viewport in real-time and save as GIF |

## How to Launch

Launch the tool from the dedicated menu or with the following command:

```python
import faketools.tools.common.snapshot_capture.ui
faketools.tools.common.snapshot_capture.ui.show_ui()
```

![image001](../../images/common/snapshot_capture/image001.png)


## Basic Usage

### Viewport Controls

The tool window contains an embedded model panel (viewport). You can rotate, pan, and zoom the camera just like in a standard Maya viewport.

#### Switching Cameras

You can switch the display camera from the **Camera** menu in the menu bar.

[Camera menu image]

### Resolution Settings

You can set the output image resolution in the lower toolbar.

![image](../../images/common/snapshot_capture/image002.png)

1. **Width/Height input fields**: Enter custom resolution directly
2. **Preset button** (▼): Select from available presets:
   - 1920x1080 (Full HD)
   - 1280x720 (HD)
   - 800x600
   - 640x480 (VGA)
   - 640x360
   - 512x512
   - 320x240
   - 256x256
   - 128x128
3. **Set button**: Apply the entered resolution to the viewport

## PNG Mode

Captures the current frame as a PNG image.

![image](../../images/common/snapshot_capture/image001.png)

### How to Use

1. Select **PNG** from the mode selector
2. Set background color if needed (see below)
3. Execute one of the following:
   - **Save button** (💾): Opens file dialog to save as PNG file
   - **Copy button** (📋): Copies image to clipboard

### Background Color Settings

Click the **BG button** to open a color picker and select the background color.

![image](../../images/common/snapshot_capture/image003.png)

#### Options Menu

Access additional settings from the gear icon options button.

- **Transparent**: Makes the background transparent (PNG with alpha channel)
- **Use Maya Background**: Uses Maya's global background color

## GIF Mode

Captures the timeline playback range as an animated GIF.

![image001](../../images/common/snapshot_capture/image004.png)

### How to Use

1. Select **GIF** from the mode selector
2. Set the start and end frames in Maya's timeline
3. Configure background color and options as needed
4. Click the **Save button** (💾) to save the file

### Options

The following settings are available from the options menu:

| Option | Description |
|--------|-------------|
| Transparent | Make background transparent |
| Use Maya Background | Use Maya's global background color |
| Loop | Loop GIF playback (default: on) |
| FPS | Set frame rate (10, 12, 15, 24, 30, 50, 60) |

## Rec Mode

Records the viewport in real-time and saves as GIF. Mouse cursor and keyboard input overlays are also available.

![image001](../../images/common/snapshot_capture/image005.png)

### How to Use

1. Select **Rec** from the mode selector
2. Configure recording settings in the options menu (see below)
3. Click the **Record button** (●) to start recording
4. Recording begins after the countdown
5. Click the **Stop button** (■) to stop recording
6. File dialog opens to save as GIF

### Cancelling During Countdown

Click the button during countdown to cancel the recording.

### Options

The following settings are available from the options menu:

| Option | Description |
|--------|-------------|
| Loop | Loop GIF playback |
| FPS | Recording frame rate (10, 12, 15, 24, 30, 50, 60) |
| Delay | Countdown seconds before recording starts (0, 1, 2, 3) |
| Trim | Seconds to trim from the end of recording (0, 1, 2, 3) |
| Show Cursor | Overlay mouse cursor |
| Show Clicks | Show click position indicators |
| Show Keys | Overlay pressed keys |

For mouse clicks, different indicators are displayed for left-click, right-click, and middle-click.

## Saving Settings

The following settings are automatically saved when the window is closed:

- Selected mode
- Resolution (width/height)
- Background color
- Transparent setting
- FPS
- Loop setting
- Delay/Trim settings
- Cursor/Clicks/Keys display settings

These settings are restored on the next launch.

## Save Location

- On first save, the tool's dedicated data directory is used as the default save location
- Once a file is saved, the last saved directory is remembered within the same session

## Notes

- In GIF mode, up to 500 frames can be captured
- Rec mode recording uses screen capture of the viewport, so other windows overlapping the viewport may be included in the capture
- High resolution and high frame rate recording increases memory usage
