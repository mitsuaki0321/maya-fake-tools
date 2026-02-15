"""Background transfer worker — runs blend shape transfer on a QThread.

Reads vertex data via MayaMeshAPI, computes deltas with transfer_batch,
and writes results back to the Maya scene. All scene writes are wrapped
in a single undo chunk.
"""

from __future__ import annotations

from ....lib_ui.qt_compat import QThread, Signal
from .bs_controller import TransferRequest


class TransferWorker(QThread):
    """Run blend shape delta transfer off the main thread."""

    finished = Signal(int, list)  # (count, skipped)
    error = Signal(str)
    progress = Signal(int, int, str)  # (current, total, name)

    def __init__(self, request: TransferRequest, parent=None) -> None:
        super().__init__(parent)
        self._request = request

    def run(self) -> None:
        try:
            from .mesh_bridge import OpenMayaMeshAPI
            from .scene_ops import (
                close_undo_chunk,
                duplicate_mesh,
                open_undo_chunk,
            )
            from .transfer.delta_transfer import transfer_batch

            api = OpenMayaMeshAPI()
            req = self._request

            # Read vertex data
            source_base_verts = api.get_vertex_positions(req.source_base_name)
            fitted_verts = api.get_vertex_positions(req.fitted_name)

            bs_list = []
            for name in req.bs_names:
                verts = api.get_vertex_positions(name)
                bs_list.append((name, verts))

            # Compute deltas (pure numpy)
            batch_result = transfer_batch(
                source_base_verts,
                fitted_verts,
                bs_list,
                on_progress=lambda cur, tot, name: self.progress.emit(cur, tot, name),
            )

            # Write results to Maya scene inside undo chunk
            open_undo_chunk("bs_transfer")
            try:
                for tr in batch_result.results:
                    new_name = f"{req.fitted_name}_{tr.name}"
                    dup_name = duplicate_mesh(req.fitted_name, new_name)
                    api.set_vertex_positions(dup_name, tr.vertices)
            finally:
                close_undo_chunk()

            self.finished.emit(
                len(batch_result.results),
                batch_result.skipped,
            )
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self.error.emit(str(exc))
