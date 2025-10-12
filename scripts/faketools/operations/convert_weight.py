"""Convert skinCluster to mesh."""

import itertools
from logging import getLogger

import maya.cmds as cmds

from ..lib import lib_skinCluster

logger = getLogger(__name__)


class SkinClusterToMesh:
    """Convert skinCluster to mesh.

    Notes:
        - Converts the bound mesh or nurbsSurface with specified divisions.
    """

    def __init__(self, skinCluster: str, divisions: int = 2, u_divisions: int = 2, v_divisions: int = 2):
        """Initialize the class.

        Args:
            skinCluster (str): The skinCluster node.
            divisions (int): Number of divisions (default: 2)
            u_divisions (int): Number of divisions in U direction (default: 2)
            v_divisions (int): Number of divisions in V direction (default: 2)
        """
        if not skinCluster:
            raise ValueError("No skinCluster node specified")

        if not cmds.objExists(skinCluster):
            cmds.error(f"Node does not exist: {skinCluster}")

        if cmds.nodeType(skinCluster) != "skinCluster":
            cmds.error(f"Node is not a skinCluster: {skinCluster}")

        self.skinCluster = skinCluster

        self.geometry = cmds.skinCluster(skinCluster, q=True, geometry=True)[0]
        self.geometry_type = cmds.nodeType(self.geometry)
        if self.geometry_type not in ["mesh", "nurbsSurface"]:
            cmds.error(f"Unsupported geometry type: {self.geometry_type}")

        self.divisions = divisions
        self.u_divisions = u_divisions
        self.v_divisions = v_divisions

    def preview(self) -> tuple[str, str]:
        """Preview the converted mesh.

        Returns:
            tuple[str, str]: The preview mesh and the preview node.
        """
        if self.geometry_type == "mesh":
            preview_geometry = cmds.duplicate(self.geometry)[0]
            geometry_shp = cmds.listRelatives(preview_geometry, shapes=True)[0]

            cmds.connectAttr(f"{self.geometry}.outMesh", f"{geometry_shp}.inMesh", f=True)
            preview_node = cmds.polySmooth(
                preview_geometry, method=0, bnr=1, dv=self.divisions, c=1.0, kb=False, khe=False, kmb=1, suv=False, ch=True
            )[0]
        else:
            preview_geometry, preview_node = cmds.nurbsToPoly(
                self.geometry, ch=True, f=2, pt=1, chr=0.9, uType=3, un=self.u_divisions, vType=3, vn=self.v_divisions
            )

        return preview_geometry, preview_node

    def convert(self) -> str:
        """Convert the skinCluster to mesh.

        Returns:
            str: The converted mesh.
        """
        # Create reference mesh
        preview_geometry, _ = self.preview()

        # Create temporary influences
        infs = cmds.skinCluster(self.skinCluster, q=True, inf=True)

        tmp_infs = []
        for inf in infs:
            tmp_inf = cmds.createNode("joint", ss=True)
            cmds.xform(tmp_inf, ws=True, t=cmds.xform(inf, q=True, ws=True, t=True))

            tmp_infs.append(tmp_inf)

        lib_skinCluster.exchange_influences(self.skinCluster, infs, tmp_infs)

        # Get the skinCluster weights
        default_positions = cmds.xform(f"{preview_geometry}.vtx[*]", q=True, ws=True, t=True)[1::3]
        vtx_num = len(default_positions)

        weights = []
        for inf in tmp_infs:
            cmds.move(1.0, inf, r=True, y=True)
            moved_positions = cmds.xform(f"{preview_geometry}.vtx[*]", q=True, ws=True, t=True)[1::3]
            weights.append([moved_positions[i] - default_positions[i] for i in range(vtx_num)])
            cmds.move(-1.0, inf, r=True, y=True)

        weights = list(itertools.chain(*zip(*weights, strict=False)))

        # Create the mesh
        convert_mesh = cmds.duplicate(preview_geometry, n=f"{self.geometry}_converted")[0]
        convert_skinCluster = cmds.skinCluster(infs, convert_mesh, tsb=True)[0]

        # Set the skinCluster weights
        cmds.setAttr(f"{convert_skinCluster}.nw", False)
        lib_skinCluster.set_skin_weights_custom(convert_skinCluster, weights, [f"{convert_mesh}.vtx[*]"])
        cmds.setAttr(f"{convert_skinCluster}.nw", True)

        # Clean up
        lib_skinCluster.exchange_influences(self.skinCluster, tmp_infs, infs)
        cmds.delete(tmp_infs, preview_geometry)

        # Normalize the weights
        cmds.skinPercent(convert_skinCluster, f"{convert_mesh}.vtx[*]", nrm=True)

        logger.debug(f"Converted skinCluster to mesh: {convert_mesh}")

        return convert_mesh
