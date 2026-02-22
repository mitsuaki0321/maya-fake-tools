"""GUI Controller — pure Python, zero Qt/Maya dependency.

All state management, validation, and config construction lives here.
The UI window is a thin shell that forwards signals to this controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .core.pipeline import PipelineResult

import numpy as np
import trimesh

from .core.algorithms import SCHEDULES, positions_to_surface_landmarks
from .core.pipeline import PipelineConfig
from .io.landmark_io import LandmarkData
from .mesh_bridge import MayaMeshAPI, maya_mesh_to_trimesh

_MIN_TARGET_REGION_FACES = 100

# ---------------------------------------------------------------------------
# MeshListProvider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MeshListProvider(Protocol):
    """Provides a list of mesh names available in the scene."""

    def list_meshes(self) -> list[str]: ...


class StaticMeshListProvider:
    """Test-friendly provider that returns a fixed list."""

    def __init__(self, names: list[str]) -> None:
        self._names = list(names)

    def list_meshes(self) -> list[str]:
        return list(self._names)


class SceneMeshListProvider:
    """Real Maya provider — delegates to scene_ops.list_meshes()."""

    def list_meshes(self) -> list[str]:
        from .scene_ops import list_meshes

        return list_meshes()


# ---------------------------------------------------------------------------
# Landmark validation
# ---------------------------------------------------------------------------


def _validate_landmark_distances(
    mesh: trimesh.Trimesh,
    positions: np.ndarray,
    label: str,
    threshold_ratio: float = 0.1,
) -> None:
    """Check that landmark positions are near the mesh surface.

    Raises ValueError if any landmark is farther than *threshold_ratio*
    of the mesh bounding-box diagonal from the nearest face.
    """
    _, distances, _ = trimesh.proximity.closest_point(mesh, positions)
    bbox_diag = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
    threshold = bbox_diag * threshold_ratio

    far = np.where(distances > threshold)[0]
    if len(far) > 0:
        details = ", ".join(f"#{i + 1} (dist={distances[i]:.3f})" for i in far)
        raise ValueError(
            f"{label.capitalize()} landmark(s) too far from mesh: {details} "
            f"(threshold={threshold:.3f}, "
            f"{threshold_ratio:.0%} of bbox diagonal {bbox_diag:.3f})"
        )


# ---------------------------------------------------------------------------
# FittingRequest — immutable snapshot for thread-safe Worker handoff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FittingRequest:
    """Immutable snapshot of all parameters needed to run a fitting."""

    source_name: str
    target_name: str
    config: PipelineConfig
    landmarks: LandmarkData | None
    duplicate_source: bool
    output_space: str
    target_face_indices: list[int] | None


# ---------------------------------------------------------------------------
# MeshFitController
# ---------------------------------------------------------------------------


def _noop(*_a: object, **_kw: object) -> None:
    pass


class MeshFitController:
    """All GUI business logic — no Qt, no Maya runtime dependency.

    Callbacks (set by the Window layer):
        on_status(msg)            — status bar text changed
        on_error(msg)             — show error to user
        on_landmarks_changed()    — landmark list needs refresh
        on_fitting_complete(res)  — fitting finished successfully
        on_fitting_state_changed(running) — enable/disable UI
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
        self._source_name: str = ""
        self._target_name: str = ""

        # Settings
        self._schedule: str = "gentle"
        self._auto_align: bool = True
        self._smooth_result: bool = False
        self._smooth_iterations: int = 3
        self._snap_to_target: bool = False
        self._symmetrize: bool = False
        self._symmetry_method: str = "position"
        self._duplicate_source: bool = True
        self._output_space: str = "source"

        # Target region (face selection)
        self._target_face_indices: list[int] | None = None

        # Advanced fitting settings
        self._stiffness: float = 0.10
        self._landmark_strength: float = 1.0
        self._steps: int = 7
        self._use_advanced: bool = False

        # Target decimation
        self._decimate_target: bool = False
        self._decimate_ratio: float = 0.25

        # Fitting state
        self._is_fitting: bool = False
        self._last_result: PipelineResult | None = None

        # Landmark pairs: (source_transform, target_transform)
        self._landmark_pairs: list[tuple[str, str]] = []

        # Callbacks (Window sets these)
        self.on_status: Callable[[str], None] = _noop
        self.on_error: Callable[[str], None] = _noop
        self.on_landmarks_changed: Callable[[], None] = _noop
        self.on_fitting_complete: Callable[[PipelineResult], None] = _noop
        self.on_fitting_state_changed: Callable[[bool], None] = _noop
        self.on_target_region_changed: Callable[[], None] = _noop

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def target_name(self) -> str:
        return self._target_name

    @property
    def mesh_names(self) -> list[str]:
        return list(self._mesh_names)

    @property
    def schedule(self) -> str:
        return self._schedule

    @property
    def auto_align(self) -> bool:
        return self._auto_align

    @property
    def smooth_result(self) -> bool:
        return self._smooth_result

    @property
    def smooth_iterations(self) -> int:
        return self._smooth_iterations

    @property
    def snap_to_target(self) -> bool:
        return self._snap_to_target

    @property
    def symmetrize(self) -> bool:
        return self._symmetrize

    @property
    def symmetry_method(self) -> str:
        return self._symmetry_method

    @property
    def duplicate_source(self) -> bool:
        return self._duplicate_source

    @property
    def output_space(self) -> str:
        return self._output_space

    @property
    def target_face_indices(self) -> list[int] | None:
        return self._target_face_indices

    @property
    def is_fitting(self) -> bool:
        return self._is_fitting

    @property
    def can_run(self) -> bool:
        return bool(self._source_name) and bool(self._target_name) and self._source_name != self._target_name and not self._is_fitting

    @property
    def last_result(self) -> PipelineResult | None:
        return self._last_result

    @property
    def landmark_pairs(self) -> list[tuple[str, str]]:
        return list(self._landmark_pairs)

    @property
    def stiffness(self) -> float:
        return self._stiffness

    @property
    def landmark_strength(self) -> float:
        return self._landmark_strength

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def use_advanced(self) -> bool:
        return self._use_advanced

    @property
    def decimate_target(self) -> bool:
        return self._decimate_target

    @property
    def decimate_ratio(self) -> float:
        return self._decimate_ratio

    @property
    def has_landmarks(self) -> bool:
        return len(self._landmark_pairs) > 0

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

    def set_source(self, name: str) -> None:
        if name == self._source_name:
            return
        self._source_name = name
        self.on_status(f"Source: {name}")

    def set_target(self, name: str) -> None:
        if name == self._target_name:
            return
        self._target_name = name
        self._target_face_indices = None
        self.on_target_region_changed()
        self.on_status(f"Target: {name}")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_schedule(self, schedule: str) -> None:
        if schedule not in SCHEDULES:
            self.on_error(f"Unknown schedule '{schedule}'. Available: {list(SCHEDULES.keys())}")
            return
        self._schedule = schedule

    def set_auto_align(self, enabled: bool) -> None:
        self._auto_align = enabled

    def set_smooth_result(self, enabled: bool) -> None:
        self._smooth_result = enabled

    def set_smooth_iterations(self, n: int) -> None:
        self._smooth_iterations = max(1, n)

    def set_snap_to_target(self, enabled: bool) -> None:
        self._snap_to_target = enabled

    def set_symmetrize(self, enabled: bool) -> None:
        self._symmetrize = enabled

    def set_symmetry_method(self, method: str) -> None:
        self._symmetry_method = method

    def set_duplicate_source(self, enabled: bool) -> None:
        self._duplicate_source = enabled

    def set_output_space(self, space: str) -> None:
        self._output_space = space

    # ------------------------------------------------------------------
    # Target region (face selection)
    # ------------------------------------------------------------------

    def set_target_faces_from_selection(self) -> None:
        """Set target region from current Maya face selection.

        If no faces are selected, clears the region. Validates that the
        selected faces belong to the current target mesh, meet minimum
        count, and have no isolated faces.
        """
        from . import scene_ops

        result = scene_ops.get_selected_face_indices()
        if result is None:
            self.clear_target_faces()
            return

        mesh_name, indices = result

        if not self._target_name:
            self.on_error("Set a target mesh before selecting a region")
            return

        if mesh_name != self._target_name:
            self.on_error(f"Selected faces belong to '{mesh_name}', not the target '{self._target_name}'")
            return

        if len(indices) < _MIN_TARGET_REGION_FACES:
            self.on_error(f"Select at least {_MIN_TARGET_REGION_FACES} faces (got {len(indices)})")
            return

        self._validate_face_connectivity(indices)

        self._target_face_indices = indices
        self.on_target_region_changed()
        self.on_status(f"Target region: {len(indices)} faces")

    def clear_target_faces(self) -> None:
        """Clear the target region."""
        self._target_face_indices = None
        self.on_target_region_changed()
        self.on_status("Target region cleared")

    def _validate_face_connectivity(self, face_indices: list[int]) -> None:
        """Check that no face is completely isolated (shares no vertex with another selected face).

        Raises:
            ValueError: If an isolated face is detected.
        """
        raw_faces = self._api.get_face_vertex_indices(self._target_name)
        selected = raw_faces[face_indices]

        # Count how many selected faces each vertex belongs to
        vert_count: dict[int, int] = {}
        face_vert_sets: list[set[int]] = []
        for row in selected:
            verts = set(int(v) for v in row if v >= 0)
            face_vert_sets.append(verts)
            for v in verts:
                vert_count[v] = vert_count.get(v, 0) + 1

        # A face is isolated if all its vertices appear only once
        for i, verts in enumerate(face_vert_sets):
            if all(vert_count[v] == 1 for v in verts):
                raise ValueError(
                    f"Isolated face detected (face index {face_indices[i]}). "
                    "All selected faces must share at least one vertex with another selected face."
                )

    def set_stiffness(self, value: float) -> None:
        self._stiffness = max(0.01, min(0.20, value))
        self._use_advanced = True

    def set_landmark_strength(self, value: float) -> None:
        self._landmark_strength = max(0.0, min(1.0, value))
        self._use_advanced = True

    def set_steps(self, value: int) -> None:
        self._steps = max(3, min(10, value))
        self._use_advanced = True

    def set_decimate_target(self, enabled: bool) -> None:
        self._decimate_target = enabled

    def set_decimate_ratio(self, value: float) -> None:
        self._decimate_ratio = max(0.05, min(1.0, value))

    def schedule_defaults(self) -> tuple[float, int]:
        """Return (initial_stiffness, num_steps) for the current preset schedule."""
        schedule = SCHEDULES.get(self._schedule)
        if schedule is None:
            return (0.10, 5)
        return (schedule[0][0], len(schedule))

    def reset_advanced(self) -> None:
        stiffness, steps = self.schedule_defaults()
        self._stiffness = stiffness
        self._landmark_strength = 1.0
        self._steps = steps
        self._use_advanced = False

    # ------------------------------------------------------------------
    # Landmarks (transform-based pairs)
    # ------------------------------------------------------------------

    def set_landmarks_from_selection(self) -> None:
        """Register landmark pairs from the current Maya transform selection.

        Expects an even number of transforms selected. The first half are
        source landmarks, the second half are targets:
        e.g. 6 selected -> (1st,4th), (2nd,5th), (3rd,6th).
        """
        from . import scene_ops

        transforms = scene_ops.get_selected_transforms()
        n = len(transforms)
        if n == 0 or n % 2 != 0:
            self.on_error(f"Select an even number of transforms (got {n})")
            return

        # Validate: all must be transforms
        for t in transforms:
            if not scene_ops.is_transform(t):
                self.on_error(f"'{t}' is not a transform node")
                return

        # Check for duplicates against existing pairs
        existing = {name for pair in self._landmark_pairs for name in pair}
        for t in transforms:
            if t in existing:
                self.on_error(f"'{t}' is already registered as a landmark")
                return

        half = n // 2
        for i in range(half):
            self._landmark_pairs.append((transforms[i], transforms[half + i]))
        self.on_landmarks_changed()
        self.on_status(f"Added {half} landmark pair(s)")

    def remove_landmark_pair(self, index: int) -> None:
        """Remove the landmark pair at *index*."""
        if 0 <= index < len(self._landmark_pairs):
            self._landmark_pairs.pop(index)
            self.on_landmarks_changed()

    def clear_all_landmarks(self) -> None:
        """Remove all landmark pairs."""
        if self._landmark_pairs:
            self._landmark_pairs.clear()
            self.on_landmarks_changed()
            self.on_status("All landmarks removed")

    def select_landmark_pair(self, index: int) -> None:
        """Select the source + target transforms of a pair in Maya."""
        from . import scene_ops

        if 0 <= index < len(self._landmark_pairs):
            src, tgt = self._landmark_pairs[index]
            scene_ops.select_nodes([src, tgt])

    def select_all_landmarks(self) -> None:
        """Select all source and target landmark transforms in Maya."""
        from . import scene_ops

        if self._landmark_pairs:
            all_nodes = [node for pair in self._landmark_pairs for node in pair]
            scene_ops.select_nodes(all_nodes)

    def select_source_landmarks(self) -> None:
        """Select all source landmark transforms in Maya."""
        from . import scene_ops

        if self._landmark_pairs:
            scene_ops.select_nodes([src for src, _ in self._landmark_pairs])

    def select_target_landmarks(self) -> None:
        """Select all target landmark transforms in Maya."""
        from . import scene_ops

        if self._landmark_pairs:
            scene_ops.select_nodes([tgt for _, tgt in self._landmark_pairs])

    # ------------------------------------------------------------------
    # Config / Request construction
    # ------------------------------------------------------------------

    def build_config(self) -> PipelineConfig:
        cfg = PipelineConfig(
            schedule=self._schedule,
            auto_align_enabled=self._auto_align,
            smooth_result=self._smooth_result,
            smooth_iterations=self._smooth_iterations,
            snap_to_target=self._snap_to_target,
            symmetrize=self._symmetrize,
            symmetry_method=self._symmetry_method,
            target_decimate_ratio=self._decimate_ratio if self._decimate_target else None,
        )
        if self._use_advanced:
            cfg.advanced_stiffness = self._stiffness
            cfg.advanced_landmark_strength = self._landmark_strength
            cfg.advanced_steps = self._steps
        return cfg

    def build_fitting_request(self) -> FittingRequest | None:
        if not self.can_run:
            self.on_error("Cannot run: check source/target selection")
            return None

        config = self.build_config()
        try:
            landmarks = self._build_landmark_data()
        except ValueError as exc:
            self.on_error(str(exc))
            return None

        return FittingRequest(
            source_name=self._source_name,
            target_name=self._target_name,
            config=config,
            landmarks=landmarks,
            duplicate_source=self._duplicate_source,
            output_space=self._output_space,
            target_face_indices=self._target_face_indices,
        )

    # ------------------------------------------------------------------
    # Fitting lifecycle (called by Window / Worker)
    # ------------------------------------------------------------------

    def on_fitting_started(self) -> None:
        self._is_fitting = True
        self.on_fitting_state_changed(True)
        self.on_status("Fitting in progress...")

    def on_fitting_finished(self, result: PipelineResult) -> None:
        self._is_fitting = False
        self._last_result = result
        self.on_fitting_state_changed(False)
        elapsed = f"{result.elapsed_total:.1f}s" if result.elapsed_total else ""
        self.on_status(f"Fitting complete ({elapsed})")
        self.on_fitting_complete(result)

    def on_fitting_error(self, error_msg: str) -> None:
        self._is_fitting = False
        self.on_fitting_state_changed(False)
        self.on_error(error_msg)
        self.on_status(f"Fitting failed: {error_msg}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_landmark_data(self) -> LandmarkData | None:
        """Build LandmarkData from transform positions at fitting time.

        Raises ValueError if any landmark is too far from its mesh surface.
        """
        if not self._landmark_pairs:
            return None

        from . import scene_ops

        # Gather world positions
        src_world = [scene_ops.get_transform_world_position(s) for s, _ in self._landmark_pairs]
        tgt_world = [scene_ops.get_transform_world_position(t) for _, t in self._landmark_pairs]

        # Convert to object space: p_local = p_world @ worldInverseMatrix
        # (Maya row-vector convention)
        src_inv = np.linalg.inv(self._api.get_world_matrix(self._source_name))
        tgt_inv = np.linalg.inv(self._api.get_world_matrix(self._target_name))
        src_obj = [(np.array([*p, 1.0]) @ src_inv)[:3].tolist() for p in src_world]
        tgt_obj = [(np.array([*p, 1.0]) @ tgt_inv)[:3].tolist() for p in tgt_world]

        # Build meshes
        source_mesh = maya_mesh_to_trimesh(self._source_name, api=self._api)
        target_mesh = maya_mesh_to_trimesh(self._target_name, api=self._api)

        # Validate: landmarks must be near their respective mesh surfaces
        _validate_landmark_distances(source_mesh, np.array(src_obj), "source")
        _validate_landmark_distances(target_mesh, np.array(tgt_obj), "target")

        # Project source positions onto mesh surface
        tri_ids, bary = positions_to_surface_landmarks(source_mesh, np.array(src_obj))

        return LandmarkData(
            source_triangle_indices=tri_ids.tolist(),
            source_barycentric_coords=bary.tolist(),
            target_positions=tgt_obj,
        )
