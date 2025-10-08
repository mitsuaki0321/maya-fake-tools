"""Node Storage Tool."""

import json
from logging import getLogger
import os

logger = getLogger(__name__)


class NodeStockFile:
    """Node Stock File."""

    _file_suffix = "stockData"

    def __init__(self, file_path: str):
        """Constructor.

        Args:
            file_path (str): The file path.
        """
        if not self.__class__.validate_file(file_path):
            raise ValueError(f"Invalid file: {file_path}")

        self._file_path = file_path

    @classmethod
    def _get_file_suffix(cls) -> str:
        """Get the file suffix.

        Returns:
            str: The file suffix.
        """
        return f".{cls._file_suffix}.json"

    @property
    def name(self) -> str:
        """Get the name.

        Returns:
            str: The name.
        """
        return self.parse_file_name(os.path.basename(self._file_path))

    @property
    def file_name(self) -> str:
        """Get the file name.

        Returns:
            str: The file name.
        """
        return os.path.basename(self._file_path)

    @classmethod
    def create_file_name(cls, name: str) -> str:
        """Create a file name.

        Args:
            name (str): The name.

        Returns:
            str: The file name.
        """
        return f"{name}{cls._get_file_suffix()}"

    @classmethod
    def parse_file_name(cls, file_name: str) -> str:
        """Parse a file name.

        Args:
            file_name (str): The file name.

        Returns:
            str: The name.
        """
        if not file_name.endswith(cls._get_file_suffix()):
            return file_name

        return file_name[: -len(cls._get_file_suffix())]

    @classmethod
    def validate_file(cls, file_path: str) -> bool:
        """Validate the file.

        Args:
            file_path (str): The file path.

        Returns:
            bool: Whether the file is valid.
        """
        if not os.path.exists(file_path):
            return False

        return file_path.endswith(cls._get_file_suffix())

    @classmethod
    def create(cls, name: str, storage_directory: str):
        """Create a new file.

        Args:
            name (str): The name.
            storage_directory (str): The storage directory.

        Returns:
            NodeStockFile: The new file.
        """
        if not os.path.exists(storage_directory):
            raise ValueError(f"Storage directory does not exist: {storage_directory}")

        file_path = os.path.join(storage_directory, cls.create_file_name(name))
        if os.path.exists(file_path):
            cls(file_path)

        # Make file
        with open(file_path, "w") as f:
            json.dump({}, f)

        logger.debug(f"Created file: {file_path}")

        return cls(file_path)

    def get_data(self) -> dict:
        """Get the data.

        Returns:
            dict: The data.
        """
        try:
            with open(self._file_path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load data: {self._file_path} {e}")
            data = {}

        logger.debug(f"Get data: {self._file_path} {data}")

        return data

    def get_nodes(self, key: str) -> list:
        """Get the nodes from the file.

        Args:
            key (str): The key.

        Returns:
            list[str]: The nodes.
        """
        data = self.get_data()
        if key not in data:
            return []

        logger.debug(f"Get nodes: {key} {data[key]}")

        return data[key]

    def add_nodes(self, key: str, nodes: list[str] | None, overwrite: bool = False) -> None:
        """Set the nodes to file.

        Args:
            key (str): The key.
            nodes (list[str]): The nodes.
            overwrite (bool): Whether to overwrite the key if it already exists.
        """
        if not key:
            raise ValueError("Invalid key")

        if nodes is None:
            nodes = []

        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        if not isinstance(nodes, list):
            raise TypeError("Nodes must be a list")

        if not all(isinstance(node, str) for node in nodes):
            raise TypeError("Nodes must be a list of strings")

        data = self.get_data()

        if overwrite:
            data[key] = nodes

            logger.debug(f"Overwritten nodes: {key} {nodes}")
        else:
            if key in data:
                logger.warning(f"Key already exists, not overwritten: {key}")
                return
            else:
                data[key] = nodes

        with open(self._file_path, "w") as f:
            json.dump(data, f, indent=4)

        logger.debug(f"Set nodes: {key} {nodes}")

    def remove_nodes(self, key: str) -> None:
        """Remove the nodes from the file.

        Args:
            key (str): The key.
        """
        data = self.get_data()
        if key not in data:
            logger.debug(f"Key does not exist, not removed: {key}")
            return
        else:
            data.pop(key)

        with open(self._file_path, "w") as f:
            json.dump(data, f, indent=4)

        logger.debug(f"Removed nodes: {key}")


class NodeStorage:
    """Node Storage."""

    def __init__(self, storage_directory: str):
        """Constructor."""
        if not os.path.exists(storage_directory):
            raise ValueError(f"Storage directory does not exist: {storage_directory}")

        self._storage_directory = storage_directory

    def get_directory(self) -> str:
        """Get the storage directory.

        Returns:
            str: The storage directory.
        """
        return self._storage_directory

    def get_file(self, name: str) -> NodeStockFile:
        """Get the storage file.

        Notes:
            If the file does not exist, a new file will be created.

        Args:
            name (str): The name.

        Returns:
            NodeStockFile: The storage file.
        """
        file_name = NodeStockFile.create_file_name(name)
        file_path = os.path.join(self._storage_directory, file_name)
        if not os.path.exists(file_path):
            return NodeStockFile.create(name, self._storage_directory)

        return NodeStockFile(file_path)

    def list_files(self) -> list[NodeStockFile]:
        """List the storage files.

        Returns:
            list[NodeStockFile]: The storage files.
        """
        files = []
        for file_name in os.listdir(self._storage_directory):
            file_path = os.path.join(self._storage_directory, file_name)
            if not NodeStockFile.validate_file(file_path):
                continue

            files.append(NodeStockFile(file_path))

        return files
