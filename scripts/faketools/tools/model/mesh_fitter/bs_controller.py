"""BS Transfer Controller — pure Python, zero Qt/Maya dependency.

All state management and validation for blend shape transfer lives here.
The UI window is a thin shell that forwards signals to this controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .controller import MeshListProvider
from .mesh_bridge import MayaMeshAPI

# ---------------------------------------------------------------------------
# TransferRequest — immutable snapshot for thread-safe Worker handoff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferRequest:
    """Immutable snapshot of all parameters needed to run a batch transfer."""

    source_base_name: str
    fitted_name: str
    bs_names: list[str]


# ---------------------------------------------------------------------------
# BSTransferController
# ---------------------------------------------------------------------------


def _noop(*_a: object, **_kw: object) -> None:
    pass


class BSTransferController:
    """All BS transfer business logic — no Qt, no Maya runtime dependency.

    Callbacks (set by the Window layer):
        on_status(msg)                          — status bar text changed
        on_error(msg)                           — show error to user
        on_progress(current, total, name)       — per-BS progress
        on_transfer_complete(count, skipped)     — transfer finished
        on_transfer_state_changed(running)       — enable/disable UI
    """

    def __init__(
        self,
        api: MayaMeshAPI,
        mesh_list_provider: MeshListProvider | None = None,
    ) -> None:
        self._api = api
        self._mesh_list_provider = mesh_list_provider

        # Mesh state
        self._mesh_names: list[str] = []
        self._source_base_name: str = ""
        self._fitted_name: str = ""
        self._selected_bs_names: list[str] = []

        # Transfer state
        self._is_transferring: bool = False

        # Callbacks (Window sets these)
        self.on_status: Callable[[str], None] = _noop
        self.on_error: Callable[[str], None] = _noop
        self.on_progress: Callable[[int, int, str], None] = _noop
        self.on_transfer_complete: Callable[[int, list], None] = _noop
        self.on_transfer_state_changed: Callable[[bool], None] = _noop

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def source_base_name(self) -> str:
        return self._source_base_name

    @property
    def fitted_name(self) -> str:
        return self._fitted_name

    @property
    def selected_bs_names(self) -> list[str]:
        return list(self._selected_bs_names)

    @property
    def mesh_names(self) -> list[str]:
        return list(self._mesh_names)

    @property
    def is_transferring(self) -> bool:
        return self._is_transferring

    @property
    def can_run(self) -> bool:
        return (
            bool(self._source_base_name)
            and bool(self._fitted_name)
            and self._source_base_name != self._fitted_name
            and len(self._selected_bs_names) > 0
            and not self._is_transferring
        )

    @property
    def available_bs_names(self) -> list[str]:
        """Mesh names excluding source_base, fitted, and already selected."""
        exclude = {self._source_base_name, self._fitted_name}
        exclude.update(self._selected_bs_names)
        return [n for n in self._mesh_names if n not in exclude]

    # ------------------------------------------------------------------
    # Mesh selection
    # ------------------------------------------------------------------

    def refresh_mesh_list(self) -> list[str]:
        """Fetch mesh list from provider and return it."""
        if self._mesh_list_provider is not None:
            self._mesh_names = self._mesh_list_provider.list_meshes()
        else:
            self._mesh_names = []
        self.on_status(f"{len(self._mesh_names)} meshes found")
        return list(self._mesh_names)

    def set_source_base(self, name: str) -> None:
        if name == self._source_base_name:
            return
        self._source_base_name = name
        # Remove from selected BS if it was there
        if name in self._selected_bs_names:
            self._selected_bs_names.remove(name)
        self.on_status(f"Source base: {name}")

    def set_fitted(self, name: str) -> None:
        if name == self._fitted_name:
            return
        self._fitted_name = name
        # Remove from selected BS if it was there
        if name in self._selected_bs_names:
            self._selected_bs_names.remove(name)
        self.on_status(f"Fitted: {name}")

    # ------------------------------------------------------------------
    # Blend shape selection
    # ------------------------------------------------------------------

    def add_bs(self, name: str) -> None:
        """Add a blend shape name to the selected list."""
        if name not in self._selected_bs_names:
            self._selected_bs_names.append(name)

    def remove_bs(self, name: str) -> None:
        """Remove a blend shape name from the selected list."""
        if name in self._selected_bs_names:
            self._selected_bs_names.remove(name)

    def set_selected_bs(self, names: list[str]) -> None:
        """Replace the entire selected BS list."""
        self._selected_bs_names = list(names)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_selection(self) -> str | None:
        """Validate current selection before transfer.

        Returns:
            None if valid, or an error message string.
        """
        if not self._source_base_name:
            return "No source base mesh selected"
        if not self._fitted_name:
            return "No fitted mesh selected"
        if self._source_base_name == self._fitted_name:
            return "Source base and fitted must be different meshes"
        if len(self._selected_bs_names) == 0:
            return "No blend shapes selected"

        # Check vertex counts match between source_base and fitted
        try:
            src_verts = self._api.get_vertex_positions(self._source_base_name)
            fit_verts = self._api.get_vertex_positions(self._fitted_name)
            if src_verts.shape[0] != fit_verts.shape[0]:
                return f"Vertex count mismatch: source base has {src_verts.shape[0]}, fitted has {fit_verts.shape[0]}"
        except Exception as exc:
            return f"Failed to read mesh vertices: {exc}"

        return None

    # ------------------------------------------------------------------
    # Request construction
    # ------------------------------------------------------------------

    def build_transfer_request(self) -> TransferRequest | None:
        """Build an immutable transfer request, or None if can't run."""
        if not self.can_run:
            self.on_error("Cannot run: check source/fitted/BS selection")
            return None

        return TransferRequest(
            source_base_name=self._source_base_name,
            fitted_name=self._fitted_name,
            bs_names=list(self._selected_bs_names),
        )

    # ------------------------------------------------------------------
    # Transfer lifecycle (called by Window / Worker)
    # ------------------------------------------------------------------

    def on_transfer_started(self) -> None:
        self._is_transferring = True
        self.on_transfer_state_changed(True)
        self.on_status("Transfer in progress...")

    def on_transfer_finished(self, count: int, skipped: list) -> None:
        self._is_transferring = False
        self.on_transfer_state_changed(False)
        msg = f"Transfer complete: {count} blend shapes created"
        if skipped:
            msg += f", {len(skipped)} skipped"
        self.on_status(msg)
        self.on_transfer_complete(count, skipped)

    def on_transfer_error(self, error_msg: str) -> None:
        self._is_transferring = False
        self.on_transfer_state_changed(False)
        self.on_error(error_msg)
        self.on_status(f"Transfer failed: {error_msg}")
