"""Box object module."""

from abc import ABC, abstractmethod
from logging import getLogger

import maya.cmds as cmds

logger = getLogger(__name__)


class BoxObject(ABC):
    """Box object class.

    Abstract class for generating Box type objects. Implement the box_object method to generate Box type objects.
    The radius of the Box type object is 0.5.
    """

    @abstractmethod
    def create(self):
        """Create a bounding box object.

        Returns:
            str: The name of the created bounding box object.
        """
        pass


class MeshBox(BoxObject):
    def create(self):
        """Create a bounding box object."""
        return cmds.polyCube(w=1, h=1, d=1, sx=1, sy=1, sz=1, ax=[0, 1, 0], cuv=4, ch=False)[0]


class CurveBox(BoxObject):
    def create(self):
        """Create a bounding box object."""
        points = [
            (-0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5),
            (0.5, 0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (-0.5, 0.5, 0.5),
            (-0.5, -0.5, 0.5),
            (-0.5, -0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (-0.5, -0.5, -0.5),
            (0.5, -0.5, -0.5),
            (0.5, 0.5, -0.5),
            (0.5, -0.5, -0.5),
            (0.5, -0.5, 0.5),
            (0.5, 0.5, 0.5),
            (0.5, -0.5, 0.5),
            (-0.5, -0.5, 0.5),
        ]

        return cmds.curve(d=1, p=points, k=[i for i in range(len(points))])


class LocatorBox(BoxObject):
    def create(self):
        """Create a bounding box object."""
        return cmds.spaceLocator()[0]
