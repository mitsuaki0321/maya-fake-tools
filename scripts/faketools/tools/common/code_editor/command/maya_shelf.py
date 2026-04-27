"""Add a Python snippet to the active Maya shelf.

Pulled out of the editor UI so the MEL escaping and ``mel.eval`` calls
don't leak into widget code. Importing this module is safe outside Maya
— the ``maya``/``mel`` imports happen inside :func:`add_to_active_shelf`.
"""

from __future__ import annotations

from logging import getLogger

logger = getLogger(__name__)


def add_to_active_shelf(code: str) -> tuple[bool, str]:
    """Add ``code`` as a Python button on Maya's currently active shelf.

    Args:
        code (str): The Python snippet to bind to the shelf button.

    Returns:
        tuple[bool, str]: ``(True, shelf_name)`` on success, ``(False, error_message)``
            on failure.
    """
    try:
        import maya.cmds as cmds
        import maya.mel as mel
    except ImportError as exc:
        return False, f"Maya not available: {exc}"

    try:
        shelf_top_level = mel.eval("$tmp = $gShelfTopLevel")
        active_shelf = cmds.tabLayout(shelf_top_level, query=True, selectTab=True)

        # MEL string escaping for the snippet body.
        mel_code = code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")

        mel.eval(f'shelfButton -rpt true -i1 "pythonFamily.png" -l "Python" -ann "{mel_code}" -stp "python" -c "{mel_code}" -p "{active_shelf}"')
        mel.eval("setShelfStyle `optionVar -query shelfItemStyle` `optionVar -query shelfItemSize`")

        logger.info(f"Added code to shelf: {active_shelf}")
        return True, active_shelf
    except Exception as exc:
        logger.error(f"Failed to add to shelf: {exc}")
        return False, str(exc)
