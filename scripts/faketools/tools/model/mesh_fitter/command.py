"""Maya integration for mesh fitting — run fitting directly from Maya.

Usage from Maya Script Editor::

    from faketools.tools.model.mesh_fitter import command
    result = command.run_fitting("sourceShape", "targetShape")
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core.pipeline import PipelineConfig, PipelineResult
    from .io.landmark_io import LandmarkData
    from .mesh_bridge import MayaMeshAPI


def run_fitting(
    source_name: str,
    target_name: str,
    config: PipelineConfig | None = None,
    landmarks: LandmarkData | None = None,
    schedule: str | None = None,
    api: MayaMeshAPI | None = None,
    duplicate_source: bool = True,
    output_space: str = "source",
    target_face_indices: list[int] | None = None,
    result_name: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Run the full fitting pipeline on Maya meshes.

    Args:
        source_name: Name of the source (template) mesh in Maya.
        target_name: Name of the target (scan) mesh in Maya.
        config: Pipeline configuration. If None, uses defaults.
        landmarks: Pre-built LandmarkData. If None, runs without landmarks.
        schedule: Shorthand to set config.schedule (overrides config.schedule).
        api: MayaMeshAPI implementation. Defaults to OpenMayaMeshAPI().
        duplicate_source: If True, duplicate source before fitting to preserve original.
        output_space: "source" to keep result at source transform, "target" to match target transform.
        target_face_indices: Optional face indices to use as target region (submesh).
        result_name: Name for the result mesh. Defaults to "{source_name}_fitted".
        on_progress: Optional progress callback.

    Returns:
        PipelineResult with the fitted mesh.
    """
    from .core.pipeline import PipelineConfig, run_pipeline_from_meshes
    from .mesh_bridge import (
        OpenMayaMeshAPI,
        maya_mesh_to_trimesh,
        trimesh_to_maya_mesh,
    )

    if api is None:
        api = OpenMayaMeshAPI()

    if config is None:
        config = PipelineConfig()

    if schedule is not None:
        config.schedule = schedule

    # Convert Maya meshes to trimesh
    if on_progress:
        on_progress("[1/4] Converting meshes...")
    source_tri = maya_mesh_to_trimesh(source_name, api=api)
    target_tri = maya_mesh_to_trimesh(target_name, api=api, face_indices=target_face_indices)

    # Run the core pipeline
    result = run_pipeline_from_meshes(
        source_tri,
        target_tri,
        config,
        landmarks,
        on_progress=on_progress,
    )

    # Write result back to Maya
    if on_progress:
        on_progress("Writing result to Maya...")
    if duplicate_source:
        from .scene_ops import duplicate_mesh

        if result_name is None:
            result_name = f"{source_name}_fitted"

        dup_name = duplicate_mesh(source_name, result_name)
        trimesh_to_maya_mesh(result.fitted_mesh, dup_name, api=api)
        result.result_mesh_name = dup_name
    else:
        # Overwrite source in-place
        trimesh_to_maya_mesh(result.fitted_mesh, source_name, api=api)
        result.result_mesh_name = source_name

    if output_space == "target":
        from .scene_ops import match_transform

        match_transform(result.result_mesh_name, target_name)

    return result
