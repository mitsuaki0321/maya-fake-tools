# __ppi_no_compile
"""
Command for skinCluster weights.

Overview:
This command provides functionality to export and import skinCluster weights.
Additionally, it offers the ability to copy skinCluster weights. During copying,
it can copy only unlocked influences or reference the original shape.

Limitations:

SkinCluster method is only classic linear mode.

Commands:

SkinWeightExport

Export skinCluster weights.

-components (-cps): Specify the components to export.

cmds.skinWeightExport('skinCluster1', components=['pCube1.vtx[0:3]'])


SkinWeightImport

Import skinCluster weights.

-components (-cps): Specify the components to import.
-weights (-w): Specify the weights to import.

cmds.skinWeightImport('skinCluster1', components=['pCube1.vtx[0:3]'], weights=[0.5, 0.5, 0.5, 0.5])


CopySkinWeightsCustom

Copy skinCluster weights.
The geometry referenced by the source skinCluster must be a mesh.

-sourceSkin (-ss): Specify the source skinCluster.
-destinationSkin (-ds): Specify the destination skinCluster.
-blendWeights (-bw): Specify the blend weights.
-onlyUnlockInfluences (-ouli): Lock influences.
-referenceOrigShape (-ros): Reference the original shape.

cmds.copySkinWeightsCustom(sourceSkin='skinCluster1', destinationSkin='skinCluster2', blendWeights=0.5, onlyUnlockInfluences=True)
"""

import sys

from maya.api import OpenMaya, OpenMayaAnim
import maya.cmds as cmds


def maya_useNewAPI():
    pass


class SkinWeightExport(OpenMaya.MPxCommand):
    """Command for skinCluster export weights."""

    # Command name
    plugin_cmd_name = "skinWeightExport"

    # Flags
    components_flag = "-cps"
    components_flag_long = "-components"

    def __init__(self):
        OpenMaya.MPxCommand.__init__(self)

        self.skinCluster_name = None
        self.components = None

    @staticmethod
    def cmdCreator():
        """ """
        return SkinWeightExport()

    @classmethod
    def syntaxCreator(cls):
        """ """
        syntax = OpenMaya.MSyntax()

        # skinCluster node
        syntax.addArg(OpenMaya.MSyntax.kString)

        # components
        syntax.addFlag(cls.components_flag, cls.components_flag_long, OpenMaya.MSyntax.kString)
        syntax.makeFlagMultiUse(cls.components_flag)

        syntax.enableQuery = False
        syntax.enableEdit = False

        return syntax

    def parse_args(self, args):
        """Get arguments from the command.

        Args:
            args (MArgList): The arguments.

        Returns:
            bool: True if successful, False otherwise.
        """
        arg_data = OpenMaya.MArgParser(self.syntax(), args)

        # Get skinCluster name from arguments
        self.skinCluster_name = arg_data.commandArgumentString(0)
        if not self.skinCluster_name:
            OpenMaya.MGlobal.displayError("SkinCluster name is required.")
            return False

        if not cmds.objExists(self.skinCluster_name):
            OpenMaya.MGlobal.displayError(f"SkinCluster not found: {self.skinCluster_name}")
            return False

        if cmds.nodeType(self.skinCluster_name) != "skinCluster":
            OpenMaya.MGlobal.displayError(f"Node is not a skinCluster: {self.skinCluster_name}")
            return False

        # Get components from arguments
        if arg_data.isFlagSet(self.components_flag):
            self.components = []
            components_flag_num = arg_data.numberOfFlagUses(self.components_flag)
            for i in range(components_flag_num):
                arg_list = arg_data.getFlagArgumentList(self.components_flag, i).asString(0)
                self.components.append(arg_list)
        else:
            OpenMaya.MGlobal.displayError("Components flag is required.")
            return False

        return True

    def doIt(self, args):
        """ """
        # Parse arguments
        status = self.parse_args(args)
        if not status:
            return

        # Get skinCluster node
        try:
            skinCluster_fn = get_skinCluster_fn(self.skinCluster_name)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.skinCluster_name}")
            return

        if not is_classic_linear(self.skinCluster_name):
            OpenMaya.MGlobal.displayError("Unsupported skinCluster method.")
            return

        # Get weights
        # Get component
        component_data = get_components_from_name(self.components)
        if not component_data:
            OpenMaya.MGlobal.displayError("Failed to get components.")
            return

        components_path, components_obj = component_data

        # Check if components_path is included in the skinCluster
        output_objs = skinCluster_fn.getOutputGeometry()
        if not output_objs:
            OpenMaya.MGlobal.displayError("No output geometry found in the skinCluster.")
            return

        include_geometry = False
        for output_obj in output_objs:
            if not output_obj.hasFn(OpenMaya.MFn.kDagNode):
                continue

            output_path = OpenMaya.MFnDagNode(output_obj).getPath()
            if components_path == output_path:
                include_geometry = True
                break

        if not include_geometry:
            OpenMaya.MGlobal.displayError("Components do not belong to the skinCluster geometry.")
            return

        # Get skinCluster weights
        weights, _ = skinCluster_fn.getWeights(components_path, components_obj)
        self.setResult(weights)

    def redoIt(self):
        """Suspends undo recording, performs the operation, and then resumes undo recording."""
        pass

    def undoIt(self):
        """Suspends undo recording, performs the operation, and then resumes undo recording."""
        pass

    def isUndoable(self):
        """Return whether the command is undoable."""
        return False


class SkinWeightImport(OpenMaya.MPxCommand):
    """Command for skinCluster import weights."""

    # Command name
    plugin_cmd_name = "skinWeightImport"

    # Flags
    components_flag = "-cps"
    components_flag_long = "-components"
    weight_flag = "-w"
    weight_flag_long = "-weights"

    def __init__(self):
        OpenMaya.MPxCommand.__init__(self)

        self.skinCluster_name = None
        self.components = None
        self.weights = None
        self.old_weights = None

    @staticmethod
    def cmdCreator():
        """ """
        return SkinWeightImport()

    @classmethod
    def syntaxCreator(cls):
        """ """
        syntax = OpenMaya.MSyntax()

        # skinCluster node
        syntax.addArg(OpenMaya.MSyntax.kString)

        # components
        syntax.addFlag(cls.components_flag, cls.components_flag_long, OpenMaya.MSyntax.kString)
        syntax.makeFlagMultiUse(cls.components_flag)

        # weights
        syntax.addFlag(cls.weight_flag, cls.weight_flag_long, OpenMaya.MSyntax.kDouble)
        syntax.makeFlagMultiUse(cls.weight_flag)

        syntax.enableQuery = False
        syntax.enableEdit = False

        return syntax

    def parse_args(self, args):
        """Parse arguments.

        Args:
            args (MArgList): The arguments.

        Returns:
            bool: True if successful, False otherwise.
        """
        arg_data = OpenMaya.MArgParser(self.syntax(), args)

        self.skinCluster_name = arg_data.commandArgumentString(0)

        if not arg_data.isFlagSet(self.components_flag) or not arg_data.isFlagSet(self.weight_flag):
            OpenMaya.MGlobal.displayError("Both -components and -weights flags must be set.")
            return False

        if arg_data.isFlagSet(self.components_flag):
            self.components = []
            components_flag_num = arg_data.numberOfFlagUses(self.components_flag)
            for i in range(components_flag_num):
                arg_list = arg_data.getFlagArgumentList(self.components_flag, i).asString(0)
                self.components.append(arg_list)

        if arg_data.isFlagSet(self.weight_flag):
            self.weights = OpenMaya.MDoubleArray()
            weight_flag_num = arg_data.numberOfFlagUses(self.weight_flag)
            for i in range(weight_flag_num):
                arg_list = arg_data.getFlagArgumentList(self.weight_flag, i).asDouble(0)
                self.weights.append(arg_list)

        return True

    def doIt(self, args):
        """ """
        # Parse arguments
        status = self.parse_args(args)
        if not status:
            return

        self.redoIt()

    def redoIt(self):
        """ """
        # Get skinCluster node
        try:
            skinCluster_fn = get_skinCluster_fn(self.skinCluster_name)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.skinCluster_name}")
            return

        if not is_classic_linear(self.skinCluster_name):
            OpenMaya.MGlobal.displayError("Unsupported skinCluster method.")
            return

        # Get weights
        # Get component
        geometry_path = skinCluster_fn.getPathAtIndex(0)

        component_data = get_components_from_name(self.components)
        if not component_data:
            return

        components_path, components_obj = component_data

        if components_path != geometry_path:
            OpenMaya.MGlobal.displayError("Component does not belong to the geometry.")
            return

        if components_obj.hasFn(OpenMaya.MFn.kSingleIndexedComponent):
            num_components = OpenMaya.MFnSingleIndexedComponent(components_obj).elementCount
        elif components_obj.hasFn(OpenMaya.MFn.kDoubleIndexedComponent):
            num_components = OpenMaya.MFnDoubleIndexedComponent(components_obj).elementCount
        elif components_obj.hasFn(OpenMaya.MFn.kTripleIndexedComponent):
            num_components = OpenMaya.MFnTripleIndexedComponent(components_obj).elementCount
        else:
            OpenMaya.MGlobal.displayError("Unsupported component type.")
            return

        num_infs = len(skinCluster_fn.influenceObjects())

        if len(self.weights) != (num_components * num_infs):
            OpenMaya.MGlobal.displayError("The number of weights does not match the number of components and influences.")
            return

        influences_index_array = OpenMaya.MIntArray(list(range(num_infs)))

        self.old_weights = skinCluster_fn.setWeights(geometry_path, components_obj, influences_index_array, self.weights, True, True)

    def undoIt(self):
        """ """
        try:
            skinCluster_fn = get_skinCluster_fn(self.skinCluster_name)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.skinCluster_name}")
            return

        geometry_path = skinCluster_fn.getPathAtIndex(0)
        infs_index_array = OpenMaya.MIntArray(list(range(len(skinCluster_fn.influenceObjects()))))

        selection = OpenMaya.MSelectionList()
        for component in self.components:
            selection.add(component)

        _, components_obj = selection.getComponent(0)

        self.old_weights = skinCluster_fn.setWeights(geometry_path, components_obj, infs_index_array, self.old_weights, True, True)

    def isUndoable(self):
        """Return whether the command is undoable."""
        return True


class CopySkinWeightsCustom(OpenMaya.MPxCommand):
    """Command for copying skinCluster weights.

    Notes:
        - Copy skinCluster weights from the source skinCluster to the destination skinCluster.
    """

    # Command name
    plugin_cmd_name = "copySkinWeightsCustom"

    # Flags
    src_flag = "-ss"
    src_flag_long = "-sourceSkin"
    dst_flag = "-ds"
    dst_flag_long = "-destinationSkin"
    blend_weights_flag = "-bw"
    blend_weights_flag_long = "-blendWeights"
    only_unlock_influences_flag = "-oui"
    only_unlock_influences_flag_long = "-onlyUnlockInfluences"
    reference_orig_flag = "-ros"
    reference_orig_flag_long = "-referenceOrigShape"

    def __init__(self):
        OpenMaya.MPxCommand.__init__(self)

        self.src_skinCluster = None
        self.dst_skinCluster = None
        self.only_unlock_infs = False
        self.reference_orig = False
        self.blend_weights = 1.0

        self.old_weights = None
        self.unlocked_infs = None

        self.components = []

    @staticmethod
    def cmdCreator():
        """ """
        return CopySkinWeightsCustom()

    @classmethod
    def syntaxCreator(cls):
        """ """
        syntax = OpenMaya.MSyntax()

        # source skinCluster
        syntax.addFlag(cls.src_flag, cls.src_flag_long, OpenMaya.MSyntax.kString)

        # destination skinCluster
        syntax.addFlag(cls.dst_flag, cls.dst_flag_long, OpenMaya.MSyntax.kString)

        # blend weights
        syntax.addFlag(cls.blend_weights_flag, cls.blend_weights_flag_long, OpenMaya.MSyntax.kDouble)

        # unlock influences
        syntax.addFlag(cls.only_unlock_influences_flag, cls.only_unlock_influences_flag_long, OpenMaya.MSyntax.kBoolean)

        # reference original shape
        syntax.addFlag(cls.reference_orig_flag, cls.reference_orig_flag_long, OpenMaya.MSyntax.kBoolean)

        syntax.enableQuery = False
        syntax.enableEdit = False

        return syntax

    def parse_args(self, args):
        """Parse arguments.

        Args:
            args (MArgList): The arguments.

        Returns:
            bool: True if successful, False otherwise.
        """
        arg_data = OpenMaya.MArgParser(self.syntax(), args)

        if not arg_data.isFlagSet(self.src_flag) or not arg_data.isFlagSet(self.dst_flag):
            OpenMaya.MGlobal.displayError("Both -source and -destination flags must be set.")
            return False

        self.src_skinCluster = arg_data.flagArgumentString(self.src_flag, 0)
        self.dst_skinCluster = arg_data.flagArgumentString(self.dst_flag, 0)

        if arg_data.isFlagSet(self.blend_weights_flag):
            self.blend_weights = arg_data.flagArgumentDouble(self.blend_weights_flag, 0)
            if self.blend_weights < 0.0 or self.blend_weights > 1.0:
                OpenMaya.MGlobal.displayError("Blend weights must be between 0.0 and 1.0.")
                return False

        if arg_data.isFlagSet(self.only_unlock_influences_flag):
            self.only_unlock_infs = arg_data.flagArgumentBool(self.only_unlock_influences_flag, 0)

        if arg_data.isFlagSet(self.reference_orig_flag):
            self.reference_orig = arg_data.flagArgumentBool(self.reference_orig_flag, 0)

        return True

    def doIt(self, args):
        """ """
        # Parse arguments
        status = self.parse_args(args)
        if not status:
            return

        self.redoIt()

    def redoIt(self):
        """ """
        # Get source skinCluster node
        try:
            src_skinCluster_fn = get_skinCluster_fn(self.src_skinCluster)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.src_skinCluster}")
            return

        # Get destination skinCluster node
        try:
            dst_skinCluster_fn = get_skinCluster_fn(self.dst_skinCluster)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.dst_skinCluster}")
            return

        if not is_classic_linear(self.src_skinCluster) or not is_classic_linear(self.dst_skinCluster):
            OpenMaya.MGlobal.displayError("Unsupported skinCluster method.")
            return

        # Check influences
        src_infs_path_array = src_skinCluster_fn.influenceObjects()
        dst_infs_path_array = dst_skinCluster_fn.influenceObjects()
        src_infs = [inf.fullPathName() for inf in src_infs_path_array]
        dst_infs = [inf.fullPathName() for inf in dst_infs_path_array]

        diff_infs = list(set(src_infs) - set(dst_infs))
        if diff_infs:
            OpenMaya.MGlobal.displayError(f"Influences do not match: {diff_infs}")
            return

        if self.only_unlock_infs:
            self.unlocked_infs = []
            for inf in dst_infs_path_array:
                lock_plug = dst_skinCluster_fn.findPlug("lockWeights", True)
                inf_index = dst_skinCluster_fn.indexForInfluenceObject(inf)
                self.unlocked_infs.append(not lock_plug.elementByLogicalIndex(inf_index).asBool())

            if not any(self.unlocked_infs):
                OpenMaya.MGlobal.displayError("onlyUnlockInfluences flag is set but all influences are locked.")
                return

        # Get source geometry
        src_geometry_path = src_skinCluster_fn.getPathAtIndex(0)
        if src_geometry_path.apiType() != OpenMaya.MFn.kMesh:
            OpenMaya.MGlobal.displayError("Source geometry must be mesh.")
            return

        src_comp_obj = get_geometry_components(src_geometry_path)

        # Get destination geometry
        dst_geometry_path = dst_skinCluster_fn.getPathAtIndex(0)

        # Get destination components
        selection = OpenMaya.MGlobal.getActiveSelectionList()
        mit_selection = OpenMaya.MItSelectionList(selection, OpenMaya.MFn.kComponent)
        dst_comp_obj = OpenMaya.MObject.kNullObj
        if not mit_selection.isDone():
            while not mit_selection.isDone():
                dst_comp_path, dst_comp_obj = mit_selection.getComponent()
                if dst_comp_path == dst_geometry_path:
                    break
                mit_selection.next()

        if dst_comp_obj.isNull():
            dst_comp_obj = get_geometry_components(dst_geometry_path)

        # Get weights
        src_weights, _ = src_skinCluster_fn.getWeights(src_geometry_path, src_comp_obj)
        dst_weights, _ = dst_skinCluster_fn.getWeights(dst_geometry_path, dst_comp_obj)

        num_src_infs = len(src_infs)
        num_dst_infs = len(dst_infs)

        if src_infs == dst_infs:
            src_weights_array = [src_weights[i : i + num_src_infs] for i in range(0, len(src_weights), num_src_infs)]

        else:
            src_weights_array = []
            target_weights_array = [src_weights[i : i + num_src_infs] for i in range(0, len(src_weights), num_src_infs)]

            vertex_count = OpenMaya.MFnMesh(src_geometry_path).numVertices
            for i in range(vertex_count):
                src_weight = OpenMaya.MDoubleArray(num_dst_infs, 0.0)
                for j in range(num_dst_infs):
                    if dst_infs[j] in src_infs:
                        src_weight[j] = target_weights_array[i][src_infs.index(dst_infs[j])]
                    else:
                        src_weight[j] = 0.0

                src_weights_array.append(src_weight)

        dst_weights_array = [dst_weights[i : i + num_dst_infs] for i in range(0, len(dst_weights), num_dst_infs)]

        # Copy weights
        src_mesh_intersector = OpenMaya.MMeshIntersector()
        if self.reference_orig:
            src_orig_path = get_original_shape(src_skinCluster_fn)
            src_mesh_intersector.create(src_orig_path.node(), src_orig_path.inclusiveMatrix())
            src_mit_mesh = OpenMaya.MItMeshPolygon(src_orig_path)

            dst_orig_path = get_original_shape(dst_skinCluster_fn)
            dst_positions = OpenMaya.MItGeometry(dst_orig_path).allPositions(OpenMaya.MSpace.kWorld)

        else:
            src_mesh_intersector.create(src_geometry_path.node(), src_geometry_path.inclusiveMatrix())
            src_mit_mesh = OpenMaya.MItMeshPolygon(src_geometry_path)

        dst_mit_geometry = OpenMaya.MItGeometry(dst_geometry_path, dst_comp_obj)

        calc_weights = OpenMaya.MDoubleArray()

        index = 0
        while not dst_mit_geometry.isDone():
            if self.reference_orig:
                position = dst_positions[dst_mit_geometry.index()]
            else:
                position = dst_mit_geometry.position(OpenMaya.MSpace.kWorld)

            src_point_on_mesh = src_mesh_intersector.getClosestPoint(position)

            uw, vw = src_point_on_mesh.barycentricCoords

            src_mit_mesh.setIndex(src_point_on_mesh.face)
            (
                _,
                triangle_vtx_indices,
            ) = src_mit_mesh.getTriangle(src_point_on_mesh.triangle, OpenMaya.MSpace.kWorld)

            calc_weight = OpenMaya.MDoubleArray(num_dst_infs, 0.0)
            for vtx_index, bary_weight in zip(triangle_vtx_indices, [uw, vw, 1 - uw - vw]):
                weights = src_weights_array[vtx_index]
                for i in range(num_dst_infs):
                    calc_weight[i] += weights[i] * bary_weight

            if self.unlocked_infs:
                unlock_new_total = 0
                unlock_old_total = 0
                for i in range(num_dst_infs):
                    if self.unlocked_infs[i]:
                        unlock_new_total += calc_weight[i] * self.blend_weights
                        unlock_old_total += dst_weights_array[index][i]

                if unlock_new_total < 1e-5 or unlock_old_total < 1e-5:
                    calc_weight = dst_weights_array[index]
                else:
                    if unlock_old_total < unlock_new_total:
                        for i in range(num_dst_infs):
                            if self.unlocked_infs[i]:
                                calc_weight[i] = unlock_old_total * calc_weight[i] * self.blend_weights / unlock_new_total
                            else:
                                calc_weight[i] = dst_weights_array[index][i]
                    else:
                        dif_total = unlock_old_total - unlock_new_total
                        for i in range(num_dst_infs):
                            if self.unlocked_infs[i]:
                                calc_weight[i] = dif_total * (dst_weights_array[index][i] / unlock_old_total) + calc_weight[i] * self.blend_weights
                            else:
                                calc_weight[i] = dst_weights_array[index][i]

            else:
                if self.blend_weights != 0.0 and self.blend_weights != 1.0:
                    for i in range(num_dst_infs):
                        calc_weight[i] = dst_weights_array[index][i] * (1 - self.blend_weights) + calc_weight[i] * self.blend_weights

            calc_weights += calc_weight

            index += 1

            dst_mit_geometry.next()

        # Set weights
        influences_index_array = OpenMaya.MIntArray(list(range(num_dst_infs)))
        self.old_weights = dst_skinCluster_fn.setWeights(dst_geometry_path, dst_comp_obj, influences_index_array, calc_weights, True, True)

    def undoIt(self):
        """ """
        try:
            dst_skinCluster_fn = get_skinCluster_fn(self.dst_skinCluster)
        except Exception:
            OpenMaya.MGlobal.displayError(f"Failed to get skinCluster node: {self.dst_skinCluster}")
            return

        dst_geometry_path = dst_skinCluster_fn.getPathAtIndex(0)

        selection = OpenMaya.MGlobal.getActiveSelectionList()
        mit_selection = OpenMaya.MItSelectionList(selection, OpenMaya.MFn.kComponent)
        dst_comp_obj = OpenMaya.MObject.kNullObj
        if not mit_selection.isDone():
            while not mit_selection.isDone():
                dst_comp_path, dst_comp_obj = mit_selection.getComponent()
                if dst_comp_path == dst_geometry_path:
                    break
                mit_selection.next()

        if dst_comp_obj.isNull():
            dst_comp_obj = get_geometry_components(dst_geometry_path)

        influences_index_array = OpenMaya.MIntArray(list(range(len(dst_skinCluster_fn.influenceObjects()))))

        self.old_weights = dst_skinCluster_fn.setWeights(dst_geometry_path, dst_comp_obj, influences_index_array, self.old_weights, True, True)

    def isUndoable(self):
        """Return whether the command is undoable."""
        return True


# Utility functions


def is_classic_linear(skinCluster_name) -> bool:
    """Check if the skinCluster is classic linear skinCluster.

    Args:
        skinCluster_name (str): The skinCluster node name.

    Returns:
        bool: True if classic linear skinCluster, False otherwise.
    """
    try:
        selection = OpenMaya.MSelectionList()
        selection.add(skinCluster_name)
        skinCluster_node = selection.getDependNode(0)

        depend_node_fn = OpenMaya.MFnDependencyNode(skinCluster_node)
        method_plug = depend_node_fn.findPlug("skinningMethod", True)

        return method_plug.asInt() == 0

    except Exception as e:
        OpenMaya.MGlobal.displayError(f"Failed to check skinCluster type: {e}")
        return False


def get_skinCluster_fn(skinCluster_name) -> OpenMayaAnim.MFnSkinCluster:
    """Get skinCluster function set.

    Args:
        skinCluster_name (str): The skinCluster node name.

    Returns:
        MFnSkinCluster: The skinCluster function set.
    """
    selection = OpenMaya.MSelectionList()
    selection.add(skinCluster_name)
    skinCluster_node = selection.getDependNode(0)
    skinCluster_fn = OpenMayaAnim.MFnSkinCluster(skinCluster_node)

    return skinCluster_fn


def get_components_from_name(components) -> tuple[OpenMaya.MDagPath, OpenMaya.MObject] | None:
    """Get components from the component name list.

    Args:
        components (list): The components.

    Returns:
        tuple[MDagPath, MObject]: The component dag path and component object. None if failed.
    """
    selection = OpenMaya.MSelectionList()
    for component in components:
        selection.add(component)

    if selection.length() == 0:
        OpenMaya.MGlobal.displayError("No components found.")
        return

    if selection.length() > 1:
        OpenMaya.MGlobal.displayError("Only one component is allowed.")
        return

    components_path, components_obj = selection.getComponent(0)
    if components_obj.isNull():
        OpenMaya.MGlobal.displayError("Invalid component.")
        return

    return components_path, components_obj


def get_geometry_components(geometry_path):
    """Get the components of the geometry."""
    try:
        # Determine the type of geometry and initialize variables
        if geometry_path.apiType() == OpenMaya.MFn.kMesh:
            component_type = OpenMaya.MFn.kMeshVertComponent
            num_components = OpenMaya.MFnMesh(geometry_path).numVertices

        elif geometry_path.apiType() == OpenMaya.MFn.kNurbsSurface:
            component_type = OpenMaya.MFn.kSurfaceCVComponent
            nurbs_fn = OpenMaya.MFnNurbsSurface(geometry_path)
            num_u = nurbs_fn.numCVsInU
            num_v = nurbs_fn.numCVsInV

        elif geometry_path.apiType() == OpenMaya.MFn.kNurbsCurve:
            component_type = OpenMaya.MFn.kCurveCVComponent
            num_components = OpenMaya.MFnNurbsCurve(geometry_path).numCVs

        elif geometry_path.apiType() == OpenMaya.MFn.kLattice:
            component_type = OpenMaya.MFn.kLatticeComponent
            geometry_name = geometry_path.fullPathName()
            s_div = cmds.getAttr(f"{geometry_name}.sDivisions")
            t_div = cmds.getAttr(f"{geometry_name}.tDivisions")
            u_div = cmds.getAttr(f"{geometry_name}.uDivisions")
        else:
            OpenMaya.MGlobal.displayError(f"Unsupported geometry type: {geometry_path.apiTypeStr()}")
            return OpenMaya.MObject.kNullObj

        # Create and populate the appropriate component object
        if component_type in [OpenMaya.MFn.kMeshVertComponent, OpenMaya.MFn.kCurveCVComponent]:
            single_index_comp = OpenMaya.MFnSingleIndexedComponent()
            components_obj = single_index_comp.create(component_type)
            single_index_comp.setCompleteData(num_components)

        elif component_type == OpenMaya.MFn.kSurfaceCVComponent:
            double_index_comp = OpenMaya.MFnDoubleIndexedComponent()
            components_obj = double_index_comp.create(component_type)
            double_index_comp.setCompleteData(num_u, num_v)

        elif component_type == OpenMaya.MFn.kLatticeComponent:
            triple_index_comp = OpenMaya.MFnTripleIndexedComponent()
            components_obj = triple_index_comp.create(component_type)
            triple_index_comp.setCompleteData(s_div, t_div, u_div)

        else:
            OpenMaya.MGlobal.displayError(f"Unknown component type: {component_type}")
            return OpenMaya.MObject.kNullObj

        return components_obj

    except Exception as e:
        OpenMaya.MGlobal.displayError(f"Failed to get geometry components: {e}")
        return OpenMaya.MObject.kNullObj


def get_original_shape(skinCluster_fn):
    """Get the original shape of the skinCluster.

    Args:
        skinCluster_fn (MFnSkinCluster): The skinCluster function set.

    Returns:
        MDagPath: The original shape dag path.
    """
    try:
        orig_plug = skinCluster_fn.findPlug("originalGeometry", True)
        plug_element = orig_plug.elementByLogicalIndex(0)
        orig_shape_obj = plug_element.source().node()
        orig_shape_fn = OpenMaya.MFnDagNode(orig_shape_obj)
        orig_shape_path = orig_shape_fn.getPath()

        return orig_shape_path
    except Exception as e:
        OpenMaya.MGlobal.displayError(f"Failed to get original shape: {e}")
        return


# Initialize and uninitialize the script plug-in


def initializePlugin(plugin):
    """Initialize the script plug-in."""
    plugin_fn = OpenMaya.MFnPlugin(plugin, "Mitsuaki Watanabe", "1.0", "Any")

    # Register command for skinClusterExport
    try:
        plugin_fn.registerCommand(SkinWeightExport.plugin_cmd_name, SkinWeightExport.cmdCreator, SkinWeightExport.syntaxCreator)
    except Exception as e:
        sys.stderr.write(f"Failed to register command: {SkinWeightExport.plugin_cmd_name}")
        raise e

    # Register command for skinClusterImport
    try:
        plugin_fn.registerCommand(SkinWeightImport.plugin_cmd_name, SkinWeightImport.cmdCreator, SkinWeightImport.syntaxCreator)
    except Exception as e:
        sys.stderr.write(f"Failed to register command: {SkinWeightImport.plugin_cmd_name}")
        raise e

    # Register command for copySkinWeights
    try:
        plugin_fn.registerCommand(CopySkinWeightsCustom.plugin_cmd_name, CopySkinWeightsCustom.cmdCreator, CopySkinWeightsCustom.syntaxCreator)
    except Exception as e:
        sys.stderr.write(f"Failed to register command: {CopySkinWeightsCustom.plugin_cmd_name}")
        raise e


def uninitializePlugin(plugin):
    """Uninitialize the script plug-in."""
    plugin_fn = OpenMaya.MFnPlugin(plugin)

    # Unregister command for skinClusterExport
    try:
        plugin_fn.deregisterCommand(SkinWeightExport.plugin_cmd_name)
    except Exception as e:
        sys.stderr.write(f"Failed to unregister command: {SkinWeightExport.plugin_cmd_name}")
        raise e

    # Unregister command for skinClusterImport
    try:
        plugin_fn.deregisterCommand(SkinWeightImport.plugin_cmd_name)
    except Exception as e:
        sys.stderr.write(f"Failed to unregister command: {SkinWeightImport.plugin_cmd_name}")
        raise e

    # Unregister command for copySkinWeights
    try:
        plugin_fn.deregisterCommand(CopySkinWeightsCustom.plugin_cmd_name)
    except Exception as e:
        sys.stderr.write(f"Failed to unregister command: {CopySkinWeightsCustom.plugin_cmd_name}")
        raise e
