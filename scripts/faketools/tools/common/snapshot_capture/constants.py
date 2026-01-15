"""Snapshot Capture constants."""

# Display mode definitions for modelEditor
DISPLAY_MODES = {
    "shaded": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "textured": {
        "displayAppearance": "smoothShaded",
        "displayTextures": True,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "wireframe": {
        "displayAppearance": "wireframe",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "wireframe_on_shaded": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": True,
        "xray": False,
    },
    "flat": {
        "displayAppearance": "flatShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": False,
    },
    "x_ray": {
        "displayAppearance": "smoothShaded",
        "displayTextures": False,
        "displayLights": "default",
        "wireframeOnShaded": False,
        "xray": True,
    },
}

# Display mode labels for UI
DISPLAY_MODE_LABELS = {
    "shaded": "Shaded",
    "textured": "Textured",
    "wireframe": "Wireframe",
    "wireframe_on_shaded": "Wireframe on Shaded",
    "flat": "Flat",
    "x_ray": "X-Ray",
}

# Resolution presets
RESOLUTION_PRESETS = {
    "1920x1080 (Full HD)": (1920, 1080),
    "1280x720 (HD)": (1280, 720),
    "800x600": (800, 600),
    "640x480 (VGA)": (640, 480),
    "640x360": (640, 360),
    "512x512": (512, 512),
    "320x240": (320, 240),
    "256x256": (256, 256),
    "128x128": (128, 128),
}

# Default resolution key
DEFAULT_RESOLUTION = "640x360"

# Background color options (None means transparent)
BACKGROUND_COLORS = {
    "Transparent": None,
    "White": (255, 255, 255),
    "Black": (0, 0, 0),
    "Gray": (128, 128, 128),
}

DEFAULT_BACKGROUND = "Transparent"
