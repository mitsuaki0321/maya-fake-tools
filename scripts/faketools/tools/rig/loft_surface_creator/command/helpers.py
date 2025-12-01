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
        ValueError: If validation fails.
    """
    validate_root_joints(root_joints)

    chains = []
    for root in root_joints:
        chain = get_joint_chain_from_root(root, skip)
        chains.append(chain)

    return chains


__all__ = [
    "validate_root_joints",
    "get_joint_chain_from_root",
    "get_joint_chains_from_roots",
]
