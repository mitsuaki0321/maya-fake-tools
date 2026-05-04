"""Language profile system for the code editor.

Public API of the package. The :class:`LanguageProfile` dataclass
(defined in :mod:`.profile`) centralizes everything that varies between
languages — file extensions, comment characters, execution
``sourceType``, syntax highlighter, indent / folding strategies,
right-click extender, etc. Required fields (``id`` / ``display_name`` /
``extensions`` / ``default_extension``) identify the language and its
file association; everything else is opt-in per language and ``None``
means the feature is disabled.

Consumers should resolve a profile via :func:`get_profile_for_path` (or
hold the profile attached to an editor tab) and skip / hide / grey out
any feature whose corresponding profile field is ``None``.

Layout:

* :mod:`.profile` -- :class:`LanguageProfile` + :class:`ShelfConfig`
* :mod:`.indent_resolver` -- :class:`IndentResolver` base class
* :mod:`.folding_strategy` -- :class:`FoldingStrategy` base class
* :mod:`.editor_helpers` -- cross-language editor plumbing
  (``find_execution_manager`` / ``dispatch_inspection``)
* :mod:`.python` -- Python implementation subpackage; exports ``PYTHON``
* :mod:`.mel` -- MEL implementation subpackage; exports ``MEL``
"""

from __future__ import annotations

import os
from typing import Optional

from .mel import MEL
from .profile import LanguageProfile, ShelfConfig
from .python import PYTHON

ALL_PROFILES: tuple[LanguageProfile, ...] = (PYTHON, MEL)
DEFAULT_PROFILE: LanguageProfile = PYTHON
KNOWN_EXTENSIONS: frozenset[str] = frozenset(ext for profile in ALL_PROFILES for ext in profile.extensions)


def get_profile_for_path(path: Optional[str]) -> LanguageProfile:
    """Resolve a :class:`LanguageProfile` for a file path.

    Falls back to :data:`DEFAULT_PROFILE` when the extension is unknown or
    the path is empty / ``None``.

    Args:
        path (Optional[str]): File path to inspect; only the extension is used.

    Returns:
        LanguageProfile: The matching profile, or :data:`DEFAULT_PROFILE` on miss.
    """
    if not path:
        return DEFAULT_PROFILE
    ext = os.path.splitext(path)[1].lower()
    for profile in ALL_PROFILES:
        if ext in profile.extensions:
            return profile
    return DEFAULT_PROFILE


__all__ = [
    "ALL_PROFILES",
    "DEFAULT_PROFILE",
    "KNOWN_EXTENSIONS",
    "MEL",
    "PYTHON",
    "LanguageProfile",
    "ShelfConfig",
    "get_profile_for_path",
]
