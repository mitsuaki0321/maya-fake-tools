"""
Centralized logging configuration for Maya Code Editor.

This module provides a consistent logging setup across the entire application,
with appropriate handlers for Maya and standalone environments.
"""

import logging
import logging.handlers
from pathlib import Path
import sys
from typing import Optional


class MayaHandler(logging.Handler):
    """Custom logging handler for Maya's Script Editor output."""

    def __init__(self):
        super().__init__()
        self.maya_available = False
        try:
            import maya.cmds as cmds

            self.cmds = cmds
            self.maya_available = True
        except ImportError:
            pass

    def emit(self, record):
        """Emit a log record to Maya's Script Editor."""
        if not self.maya_available:
            return

        try:
            msg = self.format(record)

            # Use appropriate Maya output method based on log level
            if record.levelno >= logging.ERROR:
                self.cmds.error(msg)
            elif record.levelno >= logging.WARNING:
                self.cmds.warning(msg)
            else:
                print(msg)  # INFO and DEBUG go to standard output

        except Exception:
            # Fallback to print if Maya commands fail
            print(self.format(record))


class LoggerConfig:
    """Manages logging configuration for Maya Code Editor."""

    # Default log settings
    DEFAULT_LEVEL = logging.INFO
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # Log file settings
    LOG_DIR_NAME = ".logs"
    LOG_FILE_NAME = "maya_code_editor.log"
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT = 5

    _initialized = False
    _log_dir: Optional[Path] = None

    @classmethod
    def get_log_directory(cls) -> Path:
        """Get the log directory path, creating it if necessary."""
        if cls._log_dir is not None:
            return cls._log_dir

        # Try to get Maya's user app directory first
        try:
            import maya.cmds as cmds

            maya_app_dir = cmds.internalVar(userAppDir=True)
            base_dir = Path(maya_app_dir) / "scripts" / "maya_code_editor_workspace"
        except ImportError:
            # Fallback to user home directory
            import tempfile

            base_dir = Path(tempfile.gettempdir()) / "maya_code_editor_workspace"

        cls._log_dir = base_dir / cls.LOG_DIR_NAME
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        return cls._log_dir

    @classmethod
    def setup_logging(cls, level: int = None, console: bool = True, file: bool = True, maya_handler: bool = True) -> None:
        """
        Configure the root logger with appropriate handlers.

        Args:
            level: Logging level (default: INFO)
            console: Enable console output
            file: Enable file output
            maya_handler: Enable Maya Script Editor output
        """
        if cls._initialized:
            return

        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level or cls.DEFAULT_LEVEL)

        # Remove any existing handlers
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(cls.DEFAULT_FORMAT, datefmt=cls.DEFAULT_DATE_FORMAT)

        # Add console handler if requested and not in Maya
        if console and not maya_handler:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(level or cls.DEFAULT_LEVEL)
            root_logger.addHandler(console_handler)

        # Add file handler if requested
        if file:
            try:
                log_file = cls.get_log_directory() / cls.LOG_FILE_NAME
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=cls.MAX_LOG_SIZE, backupCount=cls.BACKUP_COUNT, encoding="utf-8"
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(level or cls.DEFAULT_LEVEL)
                root_logger.addHandler(file_handler)
            except Exception as e:
                # If file logging fails, continue without it
                print(f"Failed to set up file logging: {e}")

        # Add Maya handler if available and requested
        if maya_handler:
            try:
                maya_hdlr = MayaHandler()
                maya_hdlr.setFormatter(formatter)
                maya_hdlr.setLevel(level or cls.DEFAULT_LEVEL)
                root_logger.addHandler(maya_hdlr)
            except Exception:
                # Maya not available, use console instead
                if not console:
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_handler.setFormatter(formatter)
                    console_handler.setLevel(level or cls.DEFAULT_LEVEL)
                    root_logger.addHandler(console_handler)

        cls._initialized = True

        # Log initialization
        logger = logging.getLogger(__name__)
        logger.info("Maya Code Editor logging initialized")
        logger.info(f"Log directory: {cls.get_log_directory()}")

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance for the specified module.

        Args:
            name: The name of the logger (typically __name__)

        Returns:
            Configured logger instance
        """
        # Ensure logging is set up
        if not cls._initialized:
            cls.setup_logging()

        return logging.getLogger(name)

    @classmethod
    def set_level(cls, level: int) -> None:
        """
        Change the logging level for all handlers.

        Args:
            level: New logging level
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        for handler in root_logger.handlers:
            handler.setLevel(level)

    @classmethod
    def cleanup(cls) -> None:
        """Clean up logging handlers and close files."""
        root_logger = logging.getLogger()

        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        cls._initialized = False
        cls._log_dir = None


# Convenience function for getting a logger
def get_logger(name: str = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (default: caller's module name)

    Returns:
        Logger instance
    """
    if name is None:
        # Try to get the caller's module name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "maya_code_editor")
        else:
            name = "maya_code_editor"

    return LoggerConfig.get_logger(name)


# Initialize logging on module import
LoggerConfig.setup_logging()
