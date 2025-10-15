"""Component selection operations for selecting components by various criteria."""

from logging import getLogger
from typing import Optional

import maya.api.OpenMaya as om
import maya.cmds as cmds

from ..lib.lib_componentfilter import ComponentFilter

logger = getLogger(__name__)


def _validate_components(components: list[str]) -> list[str]:
    """Validate and filter components.

    Only mesh, nurbsCurve, nurbsSurface, and lattice components are supported.

    Args:
        components (list[str]): List of component names

    Returns:
        list[str]: Validated component names

    Raises:
        ValueError: If components are not specified or not supported
    """
    if not components:
        raise ValueError("Components are not specified.")

    validated = cmds.filterExpand(components, sm=[28, 31, 32, 34, 46], ex=True)
    if not validated:
        raise ValueError("Components are not supported. Only mesh, nurbsCurve, nurbsSurface, and lattice components are supported.")

    return validated


def _get_component_positions(components: list[str]) -> list[tuple[float, float, float]]:
    """Get the component positions in world space.

    Args:
        components (list[str]): List of component names

    Returns:
        list[tuple[float, float, float]]: The component positions (x, y, z)
    """
    positions = cmds.xform(components, q=True, ws=True, t=True)
    return list(zip(positions[::3], positions[1::3], positions[2::3]))


def reverse_selection(components: list[str]) -> list[str]:
    """Reverse selection of components.

    When executed, the selected components will be inverted.

    Args:
        components (list[str]): List of component names

    Returns:
        list[str]: The reversed selected components
    """
    validated = _validate_components(components)
    cmds.select(validated, r=True)
    cmds.InvertSelection()
    return cmds.ls(sl=True, fl=True)


def unique_selection(components: list[str]) -> list[str]:
    """Unique selection of components.

    Need to soft select or symmetry enabled, before calling this function.

    Args:
        components (list[str]): List of component names

    Returns:
        list[str]: The unique selected components
    """
    validated = _validate_components(components)
    cmds.select(validated, r=True)
    return list(get_unique_selections().keys())


def x_area_selection(components: list[str], area: str = "center") -> list[str]:
    """X area selection of components.

    Args:
        components (list[str]): List of component names
        area (str): The area to select components. Default is 'center'. Options are 'center', 'left', and 'right'.

    Returns:
        list[str]: The area selected components

    Raises:
        ValueError: If area is invalid
    """
    if area not in ["center", "left", "right"]:
        raise ValueError(f"Invalid area: {area}")

    validated = _validate_components(components)
    positions = _get_component_positions(validated)

    if area == "center":
        result_components = [component for component, position in zip(validated, positions) if 0.001 > position[0] > -0.001]
        logger.debug(f"Center area components: {result_components}")
    elif area == "left":
        result_components = [component for component, position in zip(validated, positions) if position[0] > 0.001]
        logger.debug(f"Left area components: {result_components}")
    elif area == "right":
        result_components = [component for component, position in zip(validated, positions) if position[0] < -0.001]
        logger.debug(f"Right area components: {result_components}")

    logger.debug(f"X area components: {result_components}")

    return result_components


def same_position_selection(components: list[str], driver_mesh: str, *, max_distance: float = 0.001) -> list[str]:
    """Same position selection of components.

    Driver object only supports mesh geometry.

    Args:
        components (list[str]): List of component names
        driver_mesh (str): The driver mesh object
        max_distance (float): The maximum distance to consider as the same position. Default is 0.001.

    Returns:
        list[str]: The same position selected components

    Raises:
        ValueError: If driver_mesh is not specified, does not exist, or is not a mesh
    """
    if not driver_mesh:
        raise ValueError("Driver mesh is not specified.")

    if not cmds.objExists(driver_mesh):
        raise ValueError(f"Driver mesh does not exist: {driver_mesh}")

    if cmds.nodeType(driver_mesh) != "mesh":
        raise ValueError(f"Driver mesh is not a mesh: {driver_mesh}")

    validated = _validate_components(components)

    selection_list = om.MSelectionList()
    selection_list.add(driver_mesh)
    mesh_dag_path = selection_list.getDagPath(0)

    mesh_intersector = om.MMeshIntersector()
    mesh_intersector.create(mesh_dag_path.node(), mesh_dag_path.inclusiveMatrix())

    component_positions = _get_component_positions(validated)

    result_components = []
    for component, position in zip(validated, component_positions):
        component_point = om.MPoint(position)
        point_on_mesh = mesh_intersector.getClosestPoint(component_point, max_distance)

        if point_on_mesh is not None:
            continue

        result_components.append(component)

    logger.debug(f"Same position components: {result_components}")

    return result_components


def uv_area_selection(components: list[str], uv: str = "u", area: Optional[list[float]] = None) -> list[str]:
    """UV area selection of components.

    Only nurbsCurve and nurbsSurface components are supported.

    Args:
        components (list[str]): List of component names
        uv (str): The UV direction to select components. Default is 'u'. Options are 'u' and 'v'.
        area (list[float]): The UV area to select components. Default is [0.0, 1.0].

    Returns:
        list[str]: The parameter selected components

    Raises:
        ValueError: If components are not supported, uv parameter is invalid, or area is invalid
    """
    if area is None:
        area = [0.0, 1.0]

    validated = _validate_components(components)
    nurbs_components = cmds.filterExpand(validated, sm=28, ex=True)
    if not nurbs_components:
        raise ValueError("Components are not supported. Only nurbsCurve and nurbsSurface components are supported.")

    if uv not in ["u", "v"]:
        raise ValueError(f"Invalid parameter. u or v: {uv}")

    if len(area) != 2:
        raise ValueError("Invalid parameter area. Must be a list of two values.")

    if area[0] > area[1]:
        raise ValueError("Invalid parameter area. Minimum value is greater than maximum value.")

    result_components = []

    filter_components = ComponentFilter(nurbs_components)
    if filter_components.has_curve_cv():
        component_data = filter_components.get_curve_cvs()
        for shape, indices in component_data.items():
            shape_transform = cmds.listRelatives(shape, parent=True, path=True)[0]
            for index in indices:
                if area[0] <= index <= area[1]:
                    result_components.append(f"{shape_transform}.cv[{index}]")

    if filter_components.has_surface_cv():
        component_data = filter_components.get_surface_cvs()
        for shape, indices in component_data.items():
            shape_transform = cmds.listRelatives(shape, parent=True, path=True)[0]
            for index in indices:
                if uv == "u":
                    if area[0] <= index[0] <= area[1]:
                        result_components.append(f"{shape_transform}.cv[{index[0]}][{index[1]}]")
                elif uv == "v" and area[0] <= index[1] <= area[1]:
                    result_components.append(f"{shape_transform}.cv[{index[0]}][{index[1]}]")

    logger.debug(f"Parameter components: {result_components}")

    return result_components


def get_unique_selections(filter_geometries: Optional[list[str]] = None) -> dict[str, float]:
    """Get the unique components from rich selection.

    This function retrieves components with their weights from Maya's rich selection
    (which includes soft selection and symmetry).

    Args:
        filter_geometries (list[str]): List of geometry names to filter the components.

    Returns:
        dict[str, float]: The selected components with their weights

    Raises:
        ValueError: If geometry does not exist or is not a mesh
    """
    if filter_geometries is None:
        filter_geometries_path = []
    else:
        if not isinstance(filter_geometries, list):
            raise ValueError("filter_geometries must be a list of geometry names.")

        filter_geometries_path = []
        for geometry in filter_geometries:
            if not cmds.objExists(geometry):
                raise ValueError(f"Geometry does not exist: {geometry}")

            if cmds.nodeType(geometry) != "mesh":
                raise ValueError(f"Geometry is not a mesh: {geometry}")

            selection_list = om.MSelectionList()
            selection_list.add(geometry)
            dag_path = selection_list.getDagPath(0)

            filter_geometries_path.append(dag_path)

    rich_selection = om.MGlobal.getRichSelection()
    selection = rich_selection.getSelection()
    sym_selection = rich_selection.getSymmetry()
    if selection.isEmpty():
        logger.debug("No selection found.")
        return {}

    if not sym_selection.isEmpty():
        selection.merge(sym_selection)

    elements = {}

    def _process_single_indexed(selection_list, attr_list):
        """Process single indexed components.

        Args:
            selection_list (list): List of component types
            attr_list (list): List of attribute names
        """
        for component_type, attr in zip(selection_list, attr_list):
            iterator = om.MItSelectionList(selection, component_type)
            while not iterator.isDone():
                dag_path, component = iterator.getComponent()
                if filter_geometries_path and dag_path not in filter_geometries_path:
                    iterator.next()
                    continue

                dag_path.pop()  # Remove shape node
                node = dag_path.partialPathName()
                fn_comp = om.MFnSingleIndexedComponent(component)
                for i in range(fn_comp.elementCount):
                    index = fn_comp.element(i)
                    weight = fn_comp.weight(i).influence if fn_comp.hasWeights else 1.0
                    elements[f"{node}.{attr}[{index}]"] = weight

                logger.debug(f"Found components: {elements}")

                iterator.next()

    def _process_double_indexed(selection_list, attr_list):
        """Process double indexed components.

        Args:
            selection_list (list): List of component types
            attr_list (list): List of attribute names
        """
        for component_type, attr in zip(selection_list, attr_list):
            iterator = om.MItSelectionList(selection, component_type)
            while not iterator.isDone():
                dag_path, component = iterator.getComponent()
                if filter_geometries_path and dag_path not in filter_geometries_path:
                    iterator.next()
                    continue

                dag_path.pop()
                node = dag_path.partialPathName()
                fn_comp = om.MFnDoubleIndexedComponent(component)
                for i in range(fn_comp.elementCount):
                    u, v = fn_comp.getElement(i)
                    weight = fn_comp.weight(i).influence if fn_comp.hasWeights else 1.0
                    elements[f"{node}.{attr}[{u}][{v}]"] = weight

                logger.debug(f"Found components: {elements}")

                iterator.next()

    def _process_triple_indexed(selection_list, attr_list):
        """Process triple indexed components.

        Args:
            selection_list (list): List of component types
            attr_list (list): List of attribute names
        """
        for component_type, attr in zip(selection_list, attr_list):
            iterator = om.MItSelectionList(selection, component_type)
            while not iterator.isDone():
                dag_path, component = iterator.getComponent()
                if filter_geometries_path and dag_path not in filter_geometries_path:
                    iterator.next()
                    continue

                dag_path.pop()
                node = dag_path.partialPathName()
                fn_comp = om.MFnTripleIndexedComponent(component)
                for i in range(fn_comp.elementCount):
                    s, t, u = fn_comp.getElement(i)
                    weight = fn_comp.weight(i).influence if fn_comp.hasWeights else 1.0
                    elements[f"{node}.{attr}[{s}][{t}][{u}]"] = weight

                logger.debug(f"Found components: {elements}")

                iterator.next()

    _process_single_indexed(
        [om.MFn.kCurveCVComponent, om.MFn.kCurveEPComponent, om.MFn.kMeshVertComponent, om.MFn.kMeshEdgeComponent, om.MFn.kMeshPolygonComponent],
        ["cv", "ep", "vtx", "e", "f"],
    )

    _process_double_indexed(
        [om.MFn.kSurfaceCVComponent, om.MFn.kSubdivCVComponent, om.MFn.kSubdivEdgeComponent, om.MFn.kSubdivFaceComponent], ["cv", "smp", "sme", "smf"]
    )

    _process_triple_indexed([om.MFn.kLatticeComponent], ["pt"])

    return elements
