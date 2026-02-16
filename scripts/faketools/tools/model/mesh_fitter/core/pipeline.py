"""Unified fitting pipeline — orchestrates all stages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
import time

import numpy as np
import trimesh

from ..io.landmark_io import LandmarkData, load_landmarks
from ..io.mesh_io import load_mesh, mesh_info
from .algorithms import FittingParams, fit_mesh, generate_schedule, surface_landmarks_to_positions
from .postprocessing import multi_stage_snap, taubin_smooth
from .preprocessing import align_centroids, auto_align, normalize_scale
from .symmetry import SymmetryMethod, build_symmetry_table, symmetrize_vertices

logger = getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the full fitting pipeline."""

    # Fitting
    schedule: str | list[list[float]] = "gentle"
    use_landmarks: bool = True

    # Preprocessing
    auto_align_enabled: bool = True
    scale_normalize: bool = True

    # Postprocessing
    smooth_result: bool = False
    smooth_iterations: int = 3
    snap_to_target: bool = False
    snap_stages: list[float] = field(default_factory=lambda: [0.3, 0.5])

    # Symmetrize
    symmetrize: bool = False
    symmetry_method: str = "position"
    symmetry_threshold: float = 0.001
    symmetry_center_indices: list[int] | None = None

    # Advanced fitting overrides (None = use preset schedule)
    advanced_stiffness: float | None = None  # 0.01–0.20
    advanced_landmark_strength: float | None = None  # 0.0–1.0
    advanced_steps: int | None = None  # 3–10

    # Exclusion
    exclusion_mask_path: str | None = None
    exclusion_seeds: list[int] | None = None
    exclusion_radius: float = 0.0

    # Output
    save_visualization: bool = False
    output_dir: str = "output"


@dataclass
class PipelineResult:
    """Result from the fitting pipeline."""

    fitted_mesh: trimesh.Trimesh
    elapsed_total: float = 0.0
    elapsed_align: float = 0.0
    elapsed_fit: float = 0.0
    elapsed_post: float = 0.0
    source_info: dict = field(default_factory=dict)
    target_info: dict = field(default_factory=dict)
    fitted_info: dict = field(default_factory=dict)
    result_mesh_name: str | None = None


def run_pipeline_from_meshes(
    source: trimesh.Trimesh,
    target: trimesh.Trimesh,
    config: PipelineConfig | None = None,
    landmarks: LandmarkData | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Run the fitting pipeline on in-memory trimesh objects.

    Stages:
    1. Preprocessing (alignment, scale normalization)
    2. Fitting (nricp_amberg)
    3. Postprocessing (smoothing, snap)

    Args:
        source: Source mesh (template) as trimesh.Trimesh.
        target: Target mesh (scan) as trimesh.Trimesh.
        config: Pipeline configuration. Uses defaults if None.
        landmarks: Optional landmark data for guided fitting.

    Returns:
        PipelineResult with fitted mesh and timing info.
    """
    if config is None:
        config = PipelineConfig()

    result = PipelineResult(fitted_mesh=trimesh.Trimesh())
    t_total_start = time.perf_counter()

    result.source_info = mesh_info(source)
    result.target_info = mesh_info(target)
    logger.info("Source: %s v, %s f", f"{result.source_info['n_vertices']:,}", f"{result.source_info['n_faces']:,}")
    logger.info("Target: %s v, %s f", f"{result.target_info['n_vertices']:,}", f"{result.target_info['n_faces']:,}")

    if landmarks and landmarks.count > 0:
        logger.info("Landmarks: %d pairs", landmarks.count)

    # Save original source geometry before alignment changes it.
    # Alignment (ICP/Procrustes) can rotate the mesh, breaking X=0 symmetry.
    # The symmetry table must be built from the original symmetric template.
    original_source_verts = source.vertices.copy() if config.symmetrize else None
    original_source_faces = source.faces.copy() if config.symmetrize else None

    # ---- Stage 2: Preprocessing ----
    if on_progress:
        on_progress("[2/4] Preprocessing...")
    logger.info("[2/4] Preprocessing...")
    t_align = time.perf_counter()

    if config.auto_align_enabled:
        if landmarks and landmarks.count > 0:
            if landmarks.is_surface_mode and not landmarks.source_positions:
                src_lm = surface_landmarks_to_positions(
                    source,
                    np.array(landmarks.source_triangle_indices),
                    np.array(landmarks.source_barycentric_coords),
                )
            else:
                src_lm = np.array(landmarks.source_positions)
            tgt_lm = np.array(landmarks.target_positions)
            source = auto_align(source, target, src_lm, tgt_lm)
            logger.info("Landmark-based Procrustes alignment applied")
        else:
            source = auto_align(source, target)
            logger.info("Auto-alignment (centroid + scale + ICP) applied")
    elif config.scale_normalize:
        source, factor = normalize_scale(source, target)
        source = align_centroids(source, target)
        logger.info("Scale normalized (factor=%.3f) + centroid aligned", factor)

    result.elapsed_align = time.perf_counter() - t_align

    # ---- Stage 3: Fitting ----
    if on_progress:
        on_progress("[3/4] Fitting (nricp_amberg)...")
    logger.info("[3/4] Fitting (nricp_amberg)...")
    t_fit = time.perf_counter()

    has_lm = bool(landmarks and config.use_landmarks and landmarks.count > 0)
    use_advanced = any(
        v is not None
        for v in (
            config.advanced_stiffness,
            config.advanced_landmark_strength,
            config.advanced_steps,
        )
    )

    if use_advanced:
        schedule = generate_schedule(
            initial_stiffness=config.advanced_stiffness if config.advanced_stiffness is not None else 0.10,
            landmark_strength=config.advanced_landmark_strength if config.advanced_landmark_strength is not None else 1.0,
            num_steps=config.advanced_steps if config.advanced_steps is not None else 5,
            has_landmarks=has_lm,
        )
        fit_params = FittingParams(schedule=schedule)
        logger.info("Schedule: custom (advanced), %d steps", len(schedule))
    else:
        fit_params = FittingParams(schedule=config.schedule)

    if has_lm:
        if landmarks.is_surface_mode:
            fit_params.source_landmark_triangles = np.array(landmarks.source_triangle_indices)
            fit_params.source_landmark_barycentrics = np.array(landmarks.source_barycentric_coords)
        else:
            fit_params.source_landmarks = landmarks.source_vertex_indices
        fit_params.target_positions = np.array(landmarks.target_positions)
        if not use_advanced:
            schedule_name = config.schedule if isinstance(config.schedule, str) else "custom"
            # Always use with_landmarks schedule when landmarks are present.
            # Other schedules (e.g. aggressive) have landmark weights too high
            # relative to stiffness, causing extreme deformation and OOM in
            # trimesh's closest_point.
            if schedule_name != "custom":
                fit_params.schedule = "landmark"
        logger.info("Schedule: %s, %d landmarks", fit_params.schedule if isinstance(fit_params.schedule, str) else "custom", landmarks.count)
    else:
        if not use_advanced:
            schedule_name = config.schedule if isinstance(config.schedule, str) else "custom"
            logger.info("Schedule: %s, no landmarks", schedule_name)

    fitted = fit_mesh(source, target, fit_params)

    result.elapsed_fit = time.perf_counter() - t_fit
    logger.info("Fitting completed in %.1fs", result.elapsed_fit)

    # ---- Stage 4: Postprocessing ----
    if on_progress:
        on_progress("[4/4] Postprocessing...")
    logger.info("[4/4] Postprocessing...")
    t_post = time.perf_counter()

    if config.smooth_result:
        fitted = taubin_smooth(fitted, iterations=config.smooth_iterations)
        logger.info("Taubin smoothing (%d iterations)", config.smooth_iterations)

    if config.snap_to_target and config.snap_stages:
        fitted = multi_stage_snap(
            fitted,
            target,
            stages=config.snap_stages,
            smooth_between=True,
        )
        logger.info("Progressive snap (%d stages)", len(config.snap_stages))

    if config.symmetrize:
        method = SymmetryMethod(config.symmetry_method)
        sym = build_symmetry_table(
            original_source_verts,
            faces=original_source_faces,
            center_indices=config.symmetry_center_indices,
            threshold=config.symmetry_threshold,
            method=method,
        )
        fitted.vertices = symmetrize_vertices(
            fitted.vertices,
            sym.center_indices,
            sym.pair_map,
        )
        logger.info("Symmetrize [%s] (%d center, %d pairs)", method.value, len(sym.center_indices), len(sym.pair_map))

    result.elapsed_post = time.perf_counter() - t_post

    result.fitted_mesh = fitted
    result.fitted_info = mesh_info(fitted)
    result.elapsed_total = time.perf_counter() - t_total_start

    logger.info("Done! Total time: %.1fs", result.elapsed_total)
    logger.info("Aligned: %.1fs, Fitted: %.1fs, Post: %.1fs", result.elapsed_align, result.elapsed_fit, result.elapsed_post)

    return result


def run_pipeline(
    source_path: str | Path,
    target_path: str | Path,
    config: PipelineConfig | None = None,
    landmark_path: str | Path | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Run the complete fitting pipeline from file paths.

    Loads meshes and landmarks from disk, then delegates to
    run_pipeline_from_meshes.

    Returns:
        PipelineResult with fitted mesh and timing info.
    """
    if config is None:
        config = PipelineConfig()

    # ---- Stage 1: Load ----
    if on_progress:
        on_progress("[1/4] Loading meshes...")
    logger.info("[1/4] Loading meshes...")
    source = load_mesh(source_path)
    target = load_mesh(target_path)

    landmarks: LandmarkData | None = None
    if landmark_path and config.use_landmarks:
        landmarks = load_landmarks(landmark_path)

    return run_pipeline_from_meshes(source, target, config, landmarks, on_progress)
