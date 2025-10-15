"""Skin weights copy and paste command."""

from logging import getLogger

import maya.cmds as cmds

from ....lib import lib_skinCluster

logger = getLogger(__name__)


class SkinWeightsCopyPaste:
    """SkinCluster weights copy and paste class."""

    def __init__(
        self,
        *,
        method: str = "oneToAll",
        blend_weights: float = 1.0,
        only_unlock_influences: bool = False,
    ):
        """Initialize the skin weights copy and paste.

        Args:
            method (str, optional): The method. Defaults to 'oneToAll'. 'oneToAll' or 'oneToOne'.
            blend_weights (float, optional): The blend weights. Defaults to 1.0.
            only_unlock_influences (bool, optional): Only apply weights to unlocked influences. Defaults to False.
        """
        if method not in ["oneToAll", "oneToOne"]:
            raise ValueError(f"Invalid method: {method}")

        self._method = method

        if not 0.0 <= blend_weights <= 1.0:
            raise ValueError(f"Invalid blend weights: {blend_weights}")

        self._blend_weights = blend_weights
        self._only_unlock_influences = only_unlock_influences

        self._src_components = []
        self._src_weights = []
        self._src_skinCluster = None

        self._dst_components = []
        self._dst_weights = []
        self._dst_skinCluster = None

    @property
    def method(self) -> str:
        """Get the method.

        Returns:
            str: The method.
        """
        return self._method

    def set_method(self, method: str) -> None:
        """Set the method.

        Args:
            method (str): The method.
        """
        if self.get_num_dst_components() != 0:
            raise ValueError("Cannot change the method after setting the destination components.")

        if not isinstance(method, str):
            raise ValueError(f"Invalid method: {method}")

        if method not in ["oneToAll", "oneToOne"]:
            raise ValueError(f"Invalid method: {method}")

        self._method = method

        logger.debug(f"Set method: {method}")

    @property
    def blend_weights(self) -> float:
        """Get the blend weights.

        Returns:
            float: The blend weights.
        """
        return self._blend_weights

    def set_blend_weights(self, blend_weights: float) -> None:
        """Set the blend weights.

        Args:
            blend_weights (float): The blend weights.
        """
        if not isinstance(blend_weights, float):
            raise ValueError(f"Invalid blend weights: {blend_weights}")

        if not 0.0 <= blend_weights <= 1.0:
            raise ValueError(f"Invalid blend weights: {blend_weights}")

        self._blend_weights = blend_weights

        logger.debug(f"Set blend weights: {blend_weights}")

    @property
    def only_unlock_influences(self) -> bool:
        """Get the only unlock influences flag.

        Returns:
            bool: The only unlock influences flag.
        """
        return self._only_unlock_influences

    def set_only_unlock_influences(self, only_unlock_influences: bool) -> None:
        """Set the only unlock influences flag.

        Args:
            only_unlock_influences (bool): The only unlock influences flag.
        """
        if not isinstance(only_unlock_influences, bool):
            raise ValueError(f"Invalid only_unlock_influences: {only_unlock_influences}")

        self._only_unlock_influences = only_unlock_influences

        logger.debug(f"Set only_unlock_influences: {only_unlock_influences}")

    def set_src_components(self, components: list[str]) -> None:
        """Set the source components.

        Args:
            components (list[str]): The source components.
        """
        if not components:
            raise ValueError("No components specified.")

        components = cmds.ls(components, flatten=True)
        filter_components = cmds.filterExpand(components, sm=[28, 31, 46], ex=True)
        if len(filter_components) != len(components):
            cmds.error("Invalid components or objects selected.")

        shapes = list(set(cmds.ls(components, objectsOnly=True)))
        if len(shapes) > 1:
            cmds.error("Multiple shapes selected.")

        skinCluster = lib_skinCluster.get_skinCluster(shapes[0])
        if not skinCluster:
            cmds.error("No skinCluster found.")

        self._src_components = components
        self._src_skinCluster = skinCluster

        # Reset destination components
        self._dst_components = []
        self._dst_weights = []
        self._dst_skinCluster = None

        logger.debug(f"Set source components: {self._src_components}")

    def get_src_components(self) -> list[str]:
        """Get the source components.

        Returns:
            list[str]: The source components.
        """
        return self._src_components

    def clear_src_components(self) -> None:
        """Clear the source components."""
        self._src_components = []
        self._src_skinCluster = None

        self.clear_dst_components()

        logger.debug("Clear source components")

    def get_num_src_components(self) -> int:
        """Get the number of source components.

        Returns:
            int: The number of source components.
        """
        return len(self._src_components)

    def set_dst_components(self, components: list[str]) -> None:
        """Set the destination components.

        Args:
            components (list[str]): The destination components.
        """
        if not components:
            raise ValueError("No components specified.")

        if not self._src_components:
            cmds.error("No source components")

        components = cmds.ls(components, flatten=True)
        filter_components = cmds.filterExpand(components, sm=[28, 31, 46])
        if len(filter_components) != len(components):
            cmds.error("Invalid components or objects selected.")

        shapes = list(set(cmds.ls(components, objectsOnly=True)))
        if len(shapes) > 1:
            cmds.error("Multiple shapes selected.")

        if self._method == "oneToOne" and len(self._src_components) != len(components):
            cmds.error(f"The source and destination components do not match: {self._src_components} != {components}")

        skinCluster = lib_skinCluster.get_skinCluster(shapes[0])
        if not skinCluster:
            cmds.error("No skinCluster found.")

        self._dst_skinCluster = skinCluster
        self._dst_components = components
        self._dst_weights = lib_skinCluster.get_skin_weights(skinCluster, components)

        src_weights = lib_skinCluster.get_skin_weights(self._src_skinCluster, self._src_components)
        src_infs = cmds.skinCluster(self._src_skinCluster, q=True, inf=True)
        dst_infs = cmds.skinCluster(self._dst_skinCluster, q=True, inf=True)

        self._src_weights = []
        for src_weight in src_weights:
            order_weight = []
            for dst_inf in dst_infs:
                if dst_inf in src_infs:
                    order_weight.append(src_weight[src_infs.index(dst_inf)])
                else:
                    order_weight.append(0.0)

            self._src_weights.append(order_weight)

        if self._method == "oneToAll":
            self._src_weights = [self._src_weights[0]] * len(self._dst_components)

        logger.debug(f"Set destination components: {self._dst_components}")

    def get_dst_components(self) -> list[str]:
        """Get the destination components.

        Returns:
            list[str]: The destination components.
        """
        return self._dst_components

    def clear_dst_components(self) -> None:
        """Clear the destination components."""
        self._src_weights = []

        self._dst_components = []
        self._dst_weights = []
        self._dst_skinCluster = None

        logger.debug("Clear destination components")

    def get_num_dst_components(self) -> int:
        """Get the number of destination components.

        Returns:
            int: The number of destination components.
        """
        return len(self._dst_components)

    def is_pastable(self) -> bool:
        """Return True if the paste is ready.

        Returns:
            bool: True if the paste is ready.
        """
        if not self._src_components:
            logger.debug("No source components")
            return False

        if not self._dst_components:
            logger.debug("No destination components")
            return False

        if not self._src_weights:
            logger.debug("No source weights")
            return False

        if not self._dst_weights:
            logger.debug("No destination weights")
            return False

        if not self._src_skinCluster:
            logger.debug("No source skinCluster")
            return False

        if not self._dst_skinCluster:
            logger.debug("No destination skinCluster")
            return False

        return True

    def _adjust_unlock_weights(self, new_weight: list[float], original_weight: list[float], unlocked_status: list[bool]) -> list[float]:
        """Adjust weights to only modify unlocked influences.

        This method ensures that locked influences remain unchanged while
        unlocked influences are adjusted to maintain proper weight normalization.

        Args:
            new_weight (list[float]): The new weights after blending.
            original_weight (list[float]): The original weights before blending.
            unlocked_status (list[bool]): Boolean list indicating which influences are unlocked.

        Returns:
            list[float]: The adjusted weights with locked influences preserved.
        """
        num_infs = len(new_weight)
        adjusted_weight = list(original_weight)  # Start with original weights

        # Extract unlocked weights
        unlock_before_weights = []
        unlock_new_weights = []
        for j in range(num_infs):
            if unlocked_status[j]:
                unlock_before_weights.append(original_weight[j])
                unlock_new_weights.append(new_weight[j])

        unlock_before_total = sum(unlock_before_weights)
        unlock_new_total = sum(unlock_new_weights)

        # If either total is very small, keep original weights
        if unlock_before_total < 1e-5 or unlock_new_total < 1e-5:
            return adjusted_weight

        # Adjust weights based on totals
        if unlock_before_total < unlock_new_total:
            # Scale down new weights to fit within available space
            for j in range(num_infs):
                if unlocked_status[j]:
                    adjusted_weight[j] = unlock_before_total * new_weight[j] / unlock_new_total
                else:
                    adjusted_weight[j] = original_weight[j]
        else:
            # Distribute difference proportionally
            unlock_dif_total = unlock_before_total - unlock_new_total

            for j in range(num_infs):
                if unlocked_status[j]:
                    adjusted_weight[j] = unlock_dif_total * (original_weight[j] / unlock_before_total) + new_weight[j]
                else:
                    adjusted_weight[j] = original_weight[j]

        return adjusted_weight

    def paste_skinWeights(self) -> None:
        """Paste the skin weights."""
        if not self.is_pastable():
            cmds.error("Copy and paste is not ready.")

        # Calculate blended weights
        blended_weights = []
        for src_weight, dst_weight in zip(self._src_weights, self._dst_weights, strict=False):
            new_weight = []
            for src_w, dst_w in zip(src_weight, dst_weight, strict=False):
                new_weight.append(src_w * self._blend_weights + dst_w * (1.0 - self._blend_weights))

            blended_weights.append(new_weight)

        # Apply only_unlock_influences constraint if enabled
        if self._only_unlock_influences:
            dst_infs = cmds.skinCluster(self._dst_skinCluster, q=True, inf=True)
            unlocked_infs = lib_skinCluster.get_lock_influences(self._dst_skinCluster, lock=False)

            if not unlocked_infs:
                cmds.error("No unlocked influences found in destination skinCluster.")

            unlocked_status = [inf in unlocked_infs for inf in dst_infs]

            # Adjust weights for each component
            final_weights = []
            for new_weight, original_weight in zip(blended_weights, self._dst_weights, strict=False):
                adjusted_weight = self._adjust_unlock_weights(new_weight, original_weight, unlocked_status)
                final_weights.append(adjusted_weight)
        else:
            final_weights = blended_weights

        lib_skinCluster.set_skin_weights(self._dst_skinCluster, final_weights, self._dst_components)

        logger.debug(f"Copy and paste skin weights: {self._src_skinCluster} -> {self._dst_skinCluster}")
