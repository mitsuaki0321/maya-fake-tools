"""Optimize the scene."""

from abc import ABC, abstractmethod

import maya.cmds as cmds
import maya.mel as mel


class OptimizeBase(ABC):
    """Base class for optimize commands."""

    _name = "Optimize"
    _description = "Optimize the scene"

    def __init__(self, echo: bool = False):
        """Initialize the command.

        Args:
            echo (bool, optional): Whether to print the results. Defaults to False.
        """
        self.echo = echo
        self.execute()

    @abstractmethod
    def execute(self):
        """Execute the command."""
        pass


class RemoveDataStructures(OptimizeBase):
    """Remove data structures from the scene."""

    _name = "Data Structures"
    _description = "Remove dataStructures from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing data structures...")
            print("#" * 20)

        data_structures = cmds.dataStructure(removeAll=True)
        if self.echo:
            if not data_structures:
                print("No data structures found.")
            else:
                for ds in data_structures:
                    print(ds)


class RemoveUnknownNodes(OptimizeBase):
    """Remove unknown nodes from the scene."""

    _name = "Unknown Nodes"
    _description = "Remove unknown nodes from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing unknown nodes...")
            print("#" * 20)

        unknown_nodes = cmds.ls(type="unknown")
        if not unknown_nodes:
            if self.echo:
                print("No unknown nodes found.")
            return

        for node in unknown_nodes:
            try:
                cmds.delete(node)
                if self.echo:
                    print(node)
            except Exception as e:
                cmds.warning(f"Could not delete node {node}: {e}")


class RemoveUnusedNodes(OptimizeBase):
    """Remove unused nodes from the scene."""

    _name = "Unused Nodes"
    _description = "Remove unused nodes from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing unused nodes...")
            print("#" * 20)

        mel.eval("MLdeleteUnused;")


class RemoveUnknownPlugins(OptimizeBase):
    """Remove unknown plugins from the scene."""

    _name = "Unknown Plugins"
    _description = "Remove unknown plugins from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing unknown plugins...")
            print("#" * 20)

        unknown_plugins = cmds.unknownPlugin(query=True, list=True) or []
        if not unknown_plugins:
            if self.echo:
                print("No unknown plugins found.")
            return

        for plugin in unknown_plugins:
            try:
                cmds.unknownPlugin(plugin, remove=True)
                if self.echo:
                    print(plugin)
            except Exception as e:
                cmds.warning(f"Could not remove plugin {plugin}: {e}")


class RemoveScriptNodes(OptimizeBase):
    """Remove script nodes from the scene."""

    _name = "Script Nodes"
    _description = "Remove scriptNodes from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing script nodes...")
            print("#" * 20)

        script_nodes = cmds.ls(type="script")
        if not script_nodes:
            if self.echo:
                print("No script nodes found.")
            return

        for node in script_nodes:
            if node in ["sceneConfigurationScriptNode", "uiConfigurationScriptNode"]:
                continue

            try:
                cmds.delete(node)
                if self.echo:
                    print(node)
            except Exception as e:
                cmds.warning(f"Could not delete script node {node}: {e}")


class RemoveColorSets(OptimizeBase):
    """Remove color sets from the scene."""

    _name = "Color Sets"
    _description = "Remove colorSets from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing color sets...")
            print("#" * 20)

        meshes = cmds.ls(type="mesh")
        if not meshes:
            if self.echo:
                print("No meshes found.")
            return

        exist_color_sets = False
        for mesh in meshes:
            color_sets = cmds.polyColorSet(mesh, q=True, acs=True)
            if not color_sets:
                continue

            for color_set in color_sets:
                cmds.polyColorSet(mesh, delete=True, colorSet=color_set)
                exist_color_sets = True

                if self.echo:
                    print(f"{color_set} from {mesh}")

        if not exist_color_sets and self.echo:
            print("No color sets found.")


class RemoveNameSpaces(OptimizeBase):
    """Remove name spaces from the scene."""

    _name = "Name Spaces"
    _description = "Remove namespaces from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing name spaces...")
            print("#" * 20)

        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        if not namespaces:
            if self.echo:
                print("No name spaces found.")
            return

        for ns in namespaces:
            if ns in ["UI", "shared"]:
                continue

            cmds.namespace(mv=(ns, ":"), f=True)
            cmds.namespace(rm=ns)

            if self.echo:
                print(ns)


class RemoveDisplayLayers(OptimizeBase):
    """Remove display layers from the scene."""

    _name = "Display Layers"
    _description = "Remove displayLayers from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing display layers...")
            print("#" * 20)

        layers = cmds.ls(type="displayLayer")
        if not layers or layers == ["defaultLayer"]:
            if self.echo:
                print("No display layers found.")
            return

        for layer in layers:
            if layer in ["defaultLayer"]:
                continue

            cmds.delete(layer)

            if self.echo:
                print(layer)


class RemoveAnimCurves(OptimizeBase):
    """Remove animation curves from the scene."""

    _name = "Animation Curves"
    _description = "Remove animation curves from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing animation curves...")
            print("#" * 20)

        anim_curves = cmds.ls(type="animCurve")
        if not anim_curves:
            if self.echo:
                print("No animation curves found.")
            return

        cmds.delete(anim_curves)
        if self.echo:
            for anim_curve in anim_curves:
                print(anim_curve)


class RemoveDagPose(OptimizeBase):
    """Remove dagPose nodes from the scene."""

    _name = "DagPose"
    _description = "Remove dagPose nodes from the scene"

    def execute(self):
        """Execute the command."""
        if self.echo:
            print("#" * 20)
            print("Removing dagPose nodes...")
            print("#" * 20)

        dag_poses = cmds.ls(type="dagPose")
        if not dag_poses:
            if self.echo:
                print("No dagPose nodes found.")
            return

        cmds.delete(dag_poses)
        if self.echo:
            for dag_pose in dag_poses:
                print(dag_pose)


__all__ = [
    "RemoveDataStructures",
    "RemoveUnknownNodes",
    "RemoveUnusedNodes",
    "RemoveUnknownPlugins",
    "RemoveScriptNodes",
    "RemoveColorSets",
    "RemoveNameSpaces",
    "RemoveDisplayLayers",
    "RemoveAnimCurves",
    "RemoveDagPose",
]
