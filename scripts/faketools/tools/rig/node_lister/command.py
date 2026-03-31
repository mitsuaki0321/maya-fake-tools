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
    if inherited:
        matched = set(cmds.ls(nodes, type=type_str) or [])
    else:
        matched = set(cmds.ls(nodes, exactType=type_str) or [])
    return [node for node in nodes if node in matched]


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


_EXCEPT_ATTR_TYPES = {"message", "TdataCompound"}


def _list_type_attributes(node: str) -> tuple[list[str], list[str]]:
    """List type-level attributes of a node.

    Queries attribute information (compound check, type check) for a
    representative node. Results are the same for all nodes of the same type.

    Args:
        node: A representative node name.

    Returns:
        Pair of (transform_attrs, write_attrs) excluding user-defined attributes.
    """
    transform_attrs: list[str] = []
    if "transform" in (cmds.nodeType(node, inherited=True) or []):
        transform_attrs = list(DEFAULT_TRANSFORM_ATTRS)

    user_attrs_set = set(cmds.listAttr(node, userDefined=True) or [])
    skip_set = set(transform_attrs) | user_attrs_set

    write_attrs: list[str] = []
    for attr in cmds.listAttr(node, write=True) or []:
        if attr in skip_set:
            continue
        try:
            if cmds.attributeQuery(attr, node=node, listChildren=True):
                continue
            if cmds.getAttr(f"{node}.{attr}", type=True) in _EXCEPT_ATTR_TYPES:
                continue
            write_attrs.append(attr)
            skip_set.add(attr)
        except (RuntimeError, ValueError, TypeError) as e:
            logger.debug("Failed to query attribute: %s.%s: %s", node, attr, e)

    return transform_attrs, write_attrs


def get_common_attributes(nodes: list[str]) -> list[str]:
    """Get attributes common to all given nodes.

    Groups nodes by type and queries type-level attributes only once
    per unique node type. User-defined attributes are queried per node.

    Args:
        nodes: List of node names.

    Returns:
        list[str]: Common attribute names, ordered by the first node.
    """
    if not nodes:
        return []

    # Group nodes by type
    node_type_map: dict[str, str] = {}
    type_groups: dict[str, list[str]] = {}
    for node in nodes:
        ntype = cmds.nodeType(node)
        node_type_map[node] = ntype
        type_groups.setdefault(ntype, []).append(node)

    # Cache type-level attributes (one expensive query per unique type)
    type_cache: dict[str, tuple[list[str], list[str]]] = {}
    for ntype, group in type_groups.items():
        type_cache[ntype] = _list_type_attributes(group[0])

    # User-defined attributes per node (cheap, no attributeQuery/getAttr)
    user_attrs_map: dict[str, list[str]] = {}
    for node in nodes:
        user_attrs_map[node] = cmds.listAttr(node, userDefined=True) or []

    def build_attrs(node: str) -> list[str]:
        transform_attrs, write_attrs = type_cache[node_type_map[node]]
        return transform_attrs + user_attrs_map[node] + write_attrs

    first_attrs = build_attrs(nodes[0])

    if len(nodes) == 1:
        return first_attrs

    common_set = set(first_attrs)
    for node in nodes[1:]:
        common_set &= set(build_attrs(node))

    return [attr for attr in first_attrs if attr in common_set]
