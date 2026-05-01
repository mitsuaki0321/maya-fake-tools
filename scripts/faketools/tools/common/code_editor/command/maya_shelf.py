"""Add a code snippet to the active Maya shelf.

Pulled out of the editor UI so the MEL escaping and ``mel.eval`` calls
don't leak into widget code. Importing this module is safe outside Maya
— the ``maya``/``mel`` imports happen inside :func:`add_to_active_shelf`.

The button's source type, label, and icon come from the supplied
:class:`LanguageProfile`'s ``shelf_config``; languages whose profile lacks
one cannot be added to a shelf.
"""

from __future__ import annotations

from logging import getLogger

from ..languages import PYTHON, LanguageProfile

logger = getLogger(__name__)


def add_to_active_shelf(code: str, language: LanguageProfile = PYTHON) -> tuple[bool, str]:
    """Add ``code`` as a button on Maya's currently active shelf.

    Args:
        code (str): The code snippet to bind to the shelf button.
        language (LanguageProfile): Profile supplying ``shelf_config``
            (source type, label, icon). Defaults to :data:`PYTHON` so legacy
            call sites keep their original behaviour.

    Returns:
        tuple[bool, str]: ``(True, shelf_name)`` on success, ``(False, error_message)``
            on failure (Maya unavailable, no shelf config for the language,
            or a Maya-side error).
    """
    shelf_config = language.shelf_config
    if shelf_config is None:
        return False, f"Shelf-add not supported for {language.display_name}"

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

        mel.eval(
            f'shelfButton -rpt true -i1 "{shelf_config.icon}" -l "{shelf_config.label}" '
            f'-ann "{mel_code}" -stp "{shelf_config.source_type}" -c "{mel_code}" -p "{active_shelf}"'
        )
        mel.eval("setShelfStyle `optionVar -query shelfItemStyle` `optionVar -query shelfItemSize`")

        logger.info(f"Added {language.display_name} code to shelf: {active_shelf}")
        return True, active_shelf
    except Exception as exc:
        logger.error(f"Failed to add to shelf: {exc}")
        return False, str(exc)
