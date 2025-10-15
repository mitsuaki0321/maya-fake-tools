"""SkinCluster weights Import/Export command."""

from dataclasses import dataclass
import json
from logging import getLogger
import os
import pickle
from typing import Optional

import maya.cmds as cmds

from ....lib import lib_skinCluster

logger = getLogger(__name__)


@dataclass
class SkinClusterData:
    """Skin cluster data."""

    influences: list[str]
    geometry_name: str
    geometry_type: str
    num_components: int
    weights: list[list[float]]

    @classmethod
    def from_geometry(cls, geometry_name: str) -> "SkinClusterData":
        """Get the skinCluster data from the geometry.

        Args:
            geometry_name (str): The geometry name.
            influences (list[str]): The influences.

        Returns:
            SkinClusterData: The skinCluster data.
        """
        if not cmds.objExists(geometry_name):
            cmds.error(f"Geometry not found: {geometry_name}")

        geometry_type = cmds.nodeType(geometry_name)
        skinCluster = lib_skinCluster.get_skinCluster(geometry_name)

        logger.debug(f"Found skinCluster: {skinCluster} for geometry: {geometry_name}")

        if not skinCluster:
            cmds.error(f"SkinCluster not found: {geometry_name}")

        influences = cmds.skinCluster(skinCluster, q=True, inf=True)
        num_components = len(cmds.ls(f"{geometry_name}.cp[*]", fl=True))
        weights = lib_skinCluster.get_skin_weights_custom(skinCluster, all_components=True)

        logger.debug(f"Loaded skinCluster data: {geometry_name}")

        return cls(influences=influences, geometry_name=geometry_name, geometry_type=geometry_type, num_components=num_components, weights=weights)

    def apply_weights(self) -> None:
        """Apply the skinCluster weights to the geometry."""
        if not cmds.objExists(self.geometry_name):
            raise ValueError(f"Geometry not found: {self.geometry_name}")

        not_exists_infs = [inf for inf in self.influences if not cmds.objExists(inf)]
        if not_exists_infs:
            raise ValueError(f"Influences not found: {not_exists_infs}")

        if cmds.nodeType(self.geometry_name) != self.geometry_type:
            raise ValueError(f"Geometry type mismatch: {cmds.nodeType(self.geometry_name)} != {self.geometry_type}")

        skinCluster = lib_skinCluster.get_skinCluster(self.geometry_name)
        if not skinCluster:
            skinCluster = cmds.skinCluster(self.influences, self.geometry_name, tsb=True)[0]

            logger.debug(f"Created skinCluster: {skinCluster}")
        else:
            current_influences = cmds.skinCluster(skinCluster, q=True, inf=True)
            if not current_influences == self.influences:
                raise ValueError(f"Influences mismatch: {current_influences} != {self.influences}")

        lib_skinCluster.set_skin_weights_custom(skinCluster, self.weights, components=[f"{self.geometry_name}.cp[*]"])

        logger.debug(f"Applied skinCluster weights: {self.geometry_name}")


class SkinClusterDataIO:
    """SkinCluster data import/export tools."""

    def export_weights(self, skinCluster_data: SkinClusterData, output_dir_path: str, format: str = "json"):
        """Export the skinCluster weights.

        Args:
            skinCluster_data (SkinClusterData): The skinCluster data.
            output_dir_path (str): The output directory path.
            format (str): The format of the file. Default is 'json'.
        """
        if not os.path.exists(output_dir_path):
            raise FileNotFoundError(f"Output directory path not found: {output_dir_path}")

        if format not in ["json", "pickle"]:
            raise ValueError(f"Invalid format: {format}")

        output_data = {
            "influences": skinCluster_data.influences,
            "geometry_name": skinCluster_data.geometry_name,
            "geometry_type": skinCluster_data.geometry_type,
            "num_components": skinCluster_data.num_components,
            "weights": skinCluster_data.weights,
        }

        output_file_path = os.path.join(output_dir_path, f"{skinCluster_data.geometry_name}.{format}")
        if format == "json":
            with open(output_file_path, "w") as f:
                json.dump(output_data, f, indent=4)
        elif format == "pickle":
            with open(output_file_path, "wb") as f:
                pickle.dump(output_data, f)
        else:
            raise ValueError(f"Invalid format: {format}")

        logger.debug(f"Exported skinCluster data: {output_file_path}")

    def import_weights(self, skinCluster_data: SkinClusterData, target_geometry: Optional[str] = None) -> None:
        """Import the skinCluster weights.

        Args:
            skinCluster_data (SkinClusterData): The skinCluster data.
            target_geometry (str): The target geometry name. Default is None.

        Notes:
            - If the target geometry is None, the geometry name will be used.
            - If the target geometry is found, apply the weights to the geometry.

        """
        if target_geometry:
            skinCluster_data.geometry_name = target_geometry

        skinCluster_data.apply_weights()

    def load_data(self, file_path: str) -> SkinClusterData:
        """Load the skinCluster data.

        Args:
            file_path (str): The file path.

        Returns:
            SkinClusterData: The skinCluster data.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File path not found: {file_path}")

        if file_path.endswith(".json"):
            with open(file_path) as f:
                input_data = json.load(f)
        elif file_path.endswith(".pickle"):
            with open(file_path, "rb") as f:
                input_data = pickle.load(f)
        else:
            raise ValueError(f"Invalid file format: {file_path}")

        if not all(k in input_data for k in ["influences", "geometry_name", "geometry_type", "num_components", "weights"]):
            raise ValueError(f"Invalid input data: {file_path}")

        logger.debug(f"Loaded skinCluster data: {file_path}")

        return SkinClusterData(
            influences=input_data["influences"],
            geometry_name=input_data["geometry_name"],
            geometry_type=input_data["geometry_type"],
            num_components=input_data["num_components"],
            weights=input_data["weights"],
        )


def validate_export_weights(shapes: list[str]) -> None:
    """Validate the export weights command.

    Args:
        shapes (list[str]): The shapes.

    Raises:
        ValueError: If the shapes are invalid.
    """
    export_ok = True
    for shape in shapes:
        if not cmds.objExists(shape):
            cmds.warning(f"Shape not found: {shape}")
            export_ok = False
            continue

        if "deformableShape" not in cmds.nodeType(shape, inherited=True):
            cmds.warning(f"Shape is not deformableShape: {shape}")
            export_ok = False
            continue

        skinCluster = lib_skinCluster.get_skinCluster(shape)
        if not skinCluster:
            cmds.warning(f"SkinCluster not found: {shape}")
            export_ok = False
            continue

    if not export_ok:
        raise ValueError("Invalid shapes for export weights.Check details in the script editor.")
