"""
Settings package for Code Editor.
"""

# Direct imports kept as they don't cause circular dependencies
from .settings_manager import SettingsManager
from .user_settings import UserSettings

__all__ = ["SettingsManager", "UserSettings"]
