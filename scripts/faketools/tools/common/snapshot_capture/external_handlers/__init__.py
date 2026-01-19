"""External application handlers for Snapshot Capture.

This module provides a registry-based system for opening captured images
in external applications. Handlers can be registered for different platforms
and applications.

Usage:
    from .external_handlers import get_available_handlers

    handlers = get_available_handlers()
    for handler in handlers:
        print(handler.menu_name)
"""

from .base import ExternalAppHandler, ExternalAppHandlerRegistry
from .default_app import DefaultAppHandler

# Global registry instance
_registry = ExternalAppHandlerRegistry()

# Register default handlers
_registry.register(DefaultAppHandler())


def get_registry() -> ExternalAppHandlerRegistry:
    """Get the global handler registry.

    Returns:
        The global ExternalAppHandlerRegistry instance.
    """
    return _registry


def get_available_handlers() -> list[ExternalAppHandler]:
    """Get handlers available on the current platform.

    Shortcut for _registry.get_available().

    Returns:
        List of handlers that support the current platform.
    """
    return _registry.get_available()


__all__ = [
    "ExternalAppHandler",
    "ExternalAppHandlerRegistry",
    "DefaultAppHandler",
    "get_registry",
    "get_available_handlers",
]
