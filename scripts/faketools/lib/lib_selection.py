"""
Node selection functions.
"""

from contextlib import contextmanager
from logging import getLogger
import re

import maya.cmds as cmds

logger = getLogger(__name__)


class NodeFilter:
    """Node selection by filter. (by type, by regex)"""

    def __init__(self, nodes: list[str]):
        """Constructor.

        Args:
            nodes (list[str]): The node list.
        """
        if not nodes:
            raise ValueError("Nodes are not specified.")
        elif not isinstance(nodes, list):
            raise ValueError("Nodes must be a list.")

        not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
        if not_exists_nodes:
            raise ValueError(f"Nodes do not exist: {not_exists_nodes}")

        self.nodes = nodes

    def by_type(self, node_type: str, **kwargs) -> list[str]:
        """Filters the nodes by the type.

        Args:
            node_type (str): The node type.

        Keyword Args:
            invert_match (bool): Whether to invert the match. Default is False.

        Returns:
            list: The filtered nodes.
        """
        invert_match = kwargs.get("invert_match", False)

        nodes = []
        for node in self.nodes:
            node_types = cmds.nodeType(node, inherited=True)
            if invert_match:
                if node_type not in node_types:
                    nodes.append(node)
            else:
                if node_type in node_types:
                    nodes.append(node)

        return nodes

    def by_regex(self, regex: str, **kwargs) -> list[str]:
        """Filters the nodes by the regex.

        Args:
            regex (str): The regex.

        Keyword Args:
            invert_match (bool): Whether to invert the match. Default is False.

        Returns:
            list: The filtered nodes.
        """
        invert_match = kwargs.get("invert_match", False)
        ignorecase = kwargs.get("ignorecase", False)

        p = re.compile(regex, re.IGNORECASE) if ignorecase else re.compile(regex)

        nodes = []
        for node in self.nodes:
            if invert_match:
                if not p.match(node):
                    nodes.append(node)
            else:
                if p.match(node):
                    nodes.append(node)

        return nodes


class DagHierarchy:
    """Get the hierarchy nodes for dagNodes."""

    def __init__(self, nodes: list[str]):
        """Constructor.

        Args:
            nodes (list[str]): The node list.
        """
        if not nodes:
            raise ValueError("Nodes are not specified.")
        elif not isinstance(nodes, list):
            raise ValueError("Nodes must be a list.")

        not_exists_nodes = [node for node in nodes if not cmds.objExists(node)]
        if not_exists_nodes:
            cmds.error(f"Nodes do not exist: {not_exists_nodes}")

        not_dag_nodes = [node for node in nodes if "dagNode" not in cmds.nodeType(node, inherited=True)]
        if not_dag_nodes:
            cmds.error(f"Nodes are not dagNode: {not_dag_nodes}")

        self.nodes = nodes

    def get_parent(self) -> list[str]:
        """Get the parent nodes.

        Notes:
            - Only transform node is supported.

        Returns:
            list[str]: The parent nodes.
        """
        result_nodes = []
        for node in self.nodes:
            parent = cmds.listRelatives(node, parent=True, path=True)
            if parent and parent[0] not in result_nodes:
                result_nodes.append(parent[0])

        return result_nodes

    def get_children(self, include_shape: bool = False) -> list[str]:
        """Get the children nodes.

        Args:
            include_shape (bool): Whether to include shapes. Default is False.

        Returns:
            list[str]: The children nodes.
        """
        result_nodes = []
        for node in self.nodes:
            if include_shape:
                children = cmds.listRelatives(node, children=True, path=True)
            else:
                children = cmds.listRelatives(node, children=True, path=True, type="transform")

            if children:
                for child in children:
                    if child not in result_nodes:
                        result_nodes.append(child)

        return result_nodes

    def get_siblings(self) -> list[str]:
        """Get the sibling transform nodes.

        Returns:
            list[str]: The sibling nodes.
        """
        result_nodes = []
        for node in self.nodes:
            if "transform" not in cmds.nodeType(node, inherited=True):
                continue

            parent = cmds.listRelatives(node, parent=True, path=True)
            if parent:
                children = cmds.listRelatives(parent[0], children=True, path=True, type="transform")
                if children:
                    for child in children:
                        if child not in result_nodes:
                            result_nodes.append(child)
            else:
                world_nodes = cmds.ls(assemblies=True, long=True)
                for world_node in world_nodes:
                    if world_node in ["|persp", "|top", "|front", "|side"]:
                        continue

                    if world_node not in result_nodes:
                        result_nodes.append(world_node)

        return result_nodes

    def get_shapes(self, shape_type: str | None = None) -> list[str]:
        """Get the shapes.

        Args:
            shape_type (Optional[str]): The shape type.If None, all shapes are returned.

        Notes:
            - Only transform nodes are supported.

        Returns:
            list[str]: The shapes.
        """
        shapes = self.get_children(include_shape=True)
        if not shapes:
            return []

        if shape_type:
            return cmds.ls(shapes, type=shape_type, long=True)
        else:
            return shapes

    def get_hierarchy(self, include_shape: bool = False) -> list[str]:
        """Get the hierarchy nodes.

        Args:
            include_shape (bool): Whether to include shapes. Default is False.

        Returns:
            list[str]: The children nodes.
        """
        result_nodes = []

        def _get_children_recursive(node: str):
            """Get the children nodes recursively."""
            if node not in result_nodes:
                result_nodes.append(node)

            if "transform" not in cmds.nodeType(node, inherited=True):
                return

            if include_shape:
                children = cmds.listRelatives(node, children=True, path=True)
            else:
                children = cmds.listRelatives(node, children=True, path=True, type="transform")

            if children:
                for child in children:
                    _get_children_recursive(child)

        for node in self.nodes:
            _get_children_recursive(node)

        return result_nodes

    def get_children_bottoms(self) -> list[str]:
        """Get the hierarchy bottom nodes.

        Returns:
            list[str]: The leaf nodes.
        """
        nodes = self.get_hierarchy(include_shape=False)

        result_nodes = []
        for node in nodes:
            children = cmds.listRelatives(node, children=True, path=True, type="transform")
            if not children:
                result_nodes.append(node)

        return result_nodes

    def get_hierarchy_tops(self) -> list[str]:
        """Get the hierarchy top nodes.

        Notes:
            - Retrieves only the top nodes among the selected nodes. For example, if joint1|joint2|joint3 is selected, joint1 is retrieved.

        Returns:
            list[str]: The top nodes.
        """
        nodes = cmds.ls(self.nodes, l=True)
        nodes = sorted(nodes, key=lambda x: x.count("|"), reverse=True)

        except_nodes = []
        for node in nodes:
            for comp_node in nodes:
                if node == comp_node:
                    continue

                if node.startswith(comp_node):
                    except_nodes.append(node)
                    break

        return cmds.ls([node for node in nodes if node not in except_nodes])


class SelectionMode:
    """Selection mode."""

    @property
    def object_mode_types(self) -> list[str]:
        """Get the object mode types.

        Returns:
            list[str]: The object mode types.
        """
        return [
            "byName",
            "camera",
            "cluster",
            "collisionModel",
            "curve",
            "curveOnSurface",
            "dimension",
            "dynamicConstraint",
            "emitter",
            "field",
            "fluid",
            "follicle",
            "hairSystem",
            "handle",
            "ikEndEffector",
            "ikHandle",
            "implicitGeometry",
            "joint",
            "lattice",
            "light",
            "locator",
            "locatorUV",
            "locatorXYZ",
            "nCloth",
            "nParticleShape",
            "nRigid",
            "nonlinear",
            "nurbsCurve",
            "nurbsSurface",
            "orientationLocator",
            "particleShape",
            "plane",
            "polymesh",
            "rigidBody",
            "rigidConstraint",
            "sculpt",
            "spring",
            "subdiv",
            "texture",
        ]

    @property
    def component_mode_types(self) -> list[str]:
        """Get the component mode types.

        Returns:
            list[str]: The component mode types.
        """
        return [
            "controlVertex",
            "curveKnot",
            "curveParameterPoint",
            "edge",
            "editPoint",
            "facet",
            "hull",
            "imagePlane",
            "isoparm",
            "jointPivot",
            "latticePoint",
            "localRotationAxis",
            "nParticle",
            "particle",
            "polymeshEdge",
            "polymeshFace",
            "polymeshUV",
            "polymeshVertex",
            "polymeshVtxFace",
            "rotatePivot",
            "scalePivot",
            "selectHandle",
            "springComponent",
            "subdivMeshEdge",
            "subdivMeshFace",
            "subdivMeshPoint",
            "subdivMeshUV",
            "surfaceEdge",
            "surfaceFace",
            "surfaceKnot",
            "surfaceParameterPoint",
            "surfaceRange",
            "surfaceUV",
            "vertex",
        ]

    def get_mode(self) -> str:
        """Get the current selection mode. (object or component)

        Returns:
            str: The selection mode.
        """
        if cmds.selectMode(q=True, object=True):
            return "object"
        elif cmds.selectMode(q=True, component=True):
            return "component"

    def to_object(self) -> list[str]:
        """Change the selection to the object mode."""
        cmds.selectMode(object=True)

    def get_object_mode(self, mode: str) -> bool:
        """Get the object mode.

        Returns:
            bool or None: The object mode.

        """
        if not mode:
            ValueError("Mode is not specified.")

        if not self._validate_object_mode():
            return None

        if mode not in self.object_mode_types:
            cmds.error(f"Unsupported mode: {mode}")

        return cmds.selectType(q=True, **{mode: True})

    def set_object_mode(self, mode: str, value: bool = True) -> None:
        """Change the object mode.

        Args:
            mode (str): The object mode.
            value (bool): If True, the mode is enabled. If False, the mode is disabled.
        """
        if not mode:
            ValueError("Mode is not specified.")

        self.to_object()

        if mode not in self.object_mode_types:
            cmds.error(f"Unsupported mode: {mode}")

        cmds.selectType(**{mode: value})

        logger.debug(f"Set the object mode to: {mode} -> {value}")

    def toggle_object_mode(self, modes: list[str]) -> None:
        """Toggle the object mode.

        Args:
            modes (list[str]): The object mode.
        """
        if not modes:
            ValueError("Modes are not specified.")

        if not self._validate_object_mode():
            return

        for mode in modes:
            if mode not in self.object_mode_types:
                cmds.error(f"Unsupported mode: {mode}")

            cmds.selectType(**{mode: not self.get_object_mode(mode)})

            logger.debug(f"Toggle the object mode: {mode}")

    def list_current_object_mode(self) -> list[str]:
        """Get the current object mode.

        Returns:
            list[str]: The current object mode.
        """
        if not self._validate_object_mode():
            return None

        modes = []
        for mode in self.object_mode_types:
            print(mode)
            if self.get_object_mode(mode):
                modes.append(mode)

        return modes

    def to_component(self) -> list[str]:
        """Change the selection to the component mode."""
        cmds.selectMode(component=True)

    def get_component_mode(self, mode: str) -> bool:
        """Get the component mode.

        Returns:
            bool or None: The component mode.

        """
        if not mode:
            ValueError("Mode is not specified.")

        if not self._validate_component_mode():
            return None

        if mode not in self.component_mode_types:
            cmds.error(f"Unsupported mode: {mode}")

        return cmds.selectType(q=True, **{mode: True})

    def set_component_mode(self, mode: str, value: bool = True) -> None:
        """Change the component mode.

        Args:
            mode (str): The component mode.
            value (bool): If True, the mode is enabled. If False, the mode is disabled.
        """
        if not mode:
            ValueError("Mode is not specified.")

        self.to_component()

        if mode not in self.component_mode_types:
            cmds.error(f"Unsupported mode: {mode}")

        cmds.selectType(**{mode: value})

        logger.debug(f"Set the component mode to: {mode} -> {value}")

    def toggle_component_mode(self, modes: list[str]) -> None:
        """Toggle the component mode.

        Args:
            modes (list[str]): The component mode.
        """
        if not modes:
            ValueError("Modes are not specified.")

        if not self._validate_component_mode():
            return

        for mode in modes:
            if mode not in self.component_mode_types:
                cmds.error(f"Unsupported mode: {mode}")

            cmds.selectType(**{mode: not self.get_component_mode(mode)})

            logger.debug(f"Toggle the component mode: {mode}")

    def list_current_component_mode(self) -> list[str]:
        """Get the current component mode.

        Returns:
            list[str]: The current component mode.
        """
        if self._validate_component_mode():
            return None

        modes = []
        for mode in self.component_mode_types:
            if self.get_component_mode(mode):
                modes.append(mode)

        return modes

    def _validate_object_mode(self) -> bool:
        """Validate the object mode."""
        if self.get_mode() != "object":
            logger.debug("The current mode is not object.")
            return False

        return True

    def _validate_component_mode(self):
        """Validate the component mode."""
        if self.get_mode() != "component":
            logger.debug("The current mode is not component.")
            return False

        return True


class HiliteSelection:
    def list_nodes(self, full_path: bool = False) -> list[str]:
        """List the hilite nodes.

        Args:
            full_path (bool): Whether to return the full path. Default is False.

        Returns:
            list[str]: The hilite nodes.
        """
        return cmds.ls(hilite=True, long=full_path)

    def hilite(self, nodes: list[str], replace: bool = True) -> None:
        """Hilite the nodes.

        Args:
            nodes (list[str]): The nodes.
            replace (bool): If True, replace the current hilite. If False, add to the current hilite. Default is True.
        """
        if not nodes:
            ValueError("Nodes are not specified.")

        if not isinstance(nodes, list):
            ValueError("Nodes must be a list.")

        cmds.hilite(nodes, replace=replace)

    def clear(self) -> None:
        """Clear the hilite."""
        hilite_nodes = self.list_nodes()
        if not hilite_nodes:
            return

        cmds.hilite(hilite_nodes, unHilite=True)


@contextmanager
def restore_selection():
    """Context manager to restore the existing selection state."""
    initial_selection = cmds.ls(selection=True, long=True)
    try:
        yield
    finally:
        if not initial_selection:
            cmds.select(cl=True)
        else:
            exists_nodes = []
            not_exists_nodes = []
            for node in initial_selection:
                if cmds.objExists(node):
                    exists_nodes.append(node)
                else:
                    not_exists_nodes.append(node)

            if not_exists_nodes:
                cmds.warning(f"Nodes do not exist: {not_exists_nodes}")

            if exists_nodes:
                cmds.select(exists_nodes, replace=True)
            else:
                cmds.select(cl=True)
