"""Single command functions."""

from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """Base class for single commands."""

    _name = "BaseCommand"
    _description = "Base command description"

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the command."""
        pass

    def check_exists_nodes(self, nodes: list[str]) -> None:
        """Check if all nodes exist.

        Args:
            nodes (list[str]): The nodes to check.
        """
        missing_nodes = [node for node in nodes if not self.node_exists(node)]
        if missing_nodes:
            raise ValueError(f"Nodes do not exist: {', '.join(missing_nodes)}")


class SceneCommand(BaseCommand):
    """Command to process the scene."""

    _name = "SceneCommand"
    _description = "Command to process the entire scene"


class AllCommand(BaseCommand):
    """Command to select all nodes in the scene."""

    _name = "AllCommand"
    _description = "Command to select all nodes in the scene"

    def execute(self, target_nodes: list[str]):
        """Execute the command.

        Args:
            target_nodes (list[str]): The target nodes to select.
        """
        if not target_nodes:
            raise ValueError("Target nodes must be provided.")

        if not isinstance(target_nodes, list) or not all(isinstance(node, str) for node in target_nodes):
            raise TypeError("Target nodes must be a list of strings.")

        self.check_exists_nodes(target_nodes)


class OneToOneCommand(BaseCommand):
    """Command to process one node to one other node."""

    _name = "OneToOneCommand"
    _description = "Command to process one node to one other node"

    def execute(self, source_nodes: list[str], target_nodes: list[str]):
        """Execute the command.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        if not source_nodes or not target_nodes:
            raise ValueError("Source nodes and target nodes must be provided.")

        if not isinstance(source_nodes, list) or not all(isinstance(node, str) for node in source_nodes):
            raise TypeError("Source nodes must be a list of strings.")

        if not isinstance(target_nodes, list) or not all(isinstance(node, str) for node in target_nodes):
            raise TypeError("Target nodes must be a list of strings.")

        if len(source_nodes) != len(target_nodes):
            raise ValueError("Source nodes and target nodes must have the same length.")

        self.check_exists_nodes(source_nodes + target_nodes)

        if len(source_nodes) != len(target_nodes):
            if len(source_nodes) == 1:
                source_nodes = source_nodes * len(target_nodes)
            else:
                raise ValueError("The number of source nodes must be either one or equal to the number of target nodes.")

        for source_node, target_node in zip(source_nodes, target_nodes, strict=False):
            self.execute_pair(source_node, target_node)

    def execute_pair(self, source_node: str, target_node: str):
        """Execute the command for a single pair of nodes.

        Args:
            source_node (str): The source node to process.
            target_node (str): The target node to process.
        """
        pass  # To be implemented in subclasses.


__all__ = [
    "BaseCommand",
    "SceneCommand",
    "AllCommand",
    "OneToOneCommand",
]
