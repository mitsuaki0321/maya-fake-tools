"""Shared configuration for FakeTools.

Provides project-wide settings that are shared across multiple tools.
Settings are stored at:
    {MAYA_APP_DIR}/faketools_workspace/shared/config/settings/default.json

Users can customize settings by editing the JSON file directly.
"""

from .tool_settings import ToolSettingsManager

_DEFAULTS = {
    "mirror_patterns": {
        "left_to_right": ["(.*)(L)", r"\g<1>R"],
        "right_to_left": ["(.*)(R)", r"\g<1>L"],
        "adjust_center_weight": ["(.*)(L$)", r"\g<1>R"],
    },
    "hotkeys": {
        "single_commands_popup": "Ctrl+Shift+Z",
    },
}

_settings = ToolSettingsManager("config", "shared")


def get_shared_config() -> dict:
    """Load shared configuration from settings file, falling back to defaults.

    If the settings file does not exist, it is automatically created with default values.
    Missing sections or keys are filled from defaults without modifying the user's file.

    Returns:
        dict: Shared configuration dictionary.
    """
    data = _settings.load_settings()
    if not data:
        _settings.save_settings(_DEFAULTS)
        data = _DEFAULTS

    result = {}
    for section, defaults in _DEFAULTS.items():
        section_data = data.get(section, {})
        if isinstance(defaults, dict):
            result[section] = {key: section_data.get(key, val) for key, val in defaults.items()}
        else:
            result[section] = data.get(section, defaults)
    return result
