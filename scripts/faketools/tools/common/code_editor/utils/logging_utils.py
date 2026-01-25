"""
Logging utilities for Maya Code Editor.

This module provides convenient functions for managing logging from Maya.
"""

import logging

from .logger_config import LoggerConfig, get_logger

# Set up module logger
logger = get_logger(__name__)

# Log level mapping for convenience
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def set_log_level(level: str = "INFO") -> None:
    """
    Set the logging level for Maya Code Editor.

    This function can be called from Maya's Script Editor to change
    the verbosity of logging output.

    Args:
        level: Logging level as string. Valid values are:
               "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"

    Example:
        >>> import maya_code_editor.utils.logging_utils as log_utils
        >>> log_utils.set_log_level("DEBUG")  # Enable debug logging
        >>> log_utils.set_log_level("WARNING")  # Only warnings and errors
        >>> log_utils.set_log_level("INFO")  # Default level
    """
    level_upper = level.upper()

    if level_upper not in LOG_LEVELS:
        logger.error(f"Invalid log level: {level}. Valid levels are: {', '.join(LOG_LEVELS.keys())}")
        return

    log_level = LOG_LEVELS[level_upper]
    LoggerConfig.set_level(log_level)

    logger.info(f"Log level changed to: {level_upper}")


def get_current_log_level() -> str:
    """
    Get the current logging level.

    Returns:
        Current log level as string (e.g., "INFO", "DEBUG")
    """
    root_logger = logging.getLogger()
    current_level = root_logger.level

    # Find the level name
    for name, level in LOG_LEVELS.items():
        if level == current_level:
            return name

    return f"CUSTOM({current_level})"


def show_log_status() -> None:
    """
    Display current logging configuration status.

    This prints information about:
    - Current log level
    - Active handlers
    - Log file location
    """
    root_logger = logging.getLogger()
    current_level = get_current_log_level()

    print("=" * 60)
    print("Maya Code Editor - Logging Status")
    print("=" * 60)
    print(f"Current Log Level: {current_level}")
    print(f"Number of Handlers: {len(root_logger.handlers)}")

    # Show handler details
    for i, handler in enumerate(root_logger.handlers, 1):
        handler_type = handler.__class__.__name__
        print(f"  Handler {i}: {handler_type}")

        # Show file handler path
        if hasattr(handler, "baseFilename"):
            print(f"    Log File: {handler.baseFilename}")

    # Show log directory
    try:
        log_dir = LoggerConfig.get_log_directory()
        print(f"Log Directory: {log_dir}")
    except Exception as e:
        print(f"Log Directory: Unable to determine ({e})")

    print("=" * 60)


def enable_debug_mode() -> None:
    """
    Enable debug logging mode.

    This is a convenience function that sets the log level to DEBUG
    and shows the current status.
    """
    set_log_level("DEBUG")
    print("Debug mode enabled - all debug messages will be shown")


def disable_debug_mode() -> None:
    """
    Disable debug logging mode by setting level back to INFO.
    """
    set_log_level("INFO")
    print("Debug mode disabled - debug messages will be hidden")


def open_log_file() -> None:
    """
    Open the log file in the default text editor.

    This function attempts to open the current log file
    in the system's default text editor.
    """
    import os
    import platform
    import subprocess

    try:
        log_dir = LoggerConfig.get_log_directory()
        log_file = log_dir / LoggerConfig.LOG_FILE_NAME

        if not log_file.exists():
            logger.warning(f"Log file does not exist yet: {log_file}")
            return

        system = platform.system()
        if system == "Windows":
            os.startfile(str(log_file))
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", str(log_file)])
        elif system == "Linux":
            subprocess.Popen(["xdg-open", str(log_file)])
        else:
            logger.error(f"Unsupported platform: {system}")

        logger.info(f"Opened log file: {log_file}")

    except Exception as e:
        logger.error(f"Failed to open log file: {e}")


def clear_log_file() -> None:
    """
    Clear the contents of the current log file.

    This creates a backup of the current log before clearing.
    """
    from datetime import datetime
    import shutil

    try:
        log_dir = LoggerConfig.get_log_directory()
        log_file = log_dir / LoggerConfig.LOG_FILE_NAME

        if not log_file.exists():
            logger.info("Log file does not exist, nothing to clear")
            return

        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = log_dir / f"maya_code_editor_{timestamp}.log.bak"

        # Copy current log to backup
        shutil.copy2(log_file, backup_file)
        logger.info(f"Created backup: {backup_file}")

        # Clear the log file
        with open(log_file, "w") as f:
            f.write("")

        logger.info("Log file cleared")

    except Exception as e:
        logger.error(f"Failed to clear log file: {e}")


def test_logging() -> None:
    """
    Test logging at all levels.

    This function outputs a test message at each log level
    to verify that logging is working correctly.
    """
    print("=" * 60)
    print("Testing all log levels...")
    print("=" * 60)

    logger.debug("This is a DEBUG message - detailed diagnostic info")
    logger.info("This is an INFO message - general information")
    logger.warning("This is a WARNING message - something to pay attention to")
    logger.error("This is an ERROR message - something went wrong")
    logger.critical("This is a CRITICAL message - serious problem")

    print("=" * 60)
    print("Test complete. Check output above and log file.")
    print("=" * 60)


# Convenience functions for Maya Script Editor
def debug(message: str) -> None:
    """Log a debug message."""
    logger.debug(message)


def info(message: str) -> None:
    """Log an info message."""
    logger.info(message)


def warning(message: str) -> None:
    """Log a warning message."""
    logger.warning(message)


def error(message: str) -> None:
    """Log an error message."""
    logger.error(message)


def critical(message: str) -> None:
    """Log a critical message."""
    logger.critical(message)


# Create short aliases for convenience
set_level = set_log_level
get_level = get_current_log_level
status = show_log_status
debug_on = enable_debug_mode
debug_off = disable_debug_mode
open_log = open_log_file
clear_log = clear_log_file
test = test_logging
