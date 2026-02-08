"""Skin Weights Transfer command layer.

Pure Maya operations for transferring skin weights between influences.
"""

from __future__ import annotations

from collections.abc import Sequence
from logging import getLogger

import maya.cmds as cmds

from ....lib.lib_skinCluster import get_skin_weights, set_skin_weights

logger = getLogger(__name__)


def move_skin_weights(
    skin_cluster: str,
    src_infs: Sequence[str],
    tgt_inf: str,
    components: Sequence[str],
    amount: float,
    use_percentage: bool = True,
    soft_weights: dict[str, float] | None = None,
) -> int:
    """Move skin weights from source influences to a target influence.

    Weights are proportionally removed from source influences and added to the target.
    Other influences remain unchanged.

    Args:
        skin_cluster (str): The skinCluster node name.
        src_infs (Sequence[str]): Source influence names to take weights from.
        tgt_inf (str): Target influence name to receive weights.
        components (Sequence[str]): Components to operate on.
        amount (float): Amount of weight to transfer. Percentage (0-100) when
            use_percentage is True, absolute value (0.0-1.0) when False.
        use_percentage (bool): If True, amount is treated as a percentage of
            source weights. If False, amount is an absolute value clamped to
            available source weight. Defaults to True.
        soft_weights (dict[str, float] | None): Per-component soft selection weights
            (0.0-1.0). When provided, the transfer amount is multiplied by each
            component's weight. None treats all components equally. Defaults to None.

    Returns:
        int: Number of components processed.

    Raises:
        ValueError: If parameters are invalid.
    """
    if not skin_cluster:
        raise ValueError("No skinCluster specified")

    if not src_infs:
        raise ValueError("No source influences specified")

    if not tgt_inf:
        raise ValueError("No target influence specified")

    if not components:
        raise ValueError("No components specified")

    # Validate components
    components = cmds.filterExpand(components, selectionMask=[28, 31, 46]) or []
    if not components:
        raise ValueError("No valid components found (vertices, CVs, or lattice points)")

    # Get all influences for index lookup
    all_infs = cmds.skinCluster(skin_cluster, query=True, influence=True)

    # Validate that source and target influences exist in the skinCluster
    missing_src = [inf for inf in src_infs if inf not in all_infs]
    if missing_src:
        raise ValueError(f"Source influences not found in skinCluster: {missing_src}")

    if tgt_inf not in all_infs:
        raise ValueError(f"Target influence not found in skinCluster: {tgt_inf}")

    # Get influence indices
    src_indices = [all_infs.index(inf) for inf in src_infs]
    tgt_index = all_infs.index(tgt_inf)

    # Get current weights
    weights = get_skin_weights(skin_cluster, components)

    # Modify weights
    for idx, comp_weights in enumerate(weights):
        total_src = sum(comp_weights[i] for i in src_indices)
        if total_src <= 0.0:
            continue

        soft_w = soft_weights.get(components[idx], 1.0) if soft_weights else 1.0

        # Calculate amount to move
        if use_percentage:
            move_amount = total_src * (amount / 100.0) * soft_w
        else:
            move_amount = min(amount * soft_w, total_src)

        if move_amount <= 0.0:
            continue

        # Proportionally reduce each source influence
        for i in src_indices:
            if comp_weights[i] > 0.0:
                reduction = (comp_weights[i] / total_src) * move_amount
                comp_weights[i] -= reduction

        # Add to target
        comp_weights[tgt_index] += move_amount

    # Write back weights
    set_skin_weights(skin_cluster, weights, components)

    logger.info(f"Moved weights from {src_infs} to {tgt_inf} on {len(components)} components")
    return len(components)


def get_affected_influences(
    skin_cluster: str,
    components: Sequence[str],
) -> list[str]:
    """Get influences that have non-zero weights on the specified components.

    Args:
        skin_cluster (str): The skinCluster node name.
        components (Sequence[str]): Components to check.

    Returns:
        list[str]: Influence names with non-zero weights, sorted by total weight descending.
    """
    all_infs = cmds.skinCluster(skin_cluster, query=True, influence=True)
    if not all_infs:
        return []

    num_infs = len(all_infs)
    weight_sums = [0.0] * num_infs

    for component in cmds.ls(components, flatten=True):
        weights = cmds.skinPercent(skin_cluster, component, query=True, value=True)
        for i, w in enumerate(weights):
            if w > 1e-6:
                weight_sums[i] += w

    affected = [(i, weight_sums[i]) for i in range(num_infs) if weight_sums[i] > 1e-6]
    affected.sort(key=lambda x: x[1], reverse=True)

    return [all_infs[i] for i, _ in affected]
