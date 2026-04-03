# __ppi_no_compile
"""
Commands for mesh vertex positions.

Overview:
This plugin provides commands to get and set mesh vertex positions with undo/redo support.
Supports world and object space, and partial vertex updates via index specification.

Commands:

SetMeshPoints

Set mesh vertex positions.

-positions (-pos): Vertex positions as flat floats [x0, y0, z0, x1, y1, z1, ...].
-indices (-idx): Vertex indices to set. If omitted, sets all vertices.
-worldSpace (-ws): Use world space (default).
-objectSpace (-os): Use object space.

cmds.setMeshPoints('meshShape', positions=[0, 1, 2, 3, 4, 5], indices=[0, 1])
cmds.setMeshPoints('meshShape', positions=[0, 1, 2, 3, 4, 5], objectSpace=True)


GetMeshPoints

Get mesh vertex positions.

-indices (-idx): Vertex indices to get. If omitted, gets all vertices.
-worldSpace (-ws): Use world space (default).
-objectSpace (-os): Use object space.

cmds.getMeshPoints('meshShape')
cmds.getMeshPoints('meshShape', indices=[0, 1, 2])
cmds.getMeshPoints('meshShape', objectSpace=True)
"""

import sys

from maya.api import OpenMaya
import maya.cmds as cmds


def maya_useNewAPI():
    pass


def _get_mesh_fn(mesh_name: str) -> tuple[OpenMaya.MFnMesh, OpenMaya.MDagPath]:
    """Get MFnMesh and MDagPath from mesh name.

    Args:
        mesh_name (str): The mesh shape name.

    Returns:
        tuple[MFnMesh, MDagPath]: The mesh function set and dag path.

    Raises:
        RuntimeError: If the mesh is not found or not a mesh.
    """
    selection = OpenMaya.MSelectionList()
    selection.add(mesh_name)
    dag_path = selection.getDagPath(0)

    if not dag_path.hasFn(OpenMaya.MFn.kMesh):
        raise RuntimeError(f"Not a mesh: {mesh_name}")

    return OpenMaya.MFnMesh(dag_path), dag_path


class SetMeshPoints(OpenMaya.MPxCommand):
    """Command to set mesh vertex positions with undo/redo support."""

    plugin_cmd_name = "setMeshPoints"

    positions_flag = "-pos"
    positions_flag_long = "-positions"
    indices_flag = "-idx"
    indices_flag_long = "-indices"
    ws_flag = "-ws"
    ws_flag_long = "-worldSpace"
    os_flag = "-os"
    os_flag_long = "-objectSpace"

    def __init__(self):
        OpenMaya.MPxCommand.__init__(self)

        self.mesh_name = None
        self.positions = None
        self.indices = None
        self.space = OpenMaya.MSpace.kWorld

        self.old_positions = None

    @staticmethod
    def cmdCreator():
        return SetMeshPoints()

    @classmethod
    def syntaxCreator(cls):
        syntax = OpenMaya.MSyntax()

        # mesh shape name
        syntax.addArg(OpenMaya.MSyntax.kString)

        # positions (flat floats: x0, y0, z0, x1, y1, z1, ...)
        syntax.addFlag(cls.positions_flag, cls.positions_flag_long, OpenMaya.MSyntax.kDouble)
        syntax.makeFlagMultiUse(cls.positions_flag)

        # indices
        syntax.addFlag(cls.indices_flag, cls.indices_flag_long, OpenMaya.MSyntax.kLong)
        syntax.makeFlagMultiUse(cls.indices_flag)

        # space
        syntax.addFlag(cls.ws_flag, cls.ws_flag_long, OpenMaya.MSyntax.kBoolean)
        syntax.addFlag(cls.os_flag, cls.os_flag_long, OpenMaya.MSyntax.kBoolean)

        syntax.enableQuery = False
        syntax.enableEdit = False

        return syntax

    def parse_args(self, args):
        """Parse command arguments.

        Args:
            args (MArgList): The arguments.

        Returns:
            bool: True if successful, False otherwise.
        """
        arg_data = OpenMaya.MArgParser(self.syntax(), args)

        # Mesh name
        self.mesh_name = arg_data.commandArgumentString(0)
        if not self.mesh_name:
            OpenMaya.MGlobal.displayError("Mesh name is required.")
            return False

        if not cmds.objExists(self.mesh_name):
            OpenMaya.MGlobal.displayError(f"Mesh not found: {self.mesh_name}")
            return False

        # Positions
        if not arg_data.isFlagSet(self.positions_flag):
            OpenMaya.MGlobal.displayError("Positions flag is required.")
            return False

        flat_positions = []
        num_uses = arg_data.numberOfFlagUses(self.positions_flag)
        for i in range(num_uses):
            value = arg_data.getFlagArgumentList(self.positions_flag, i).asDouble(0)
            flat_positions.append(value)

        if len(flat_positions) % 3 != 0:
            OpenMaya.MGlobal.displayError(f"Positions must be multiples of 3, got {len(flat_positions)}.")
            return False

        self.positions = OpenMaya.MPointArray()
        for i in range(0, len(flat_positions), 3):
            self.positions.append(OpenMaya.MPoint(flat_positions[i], flat_positions[i + 1], flat_positions[i + 2]))

        # Indices (optional)
        if arg_data.isFlagSet(self.indices_flag):
            self.indices = []
            num_idx = arg_data.numberOfFlagUses(self.indices_flag)
            for i in range(num_idx):
                value = arg_data.getFlagArgumentList(self.indices_flag, i).asInt(0)
                self.indices.append(value)

            if len(self.indices) != len(self.positions):
                OpenMaya.MGlobal.displayError(f"Number of indices ({len(self.indices)}) doesn't match number of positions ({len(self.positions)}).")
                return False

        # Space (default: world)
        ws_set = arg_data.isFlagSet(self.ws_flag) and arg_data.flagArgumentBool(self.ws_flag, 0)
        os_set = arg_data.isFlagSet(self.os_flag) and arg_data.flagArgumentBool(self.os_flag, 0)
        if ws_set and os_set:
            OpenMaya.MGlobal.displayError("Cannot specify both worldSpace and objectSpace.")
            return False
        if os_set:
            self.space = OpenMaya.MSpace.kObject

        return True

    def doIt(self, args):
        status = self.parse_args(args)
        if not status:
            return

        # Validate mesh and store old positions
        try:
            mesh_fn, _ = _get_mesh_fn(self.mesh_name)
        except RuntimeError as e:
            OpenMaya.MGlobal.displayError(str(e))
            return

        if self.indices is None:
            # All vertices
            if len(self.positions) != mesh_fn.numVertices:
                OpenMaya.MGlobal.displayError(f"Number of positions ({len(self.positions)}) doesn't match vertex count ({mesh_fn.numVertices}).")
                return
        else:
            # Validate indices
            num_vertices = mesh_fn.numVertices
            for idx in self.indices:
                if idx < 0 or idx >= num_vertices:
                    OpenMaya.MGlobal.displayError(f"Vertex index out of range: {idx}")
                    return

        self.redoIt()

    def redoIt(self):
        try:
            mesh_fn, _ = _get_mesh_fn(self.mesh_name)
        except RuntimeError as e:
            OpenMaya.MGlobal.displayError(str(e))
            return

        # Save old positions for undo
        current_points = mesh_fn.getPoints(self.space)

        if self.indices is None:
            self.old_positions = OpenMaya.MPointArray(current_points)
            mesh_fn.setPoints(self.positions, self.space)
        else:
            self.old_positions = OpenMaya.MPointArray(current_points)
            for i, idx in enumerate(self.indices):
                current_points[idx] = self.positions[i]
            mesh_fn.setPoints(current_points, self.space)

    def undoIt(self):
        try:
            mesh_fn, _ = _get_mesh_fn(self.mesh_name)
        except RuntimeError as e:
            OpenMaya.MGlobal.displayError(str(e))
            return

        mesh_fn.setPoints(self.old_positions, self.space)

    def isUndoable(self):
        return True


class GetMeshPoints(OpenMaya.MPxCommand):
    """Command to get mesh vertex positions."""

    plugin_cmd_name = "getMeshPoints"

    indices_flag = "-idx"
    indices_flag_long = "-indices"
    ws_flag = "-ws"
    ws_flag_long = "-worldSpace"
    os_flag = "-os"
    os_flag_long = "-objectSpace"

    def __init__(self):
        OpenMaya.MPxCommand.__init__(self)

        self.mesh_name = None
        self.indices = None
        self.space = OpenMaya.MSpace.kWorld

    @staticmethod
    def cmdCreator():
        return GetMeshPoints()

    @classmethod
    def syntaxCreator(cls):
        syntax = OpenMaya.MSyntax()

        # mesh shape name
        syntax.addArg(OpenMaya.MSyntax.kString)

        # indices
        syntax.addFlag(cls.indices_flag, cls.indices_flag_long, OpenMaya.MSyntax.kLong)
        syntax.makeFlagMultiUse(cls.indices_flag)

        # space
        syntax.addFlag(cls.ws_flag, cls.ws_flag_long, OpenMaya.MSyntax.kBoolean)
        syntax.addFlag(cls.os_flag, cls.os_flag_long, OpenMaya.MSyntax.kBoolean)

        syntax.enableQuery = False
        syntax.enableEdit = False

        return syntax

    def parse_args(self, args):
        """Parse command arguments.

        Args:
            args (MArgList): The arguments.

        Returns:
            bool: True if successful, False otherwise.
        """
        arg_data = OpenMaya.MArgParser(self.syntax(), args)

        # Mesh name
        self.mesh_name = arg_data.commandArgumentString(0)
        if not self.mesh_name:
            OpenMaya.MGlobal.displayError("Mesh name is required.")
            return False

        if not cmds.objExists(self.mesh_name):
            OpenMaya.MGlobal.displayError(f"Mesh not found: {self.mesh_name}")
            return False

        # Indices (optional)
        if arg_data.isFlagSet(self.indices_flag):
            self.indices = []
            num_idx = arg_data.numberOfFlagUses(self.indices_flag)
            for i in range(num_idx):
                value = arg_data.getFlagArgumentList(self.indices_flag, i).asInt(0)
                self.indices.append(value)

        # Space (default: world)
        ws_set = arg_data.isFlagSet(self.ws_flag) and arg_data.flagArgumentBool(self.ws_flag, 0)
        os_set = arg_data.isFlagSet(self.os_flag) and arg_data.flagArgumentBool(self.os_flag, 0)
        if ws_set and os_set:
            OpenMaya.MGlobal.displayError("Cannot specify both worldSpace and objectSpace.")
            return False
        if os_set:
            self.space = OpenMaya.MSpace.kObject

        return True

    def doIt(self, args):
        status = self.parse_args(args)
        if not status:
            return

        try:
            mesh_fn, _ = _get_mesh_fn(self.mesh_name)
        except RuntimeError as e:
            OpenMaya.MGlobal.displayError(str(e))
            return

        points = mesh_fn.getPoints(self.space)

        if self.indices is not None:
            num_vertices = mesh_fn.numVertices
            for idx in self.indices:
                if idx < 0 or idx >= num_vertices:
                    OpenMaya.MGlobal.displayError(f"Vertex index out of range: {idx}")
                    return

            result = OpenMaya.MDoubleArray()
            for idx in self.indices:
                result.append(points[idx].x)
                result.append(points[idx].y)
                result.append(points[idx].z)
        else:
            result = OpenMaya.MDoubleArray()
            for i in range(len(points)):
                result.append(points[i].x)
                result.append(points[i].y)
                result.append(points[i].z)

        self.setResult(result)

    def isUndoable(self):
        return False


# Initialize and uninitialize the plugin


def initializePlugin(plugin):
    """Initialize the plugin."""
    plugin_fn = OpenMaya.MFnPlugin(plugin, "Mitsuaki Watanabe", "1.0", "Any")

    try:
        plugin_fn.registerCommand(SetMeshPoints.plugin_cmd_name, SetMeshPoints.cmdCreator, SetMeshPoints.syntaxCreator)
    except Exception as e:
        sys.stderr.write(f"Failed to register command: {SetMeshPoints.plugin_cmd_name}")
        raise e

    try:
        plugin_fn.registerCommand(GetMeshPoints.plugin_cmd_name, GetMeshPoints.cmdCreator, GetMeshPoints.syntaxCreator)
    except Exception as e:
        sys.stderr.write(f"Failed to register command: {GetMeshPoints.plugin_cmd_name}")
        raise e


def uninitializePlugin(plugin):
    """Uninitialize the plugin."""
    plugin_fn = OpenMaya.MFnPlugin(plugin)

    try:
        plugin_fn.deregisterCommand(SetMeshPoints.plugin_cmd_name)
    except Exception as e:
        sys.stderr.write(f"Failed to unregister command: {SetMeshPoints.plugin_cmd_name}")
        raise e

    try:
        plugin_fn.deregisterCommand(GetMeshPoints.plugin_cmd_name)
    except Exception as e:
        sys.stderr.write(f"Failed to unregister command: {GetMeshPoints.plugin_cmd_name}")
        raise e
