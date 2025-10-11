"""Single command functions."""

from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """Base class for single commands."""

    _name = "BaseCommand"
    _description = "Base command description"

    @classmethod
    def get_name(cls) -> str:
        """Get the name of the command.

        Returns:
            str: The name of the command.
        """
        return cls._name

    @classmethod
    def get_description(cls) -> str:
        """Get the description of the command.

        Returns:
            str: The description of the command.
        """
        return cls._description

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the command."""
        pass


class SceneCommand(BaseCommand):
    """Command to process the scene.

    Notes:
        - Executes automatically on instantiation.
        - No selection required.
    """

    _name = "SceneCommand"
    _description = "Command to process the entire scene"

    def __init__(self):
        """Initialize and execute the scene command."""
        self.execute()

    def execute(self):
        """Execute the scene command.

        Notes:
            - Override this method in subclasses.
        """
        pass


class AllCommand(BaseCommand):
    """Command to process all selected nodes.

    Notes:
        - Executes automatically on instantiation.
        - Requires node selection.
    """

    _name = "AllCommand"
    _description = "Command to select all nodes in the scene"

    def __init__(self, target_nodes: list[str]):
        """Initialize and execute the command with target nodes.

        Args:
            target_nodes (list[str]): The target nodes to process.

        Raises:
            ValueError: If target_nodes is empty.
            TypeError: If target_nodes is not a list of strings.
        """
        if not target_nodes:
            raise ValueError("Target nodes must be provided.")

        if not isinstance(target_nodes, list) or not all(isinstance(node, str) for node in target_nodes):
            raise TypeError("Target nodes must be a list of strings.")

        self.target_nodes = target_nodes
        self.execute(target_nodes)

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to process.

        Notes:
            - Override this method in subclasses.
            - Validation is already done in __init__.
        """
        pass


class PairCommand(BaseCommand):
    """Command to process pairs of nodes (source -> target).

    Notes:
        - Executes automatically on instantiation.
        - If source_nodes has one element, it will be duplicated for each target.
        - Otherwise, source_nodes and target_nodes must have the same length.
    """

    _name = "PairCommand"
    _description = "Command to process one node to one other node"

    def __init__(self, source_nodes: list[str], target_nodes: list[str]):
        """Initialize and execute the command with source and target nodes.

        Args:
            source_nodes (list[str]): The source nodes.
            target_nodes (list[str]): The target nodes.

        Raises:
            ValueError: If arguments are invalid.
            TypeError: If arguments are not lists of strings.
        """
        if not source_nodes or not target_nodes:
            raise ValueError("Source nodes and target nodes must be provided.")

        if not isinstance(source_nodes, list) or not all(isinstance(node, str) for node in source_nodes):
            raise TypeError("Source nodes must be a list of strings.")

        if not isinstance(target_nodes, list) or not all(isinstance(node, str) for node in target_nodes):
            raise TypeError("Target nodes must be a list of strings.")

        # If one source node, duplicate it for each target
        if len(source_nodes) == 1:
            source_nodes = source_nodes * len(target_nodes)
        elif len(source_nodes) != len(target_nodes):
            raise ValueError("The number of source nodes must be either one or equal to the number of target nodes.")

        self.source_nodes = source_nodes
        self.target_nodes = target_nodes

        # Execute for each pair
        for source_node, target_node in zip(source_nodes, target_nodes, strict=False):
            self.execute_pair(source_node, target_node)

    def execute(self, source_nodes: list[str], target_nodes: list[str]):
        """Execute the command (not used, kept for compatibility).

        Args:
            source_nodes (list[str]): The source nodes.
            target_nodes (list[str]): The target nodes.
        """
        pass

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a single pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.

        Notes:
            - Override this method in subclasses.
        """
        pass


__all__ = [
    "BaseCommand",
    "SceneCommand",
    "AllCommand",
    "PairCommand",
]
