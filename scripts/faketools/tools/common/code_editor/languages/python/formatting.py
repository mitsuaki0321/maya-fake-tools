"""Python literal formatting for inserted values.

Bound onto the Python :class:`LanguageProfile` as ``format_string_literal``
/ ``format_string_list`` so insert commands can produce Python-native text
without branching on language themselves.
"""

from __future__ import annotations


def python_string_literal(value: str) -> str:
    """Format a single value as a Python double-quoted string literal.

    Backslashes and double quotes are escaped so the result is always a
    valid literal even for unusual node names.

    Args:
        value (str): The raw value (e.g. a node name).

    Returns:
        str: e.g. ``"pCube1"``.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def python_string_list(values: list[str]) -> str:
    """Format values as a Python list of double-quoted strings.

    Args:
        values (list[str]): The raw values.

    Returns:
        str: e.g. ``["pCube1", "pSphere1"]``.
    """
    inner = ", ".join(python_string_literal(v) for v in values)
    return f"[{inner}]"
