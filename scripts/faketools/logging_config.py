"""
Logging configuration for FakeTools.

Provides centralized logging setup for the entire FakeTools package.
All modules should use logging.getLogger(__name__) to obtain a logger instance.
"""

import logging
import sys

# Package logger name
LOGGER_NAME = "faketools"

# Default log level
DEFAULT_LOG_LEVEL = logging.INFO

# Log format
LOG_FORMAT = "[%(levelname)s] %(name)s: %(message)s"
DETAILED_LOG_FORMAT = "[%(levelname)s] %(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"


def setup_logging(level: int = DEFAULT_LOG_LEVEL, detailed: bool = False) -> logging.Logger:
    """
    Setup the root logger for FakeTools.

    This should be called once when the package is initialized.
    Configures the logger with console output and specified log level.

    Args:
        level (int): Logging level (e.g., logging.DEBUG, logging.INFO)
        detailed (bool): If True, use detailed format with timestamp and file info

    Returns:
        logging.Logger: Configured root logger for FakeTools

    Example:
        >>> from faketools.logging_config import setup_logging
        >>> import logging
        >>> logger = setup_logging(level=logging.DEBUG)
    """
    # Get the root logger for faketools
    logger = logging.getLogger(LOGGER_NAME)

    # Avoid adding duplicate handlers if setup is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    # Set log level
    logger.setLevel(level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Set format
    log_format = DETAILED_LOG_FORMAT if detailed else LOG_FORMAT
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    logger.debug(f"FakeTools logging initialized (level={logging.getLevelName(level)})")

    return logger


def set_log_level(level: int) -> None:
    """
    Change the log level for all FakeTools loggers.

    Args:
        level (int): New logging level (e.g., logging.DEBUG, logging.INFO)

    Example:
        >>> from faketools.logging_config import set_log_level
        >>> import logging
        >>> set_log_level(logging.DEBUG)
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # Update all handlers
    for handler in logger.handlers:
        handler.setLevel(level)

    logger.debug(f"Log level changed to {logging.getLevelName(level)}")


def get_log_level() -> int:
    """
    Get the current log level.

    Returns:
        int: Current logging level

    Example:
        >>> from faketools.logging_config import get_log_level
        >>> import logging
        >>> level = get_log_level()
        >>> print(logging.getLevelName(level))
    """
    logger = logging.getLogger(LOGGER_NAME)
    return logger.level


__all__ = [
    "setup_logging",
    "set_log_level",
    "get_log_level",
    "LOGGER_NAME",
]
