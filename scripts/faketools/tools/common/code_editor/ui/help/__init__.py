"""Floating docstring help popup.

The Qt parts (:class:`HelpPopupController`, :class:`HelpPopup`) live in
``controller.py`` / ``popup.py``. The ``renderer/`` sub-package is
Qt-independent on purpose so it can be exercised without loading the full
editor — :mod:`scripts/debug/help_popup_preview` relies on this.

Imports are intentionally lazy: pulling Qt at package import time would
break that Qt-independent renderer path.
"""

__all__ = ["HelpPopup", "HelpPopupController"]
