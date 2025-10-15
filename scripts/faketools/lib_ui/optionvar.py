"""
Maya-specific functions for optionVar management.

This module provides a convenient interface for storing and retrieving
tool settings using Maya's optionVar system. Settings are automatically
serialized to JSON for complex data types.

Example:
    >>> settings = ToolOptionSettings("my_tool")
    >>> settings.write("window_size", [800, 600])
    >>> size = settings.read("window_size", [400, 300])
    >>> print(size)
    [800, 600]
"""

import json
import logging
from typing import Any, Optional

import maya.cmds as cmds

logger = logging.getLogger(__name__)


class ToolOptionSettings:
    """
    A class to save and read tool settings in optionVar.

    Provides automatic JSON serialization for complex data types
    and namespaces settings by tool name to avoid conflicts.

    Attributes:
        tool_name (str): The name of the tool (used as namespace prefix)
    """

    def __init__(self, tool_name: str):
        """
        Initialize the ToolOptionSettings instance.

        Args:
            tool_name (str): The name of the tool (used to namespace optionVar keys)
        """
        self.tool_name = tool_name
        logger.debug(f"ToolOptionSettings initialized for tool: {tool_name}")

    def _full_key(self, key: str) -> str:
        """
        Format the key with the tool name as namespace.

        Args:
            key (str): The key to format.

        Returns:
            str: The formatted key (e.g., "tool_name.key")
        """
        return f"{self.tool_name}.{key}"

    def read(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Read the specified key from the optionVar.

        Automatically deserializes JSON data. If deserialization fails,
        returns the raw value.

        Args:
            key (str): The key to read.
            default: The default value to return if the key does not exist.

        Returns:
            Any: The value for the specified key, or default if key doesn't exist.

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> value = settings.read("my_key", default=100)
        """
        full_key = self._full_key(key)
        if not cmds.optionVar(exists=full_key):
            logger.debug(f"Key not found, returning default: {full_key}")
            return default

        value = cmds.optionVar(q=full_key)
        try:
            deserialized = json.loads(value)
            logger.debug(f"Read and deserialized: {full_key}")
            return deserialized
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to deserialize {full_key}, returning raw value: {e}")
            return value

    def write(self, key: str, value: Any) -> None:
        """
        Write the specified value to the optionVar.

        Automatically serializes complex data types to JSON.

        Args:
            key (str): The key to write.
            value (Any): The value to write. Must be JSON serializable.

        Raises:
            ValueError: If the value is not JSON serializable.

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> settings.write("window_size", [800, 600])
        """
        full_key = self._full_key(key)
        try:
            serialized_value = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value for {full_key}: {e}")
            raise ValueError(f"Value must be JSON serializable: {e}") from e

        cmds.optionVar(sv=(full_key, serialized_value))
        logger.debug(f"Wrote to optionVar: {full_key}")

    def delete(self, key: str) -> None:
        """
        Delete the specified key from the optionVar.

        Args:
            key (str): The key to delete.

        Raises:
            KeyError: If the key does not exist.

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> settings.delete("my_key")
        """
        full_key = self._full_key(key)
        if not cmds.optionVar(exists=full_key):
            logger.warning(f"Attempted to delete non-existent key: {full_key}")
            raise KeyError(f"Key '{key}' does not exist")

        cmds.optionVar(remove=full_key)
        logger.debug(f"Deleted from optionVar: {full_key}")

    def exists(self, key: str) -> bool:
        """
        Check whether the specified key exists in the optionVar.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> if settings.exists("my_key"):
            ...     print("Key exists")
        """
        exists = cmds.optionVar(exists=self._full_key(key))
        logger.debug(f"Key exists check for {self._full_key(key)}: {exists}")
        return exists

    def get_window_geometry(self) -> Optional[dict]:
        """
        Get saved window geometry (size and position).

        Returns:
            Dictionary with 'size' and 'position' keys, or None if not saved

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> geometry = settings.get_window_geometry()
            >>> if geometry:
            ...     window.resize(*geometry["size"])
            ...     window.move(*geometry["position"])
        """
        geometry = self.read("window_geometry")
        if geometry and isinstance(geometry, dict):
            logger.debug(f"Retrieved window geometry: {geometry}")
            return geometry
        logger.debug("No window geometry found")
        return None

    def set_window_geometry(self, size: list, position: Optional[list] = None) -> None:
        """
        Save window geometry (size and optionally position).

        Args:
            size: Window size [width, height]
            position: Window position [x, y]. If None, only size is saved.

        Example:
            >>> settings = ToolOptionSettings("my_tool")
            >>> settings.set_window_geometry([800, 600], [100, 100])
        """
        geometry = {"size": size}
        if position is not None:
            geometry["position"] = position

        self.write("window_geometry", geometry)
        logger.debug(f"Saved window geometry: {geometry}")


__all__ = ["ToolOptionSettings"]
