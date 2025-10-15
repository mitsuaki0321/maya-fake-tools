"""Maya Qt utilities."""

from typing import Optional

import maya.OpenMayaUI as omui

from .qt_compat import QObject, QWidget, shiboken


def qt_widget_from_maya_control(name: str, qt_object: QObject = QWidget) -> QWidget:
    """Get Qt widget from Maya UI control name.

    Args:
        name: Name of the Maya control.
        qt_object: Qt object type to wrap the control with. Defaults to QWidget.

    Returns:
        Qt widget wrapping the Maya control.

    Raises:
        RuntimeError: If the control is not found.
    """
    ptr = omui.MQtUtil.findControl(name)
    if ptr is None:
        raise RuntimeError(f'Failed to find control "{name}".')

    return shiboken.wrapInstance(int(ptr), qt_object)


def maya_name_from_qt_widget(qt_object: QObject) -> str:
    """Get Maya UI name from Qt widget.

    Args:
        qt_object: Qt object to get the Maya name from.

    Returns:
        Full Maya UI name of the object.
    """
    return omui.MQtUtil.fullName(int(shiboken.getCppPointer(qt_object)[0]))


def qt_widget_from_maya_window(object_name: str) -> QWidget:
    """Get Qt widget from Maya window name.

    Args:
        object_name: The object name of the Maya window.

    Returns:
        Qt widget wrapping the Maya window.

    Raises:
        RuntimeError: If the window is not found.
    """
    ptr = omui.MQtUtil.findWindow(object_name)
    if ptr is None:
        raise RuntimeError(f'Failed to find window "{object_name}".')

    return shiboken.wrapInstance(int(ptr), QWidget)


def get_maya_main_window() -> Optional[QWidget]:
    """Get the Maya main window as a Qt widget.

    Returns:
        Maya main window widget, or None if not available.
    """
    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    if maya_main_window_ptr is not None:
        return shiboken.wrapInstance(int(maya_main_window_ptr), QWidget)
    return None


__all__ = [
    "qt_widget_from_maya_control",
    "maya_name_from_qt_widget",
    "qt_widget_from_maya_window",
    "get_maya_main_window",
]
