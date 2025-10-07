"""
Maya FakeTools Package.

A collection of tools for Autodesk Maya.
"""

from .logging_config import set_log_level, setup_logging

# Initialize logging when package is imported
setup_logging()

__version__ = "1.0.0"
__author__ = "FakeTools"

__all__ = [
    "set_log_level",
    "setup_logging",
]
