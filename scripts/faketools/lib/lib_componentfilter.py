"""Component filter functions for filtering components by type."""

from logging import getLogger

import maya.api.OpenMaya as om
import maya.cmds as cmds

logger = getLogger(__name__)


class ComponentFilter:
    """Component filter class for filtering components by type."""

    def __init__(self, components: list[str]):
        """Initialize the component filter with a list of components.

        Args:
            components (list[str]): List of component names
        """
        self._selection_list = om.MSelectionList()
        self.add_selection_list(components)

    def add_selection_list(self, components: list[str]) -> None:
        """Add components to the selection list."""
        for component in components:
            self._selection_list.add(component)

    def clear_selection_list(self) -> None:
        """Clear the selection list."""
        self._selection_list.clear()

    def has_component(self) -> bool:
        """Check if the selection list has any components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kComponent)
        return not it_selection_list.isDone()

    def has_vertex(self) -> bool:
        """Check if the selection list has vertex components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kMeshVertComponent)
        return not it_selection_list.isDone()

    def has_edge(self) -> bool:
        """Check if the selection list has edge components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kMeshEdgeComponent)
        return not it_selection_list.isDone()

    def has_face(self) -> bool:
        """Check if the selection list has face components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kMeshPolygonComponent)
        return not it_selection_list.isDone()

    def has_curve_cv(self) -> bool:
        """Check if the selection list has curve CV components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kCurveCVComponent)
        return not it_selection_list.isDone()

    def has_curve_ep(self) -> bool:
        """Check if the selection list has curve EP components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kCurveEPComponent)
        return not it_selection_list.isDone()

    def has_surface_cv(self) -> bool:
        """Check if the selection list has surface CV components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kSurfaceCVComponent)
        return not it_selection_list.isDone()

    def has_lattice_point(self) -> bool:
        """Check if the selection list has lattice point components."""
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kLatticeComponent)
        return not it_selection_list.isDone()

    def get_vertices(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of vertex components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[int]]: The mesh shape name and vertex indices.
        """
        component_data = self._get_single_components(om.MFn.kMeshVertComponent)
        if as_component_name and component_data:
            for shape, indices in component_data.items():
                geometry = cmds.listRelatives(shape, parent=True, path=True)[0]
                component_data[shape] = [f"{geometry}.vtx[{i}]" for i in indices]

        return component_data

    def get_edges(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of edge components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[int]]: The mesh shape name and edge indices.
        """
        component_data = self._get_single_components(om.MFn.kMeshEdgeComponent)
        if as_component_name and component_data:
            for shape, indices in component_data.items():
                geometry = cmds.listRelatives(shape, parent=True, path=True)[0]
                component_data[shape] = [f"{geometry}.e[{i}]" for i in indices]

        return component_data

    def get_faces(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of face components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[int]]: The mesh shape name and face indices.
        """
        component_data = self._get_single_components(om.MFn.kMeshPolygonComponent)
        if as_component_name and component_data:
            for shape, indices in component_data.items():
                geometry = cmds.listRelatives(shape, parent=True, path=True)[0]
                component_data[shape] = [f"{geometry}.f[{i}]" for i in indices]

        return component_data

    def get_curve_cvs(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of curve CV components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[int]]: The nurbsCurve shape name and CV indices.
        """
        component_data = self._get_single_components(om.MFn.kCurveCVComponent)
        if as_component_name and component_data:
            for shape, indices in component_data.items():
                component_data[shape] = [f"{shape}.cv[{i}]" for i in indices]

        return component_data

    def get_curve_eps(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of curve EP components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[int]]: The nurbsCurve shape name and EP indices.
        """
        component_data = self._get_single_components(om.MFn.kCurveEPComponent)
        if as_component_name and component_data:
            for shape, indices in component_data.items():
                component_data[shape] = [f"{shape}.ep[{i}]" for i in indices]

        return component_data

    def get_surface_cvs(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of surface CV components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[tuple[int, int]]]: The nurbsSurface shape name and UV indices ( pair indices ).
        """
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kSurfaceCVComponent)
        if it_selection_list.isDone():
            return {}

        result_components = {}
        while not it_selection_list.isDone():
            node, component = it_selection_list.getComponent()
            double_index_component = om.MFnDoubleIndexedComponent(component)
            result_components[node.partialPathName()] = double_index_component.getElements()
            it_selection_list.next()

        logger.debug(f"Found components: {result_components}")

        if as_component_name and result_components:
            for shape, indices in result_components.items():
                geometry = cmds.listRelatives(shape, parent=True, path=True)[0]
                result_components[shape] = [f"{geometry}.cv[{i[0]}][{i[1]}]" for i in indices]

        return result_components

    def get_lattice_points(self, as_component_name: bool = False) -> dict[str, list[int]]:
        """Get a list of lattice point components.

        Args:
            as_component_name (bool): Return the component name instead of the index.

        Returns:
            dict[str, list[tuple[int, int, int]]]: The lattice shape name and lattice indices ( tuple indices ).
        """
        it_selection_list = om.MItSelectionList(self._selection_list, om.MFn.kLatticeComponent)
        if it_selection_list.isDone():
            return {}

        result_components = {}
        while not it_selection_list.isDone():
            node, component = it_selection_list.getComponent()
            triple_index_component = om.MFnTripleIndexedComponent(component)
            result_components[node.partialPathName()] = triple_index_component.getElements()
            it_selection_list.next()

        logger.debug(f"Found components: {result_components}")

        if as_component_name and result_components:
            for shape, indices in result_components.items():
                geometry = cmds.listRelatives(shape, parent=True, path=True)[0]
                result_components[shape] = [f"{geometry}.pt[{i[0]}][{i[1]}][{i[2]}]" for i in indices]

        return result_components

    def get_components(self, component_type: list[str]) -> dict[str, list[int]]:
        """Get a list of components by type.

        Args:
            component_type (list[str]): List of component types.

        Returns:
            dict[str, list[int]]: The shape name and component indices.
        """
        component_data = {}
        for component in component_type:
            if component == "vertex":
                component_data.update(self.get_vertices(as_component_name=True))
            elif component == "edge":
                component_data.update(self.get_edges(as_component_name=True))
            elif component == "face":
                component_data.update(self.get_faces(as_component_name=True))
            elif component == "curve_cv":
                component_data.update(self.get_curve_cvs(as_component_name=True))
            elif component == "curve_ep":
                component_data.update(self.get_curve_eps(as_component_name=True))
            elif component == "surface_cv":
                component_data.update(self.get_surface_cvs(as_component_name=True))
            elif component == "lattice_point":
                component_data.update(self.get_lattice_points(as_component_name=True))
            else:
                logger.warning(f"Unknown component type: {component}")

        return component_data

    def _get_single_components(self, component_type: om.MFn.kComponent) -> dict[str, list[int]]:
        """Get a list of single components.

        Args:
            component_type (om.MFn.kComponent): The component type.

        Returns:
            dict[str, list[int]]: The shape name and component indices.
        """
        it_selection_list = om.MItSelectionList(self._selection_list, component_type)
        if it_selection_list.isDone():
            return {}

        result_components = {}
        while not it_selection_list.isDone():
            node, component = it_selection_list.getComponent()
            single_index_component = om.MFnSingleIndexedComponent(component)
            result_components[node.partialPathName()] = list(single_index_component.getElements())
            it_selection_list.next()

        logger.debug(f"Found components: {result_components}")

        return result_components
