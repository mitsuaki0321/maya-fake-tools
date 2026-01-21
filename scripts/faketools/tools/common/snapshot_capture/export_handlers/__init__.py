"""Export handlers for snapshot capture.

This module provides export handlers for different output formats.
Each handler implements the BaseExportHandler interface and can be
queried for availability.

Usage:
    from .export_handlers import get_handler, get_available_handlers

    # Get all available handlers
    handlers = get_available_handlers()

    # Get specific handler by format key
    handler = get_handler("mp4")
    if handler and handler.is_available():
        handler.export(images, output_path, fps=24)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseExportHandler
from .gif_handler import GifExportHandler
from .mp4_handler import Mp4ExportHandler

if TYPE_CHECKING:
    pass

# Registry of all export handlers
EXPORT_HANDLERS: dict[str, type[BaseExportHandler]] = {
    "gif": GifExportHandler,
    "mp4": Mp4ExportHandler,
}


def get_available_handlers() -> list[type[BaseExportHandler]]:
    """Get list of available export handlers.

    Returns:
        List of handler classes that are currently available.
    """
    return [h for h in EXPORT_HANDLERS.values() if h.is_available()]


def get_handler(format_key: str) -> type[BaseExportHandler] | None:
    """Get export handler by format key.

    Args:
        format_key: Format identifier ("gif", "mp4", etc.).

    Returns:
        Handler class, or None if not found.
    """
    return EXPORT_HANDLERS.get(format_key.lower())


def get_all_handlers() -> list[type[BaseExportHandler]]:
    """Get list of all registered export handlers.

    Returns:
        List of all handler classes (may include unavailable ones).
    """
    return list(EXPORT_HANDLERS.values())


__all__ = [
    "BaseExportHandler",
    "GifExportHandler",
    "Mp4ExportHandler",
    "EXPORT_HANDLERS",
    "get_available_handlers",
    "get_handler",
    "get_all_handlers",
]
