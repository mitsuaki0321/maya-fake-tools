"""
This module contains the scene optimization commands.

Optimizations:
    - DataStructure: Delete all dataStructure.
    - UnknownNodes: Delete unknown nodes.
    - UnusedNodes: Delete unused nodes.
    - UnknownPlugins: Remove unknown plugins.
    - ScriptNodes: Delete unused scriptNodes.
    - ColorSets: Delete color sets.
    - NameSpaces: Delete unused namespaces.
    - DisplayLayers: Delete display layers.
    - AnimCurves: Delete animCurves from time.
    - UnusedInfluences: Optimize unused influences from skinCluster.
    - DeleteDagPose: Delete dagPose nodes.
"""

import maya.cmds as cmds
import maya.mel as mel


class OptimizeBase:
    _category = "base"
    _label = "Base"
    _description = "Base optimization."

    @property
    def category(self) -> str:
        """str: The optimization category."""
        return self._category

    @property
    def label(self) -> str:
        """str: The optimization label."""
        return self._label

    @property
    def description(self) -> str:
        """str: The optimization description."""
        return self._description

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        raise NotImplementedError

    def execute(self, echo: bool = False) -> None:
        """Executes the optimization.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        if echo:
            print("#" * len(self.description))
            print(self.description)
            print("#" * len(self.description))
            print("")

        self.optimize(echo=echo)

        if echo:
            print("")


# Base Optimizers


class OptimizeDataStructure(OptimizeBase):
    _category = "base"
    _label = "DataStructure"
    _description = "Delete all dataStructure."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene dataStructure.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.dataStructure(removeAll=True)
        if echo:
            if not nodes:
                print("No dataStructure found.")
            else:
                for node in nodes:
                    print(node)


class OptimizeUnknownNodes(OptimizeBase):
    _category = "base"
    _label = "UnknownNodes"
    _description = "Delete unknown nodes."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unknown nodes.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type="unknown")
        if nodes:
            cmds.delete(nodes)

        if echo:
            if not nodes:
                print("No unknown nodes found.")
            else:
                for node in nodes:
                    print(node)


class OptimizeUnusedNodes(OptimizeBase):
    _category = "base"
    _label = "UnusedNodes"
    _description = "Delete unused nodes.Called by maya MLdeleteUnused"

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused nodes.

        Notes:
            - This function is force echo because it is called by maya MLdeleteUnused.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        node_count = mel.eval("MLdeleteUnused")
        if not node_count:
            print("No unused nodes found.")


class OptimizeUnknownPlugins(OptimizeBase):
    _category = "base"
    _label = "UnknownPlugins"
    _description = "Remove unknown plugins."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unknown plugins.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        plugins = cmds.unknownPlugin(query=True, list=True)

        if not plugins and echo:
            print("No unknown plugins found.")
            return

        if not plugins:
            return

        for plugin in plugins:
            try:
                cmds.unknownPlugin(plugin, remove=True)
            except RuntimeError:
                if echo:
                    print(f"Failed to remove unknown plugin: {plugin}")
                continue

            if echo:
                print(plugin)


# Modeling Optimizers


class OptimizeScriptNodes(OptimizeBase):
    _category = "modeling"
    _label = "ScriptNodes"
    _description = "Delete unused scriptNodes."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused script nodes.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type="script")
        if not nodes:
            if echo:
                print("No scriptNodes found.")
            return

        status = False
        for node in nodes:
            if node in ["sceneConfigurationScriptNode", "uiConfigurationScriptNode"]:
                continue

            cmds.delete(node)
            status = True

            if echo:
                print(node)

        if not status and echo:
            print("No unused scriptNodes found.")


class OptimizeColorSets(OptimizeBase):
    _category = "modeling"
    _label = "ColorSets"
    _description = "Delete color sets."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused color sets.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type="mesh")
        if not nodes:
            if echo:
                print("No mesh color sets found.")
            return

        status = False
        for node in nodes:
            color_sets = cmds.polyColorSet(node, q=True, acs=True)
            if not color_sets:
                continue

            for color_set in color_sets:
                cmds.polyColorSet(node, delete=True, colorSet=color_set)
                status = True

                if echo:
                    print(f"{color_set} from {node}")

        if not status and echo:
            print("No unused color sets found.")


class OptimizeNameSpaces(OptimizeBase):
    _category = "modeling"
    _label = "Namespace"
    _description = "Delete unused namespaces."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused namespaces.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True)
        if not namespaces:
            if echo:
                print("No namespaces found.")
            return

        status = False
        for namespace in namespaces:
            if namespace in ["UI", "shared"]:
                continue

            cmds.namespace(mv=(namespace, ":"), f=True)
            cmds.namespace(rm=namespace)

            if echo:
                print(namespace)

        if not status and echo:
            print("No unused namespaces found.")


class OptimizeDisplayLayers(OptimizeBase):
    _category = "modeling"
    _label = "DisplayLayers"
    _description = "Delete display layers."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused display layers.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        layers = cmds.ls(type="displayLayer")
        if not layers:
            if echo:
                print("No display layers found.")
            return

        status = False
        for layer in layers:
            if layer in ["defaultLayer"]:
                continue

            cmds.delete(layer)
            status = True

            if echo:
                print(layer)

        if not status and echo:
            print("No unused display layers found.")


class OptimizeAnimCurves(OptimizeBase):
    _category = "modeling"
    _label = "TimeAnimCurves"
    _description = "Delete animCurves from time."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene anim curves.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type=["animCurveTA", "animCurveTL", "animCurveTT", "animCurveTU"])
        if nodes:
            cmds.delete(nodes)

        if echo:
            if not nodes:
                print("No anim curves found.")
            else:
                for node in nodes:
                    print(node)


# Rigging Optimizers


class OptimizeUnusedInfluences(OptimizeBase):
    _category = "rigging"
    _label = "UnusedInfluences"
    _description = "Optimize unused influences from skinCluster."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene unused influences from skinCluster.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type="skinCluster")
        if not nodes:
            if echo:
                print("No skinCluster nodes found.")
            return

        status = False
        for node in nodes:
            infs = cmds.skinCluster(node, q=True, inf=True)
            weight_infs = cmds.skinCluster(node, q=True, wi=True)
            if infs == weight_infs:
                continue

            unused_infs = list(set(infs) - set(weight_infs))
            for inf in unused_infs:
                cmds.skinCluster(node, e=True, ri=inf)
                status = True

                if echo:
                    print(f"{inf} from {node}")

        if not status and echo:
            print("No unused influences found.")


class OptimizeDeleteDagPose(OptimizeBase):
    _category = "rigging"
    _label = "DeleteDagPose"
    _description = "Delete dagPose nodes."

    def optimize(self, echo: bool = False) -> None:
        """Optimizes the scene dagPose nodes.

        Args:
            echo (bool): Whether to echo the optimization. Default is False.
        """
        nodes = cmds.ls(type="dagPose")
        if not nodes:
            if echo:
                print("No dagPose nodes found.")
            return

        for node in nodes:
            cmds.delete(node)
            if echo:
                print(node)


def list_optimizers(category: str = None) -> list:
    """List all optimizers.

    Args:
        category (str): The category of the optimizers. Default is None.

    Returns:
        list: The list of optimizers.
    """
    optimizers = [
        OptimizeDataStructure(),
        OptimizeUnknownNodes(),
        OptimizeUnusedNodes(),
        OptimizeUnknownPlugins(),
        OptimizeScriptNodes(),
        OptimizeColorSets(),
        OptimizeNameSpaces(),
        OptimizeDisplayLayers(),
        OptimizeAnimCurves(),
        OptimizeUnusedInfluences(),
        OptimizeDeleteDagPose(),
    ]

    if category:
        return [optimizer for optimizer in optimizers if optimizer.category == category]

    return optimizers
