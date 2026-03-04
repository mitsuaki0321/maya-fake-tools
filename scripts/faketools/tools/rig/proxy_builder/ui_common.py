"""Shared widgets and helper functions for Proxy Builder tabs."""

from __future__ import annotations

import maya.cmds as cmds  # type: ignore[import]

from ....lib_ui.qt_compat import QListWidget, QListWidgetItem, Qt, QWidget


class SceneNodeListWidget(QListWidget):
    """QListWidget that selects corresponding Maya scene nodes on item selection.

    Node names are resolved from ``Qt.UserRole`` data first, falling back to
    ``item.text()``.  A ``_sync_enabled`` flag prevents ``cmds.select`` from
    firing during programmatic list modifications (clear / addItem / takeItem).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sync_enabled = True
        self.itemSelectionChanged.connect(self._on_selection_changed)

    # -- public helpers --------------------------------------------------

    def set_sync_enabled(self, enabled: bool) -> None:
        """Enable / disable scene-selection syncing."""
        self._sync_enabled = enabled

    # -- internal --------------------------------------------------------

    def _node_name(self, item: QListWidgetItem) -> str:
        """Return the Maya node name stored on *item*."""
        data = item.data(Qt.UserRole)
        return data if data else item.text()

    def _on_selection_changed(self) -> None:
        if not self._sync_enabled:
            return
        items = self.selectedItems()
        if not items:
            return
        nodes = [self._node_name(it) for it in items]
        valid = [n for n in nodes if cmds.objExists(n)]
        if valid:
            cmds.select(valid, replace=True)


def select_all_items(list_widget: QListWidget) -> None:
    """Select all items in the given list widget."""
    list_widget.selectAll()


def add_joints_to_list(list_widget: SceneNodeListWidget) -> None:
    """Add selected joints to the given list widget (skip duplicates)."""
    sel = cmds.ls(selection=True, type="joint")
    if not sel:
        cmds.warning("Proxy Builder: Select one or more joints")
        return
    existing = {list_widget.item(i).text() for i in range(list_widget.count())}
    for joint in sel:
        if joint not in existing:
            list_widget.addItem(joint)


def remove_from_list(list_widget: SceneNodeListWidget) -> None:
    """Remove selected items from the given list widget."""
    list_widget.set_sync_enabled(False)
    for item in reversed(list_widget.selectedItems()):
        list_widget.takeItem(list_widget.row(item))
    list_widget.set_sync_enabled(True)
