"""Viewport display management for snapshot capture tool."""

import maya.cmds as cmds

MODEL_EDITOR_FLAGS = [
    "planes",
    "dimensions",
    "nurbsCurves",
    "cv",
    "nurbsSurfaces",
    "hulls",
    "polymeshes",
    "subdivSurfaces",
    "dynamics",
    "dynamicConstraints",
    "fluids",
    "follicles",
    "hairSystems",
    "nCloths",
    "nParticles",
    "nRigids",
    "particleInstancers",
    "clipGhosts",
    "controllers",
    "deformers",
    "handles",
    "ikHandles",
    "joints",
    "locators",
    "motionTrails",
    "pivots",
    "cameras",
    "imagePlane",
    "lights",
    "strokes",
    "textures",
    "hud",
    "hos",
    "grid",
    "manipulators",
    "bluePencil",
    "pluginShapes",
]


DISPLAY_PRESETS = {
    "Mesh": ["polymeshes"],
    "Geometry": ["nurbsSurfaces", "polymeshes", "subdivSurfaces"],
    "Joint": ["joints"],
    "Controller": ["controllers", "nurbsCurves"],
}

DISPLAY_TOGGLE = {
    "HUD": ["hud", "hos", "sel"],
    "Grid": ["grid"],
}


def display_all(model_panel):
    """Enable all display flags in the given model panel.

    Args:
        model_panel (str): The name of the model panel.
    """
    for flag in MODEL_EDITOR_FLAGS:
        cmds.modelEditor(model_panel, e=True, **{flag: True})


def apply_display_presets(model_panel, preset_name):
    """Apply display presets to the given model panel.

    Args:
        model_panel (str): The name of the model panel.
        preset_name (str): The name of the preset to apply.
    """
    if preset_name not in DISPLAY_PRESETS:
        return

    # First, turn off all flags
    for flag in MODEL_EDITOR_FLAGS:
        cmds.modelEditor(model_panel, e=True, **{flag: False})

    # Then, enable the flags in the preset
    for flag in DISPLAY_PRESETS[preset_name]:
        cmds.modelEditor(model_panel, e=True, **{flag: True})


def toggle_display_flags(model_panel, flag_names, state):
    """Toggle display flags in the given model panel.

    Args:
        model_panel (str): The name of the model panel.
        flag_names (list of str): The list of flag names to toggle.
        state (bool): The state to set for the flags (True to enable, False to disable).
    """
    for flag_name in flag_names:
        if flag_name in DISPLAY_TOGGLE:
            for flag in DISPLAY_TOGGLE[flag_name]:
                cmds.modelEditor(model_panel, e=True, **{flag: state})
