"""Skin Weights Transfer command layer.

Pure Maya operations for transferring skin weights between influences.
"""

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
) -> int:
    """Move skin weights from source influences to a target influence.

    Weights are proportionally removed from source influences and added to the target.
    Other influences remain unchanged.

    Args:
        skin_cluster (str): The skinCluster node name.
        src_infs (Sequence[str]): Source influence names to take weights from.
        tgt_inf (str): Target influence name to receive weights.
        components (Sequence[str]): Components to operate on.
        amount (float): Percentage of source weights to transfer (0-100).

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
    for comp_weights in weights:
        total_src = sum(comp_weights[i] for i in src_indices)
        if total_src <= 0.0:
            continue

        # Calculate amount to move
        move_amount = total_src * (amount / 100.0)

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
