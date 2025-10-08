"""
String manipulation functions.
"""

from logging import getLogger
import re

import maya.cmds as cmds

logger = getLogger(__name__)


def num_to_alpha(num):
    """Converts a number to its corresponding letters (e.g., 1 -> 'A', 27 -> 'AA').

    Args:
        num (int): The number to convert.

    Returns:
        str: The converted letters.
    """
    result = ""
    while num > 0:
        num, remainder = divmod(num - 1, 26)
        result = chr(65 + remainder) + result

    return result


def alpha_to_num(alpha):
    """Converts a letter sequence into its corresponding number (inverse of num_to_alpha).

    Args:
        alpha (str): The letter sequence.

    Returns:
        int: The converted number.
    """
    num = 0
    for c in alpha:
        num = num * 26 + (ord(c.upper()) - 64)

    return num


def substitute_names(names: list[str], regex_name: str, replace_name: str) -> list[str]:
    """Substitute the names with the corresponding letters.

    Args:
        names (list[str]): The names to substitute.
        regex_name (str): The name to substitute.
        replace_name (str): The new name.

    Returns:
        list[str]: The substituted names.
    """
    if not names:
        raise ValueError("Names are not specified.")

    if not regex_name:
        raise ValueError("Regex name is not specified.")

    p = re.compile(regex_name)

    result_names = []
    for name in names:
        result_name = p.sub(replace_name, name)
        result_names.append(result_name)

        logger.debug(f"Substituted: {name} -> {result_name}")

    return result_names


def solve_names(names: list[str], regex_name: str, **kwargs) -> list[str]:
    """Solve the names with the corresponding letters and numbers.

    Args:
        names (list[str]): The target names.
        regex_name (str): The regex name.

    Keyword Args:
        start_alpha (int): The start alphabet. Default is A.
        start_number (int): The start number. Default is 1.

    Returns:
        list[str]: The solved names.
    """
    if not names:
        raise ValueError("Names are not specified.")
    if not regex_name:
        raise ValueError("Regex name is not specified.")

    # Delete blank
    regex_name = regex_name.replace(" ", "")

    # Check regex name
    for mark in ["@", "#", "~"]:
        if regex_name.count(mark) > 1:
            raise ValueError(f"Invalid regex name: {regex_name}")

    for k in ["$", "%", "^", "&", "?", "+", "-", "=", "*"]:
        if k in regex_name:
            raise ValueError(f"Invalid regex name: {regex_name}")

    start_alpha_index = alpha_to_num(kwargs.get("start_alpha", "A"))
    start_number_index = kwargs.get("start_number", 0)

    new_names = []
    for i, name in enumerate(names):
        new_name = regex_name

        # Replace the '~' with the name
        if new_name.count("~"):
            new_name = new_name.replace("~", name)

        # Replace the '@' with the alphabet
        if new_name.count("@"):
            new_name = new_name.replace("@", num_to_alpha(start_alpha_index + i))

        # Replace the '#' with the number
        if new_name.count("#"):
            new_name = new_name.replace("#", str(start_number_index + i))

        new_names.append(new_name)

        logger.debug(f"Solved: {name} -> {new_name}")

    return new_names


def get_local_name(name: str) -> str:
    """Get the local names.

    Args:
        name (str): The target name.

    Returns:
        str: The local name.
    """
    if not name:
        raise ValueError("Name is not specified.")

    if "|" in name:
        return name.split("|")[-1]

    return name


def replace_namespaces(names: list[str], namespace: str) -> list[str]:
    """Replace the namespace names.

    Notes:
        - In the case of a full path, all parent nodes are replaced.

    Args:
        names (list[str]): The target names.
        namespace (str): The namespace.

    Returns:
        list[str]: The replaced names.
    """
    if not names:
        raise ValueError("Names are not specified.")

    if not isinstance(names, list):
        raise ValueError("Names must be a list.")

    if namespace is None:
        raise ValueError("Namespace is not specified.")

    result_names = []
    for name in names:
        # Corresponds to full path
        if "|" in name:
            full_names = name.split("|")
        else:
            full_names = [name]

        # Replace the namespace
        result_full_names = []
        for full_name in full_names:
            if ":" in full_name:
                full_name_without_ns = get_without_namespace(full_name)
                if namespace:
                    result_full_names.append(f"{namespace}:{full_name_without_ns}")
                else:
                    result_full_names.append(full_name_without_ns)
            else:
                result_full_names.append(f"{namespace}:{full_name}")

        result_names.append("|".join(result_full_names))

        logger.debug(f"Replaced: {name} -> {result_names[-1]}")

    return result_names


def get_namespace(name: str) -> str:
    """Get the namespace.

    Args:
        name (str): The target name.

    Returns:
        str: The namespace.
    """
    if not name:
        raise ValueError("Name is not specified.")

    if ":" not in name:
        return ""

    return name.rsplit(":", 1)[0]


def get_without_namespace(name: str) -> str:
    """Get the name without namespace.

    Args:
        name (str): The target name.

    Returns:
        str: The name without namespace.
    """
    if not name:
        raise ValueError("Name is not specified.")

    if ":" not in name:
        return name

    return name.rsplit(":", 1)[1]


def list_all_namespace() -> list[str]:
    """Lists all namespaces, including nested ones.

    Returns:
        list[str]: The namespaces.
    """
    result_namespaces = []

    def _list_namespace(namespace):
        """List the namespace."""
        result_namespaces.append(namespace)

        sub_namespaces = cmds.namespaceInfo(namespace, listOnlyNamespaces=True)
        if sub_namespaces:
            for sub_ns in sub_namespaces:
                _list_namespace(sub_ns)

    root_namespaces = [ns for ns in cmds.namespaceInfo(listOnlyNamespaces=True) if ns not in ["UI", "shared"]]
    if not root_namespaces:
        return result_namespaces

    for ns in root_namespaces:
        _list_namespace(ns)

    return result_namespaces
