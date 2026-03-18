"""Business logic for Node Lister.

Provides SelectFilter classes for node acquisition,
filtering functions for node type and name matching,
and attribute listing utilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
import re

import maya.cmds as cmds

from ....lib.lib_selection import get_hierarchy

logger = getLogger(__name__)

# Default transform attributes to display
DEFAULT_TRANSFORM_ATTRS = [
    "translateX",
    "translateY",
    "translateZ",
    "rotateX",
    "rotateY",
    "rotateZ",
    "scaleX",
    "scaleY",
    "scaleZ",
    "visibility",
]


# ---------------------------------------------------------------------------
# SelectFilter classes
# ---------------------------------------------------------------------------


class SelectFilterBase(ABC):
    """Base class for node selection filters."""

    label: str

    @abstractmethod
    def get_nodes(self) -> list[str]:
        """Return a list of node names."""
        ...


class AllNodes(SelectFilterBase):
    """Return all nodes in the scene."""

    label = "All Nodes"

    def get_nodes(self) -> list[str]:
        return cmds.ls() or []


class SelectedNodes(SelectFilterBase):
    """Return currently selected nodes."""

    label = "Selected Nodes"

    def get_nodes(self) -> list[str]:
        return cmds.ls(sl=True) or []


class ShapesOfSelected(SelectFilterBase):
    """Return shape nodes of the current selection."""

    label = "Shapes of Selected"

    def get_nodes(self) -> list[str]:
        sel = cmds.ls(sl=True)
        if not sel:
            return []
        return cmds.listRelatives(sel, shapes=True) or []


class HierarchyOfSelected(SelectFilterBase):
    """Return selected nodes and all their descendants."""

    label = "Hierarchy of Selected"

    def get_nodes(self) -> list[str]:
        sel = cmds.ls(sl=True)
        if not sel:
            return []
        return get_hierarchy(sel)


class HistoryOfSelected(SelectFilterBase):
    """Return construction history of selected nodes."""

    label = "History of Selected"

    def get_nodes(self) -> list[str]:
        sel = cmds.ls(sl=True)
        if not sel:
            return []
        return cmds.listHistory(sel) or []


class FutureOfSelected(SelectFilterBase):
    """Return future history of selected nodes."""

    label = "Future of Selected"

    def get_nodes(self) -> list[str]:
        sel = cmds.ls(sl=True)
        if not sel:
            return []
        return cmds.listHistory(sel, future=True) or []


class ConnectionsOfSelected(SelectFilterBase):
    """Return nodes connected to the current selection."""

    label = "Connections of Selected"

    def get_nodes(self) -> list[str]:
        sel = cmds.ls(sl=True)
        if not sel:
            return []
        connections = cmds.listConnections(sel) or []
        # Remove duplicates while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for node in connections:
            if node not in seen:
                seen.add(node)
                result.append(node)
        return result


class DAGNodes(SelectFilterBase):
    """Return all DAG nodes in the scene."""

    label = "DAG Nodes"

    def get_nodes(self) -> list[str]:
        return cmds.ls(dag=True) or []


DEFAULT_SELECT_FILTERS: list[SelectFilterBase] = [
    AllNodes(),
    SelectedNodes(),
    ShapesOfSelected(),
    HierarchyOfSelected(),
    HistoryOfSelected(),
    FutureOfSelected(),
    ConnectionsOfSelected(),
    DAGNodes(),
]


# ---------------------------------------------------------------------------
# Node filtering functions
# ---------------------------------------------------------------------------


def filter_by_node_type(nodes: list[str], type_str: str, inherited: bool = False) -> list[str]:
    """Filter nodes by node type.

    Args:
        nodes: List of node names.
        type_str: Node type string to match.
        inherited: If False, exact match with cmds.nodeType(node).
            If True, check if type_str is in cmds.nodeType(node, inherited=True).

    Returns:
        list[str]: Filtered node names.
    """
    if not type_str:
        return nodes
    result = []
    for node in nodes:
        if inherited:
            types = cmds.nodeType(node, inherited=True) or []
            if type_str in types:
                result.append(node)
        else:
            if cmds.nodeType(node) == type_str:
                result.append(node)
    return result


def filter_by_name(nodes: list[str], pattern: str, ignorecase: bool = False) -> list[str]:
    """Filter nodes by name using regex search.

    Args:
        nodes: List of node names.
        pattern: Regular expression pattern (matched via re.search).
        ignorecase: If True, use case-insensitive matching.

    Returns:
        list[str]: Filtered node names.
    """
    if not pattern:
        return nodes
    flags = re.IGNORECASE if ignorecase else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error:
        return nodes
    return [node for node in nodes if compiled.search(node)]


# ---------------------------------------------------------------------------
# Attribute listing functions
# ---------------------------------------------------------------------------


def list_attributes(node: str, except_attr_types: list[str] | None = None) -> list[str]:
    """List writable attributes of a node.

    Includes default transform attributes (for transform nodes), user-defined
    attributes, and other writable attributes excluding compound attributes
    and specified types.

    Args:
        node: The node name.
        except_attr_types: Attribute types to exclude.
            Defaults to ["message", "TdataCompound"].

    Returns:
        list[str]: List of attribute names.
    """
    if except_attr_types is None:
        except_attr_types = ["message", "TdataCompound"]

    result_attrs: list[str] = []

    if "transform" in (cmds.nodeType(node, inherited=True) or []):
        result_attrs.extend(DEFAULT_TRANSFORM_ATTRS)

    user_attrs = cmds.listAttr(node, userDefined=True)
    if user_attrs:
        result_attrs.extend(user_attrs)

    write_attrs = cmds.listAttr(node, write=True) or []
    for attr in write_attrs:
        if attr in result_attrs:
            continue
        try:
            if cmds.attributeQuery(attr, node=node, listChildren=True):
                continue
            if cmds.getAttr(f"{node}.{attr}", type=True) in except_attr_types:
                continue
            result_attrs.append(attr)
        except (RuntimeError, ValueError, TypeError) as e:
            logger.debug("Failed to query attribute: %s.%s: %s", node, attr, e)

    return result_attrs


def get_common_attributes(nodes: list[str]) -> list[str]:
    """Get attributes common to all given nodes.

    Args:
        nodes: List of node names.

    Returns:
        list[str]: Common attribute names, ordered by the first node.
    """
    if not nodes:
        return []

    first_attrs = list_attributes(nodes[0])

    if len(nodes) == 1:
        return first_attrs

    common_set = set(first_attrs)
    for node in nodes[1:]:
        common_set &= set(list_attributes(node))

    return [attr for attr in first_attrs if attr in common_set]
