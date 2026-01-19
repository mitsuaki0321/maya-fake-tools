"""Base class and registry for external application handlers."""

from abc import ABC, abstractmethod
import sys


class ExternalAppHandler(ABC):
    """Abstract base class for external application handlers.

    Subclasses define how to open captured images in external applications.
    Each handler specifies which platforms it supports and its menu display name.
    """

    @property
    @abstractmethod
    def menu_name(self) -> str:
        """Return the name to display in context menus.

        Returns:
            Display name for this handler.
        """
        pass

    @property
    @abstractmethod
    def supported_platforms(self) -> list[str]:
        """Return list of supported platform identifiers.

        Platform identifiers match sys.platform values:
        - "win32" for Windows
        - "darwin" for macOS
        - "linux" for Linux

        Returns:
            List of supported platform identifiers.
        """
        pass

    def is_available(self) -> bool:
        """Check if this handler is available on the current platform.

        Returns:
            True if the current platform is supported.
        """
        return sys.platform in self.supported_platforms

    @abstractmethod
    def open_image(self, image_path: str) -> bool:
        """Open an image file in the external application.

        Args:
            image_path: Absolute path to the image file.

        Returns:
            True if the application was launched successfully.
        """
        pass


class ExternalAppHandlerRegistry:
    """Registry for managing external application handlers.

    Provides methods to register, unregister, and query available handlers.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._handlers: list[ExternalAppHandler] = []

    def register(self, handler: ExternalAppHandler) -> None:
        """Register a handler.

        Args:
            handler: Handler instance to register.
        """
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unregister(self, handler: ExternalAppHandler) -> None:
        """Unregister a handler.

        Args:
            handler: Handler instance to unregister.
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    def get_all(self) -> list[ExternalAppHandler]:
        """Get all registered handlers.

        Returns:
            List of all registered handlers.
        """
        return list(self._handlers)

    def get_available(self) -> list[ExternalAppHandler]:
        """Get handlers available on the current platform.

        Returns:
            List of handlers that support the current platform.
        """
        return [h for h in self._handlers if h.is_available()]
