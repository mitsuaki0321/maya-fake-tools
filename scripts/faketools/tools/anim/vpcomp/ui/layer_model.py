"""QStandardItemModel wrapper that syncs with LayerStack."""

from __future__ import annotations

from .....lib_ui.qt_compat import QStandardItem, QStandardItemModel, Qt

# Custom item roles
ROLE_STACK_IDX = Qt.UserRole + 1  # int: LayerStack index
ROLE_LAYER_TYPE = Qt.UserRole + 2  # LayerType enum
ROLE_VISIBLE = Qt.UserRole + 3  # bool
ROLE_BADGE = Qt.UserRole + 4  # str: "CAM" / "IMG" / "SEQ"
ROLE_NAME = Qt.UserRole + 5  # str: layer name


class LayerModel(QStandardItemModel):
    """Model holding LayerStack display order (top=front).

    Row 0 = frontmost layer (last index of the stack).
    After DnD row moves, call rows_moved_to_stack() to sync
    the LayerStack order.
    """

    def rebuild(self, stack) -> None:
        """Rebuild the model from the entire LayerStack."""
        self.clear()
        layers = stack.layers
        for stack_idx in reversed(range(len(layers))):
            layer = layers[stack_idx]
            item = QStandardItem()
            item.setData(stack_idx, ROLE_STACK_IDX)
            item.setData(layer.layer_type, ROLE_LAYER_TYPE)
            item.setData(layer.visible, ROLE_VISIBLE)
            item.setData(layer.layer_type.label, ROLE_BADGE)
            item.setData(layer.name, ROLE_NAME)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            self.appendRow(item)

    def update_row(self, row: int, layer) -> None:
        """Update data for a single row (lighter than rebuild)."""
        item = self.item(row)
        if item is None:
            return
        item.setData(layer.visible, ROLE_VISIBLE)
        item.setData(layer.name, ROLE_NAME)

    def rows_moved_to_stack(self, stack) -> None:
        """Rebuild LayerStack order from model row order after DnD."""
        row_count = self.rowCount()
        old_layers = list(stack.layers)
        new_order: list[int] = []
        for row in range(row_count):
            old_idx = self.item(row).data(ROLE_STACK_IDX)
            new_order.append(old_idx)
        # new_order[0] is frontmost = stack tail, so reverse to rebuild stack
        new_layers = [old_layers[i] for i in reversed(new_order)]
        stack.replace_layers(new_layers)

        # Reassign ROLE_STACK_IDX
        for row in range(row_count):
            self.item(row).setData(row_count - 1 - row, ROLE_STACK_IDX)
