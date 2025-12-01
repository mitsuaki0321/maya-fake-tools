"""Helper functions for loft surface creation."""

from logging import getLogger

import maya.cmds as cmds

from .....lib.lib_selection import filter_by_type, get_hierarchy

logger = getLogger(__name__)


def validate_root_joints(root_joints: list[str]) -> None:
    """Validate that root joints are valid joint nodes.

    Args:
        root_joints (list[str]): List of root joint names to validate.

    Raises:
        ValueError: If root_joints is empty, nodes don't exist, or are not joints.
    """
    if not root_joints:
        raise ValueError("No root joints specified.")

    if len(root_joints) < 2:
        raise ValueError("At least 2 root joints are required for lofting.")

    # Check existence
    not_exist_joints = [joint for joint in root_joints if not cmds.objExists(joint)]
    if not_exist_joints:
        raise ValueError(f"Joints not found: {not_exist_joints}")

    # Check if they are joints
    not_joints = [joint for joint in root_joints if cmds.nodeType(joint) != "joint"]
    if not_joints:
        raise ValueError(f"Not joint nodes: {not_joints}")


def validate_joint_chains(joint_chains: list[list[str]], min_joints_per_chain: int = 3) -> None:
    """Validate joint chains for loft surface creation.

    Args:
        joint_chains (list[list[str]]): List of joint chains.
            Each chain is a list of joint names.
        min_joints_per_chain (int): Minimum joints required per chain.
            Default is 3 for degree 3 curves.

    Raises:
        ValueError: If validation fails.
    """
    if not joint_chains:
        raise ValueError("No joint chains specified.")

    if len(joint_chains) < 2:
        raise ValueError("At least 2 joint chains are required for lofting.")

    # Check all chains have the same length
    chain_lengths = [len(chain) for chain in joint_chains]
    if len(set(chain_lengths)) > 1:
        raise ValueError(f"All joint chains must have the same length. Found: {chain_lengths}")

    # Check minimum chain length
    if chain_lengths[0] < min_joints_per_chain:
        raise ValueError(f"Each chain must have at least {min_joints_per_chain} joints. Found: {chain_lengths[0]}")

    # Check all joints exist and are joint nodes
    for chain_idx, chain in enumerate(joint_chains):
        for joint in chain:
            if not cmds.objExists(joint):
                raise ValueError(f"Joint not found in chain {chain_idx}: {joint}")
            if cmds.nodeType(joint) != "joint":
                raise ValueError(f"Not a joint node in chain {chain_idx}: {joint}")


def get_joint_chain_from_root(root_joint: str, skip: int = 0) -> list[str]:
    """Get joint chain from a root joint.

    Args:
        root_joint (str): Root joint name.
        skip (int): Number of joints to skip between each selected joint.
            0 means no skip (use all joints).

    Returns:
        list[str]: List of joints in the chain, from root to end.

    Raises:
        ValueError: If root_joint doesn't exist or is not a joint.
    """
    if not cmds.objExists(root_joint):
        raise ValueError(f"Joint not found: {root_joint}")

    if cmds.nodeType(root_joint) != "joint":
        raise ValueError(f"Not a joint node: {root_joint}")

    # Get hierarchy and filter to joints only
    hierarchy = get_hierarchy([root_joint], include_shape=False)
    joints = filter_by_type(hierarchy, "joint")

    if not joints:
        raise ValueError(f"No joints found in hierarchy of: {root_joint}")

    # Apply skip logic
    if skip > 0:
        # Take every (skip+1)th joint, but always include the last joint
        skipped_joints = joints[:: skip + 1]

        # Ensure last joint is included
        if joints[-1] not in skipped_joints:
            skipped_joints.append(joints[-1])

        joints = skipped_joints

    logger.debug(f"Joint chain from {root_joint}: {joints}")
    return joints


def get_joint_chains_from_roots(root_joints: list[str], skip: int = 0) -> list[list[str]]:
    """Get joint chains from multiple root joints.

    Args:
        root_joints (list[str]): List of root joint names.
        skip (int): Number of joints to skip between each selected joint.

    Returns:
        list[list[str]]: List of joint chains.

    Raises:
        ValueError: If validation fails or chains have different lengths.
    """
    validate_root_joints(root_joints)

    chains = []
    for root in root_joints:
        chain = get_joint_chain_from_root(root, skip)
        chains.append(chain)

    # Validate that all chains have the same length
    validate_joint_chains(chains)

    return chains


def transpose_parallel_joints(parallel_rows: list[list[str]]) -> list[list[str]]:
    """Transpose parallel joint rows to joint chains (columns).

    Args:
        parallel_rows (list[list[str]]): List of parallel joint rows.
            Each row contains joints at the same hierarchy level across chains.
            Example: [[jointAA, jointBA, jointCA], [jointAB, jointBB, jointCB], ...]

    Returns:
        list[list[str]]: Transposed joint chains.
            Example: [[jointAA, jointAB, ...], [jointBA, jointBB, ...], ...]

    Raises:
        ValueError: If rows have different lengths.
    """
    if not parallel_rows:
        raise ValueError("No parallel joint rows specified.")

    # Check all rows have the same length
    row_lengths = [len(row) for row in parallel_rows]
    if len(set(row_lengths)) > 1:
        raise ValueError(f"All parallel rows must have the same length. Found: {row_lengths}")

    # Transpose: rows become columns
    num_chains = row_lengths[0]
    num_joints_per_chain = len(parallel_rows)

    chains = []
    for chain_idx in range(num_chains):
        chain = [parallel_rows[row_idx][chain_idx] for row_idx in range(num_joints_per_chain)]
        chains.append(chain)

    return chains


__all__ = [
    "validate_root_joints",
    "validate_joint_chains",
    "get_joint_chain_from_root",
    "get_joint_chains_from_roots",
    "transpose_parallel_joints",
]
