"""
FakeTools global configuration management.

Provides centralized configuration for the entire FakeTools package.
Settings are stored in a JSON file in the user's home directory.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_default_data_root_dir() -> str:
    """
    Get the default data root directory based on Maya's app directory.

    Returns:
        str: Path to default data directory

    Raises:
        RuntimeError: If MAYA_APP_DIR environment variable is not set
    """
    # MAYA_APP_DIR must be set (respects Maya's per-version directories)
    maya_app_dir = os.environ.get("MAYA_APP_DIR")
    if not maya_app_dir:
        raise RuntimeError("MAYA_APP_DIR environment variable is not set. FakeTools must be run within Maya environment.")

    return str(Path(maya_app_dir) / "faketools_data")


# Default configuration values
DEFAULT_CONFIG = {
    "data_root_dir": _get_default_data_root_dir(),
    "log_level": "INFO",
    "version": "1.0.0",
}


class GlobalConfig:
    """
    Global configuration manager for FakeTools.

    Manages FakeTools-wide settings stored in a JSON file.
    Provides methods for reading and writing configuration values.

    Attributes:
        config_path (Path): Path to the configuration JSON file
    """

    def __init__(self, config_path: Path | None = None):
        """
        Initialize the global configuration.

        Args:
            config_path (Path | None): Custom path to config file.
                                       If None, uses default location.
        """
        self._config_path = config_path or self._default_config_path()
        self._config = self._load_config()
        logger.debug(f"GlobalConfig initialized with config file: {self._config_path}")

    @staticmethod
    def _default_config_path() -> Path:
        """
        Get the default configuration file path.

        Returns:
            Path: Default config file path (~/Documents/maya/faketools/config.json)
        """
        return Path.home() / "Documents" / "maya" / "faketools" / "config.json"

    def _load_config(self) -> dict[str, Any]:
        """
        Load configuration from JSON file.

        If file doesn't exist, creates it with default values.

        Returns:
            dict[str, Any]: Configuration dictionary
        """
        if not self._config_path.exists():
            logger.info(f"Config file not found, creating default: {self._config_path}")
            config = DEFAULT_CONFIG.copy()
            self._save_config(config)
            return config

        try:
            with open(self._config_path, encoding="utf-8") as f:
                config = json.load(f)
            logger.debug(f"Loaded config from: {self._config_path}")
            return config
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load config, using defaults: {e}")
            return DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict[str, Any]) -> None:
        """
        Save configuration to JSON file.

        Args:
            config (dict[str, Any]): Configuration dictionary to save
        """
        try:
            # Ensure parent directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.debug(f"Saved config to: {self._config_path}")
        except OSError as e:
            logger.error(f"Failed to save config: {e}")
            raise

    def get_data_root_dir(self) -> Path:
        """
        Get the data root directory path.

        Returns:
            Path: Data root directory path (expanded and absolute)

        Example:
            >>> config = GlobalConfig()
            >>> data_dir = config.get_data_root_dir()
            >>> print(data_dir)
            /home/user/Documents/maya/faketools_data
        """
        path_str = self._config.get("data_root_dir", DEFAULT_CONFIG["data_root_dir"])
        path = Path(path_str).expanduser().resolve()
        logger.debug(f"Data root directory: {path}")
        return path

    def set_data_root_dir(self, path: Path | str) -> None:
        """
        Set the data root directory path.

        Args:
            path (Path | str): New data root directory path

        Example:
            >>> config = GlobalConfig()
            >>> config.set_data_root_dir("D:/MyProject/maya_data")
            >>> config.save()
        """
        path_obj = Path(path).expanduser().resolve()
        self._config["data_root_dir"] = str(path_obj)
        logger.info(f"Data root directory set to: {path_obj}")

    def get_log_level(self) -> str:
        """
        Get the current log level.

        Returns:
            str: Log level name (e.g., "INFO", "DEBUG")

        Example:
            >>> config = GlobalConfig()
            >>> level = config.get_log_level()
            >>> print(level)
            INFO
        """
        level = self._config.get("log_level", DEFAULT_CONFIG["log_level"])
        logger.debug(f"Log level: {level}")
        return level

    def set_log_level(self, level: str) -> None:
        """
        Set the log level.

        Args:
            level (str): Log level name (e.g., "DEBUG", "INFO", "WARNING", "ERROR")

        Example:
            >>> config = GlobalConfig()
            >>> config.set_log_level("DEBUG")
            >>> config.save()
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level.upper() not in valid_levels:
            logger.warning(f"Invalid log level: {level}, using INFO")
            level = "INFO"

        self._config["log_level"] = level.upper()
        logger.info(f"Log level set to: {level.upper()}")

    def save(self) -> None:
        """
        Save current configuration to file.

        Example:
            >>> config = GlobalConfig()
            >>> config.set_log_level("DEBUG")
            >>> config.save()
        """
        self._save_config(self._config)
        logger.info("Configuration saved")

    def reset_to_defaults(self) -> None:
        """
        Reset configuration to default values and save.

        Example:
            >>> config = GlobalConfig()
            >>> config.reset_to_defaults()
        """
        self._config = DEFAULT_CONFIG.copy()
        self.save()
        logger.info("Configuration reset to defaults")

    def get_all(self) -> dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            dict[str, Any]: Copy of the entire configuration dictionary

        Example:
            >>> config = GlobalConfig()
            >>> all_config = config.get_all()
            >>> print(all_config)
            {'data_root_dir': '...', 'log_level': 'INFO', 'version': '1.0.0'}
        """
        return self._config.copy()


# Global singleton instance
_global_config: GlobalConfig | None = None


def get_global_config() -> GlobalConfig:
    """
    Get the global configuration singleton instance.

    Returns:
        GlobalConfig: The global configuration instance

    Example:
        >>> from faketools.config import get_global_config
        >>> config = get_global_config()
        >>> config.set_log_level("DEBUG")
        >>> config.save()
    """
    global _global_config
    if _global_config is None:
        _global_config = GlobalConfig()
        logger.debug("Global config singleton created")
    return _global_config


__all__ = ["GlobalConfig", "get_global_config", "DEFAULT_CONFIG"]
