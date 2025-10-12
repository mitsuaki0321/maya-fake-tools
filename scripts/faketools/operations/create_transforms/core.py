"""Core class for creating transform nodes."""

from logging import getLogger

import maya.cmds as cmds

from ...lib import lib_math

logger = getLogger(__name__)


class CreateTransforms:
    """Create transform nodes at positions."""

    _shape_types = ["locator", "joint"]

    def __init__(
        self,
        func: callable,
        size: float = 1.0,
        shape_type: str = "locator",
        chain: bool = False,
        reverse: bool = False,
        rotation_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        """Constructor.

        Args:
            func (callable): The function to get the position and rotation.
            size (float): The size of the transform node. Default is 1.0.
            shape_type (str): The shape type of the transform node. Default is 'locator'.
            chain (bool): Whether to chain the transform node. Default is False.
            reverse (bool): Whether to reverse the transform node. Default is False.
            rotation_offset (tuple[float] | None): The rotation to add to the current rotation. Default is None.
        """
        if shape_type not in self._shape_types:
            raise ValueError("Invalid shape type.")

        self.func = func

        self.size = size
        self.shape_type = shape_type
        self.chain = chain
        self.reverse = reverse
        self.rotation_offset = rotation_offset

    def create(self, *args, **kwargs) -> list[str]:
        """Create the transform nodes.

        Returns:
            list[str]: Created transform node names.
        """
        position_rotations = self.func(*args, **kwargs)  # [{'position': [], 'rotation': []}, ...]
        if not position_rotations:
            cmds.error("No valid object selected ( component or transform ).")
            return

        result_nodes = []
        for data in position_rotations:
            positions = data["position"]
            rotations = data["rotation"]

            if self.reverse:
                positions.reverse()

                if rotations:
                    rotations.reverse()

            if rotations and self.rotation_offset != (0.0, 0.0, 0.0):
                rotations = [lib_math.multiply_rotation([self.rotation_offset, rotation]) for rotation in rotations]

            make_nodes = []
            for i in range(len(positions)):
                # Create a transform node and set the size
                if self.shape_type == "locator":
                    shp = cmds.createNode(self.shape_type, ss=True)
                    node = cmds.listRelatives(shp, p=True)[0]

                    cmds.setAttr(f"{shp}.localScale", self.size, self.size, self.size)

                elif self.shape_type == "joint":
                    node = cmds.createNode(self.shape_type, ss=True)
                    cmds.setAttr(f"{node}.radius", self.size)

                # Set position and rotation
                cmds.xform(node, ws=True, t=positions[i])

                if rotations:
                    cmds.xform(node, ws=True, ro=rotations[i])

                make_nodes.append(node)

            if self.chain:
                for i in range(len(make_nodes) - 1):
                    cmds.parent(make_nodes[i + 1], make_nodes[i])

            result_nodes.extend(make_nodes)

        logger.debug(f"Transform nodes created: {result_nodes}")

        return result_nodes
