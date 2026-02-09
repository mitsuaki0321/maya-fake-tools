"""Skin Weights Transfer command layer.

Pure Maya operations for transferring skin weights between influences.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from logging import getLogger

import maya.cmds as cmds

from ....lib.lib_skinCluster import get_skin_weights, set_skin_weights

logger = getLogger(__name__)


class DistributionMethod(str, Enum):
    """Method for distributing weights across multiple target influences."""

    EVEN = "even"
    PROPORTIONAL = "proportional"
    DISTANCE = "distance"


def _get_joint_positions(influences: Sequence[str]) -> list[list[float]]:
    """Get world-space positions for joint/transform influences.

    Args:
        influences (Sequence[str]): Influence node names.

    Returns:
        list[list[float]]: World positions as [[x, y, z], ...].
    """
    positions = []
    for inf in influences:
        pos = cmds.xform(inf, query=True, worldSpace=True, translation=True)
        positions.append(pos)
    return positions


def _get_component_positions(components: Sequence[str]) -> list[list[float]]:
    """Get world-space positions for mesh/nurbs/lattice components.

    Args:
        components (Sequence[str]): Component names.

    Returns:
        list[list[float]]: World positions as [[x, y, z], ...].
    """
    positions = []
    for comp in components:
        pos = cmds.xform(comp, query=True, worldSpace=True, translation=True)
        positions.append(pos)
    return positions


def _compute_distribution_weights(
    distribution: DistributionMethod,
    tgt_indices: list[int],
    comp_weights: list[float],
    comp_pos: list[float] | None,
    tgt_positions: list[list[float]] | None,
) -> list[float]:
    """Compute distribution ratios for multiple target influences.

    Args:
        distribution (DistributionMethod): Distribution method.
        tgt_indices (list[int]): Target influence indices in the weight array.
        comp_weights (list[float]): Current weight array for this component.
        comp_pos (list[float] | None): Component world position [x, y, z] (for distance mode).
        tgt_positions (list[list[float]] | None): Target influence positions (for distance mode).

    Returns:
        list[float]: Normalized distribution ratios (sum=1.0), one per target.
    """
    n = len(tgt_indices)

    if distribution == DistributionMethod.EVEN:
        return [1.0 / n] * n

    if distribution == DistributionMethod.PROPORTIONAL:
        existing = [comp_weights[i] for i in tgt_indices]
        total = sum(existing)
        if total > 0.0:
            return [w / total for w in existing]
        # Fallback to even when all target weights are zero
        return [1.0 / n] * n

    # DistributionMethod.DISTANCE
    if comp_pos is None or tgt_positions is None:
        return [1.0 / n] * n

    cx, cy, cz = comp_pos
    inv_dists = []
    for tgt_pos in tgt_positions:
        dx = tgt_pos[0] - cx
        dy = tgt_pos[1] - cy
        dz = tgt_pos[2] - cz
        dist = max((dx * dx + dy * dy + dz * dz) ** 0.5, 1e-8)
        inv_dists.append(1.0 / dist)

    total = sum(inv_dists)
    return [d / total for d in inv_dists]


def move_skin_weights(
    skin_cluster: str,
    src_infs: Sequence[str],
    tgt_infs: Sequence[str],
    components: Sequence[str],
    amount: float,
    use_percentage: bool = True,
    soft_weights: dict[str, float] | None = None,
    distribution: DistributionMethod = DistributionMethod.EVEN,
) -> int:
    """Move skin weights from source influences to target influences.

    Weights are proportionally removed from source influences and distributed
    to target influences according to the chosen distribution method.
    Other influences remain unchanged.

    Args:
        skin_cluster (str): The skinCluster node name.
        src_infs (Sequence[str]): Source influence names to take weights from.
        tgt_infs (Sequence[str]): Target influence names to receive weights.
        components (Sequence[str]): Components to operate on.
        amount (float): Amount of weight to transfer. Percentage (0-100) when
            use_percentage is True, absolute value (0.0-1.0) when False.
        use_percentage (bool): If True, amount is treated as a percentage of
            source weights. If False, amount is an absolute value clamped to
            available source weight. Defaults to True.
        soft_weights (dict[str, float] | None): Per-component soft selection weights
            (0.0-1.0). When provided, the transfer amount is multiplied by each
            component's weight. None treats all components equally. Defaults to None.
        distribution (DistributionMethod): Method for distributing weights across
            multiple targets. Defaults to EVEN.

    Returns:
        int: Number of components processed.

    Raises:
        ValueError: If parameters are invalid.
    """
    if not skin_cluster:
        raise ValueError("No skinCluster specified")

    if not src_infs:
        raise ValueError("No source influences specified")

    if not tgt_infs:
        raise ValueError("No target influences specified")

    if not components:
        raise ValueError("No components specified")

    # Check for overlap between source and target
    overlap = set(src_infs) & set(tgt_infs)
    if overlap:
        raise ValueError(f"Source and target influences must not overlap: {sorted(overlap)}")

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

    missing_tgt = [inf for inf in tgt_infs if inf not in all_infs]
    if missing_tgt:
        raise ValueError(f"Target influences not found in skinCluster: {missing_tgt}")

    # Get influence indices
    src_indices = [all_infs.index(inf) for inf in src_infs]
    tgt_indices = [all_infs.index(inf) for inf in tgt_infs]

    # Get current weights
    weights = get_skin_weights(skin_cluster, components)

    # Pre-compute positions for distance mode
    tgt_positions = None
    comp_positions = None
    if distribution == DistributionMethod.DISTANCE and len(tgt_indices) > 1:
        tgt_positions = _get_joint_positions(tgt_infs)
        comp_positions = _get_component_positions(components)

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

        # Distribute to target influences
        if len(tgt_indices) == 1:
            comp_weights[tgt_indices[0]] += move_amount
        else:
            comp_pos = comp_positions[idx] if comp_positions else None
            dist_weights = _compute_distribution_weights(distribution, tgt_indices, comp_weights, comp_pos, tgt_positions)
            for ti, dw in zip(tgt_indices, dist_weights):
                comp_weights[ti] += move_amount * dw

    # Write back weights
    set_skin_weights(skin_cluster, weights, components)

    logger.info(f"Moved weights from {list(src_infs)} to {list(tgt_infs)} on {len(components)} components")
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
